"""Bundled AI harness: inventory, install planning, currency and rollback.

Midas ships a curated harness - skills, rules, hooks, agents, commands, MCP servers,
knowledge-base entries, quality gates and CLI recipes - and installs it into the local
tools (Claude Code, Cursor). This module owns the *what is installed, from which version,
and is it current* question. `integrate.py` owns the mechanics of writing into the tools.

Design notes:

- **Nine item kinds**, matching the fleet architecture's closed taxonomy:
  skill, rule, hook, agent, command, mcp, kb, cli, quality-gate.
- **Every item is versioned independently** by the sha256 of its payload; the harness
  version is the sha256 over the sorted item digests. No timestamps, so the same content
  always yields the same version on any machine.
- **`mandatory` items drive outdated detection.** Missing a mandatory item makes this
  client outdated, which (in a Morpheus farm) ranks it last for delegated work and makes
  every midas command warn loudly.
- **`external` items carry no payload** (a 10 MB CLI, a 4.7 MB doc catalogue). They are
  verified by running a probe, never trusted because the manifest mentions them.
- Nothing is applied without being asked. Planning and applying are separate calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

import tomlkit

from . import logging_setup, paths

log = logging_setup.get("harness")

KINDS = ("skill", "rule", "hook", "agent", "command", "mcp", "kb", "cli", "quality-gate")

# Where each kind is projected. Relative to the projection root (default ~).
# Mirrors Morpheus's copier map so both sides agree on destinations.
PROJECTION: dict[str, tuple[str, ...]] = {
    "skill": (".claude/skills", ".cursor/skills"),
    "rule": (".claude/rules", ".cursor/rules"),
    "hook": (".cursor/hooks",),
    "agent": (".claude/agents",),
    "command": (".claude/commands", ".cursor/commands"),
    "kb": (".cursor/kb", ".claude/kb"),
    "quality-gate": (".cursor/kb/validation", ".claude/kb/validation"),
    "mcp": (),   # handled specially: templated + secrets resolved, 0600
    "cli": (),   # external: install recipe + probe
}


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

@dataclass
class Item:
    id: str
    kind: str
    source: str = ""          # path relative to the package, "" for external items
    mandatory: bool = False
    external: bool = False
    summary: str = ""
    sha256: str = ""
    files: int = 0
    bytes: int = 0

    @property
    def payload_path(self) -> Path | None:
        if self.external or not self.source:
            return None
        return Path(__file__).parent / self.source


def projectable(item: "Item") -> bool:
    """Can `install_harness` actually place this item into the local tools?

    Two kinds cannot be, and must therefore stay out of the currency and patch views or
    they would sit in the "available" list forever and `current` would be unreachable:

    - `external` items (rtk, the offline-reference catalogue) carry no payload; they are
      obtained by their install recipe and reported by their probe.
    - `mcp` items go through `resolve_mcp_template`, which needs credentials, so they are
      written by `midas touch --mcp` rather than by a plain projection.

    They are still real harness items with real versions - they are just reported through
    `verify_externals()` and the MCP section instead of through the patch list.
    """
    return not item.external and bool(PROJECTION.get(item.kind))


@dataclass
class Manifest:
    version: str
    generated_from: str
    items: list[Item] = field(default_factory=list)

    def by_kind(self, kind: str) -> list[Item]:
        return [i for i in self.items if i.kind == kind]

    def mandatory(self) -> list[Item]:
        return [i for i in self.items if i.mandatory and projectable(i)]

    def projectable(self) -> list[Item]:
        return [i for i in self.items if projectable(i)]

    def get(self, item_id: str) -> Item | None:
        return next((i for i in self.items if i.id == item_id), None)


def _sha256_path(path: Path) -> tuple[str, int, int]:
    """Content digest over a file or a directory tree. Returns (sha, files, bytes).

    Directory walk is sorted by relative path and mixes the path into the digest, so a
    rename changes the version even when the bytes do not.
    """
    h = hashlib.sha256()
    nfiles = 0
    nbytes = 0
    if path.is_file():
        data = path.read_bytes()
        h.update(data)
        return h.hexdigest(), 1, len(data)
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = f.relative_to(path).as_posix()
        data = f.read_bytes()
        h.update(rel.encode())
        h.update(data)
        nfiles += 1
        nbytes += len(data)
    return h.hexdigest(), nfiles, nbytes


def _digest_items(items: list[Item]) -> str:
    h = hashlib.sha256()
    for i in sorted(items, key=lambda x: (x.kind, x.id)):
        h.update(f"{i.kind}/{i.id}:{i.sha256}".encode())
    return h.hexdigest()


def discover_items() -> list[Item]:
    """Scan the bundled trees and build the item list with fresh digests."""
    root = Path(__file__).parent
    assets = paths.harness_assets_dir()
    items: list[Item] = []

    def add(item_id: str, kind: str, path: Path, *, mandatory: bool = False, summary: str = "") -> None:
        if not path.exists():
            return
        sha, nfiles, nbytes = _sha256_path(path)
        items.append(Item(
            id=item_id, kind=kind, source=path.relative_to(root).as_posix(),
            mandatory=mandatory, summary=summary, sha256=sha, files=nfiles, bytes=nbytes,
        ))

    # skills: midas-* adapters (mandatory - the pipeline invokes them by name)
    skills = paths.skills_dir()
    if skills.is_dir():
        for d in sorted(skills.iterdir()):
            if d.is_dir() and d.name.startswith("midas-") and (d / "SKILL.md").is_file():
                add(d.name, "skill", d, mandatory=True, summary="midas pipeline adapter")
        vendor = skills / "vendor"
        if vendor.is_dir():
            for d in sorted(vendor.iterdir()):
                if d.is_dir() and (d / "SKILL.md").is_file():
                    add(d.name, "skill", d, mandatory=True, summary="canonical upstream skill")

    # rules: git-safety and token-efficiency rules are mandatory, the rest are not
    mandatory_rules = {
        "no-git-shell-commands", "no-git-index-writes", "no-git-reset",
        "no-commit-co-authors", "git-amend-explicit-order", "token-efficiency-chat",
    }
    for f in sorted((assets / "rules").glob("*.mdc")):
        add(f.stem, "rule", f, mandatory=f.stem in mandatory_rules, summary="agent rule")

    # hooks: the git-push denial is a safety invariant
    mandatory_hooks = {"git-push-policy.sh", "deny-git.sh", "claude-deny-git.sh"}
    for f in sorted((assets / "hooks").iterdir()) if (assets / "hooks").is_dir() else []:
        if f.is_file():
            add(f.name, "hook", f, mandatory=f.name in mandatory_hooks, summary="tool hook")

    for f in sorted((assets / "agents").glob("*.md")):
        add(f.stem, "agent", f, summary="subagent definition")

    for f in sorted((assets / "commands").glob("*")) if (assets / "commands").is_dir() else []:
        if f.is_file():
            add(f.stem, "command", f, summary="slash command")

    # kb: quality gates are a distinguished subtree; How-to-resolve-task-context is
    # mandatory because every context-budget section in every skill delegates to it.
    kb = assets / "kb"
    if kb.is_dir():
        for f in sorted(p for p in kb.rglob("*") if p.is_file()):
            rel = f.relative_to(kb).as_posix()
            kind = "quality-gate" if rel.startswith("validation/Quality-gate-") else "kb"
            mandatory = rel in {
                "implementation/How-to-resolve-task-context.md",
                "implementation/How-to-optimize-agent-token-usage.md",
                "implementation/How-to-route-cursor-skills.md",
                "validation/Quality-gate-delivery-scope.md",
                "validation/Quality-gate-delivery-standards.md",
            }
            add(rel, kind, f, mandatory=mandatory, summary="knowledge base entry")

    mcp_tpl = assets / "mcp" / "mcp.template.json"
    add("mcp.template", "mcp", mcp_tpl, summary="MCP server template (secrets templated)")

    # external items: declared by a .toml recipe, payload not carried
    for f in sorted((assets / "clis").glob("*.toml")):
        doc = tomlkit.parse(f.read_text())
        meta = dict(doc.get("item", {}))
        sha, _, _ = _sha256_path(f)
        items.append(Item(
            id=str(meta.get("id", f.stem)),
            kind=str(meta.get("kind", "cli")),
            source=f.relative_to(root).as_posix(),
            mandatory=bool(meta.get("mandatory", False)),
            external=True,
            summary=str(meta.get("summary", "")),
            sha256=sha,
        ))

    return items


def build_manifest(generated_from: str = "bundled") -> Manifest:
    items = discover_items()
    return Manifest(version=_digest_items(items), generated_from=generated_from, items=items)


def write_manifest(manifest: Manifest, dest: Path | None = None) -> Path:
    dest = dest or paths.bundled_manifest_file()
    doc = tomlkit.document()
    doc.add(tomlkit.comment("Generated by `midas harness reindex` - do not hand-edit."))
    doc.add(tomlkit.comment("version = sha256 over every item's (kind/id: sha256), sorted."))
    meta = tomlkit.table()
    meta["version"] = manifest.version
    meta["generated_from"] = manifest.generated_from
    meta["item_count"] = len(manifest.items)
    meta["mandatory_count"] = len(manifest.mandatory())
    doc["harness"] = meta
    arr = tomlkit.aot()
    for i in sorted(manifest.items, key=lambda x: (x.kind, x.id)):
        t = tomlkit.table()
        for k, v in asdict(i).items():
            if v != "" and v is not False and v != 0:
                t[k] = v
            elif k in ("id", "kind"):
                t[k] = v
        arr.append(t)
    doc["item"] = arr
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(tomlkit.dumps(doc))
    return dest


def load_manifest(path: Path | None = None) -> Manifest:
    """Load the bundled manifest, rebuilding from disk if it is absent or stale."""
    path = path or paths.bundled_manifest_file()
    if not path.is_file():
        return build_manifest()
    doc = tomlkit.parse(path.read_text())
    items = [
        Item(
            id=str(t.get("id")), kind=str(t.get("kind")), source=str(t.get("source", "")),
            mandatory=bool(t.get("mandatory", False)), external=bool(t.get("external", False)),
            summary=str(t.get("summary", "")), sha256=str(t.get("sha256", "")),
            files=int(t.get("files", 0)), bytes=int(t.get("bytes", 0)),
        )
        for t in doc.get("item", [])
    ]
    meta = doc.get("harness", {})
    return Manifest(
        version=str(meta.get("version", _digest_items(items))),
        generated_from=str(meta.get("generated_from", "bundled")),
        items=items,
    )


# ---------------------------------------------------------------------------
# applied state
# ---------------------------------------------------------------------------

def load_applied() -> dict:
    f = paths.harness_applied_file()
    if f.is_file():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            log.warning("%s is corrupt - treating this machine as never installed", f)
    return {}


def save_applied(version: str, installed: dict[str, str], targets: list[str]) -> None:
    paths.harness_state_dir().mkdir(parents=True, exist_ok=True)
    paths.harness_applied_file().write_text(json.dumps({
        "version": version,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "items": installed,
        "targets": targets,
    }, indent=2) + "\n")


# ---------------------------------------------------------------------------
# currency: is this machine up to date?
# ---------------------------------------------------------------------------

@dataclass
class Currency:
    state: str                                  # current | behind | outdated | never-installed
    applied_version: str = ""
    available_version: str = ""
    missing_mandatory: list[str] = field(default_factory=list)
    behind: list[str] = field(default_factory=list)

    @property
    def outdated(self) -> bool:
        return bool(self.missing_mandatory)

    def label(self) -> str:
        if self.state == "never-installed":
            return "never installed"
        if self.outdated:
            return f"outdated ({len(self.missing_mandatory)} mandatory missing)"
        if self.behind:
            return f"behind ({len(self.behind)} items)"
        return "current"


def currency(manifest: Manifest | None = None) -> Currency:
    """Compare what is installed against what is available.

    `behind` is a choice the operator is entitled to make. `outdated` means a *mandatory*
    item is missing, which carries a real cost: a Morpheus farm defers work to up-to-date
    clients, and every midas command warns until it is fixed.
    """
    manifest = manifest or load_manifest()
    applied = load_applied()
    if not applied:
        return Currency(
            state="never-installed",
            available_version=manifest.version,
            missing_mandatory=[f"{i.kind}/{i.id}" for i in manifest.mandatory()],
            behind=[f"{i.kind}/{i.id}" for i in manifest.projectable()],
        )

    installed: dict[str, str] = applied.get("items", {})
    missing_mandatory, behind = [], []
    for i in manifest.projectable():
        key = f"{i.kind}/{i.id}"
        if installed.get(key) != i.sha256:
            behind.append(key)
            if i.mandatory:
                missing_mandatory.append(key)

    state = "current"
    if missing_mandatory:
        state = "outdated"
    elif behind:
        state = "behind"
    return Currency(
        state=state,
        applied_version=str(applied.get("version", "")),
        available_version=manifest.version,
        missing_mandatory=missing_mandatory,
        behind=behind,
    )


def warning_banner(cur: Currency) -> str:
    """The loud, unmissable outdated banner (architecture plan D18)."""
    if not cur.outdated and cur.state != "never-installed":
        return ""
    shown = cur.missing_mandatory[:4]
    more = len(cur.missing_mandatory) - len(shown)
    lines = [
        "THIS CLIENT IS OUTDATED" if cur.state != "never-installed"
        else "HARNESS NOT INSTALLED ON THIS MACHINE",
        f"{len(cur.missing_mandatory)} mandatory harness item(s) missing:",
    ]
    lines += [f"  - {m}" for m in shown]
    if more > 0:
        lines.append(f"  ... and {more} more")
    lines += [
        "Morpheus defers delegated work to up-to-date clients.",
        "Fix:  midas harness apply --mandatory-only",
    ]
    width = max(len(x) for x in lines) + 4
    out = ["", "!" + "=" * width + "!"]
    for i, x in enumerate(lines):
        prefix = "!! " if i == 0 else "!  "
        out.append(f"{prefix}{x}".ljust(width + 1) + "!")
    out.append("!" + "=" * width + "!")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# patches: item-level diff, offered rather than applied
# ---------------------------------------------------------------------------

@dataclass
class PatchEntry:
    key: str
    kind: str
    item_id: str
    change: str          # added | updated
    mandatory: bool
    external: bool
    bytes: int
    summary: str


def available_patch(manifest: Manifest | None = None) -> list[PatchEntry]:
    """Every item whose installed digest differs from the bundled one."""
    manifest = manifest or load_manifest()
    installed: dict[str, str] = load_applied().get("items", {})
    entries = []
    for i in manifest.projectable():
        key = f"{i.kind}/{i.id}"
        have = installed.get(key)
        if have == i.sha256:
            continue
        entries.append(PatchEntry(
            key=key, kind=i.kind, item_id=i.id,
            change="updated" if have else "added",
            mandatory=i.mandatory, external=i.external, bytes=i.bytes, summary=i.summary,
        ))
    # mandatory first, then by kind/id - the order the operator should act in
    return sorted(entries, key=lambda e: (not e.mandatory, e.kind, e.item_id))


def select(entries: list[PatchEntry], *, mandatory_only: bool = False,
           kinds: tuple[str, ...] = ()) -> list[PatchEntry]:
    out = entries
    if mandatory_only:
        out = [e for e in out if e.mandatory]
    if kinds:
        out = [e for e in out if e.kind in kinds]
    return out


# ---------------------------------------------------------------------------
# external item verification (never trust the manifest for these)
# ---------------------------------------------------------------------------

@dataclass
class ExternalStatus:
    item_id: str
    kind: str
    present: bool
    detail: str
    mandatory: bool


def verify_external(item: Item) -> ExternalStatus:
    """Run an external item's declared probe. The probe is the source of truth."""
    recipe_path = item.payload_path or (Path(__file__).parent / item.source)
    present, detail = False, "no recipe"
    try:
        doc = tomlkit.parse(recipe_path.read_text())
    except OSError as exc:
        return ExternalStatus(item.id, item.kind, False, f"recipe unreadable: {exc}", item.mandatory)

    verify = dict(doc.get("verify", {}))
    if "probe" in verify:
        cmd = [str(x) for x in verify["probe"]]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            present = r.returncode == int(verify.get("expect_exit", 0))
            detail = (r.stdout or r.stderr).strip().splitlines()[0][:120] if (r.stdout or r.stderr) else f"exit {r.returncode}"
        except FileNotFoundError:
            present, detail = False, f"{cmd[0]} not found on PATH"
        except (OSError, subprocess.SubprocessError) as exc:
            present, detail = False, f"probe failed: {exc}"
    elif "probe_path" in verify:
        p = Path(os.path.expanduser(str(verify["probe_path"])))
        present = p.exists()
        if present and "expect_min_files" in verify:
            n = sum(1 for _ in p.parent.rglob("*") if _.is_file())
            present = n >= int(verify["expect_min_files"])
            detail = f"{n} files under {p.parent}"
        else:
            detail = str(p) if present else f"{p} absent"
    return ExternalStatus(item.id, item.kind, present, detail, item.mandatory)


def verify_externals(manifest: Manifest | None = None) -> list[ExternalStatus]:
    manifest = manifest or load_manifest()
    return [verify_external(i) for i in manifest.items if i.external]


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

def _denest(targets: list[Path]) -> list[Path]:
    """Drop targets that resolve to, or inside, another target.

    The projection map deliberately overlaps: `.cursor/kb` contains
    `.cursor/kb/validation`, and `.claude/kb` is often a symlink to `.cursor/kb`. Copying
    all of them would snapshot the same bytes repeatedly and - worse - a snapshotted
    symlink can later be written *through*, leaking a restore back into the live tree.
    Keep only the outermost distinct real directories.
    """
    resolved: list[tuple[Path, Path]] = []
    for t in targets:
        try:
            resolved.append((t, t.resolve()))
        except OSError:
            resolved.append((t, t))
    keep: list[tuple[Path, Path]] = []
    for t, r in sorted(resolved, key=lambda pair: len(pair[1].parts)):
        if any(r == kr or kr in r.parents for _, kr in keep):
            continue
        keep.append((t, r))
    # prefer the concrete path over a symlink alias to the same place
    return [t for t, _ in keep]


def snapshot(targets: list[Path], keep: int = 5, root: Path | None = None) -> Path | None:
    """Copy the current projections aside before a mutation; prune to `keep`.

    Symlinks are preserved as symlinks: the curated harness is largely
    ~/.claude/... -> ~/.cursor/... links, and a snapshot that silently dereferenced them
    would restore real copies and quietly destroy the convention it was meant to protect.
    The `root` is recorded so a rollback restores where it came from.
    """
    root = root or Path.home()
    existing = _denest([t for t in targets if t.exists() or t.is_symlink()])
    if not existing:
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = paths.harness_backups_dir() / stamp
    if dest.exists():                        # sub-second repeat call
        dest = paths.harness_backups_dir() / f"{stamp}-{len(generations()) + 1}"
    dest.mkdir(parents=True, exist_ok=True)
    for t in existing:
        rel = t.relative_to(root) if t.is_relative_to(root) else Path(t.name)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if t.is_symlink():
            out.symlink_to(os.readlink(t))
        elif t.is_dir():
            shutil.copytree(t, out, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(t, out)
    (dest / ".root").write_text(str(root) + "\n")
    applied = paths.harness_applied_file()
    if applied.is_file():
        shutil.copy2(applied, dest / "applied.json")
    gens = sorted(p for p in paths.harness_backups_dir().iterdir() if p.is_dir())
    for old in gens[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    log.info("harness snapshot -> %s", dest)
    return dest


def generations() -> list[str]:
    d = paths.harness_backups_dir()
    return sorted((p.name for p in d.iterdir() if p.is_dir()), reverse=True) if d.is_dir() else []


def _restore_tree(src: Path, dest: Path) -> None:
    """Mirror `src` onto `dest`, replacing whatever is in the way.

    `shutil.copytree(dirs_exist_ok=True)` raises when a destination entry is an existing
    symlink, which is the normal case here - so each entry is cleared before it is written.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        elif dest.is_dir():
            shutil.rmtree(dest)
        dest.symlink_to(os.readlink(src))
        return
    if src.is_file():
        if dest.is_symlink() or dest.is_dir():
            dest.unlink() if dest.is_symlink() else shutil.rmtree(dest)
        shutil.copy2(src, dest)
        return
    # directory: recurse so existing symlinks inside dest are handled one by one
    if dest.is_symlink():
        dest.unlink()
    dest.mkdir(parents=True, exist_ok=True)
    for child in sorted(src.iterdir()):
        _restore_tree(child, dest / child.name)


def rollback(generation: str | None = None, root: Path | None = None) -> str:
    """Restore a retained generation over the live projections."""
    gens = generations()
    if not gens:
        raise RuntimeError("no harness snapshots retained - nothing to roll back to")
    target = generation or gens[0]
    if target not in gens:
        raise RuntimeError(f"unknown generation {target!r}; have: {', '.join(gens)}")
    src = paths.harness_backups_dir() / target
    recorded = src / ".root"
    if root is None:
        root = Path(recorded.read_text().strip()) if recorded.is_file() else Path.home()
    for entry in sorted(src.iterdir()):
        if entry.name in ("applied.json", ".root"):
            continue
        _restore_tree(entry, root / entry.name)
    saved = src / "applied.json"
    if saved.is_file():
        paths.harness_state_dir().mkdir(parents=True, exist_ok=True)
        shutil.copy2(saved, paths.harness_applied_file())
    elif paths.harness_applied_file().is_file():
        paths.harness_applied_file().unlink()   # snapshot predates any install
    log.info("harness rolled back to %s (root %s)", target, root)
    return target
