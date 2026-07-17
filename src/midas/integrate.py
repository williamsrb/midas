"""Workspace integration: `midas touch` (install skills + hooks into the
user's Claude/Cursor setup) and `midas greed` (harvest useful skills from the
user's workspace into midas)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import logging_setup, paths

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
    """Copy skill folders into dest_root; returns names installed (skips existing)."""
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
    log.info("installed %d skills into %s", len(installed), dest_root)
    return installed


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
