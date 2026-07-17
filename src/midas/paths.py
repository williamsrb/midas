"""Central filesystem locations (XDG-style, overridable via env for tests)."""

from __future__ import annotations

import os
from pathlib import Path


def config_dir() -> Path:
    return Path(os.environ.get(
        "MIDAS_CONFIG_DIR",
        os.path.join(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")), "midas"),
    ))


def state_dir() -> Path:
    return Path(os.environ.get(
        "MIDAS_STATE_DIR",
        os.path.join(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")), "midas"),
    ))


def config_file() -> Path:
    return config_dir() / "config.toml"


def credentials_file() -> Path:
    return config_dir() / "credentials"


def mcp_file() -> Path:
    return config_dir() / "mcp.json"


def tasks_dir() -> Path:
    return state_dir() / "tasks"


def logs_dir() -> Path:
    return state_dir() / "logs"


def locks_dir() -> Path:
    return state_dir() / "locks"


def completed_dir() -> Path:
    return state_dir() / "completed"


def blocked_file() -> Path:
    return state_dir() / "blocked.json"


def skills_dir() -> Path:
    """Bundled agent skills shipped inside the package."""
    return Path(__file__).parent / "skills"


def user_skills_dir() -> Path:
    """User-imported skills (via `midas greed`), merged into agent runs."""
    return config_dir() / "skills"


def hooks_dir() -> Path:
    """Installed copies of midas hook scripts (via `midas touch`)."""
    return config_dir() / "hooks"


def usage_ledger() -> Path:
    """JSONL ledger of every LLM interaction (midas runs + hooked sessions)."""
    return logs_dir() / "llm-usage.jsonl"


def manifest_file() -> Path:
    """Integrity manifest written by the installer next to the package."""
    return Path(__file__).parent / "MANIFEST.sha256"


def ensure_runtime_dirs() -> None:
    for d in (config_dir(), tasks_dir(), logs_dir(), locks_dir(), completed_dir()):
        d.mkdir(parents=True, exist_ok=True)
