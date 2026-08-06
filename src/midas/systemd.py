"""Systemd user-unit management for the delegated-work agent (spec §4.1, S4b).

`midas enable` used to mean "install a crontab entry that polls Jira every N minutes." Now it
means "run midas-agent.service" - a long-lived process (`midas agent --foreground`) that polls
the fleet queue continuously rather than waking on a fixed schedule. `--legacy` (cli.py) keeps
the old crontab path available for anyone not yet delegating through a Morpheus server.

Every systemctl call goes through an injectable `runner` (default `subprocess.run`) so tests can
verify the exact commands issued without a real systemd user session - this project has no
existing test coverage for `cron.py`'s equivalent `crontab` calls at all, for the same underlying
reason (nothing to safely exercise for real in CI); dependency injection here is a small
improvement on that gap rather than repeating it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import logging_setup

log = logging_setup.get("systemd")

UNIT_NAME = "midas-agent.service"


class SystemdError(Exception):
    pass


def unit_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def unit_path() -> Path:
    return unit_dir() / UNIT_NAME


def _midas_bin() -> str:
    found = shutil.which("midas")
    if found:
        return found
    return f"{sys.executable} -m midas.cli"


def unit_contents() -> str:
    return (
        "[Unit]\n"
        "Description=Midas delegated-work agent (Morpheus fleet)\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={_midas_bin()} agent --foreground\n"
        "Restart=always\n"
        "RestartSec=5\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _systemctl(args: list[str], runner: Callable | None = None):
    runner = runner or subprocess.run
    result = runner(["systemctl", "--user", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemdError(f"systemctl --user {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def install(*, runner: Callable | None = None) -> Path:
    unit_dir().mkdir(parents=True, exist_ok=True)
    unit_path().write_text(unit_contents())
    _systemctl(["daemon-reload"], runner)
    _systemctl(["enable", "--now", UNIT_NAME], runner)
    log.info("systemd user unit installed and started: %s", unit_path())
    return unit_path()


def uninstall(*, runner: Callable | None = None) -> bool:
    if not unit_path().is_file():
        return False
    try:
        _systemctl(["disable", "--now", UNIT_NAME], runner)
    except SystemdError as exc:
        log.warning("systemctl disable failed (removing the unit file anyway): %s", exc)
    unit_path().unlink(missing_ok=True)
    try:
        _systemctl(["daemon-reload"], runner)
    except SystemdError as exc:
        log.warning("systemctl daemon-reload failed after removing the unit: %s", exc)
    return True


def status(*, runner: Callable | None = None) -> str:
    if not unit_path().is_file():
        return "not installed"
    runner = runner or subprocess.run
    result = runner(["systemctl", "--user", "is-active", UNIT_NAME], capture_output=True, text=True)
    return (result.stdout or "").strip() or "unknown"
