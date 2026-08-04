"""Workspace integration: `midas touch` (install the bundled harness into the
user's Claude/Cursor setup) and `midas greed` (harvest reuse candidates from the
user's workspace).

`touch` installs the whole harness - skills, rules, hooks, agents, commands,
knowledge base, quality gates and the MCP template - so a fresh machine can be
brought up to the same standard as the one the harness was curated on.
`harness.py` decides *what* and *which version*; this module does the writing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import harness, logging_setup, paths

log = logging_setup.get("integrate")

HOOK_NAME = "midas-usage-hook.py"

# Skill roots scanned by `greed` / targeted by `touch`.
CLAUDE_SKILLS = Path.home() / ".claude" / "skills"
CURSOR_SKILLS = Path.home() / ".cursor" / "skills"

# Keywords that make a workspace skill interesting for the midas workflow.
GREED_KEYWORDS = (
    "jira", "git", "commit", "valid", "test", "review", "qa", "lint",
    "enonic", "deploy", "pipeline", "evidence", "playwright", "worklog", "task",
)


# ---------------------------------------------------------------------------
# touch: install midas skills into the user's workspace
# ---------------------------------------------------------------------------

def installable_skills() -> list[Path]:
    """Bundled midas-* skills (adapters, not vendor copies)."""
    return sorted(
        d for d in paths.skills_dir().iterdir()
        if d.is_dir() and d.name.startswith("midas-") and (d / "SKILL.md").is_file()
    )


def install_skills(dest_root: Path, skills: list[Path], overwrite: bool = False) -> list[str]:
    """Copy skill folders into dest_root; returns names installed (skips existing).

    The midas-* skills reference `../vendor/<skill>/SKILL.md`, so the bundled
    vendor folder is installed alongside them (its subfolders are one level
    too deep to be discovered as skills - they are reference material only).
    """
    installed = []
    dest_root.mkdir(parents=True, exist_ok=True)
    for src in skills:
        dest = dest_root / src.name
        if dest.exists() and not overwrite:
            continue
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        installed.append(src.name)
    vendor_src = paths.skills_dir() / "vendor"
    if installed and vendor_src.is_dir():
        vendor_dest = dest_root / "vendor"
        if vendor_dest.exists():
            shutil.rmtree(vendor_dest)
        shutil.copytree(vendor_src, vendor_dest)
    log.info("installed %d skills into %s", len(installed), dest_root)
    return installed


# ---------------------------------------------------------------------------
# touch: install the full bundled harness (every kind, not just skills)
# ---------------------------------------------------------------------------

_SECRET_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


@dataclass
class PlannedWrite:
    key: str            # "<kind>/<id>"
    kind: str
    dest: Path
    action: str         # create | update | unchanged | link
    sha256: str
    link_to: Path | None = None


def _links_into(dest_dir: Path, other: Path, threshold: float = 0.5) -> bool:
    """Does `dest_dir` predominantly hold symlinks pointing into `other`?

    The curated harness keeps one real copy under ~/.cursor and symlinks ~/.claude at it,
    so an edit in either tool hits the same file. Writing a second real copy would silently
    break that. Detect the convention and follow it instead of imposing ours.
    """
    if not dest_dir.is_dir():
        return False
    entries = list(dest_dir.iterdir())
    links = [e for e in entries if e.is_symlink()]
    if not entries or len(links) / len(entries) < threshold:
        return False
    try:
        return any(other.resolve() in e.resolve().parents or e.resolve().parent == other.resolve()
                   for e in links)
    except OSError:
        return False


def _order_targets(root: Path, targets: tuple[str, ...]) -> list[str]:
    """Put the real-content target first and any link farm last.

    `PROJECTION` lists targets in a fixed order, but which one holds the real files is the
    operator's choice: here ~/.cursor/skills is real and ~/.claude/skills is a tree of links
    into it. Writing the payload to the link farm and linking the other way round would
    invert their layout, so decide from what is on disk rather than from the declaration.
    """
    dirs = {rel: root / rel for rel in targets}
    def is_farm(rel: str) -> bool:
        return any(_links_into(dirs[rel], other)
                   for r, other in dirs.items() if r != rel)
    return sorted(targets, key=is_farm)


def _same_content(src: Path, dest: Path) -> bool:
    if not dest.exists():
        return False
    try:
        return harness._sha256_path(src)[0] == harness._sha256_path(dest)[0]
    except OSError:
        return False


def plan_harness(manifest: harness.Manifest | None = None,
                 root: Path | None = None,
                 kinds: tuple[str, ...] = (),
                 only: set[str] | None = None) -> list[PlannedWrite]:
    """Work out every write `install_harness` would make. No side effects.

    `only` restricts to a set of "<kind>/<id>" keys, which is how per-patch consent
    is honoured: the operator picks a subset and nothing else is touched.
    """
    manifest = manifest or harness.load_manifest()
    root = root or Path.home()
    plan: list[PlannedWrite] = []
    for item in manifest.items:
        key = f"{item.kind}/{item.id}"
        if kinds and item.kind not in kinds:
            continue
        if only is not None and key not in only:
            continue
        if item.external:
            continue                      # handled by verify/probe, never written here
        src = item.payload_path
        if src is None or not src.exists():
            continue
        targets = _order_targets(root, harness.PROJECTION.get(item.kind, ()))
        primary_dest: Path | None = None
        seen_real: set[Path] = set()
        for rel in targets:
            # kb/quality-gate ids carry their own sub-path; other kinds are flat names
            leaf = item.id if item.kind in ("kb", "quality-gate") else src.name
            if item.kind == "quality-gate":
                leaf = Path(item.id).name
            dest = root / rel / leaf

            # A target directory that is itself a symlink (e.g. ~/.claude/kb -> ~/.cursor/kb)
            # already unifies with another target; planning it twice would double the work
            # and report phantom writes.
            try:
                resolved_parent = (root / rel).resolve()
            except OSError:
                resolved_parent = root / rel
            if resolved_parent in seen_real:
                continue
            seen_real.add(resolved_parent)

            if primary_dest is None:
                action = ("unchanged" if _same_content(src, dest)
                          else ("update" if dest.exists() else "create"))
                plan.append(PlannedWrite(key, item.kind, dest, action, item.sha256))
                primary_dest = dest
                continue

            # Secondary target: honour an existing symlink convention rather than
            # replacing the operator's symlink with a divergent second copy.
            if _links_into(dest.parent, primary_dest.parent):
                already = dest.is_symlink() and dest.resolve() == primary_dest.resolve()
                plan.append(PlannedWrite(key, item.kind, dest,
                                         "unchanged" if already else "link",
                                         item.sha256, link_to=primary_dest))
            else:
                action = ("unchanged" if _same_content(src, dest)
                          else ("update" if dest.exists() else "create"))
                plan.append(PlannedWrite(key, item.kind, dest, action, item.sha256))
    return plan


def _clear(dest: Path) -> None:
    """Remove whatever is at `dest`, symlink or not, without following it."""
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)


def _write(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _clear(dest)
    if src.is_dir():
        shutil.copytree(src, dest, symlinks=True)
    else:
        shutil.copy2(src, dest)
        if dest.suffix in (".sh", ".py"):
            dest.chmod(0o755)


def _symlink(dest: Path, target: Path) -> None:
    """Point `dest` at `target`, relatively when both live under the same root."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _clear(dest)
    try:
        rel = os.path.relpath(target, dest.parent)
    except ValueError:
        rel = str(target)
    dest.symlink_to(rel)


def install_harness(manifest: harness.Manifest | None = None,
                    root: Path | None = None,
                    kinds: tuple[str, ...] = (),
                    only: set[str] | None = None,
                    dry_run: bool = False,
                    snapshot: bool = True) -> tuple[list[PlannedWrite], dict[str, str]]:
    """Project the bundled harness into the local tools.

    Returns (plan, installed) where `installed` maps "<kind>/<id>" -> sha256 for
    everything actually written, so the caller can record applied state.
    """
    manifest = manifest or harness.load_manifest()
    root = root or Path.home()
    plan = plan_harness(manifest, root=root, kinds=kinds, only=only)
    if dry_run:
        return plan, {}

    if snapshot:
        roots = {root / rel for kind in harness.PROJECTION for rel in harness.PROJECTION[kind]}
        harness.snapshot(sorted(roots), root=root)

    installed: dict[str, str] = {}
    for w in plan:
        if w.action == "unchanged":
            installed[w.key] = w.sha256
            continue
        if w.action == "link" and w.link_to is not None:
            _symlink(w.dest, w.link_to)
            installed[w.key] = w.sha256
            continue
        item = next((i for i in manifest.items if f"{i.kind}/{i.id}" == w.key), None)
        if item is None or item.payload_path is None:
            continue
        _write(item.payload_path, w.dest)
        installed[w.key] = w.sha256
    log.info("harness: %d writes into %s", sum(1 for w in plan if w.action != "unchanged"), root)
    return plan, installed


def resolve_mcp_template(dest: Path | None = None,
                         env: dict[str, str] | None = None) -> tuple[Path, list[str]]:
    """Write the MCP config from the bundled template, resolving ${VAR} placeholders.

    Secrets are never bundled. Unresolved placeholders are left verbatim so a missing
    credential fails loudly at first use instead of silently disabling a server. The
    result is written 0600 because a resolved copy does hold real tokens.
    """
    src = paths.harness_assets_dir() / "mcp" / "mcp.template.json"
    dest = dest or paths.mcp_file()
    env = env if env is not None else dict(os.environ)
    text = src.read_text()
    unresolved: list[str] = []

    def sub(m: re.Match) -> str:
        name, default = m.group(1), m.group(2)
        if name in env and env[name]:
            return env[name]
        if default is not None:
            return default
        unresolved.append(name)
        return m.group(0)

    resolved = _SECRET_RE.sub(sub, text)
    data = json.loads(resolved) if not unresolved else None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(json.dumps(data, indent=2) + "\n" if data is not None else resolved)
    tmp.replace(dest)
    dest.chmod(0o600)
    log.info("mcp config written to %s (%d unresolved)", dest, len(unresolved))
    return dest, sorted(set(unresolved))


# ---------------------------------------------------------------------------
# touch: install the usage hook into Claude Code and Cursor
# ---------------------------------------------------------------------------

def deploy_hook_script() -> Path:
    """Copy the bundled hook script to the midas hooks dir; returns its path."""
    src = Path(__file__).parent / "hooks" / HOOK_NAME
    paths.hooks_dir().mkdir(parents=True, exist_ok=True)
    dest = paths.hooks_dir() / HOOK_NAME
    shutil.copy2(src, dest)
    dest.chmod(0o755)
    return dest


def _load_json(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{path} contains invalid JSON ({exc}) - fix it first") from exc
    return {}


def install_claude_hook(settings_path: Path | None = None) -> bool:
    """Register the usage hook as a Stop hook in ~/.claude/settings.json.

    Merges with existing hooks; returns False if already registered.
    """
    settings_path = settings_path or Path.home() / ".claude" / "settings.json"
    hook_script = deploy_hook_script()
    command = f"python3 {hook_script} stop"

    settings = _load_json(settings_path)
    stop_entries = settings.setdefault("hooks", {}).setdefault("Stop", [])
    for entry in stop_entries:
        for hook in entry.get("hooks", []):
            if HOOK_NAME in hook.get("command", ""):
                return False
    stop_entries.append({"hooks": [{"type": "command", "command": command}]})
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    log.info("claude Stop hook registered in %s", settings_path)
    return True


def install_cursor_hook(hooks_path: Path | None = None) -> bool:
    """Register the usage hook as a stop hook in ~/.cursor/hooks.json."""
    hooks_path = hooks_path or Path.home() / ".cursor" / "hooks.json"
    hook_script = deploy_hook_script()
    command = f"python3 {hook_script} cursor-stop"

    data = _load_json(hooks_path)
    data.setdefault("version", 1)
    stop_entries = data.setdefault("hooks", {}).setdefault("stop", [])
    for entry in stop_entries:
        if HOOK_NAME in entry.get("command", ""):
            return False
    stop_entries.append({"command": command})
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(json.dumps(data, indent=2) + "\n")
    log.info("cursor stop hook registered in %s", hooks_path)
    return True


# ---------------------------------------------------------------------------
# greed: harvest useful skills from the user's workspace
# ---------------------------------------------------------------------------

@dataclass
class FoundSkill:
    name: str
    description: str
    path: Path
    source: str      # "claude" | "cursor"
    score: int       # keyword hits
    known: bool      # already bundled/imported into midas


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)


def parse_skill_md(skill_md: Path) -> tuple[str, str]:
    """Return (name, description) from a SKILL.md frontmatter (lenient YAML)."""
    try:
        text = skill_md.read_text(errors="replace")
    except OSError:
        return skill_md.parent.name, ""
    m = _FRONTMATTER_RE.match(text)
    name, desc = skill_md.parent.name, ""
    if m:
        block = m.group(1)
        nm = re.search(r"^name:\s*(.+)$", block, re.MULTILINE)
        if nm:
            name = nm.group(1).strip().strip("'\"")
        dm = re.search(r"^description:\s*>?-?\s*(.*?)(?=^\w+:|\Z)", block, re.MULTILINE | re.DOTALL)
        if dm:
            desc = " ".join(dm.group(1).split())
    return name, desc


def _known_skill_names() -> set[str]:
    known = set()
    for root in (paths.skills_dir(), paths.skills_dir() / "vendor", paths.user_skills_dir()):
        if root.is_dir():
            for d in root.iterdir():
                if d.is_dir():
                    known.add(d.name)
    return known


def scan_workspace_skills() -> list[FoundSkill]:
    """Scan the user's Claude/Cursor skill folders for reuse candidates."""
    known = _known_skill_names()
    found: dict[str, FoundSkill] = {}
    for source, root in (("claude", CLAUDE_SKILLS), ("cursor", CURSOR_SKILLS)):
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            skill_md = d / "SKILL.md"
            if not d.is_dir() or not skill_md.is_file() or d.name in found:
                continue
            name, desc = parse_skill_md(skill_md)
            haystack = f"{name} {desc}".lower()
            score = sum(1 for kw in GREED_KEYWORDS if kw in haystack)
            found[d.name] = FoundSkill(
                name=name, description=desc, path=d, source=source,
                score=score, known=d.name in known or f"midas-{d.name}" in known,
            )
    return sorted(found.values(), key=lambda s: (-s.score, s.name))


def import_skill(skill: FoundSkill) -> Path:
    """Copy a workspace skill into the midas user skills dir (used in agent runs)."""
    dest = paths.user_skills_dir() / skill.path.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(skill.path, dest)
    log.info("imported skill %s -> %s", skill.name, dest)
    return dest
