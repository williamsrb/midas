"""Run a task's generated Playwright test plan inside the official docker image."""

from __future__ import annotations

import shutil
import subprocess

from . import logging_setup
from .state import TaskState

log = logging_setup.get("testrun")

PLAYWRIGHT_IMAGE = "mcr.microsoft.com/playwright:v1.49.1-noble"


def run_test_plan(st: TaskState, timeout_minutes: int = 30) -> int:
    """Execute the Playwright specs in tasks/<KEY>/test-plan/ via docker.

    Results (report + output) land in test-plan/results/.
    Returns the playwright exit code (0 = all tests passed).
    """
    plan_dir = st.test_plan_dir
    if not plan_dir.is_dir() or not any(plan_dir.rglob("*.spec.*")):
        raise RuntimeError(
            f"no Playwright specs found under {plan_dir} - "
            "the test plan was not generated for this task"
        )
    if not shutil.which("docker"):
        raise RuntimeError("docker is required to run the test plan (not found on PATH)")

    results = plan_dir / "results"
    results.mkdir(exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "--network", "host",
        "-v", f"{plan_dir}:/work",
        "-w", "/work",
        PLAYWRIGHT_IMAGE,
        "bash", "-lc",
        "npm init -y >/dev/null 2>&1 && npm i -D @playwright/test >/dev/null 2>&1 && "
        "npx playwright test --reporter=list,html --output=results 2>&1 | tee results/run.log",
    ]
    log.info("running playwright test plan for %s", st.key)
    proc = subprocess.run(cmd, timeout=timeout_minutes * 60)
    log.info("playwright finished for %s with exit code %d", st.key, proc.returncode)
    return proc.returncode
