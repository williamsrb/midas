"""Rotating file logging + optional console echo."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import paths

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_configured = False


def setup(console: bool = True, level: int = logging.INFO) -> logging.Logger:
    """Configure the root 'midas' logger once; safe to call repeatedly."""
    global _configured
    logger = logging.getLogger("midas")
    if _configured:
        return logger
    logger.setLevel(level)
    paths.logs_dir().mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        paths.logs_dir() / "midas.log", maxBytes=5 * 1024 * 1024, backupCount=5
    )
    fh.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(fh)
    if console and sys.stderr.isatty():
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
        logger.addHandler(ch)
    _configured = True
    return logger


def get(name: str) -> logging.Logger:
    return logging.getLogger(f"midas.{name}")


def task_logger(key: str, task_dir: Path) -> logging.Logger:
    """Per-task log file under the task state dir (in addition to the main log)."""
    logger = logging.getLogger(f"midas.task.{key}")
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        log_dir = task_dir / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_dir / "task.log", maxBytes=2 * 1024 * 1024, backupCount=2)
        fh.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(fh)
    return logger
