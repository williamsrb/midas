"""Disk monitoring for the Automated workspace folder."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

GB = 1024 ** 3


def workspace_usage_bytes(root: Path) -> int:
    """Total size of the workspace folder (du -sb; deterministic and fast)."""
    if not root.is_dir():
        return 0
    try:
        out = subprocess.run(
            ["du", "-sb", str(root)], capture_output=True, text=True, timeout=120
        )
        return int(out.stdout.split()[0])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        # Fallback: python walk (slower, still deterministic)
        total = 0
        for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda e: None):
            for name in filenames:
                try:
                    total += os.lstat(os.path.join(dirpath, name)).st_size
                except OSError:
                    continue
        return total


def free_bytes(path: Path) -> int:
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    st = os.statvfs(probe)
    return st.f_bavail * st.f_frsize


def check(workspace_root: Path, max_workspace_gb: float, min_free_disk_gb: float) -> list[str]:
    """Return a list of human-readable problems (empty = OK)."""
    problems = []
    usage = workspace_usage_bytes(workspace_root)
    free = free_bytes(workspace_root)
    if usage > max_workspace_gb * GB:
        problems.append(
            f"workspace {workspace_root} uses {usage / GB:.1f} GB "
            f"(limit {max_workspace_gb:g} GB)"
        )
    if free < min_free_disk_gb * GB:
        problems.append(
            f"only {free / GB:.1f} GB free on the filesystem of {workspace_root} "
            f"(minimum {min_free_disk_gb:g} GB)"
        )
    return problems


def summary(workspace_root: Path) -> str:
    usage = workspace_usage_bytes(workspace_root)
    free = free_bytes(workspace_root)
    return f"workspace {usage / GB:.1f} GB used, {free / GB:.1f} GB free on disk"
