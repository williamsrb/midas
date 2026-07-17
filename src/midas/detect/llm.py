"""Last-resort LLM detection when deterministic detectors find nothing."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .. import agent, logging_setup, paths
from ..config import Config

log = logging_setup.get("detect.llm")


def detect_from_task_text(task_md: Path, cfg: Config, transcript: Path | None = None) -> dict:
    """Ask the agent to extract repo/review-url hints from the task text as JSON."""
    skill = paths.skills_dir() / "midas-env-detect" / "SKILL.md"
    prompt = (
        f"Read and follow the skill at {skill}. "
        f"The task file is at {task_md}. Git host: {cfg.git.host}. "
        f"Clone template: {cfg.git.clone_url_template} . "
        f'Reply with ONLY the JSON object described in the skill.'
    )
    with tempfile.TemporaryDirectory(prefix="midas-detect-") as tmp:
        res = agent.run(
            prompt, cwd=Path(tmp), model=cfg.agents.utility_model, cfg=cfg,
            transcript=transcript, timeout_minutes=10, context="env-detect",
        )
    if not res.ok:
        log.error("LLM detection failed: %s", res.text[:300])
        return {}
    try:
        data = agent.extract_json(res.text)
    except agent.AgentError as exc:
        log.error("LLM detection returned no JSON: %s", exc)
        return {}
    return {
        k: v for k, v in data.items()
        if k in ("repo_url", "review_url", "notes") and isinstance(v, str)
    }
