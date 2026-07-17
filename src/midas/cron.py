"""Crontab entry management for the midas polling cycle."""

from __future__ import annotations

import shutil
import subprocess
import sys

from . import logging_setup, paths
from .config import Config

log = logging_setup.get("cron")

MARKER = "# midas-auto"


def _midas_bin() -> str:
    found = shutil.which("midas")
    if found:
        return found
    return f"{sys.executable} -m midas.cli"


def _read_crontab() -> list[str]:
    proc = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    return proc.stdout.splitlines()


def _write_crontab(lines: list[str]) -> None:
    content = "\n".join(lines) + ("\n" if lines else "")
    proc = subprocess.run(["crontab", "-"], input=content, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"crontab update failed: {proc.stderr.strip()}")


def entry(cfg: Config) -> str:
    log_file = paths.logs_dir() / "cron.log"
    return (
        f"*/{cfg.cron.interval_minutes} * * * * "
        f"{_midas_bin()} run --cron >> {log_file} 2>&1 {MARKER}"
    )


def install(cfg: Config) -> str:
    lines = [ln for ln in _read_crontab() if MARKER not in ln]
    new = entry(cfg)
    lines.append(new)
    _write_crontab(lines)
    log.info("cron entry installed: %s", new)
    return new


def uninstall() -> bool:
    lines = _read_crontab()
    kept = [ln for ln in lines if MARKER not in ln]
    if len(kept) == len(lines):
        return False
    _write_crontab(kept)
    log.info("cron entry removed")
    return True


def installed() -> str | None:
    for ln in _read_crontab():
        if MARKER in ln:
            return ln
    return None
