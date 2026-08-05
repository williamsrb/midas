"""Capability advertisement (spec §4.2) - what this Midas can do, on enroll and every heartbeat.

The server cannot route work it does not understand the shape of; this is what lets the
linter reject an unrunnable playbook at authoring time, and what the fleet dashboard shows
per client. Built entirely from facts midas can already determine locally - nothing here
requires a network call.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from pathlib import Path

from .. import disk, kernel, policy
from ..config import Config
from .sync import NetworkAppliedState

# Mirrors the closed action vocabulary in policy.py (spec §4.2) - what midas implements, not
# what a given operator's policy allows. Kept in sync with policy.KNOWN_ACTIONS.
ACTIONS = list(policy.KNOWN_ACTIONS)


def _claude_status() -> dict:
    """Presence and login state for `claude`. Duplicates preflight.check_agent_cli's and
    cli.py's _agent_login_status's checks in miniature - those two already duplicate each
    other in this codebase; a shared helper would be a reasonable follow-up, not this commit."""
    present = shutil.which("claude") is not None
    if not present:
        return {"present": False}
    logged_in = False
    try:
        data = json.loads((Path.home() / ".claude.json").read_text())
        logged_in = bool(data.get("oauthAccount", {}).get("emailAddress"))
    except (OSError, json.JSONDecodeError):
        pass
    return {"present": True, "auth": "subscription" if logged_in else "unknown", "loggedIn": logged_in, "bin": "claude"}


def _cursor_status() -> dict:
    present = shutil.which("cursor-agent") is not None
    if not present:
        return {"present": False}
    try:
        rc = subprocess.run(["cursor-agent", "status"], capture_output=True, timeout=20).returncode
    except (OSError, subprocess.TimeoutExpired):
        rc = -1
    return {"present": True, "auth": "subscription", "loggedIn": rc == 0, "bin": "cursor-agent"}


def _tool_version(bin_name: str, *version_args: str) -> str | bool:
    if not shutil.which(bin_name):
        return False
    try:
        out = subprocess.run([bin_name, *version_args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip().splitlines()[0] if out.stdout.strip() else True
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return True


def _policy_summary() -> dict | None:
    try:
        return policy.load().summary()
    except policy.PolicyError:
        return None  # not set up yet - the server treats an absent summary as "unknown, be conservative"


def build(cfg: Config, *, labels: list[str] | None = None) -> dict:
    """The exact §4.2 payload, sent on enroll and every heartbeat."""
    workspace_root = Path(cfg.paths.workspace_root).expanduser()
    return {
        "kernelVersion": kernel.active_version(),
        "actions": ACTIONS,
        "subscriptions": {
            "claude": _claude_status(),
            "cursor": _cursor_status(),
            "shell": {"present": True},
        },
        "tools": {
            "git": _tool_version("git", "--version"),
            "node": _tool_version("node", "--version"),
            "docker": shutil.which("docker") is not None,
            "python": platform.python_version(),
        },
        "limits": {
            "maxConcurrentRuns": 1,
            "freeDiskGb": round(disk.free_bytes(workspace_root) / disk.GB, 1),
            "workspaceGb": round(disk.workspace_usage_bytes(workspace_root) / disk.GB, 1),
        },
        "labels": labels or [],
        "timezone": time.strftime("%Z") or "UTC",
        # The server's evaluateCurrency() (patches.ts) compares this against an epoch SHA it
        # loaded a manifest snapshot for - it is NOT the bundled harness's own version (a
        # sha256-over-item-digests, a completely different value space; see fleet/sync.py's
        # NetworkAppliedState docstring). Reporting the bundled version here made every client
        # compare as permanently outdated, since the server could never find a matching snapshot.
        "harnessVersion": NetworkAppliedState.load().version or None,
        "policySummary": _policy_summary(),
    }
