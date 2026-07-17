"""Fallback Jira access via agent CLI + Atlassian MCP (used when no API token).

Degraded mode: every operation costs an LLM call. The REST client is preferred.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from . import agent, logging_setup, paths
from .config import Config

log = logging_setup.get("jira-fallback")


def fetch_task_md(key: str, dest: Path, cfg: Config) -> bool:
    """Ask the agent to download a Jira issue via MCP and write task.md to dest."""
    skill = paths.skills_dir() / "midas-jira-fallback" / "SKILL.md"
    prompt = (
        f"Read and follow the skill at {skill}. "
        f"Download Jira issue {key} from {cfg.jira.base_url} using the Atlassian MCP tools "
        f"and write the markdown file EXACTLY to this absolute path: {dest} . "
        f"Reply with only DONE or FAILED: <reason>."
    )
    with tempfile.TemporaryDirectory(prefix="midas-jira-") as tmp:
        res = agent.run(
            prompt, cwd=Path(tmp), model=cfg.agents.utility_model, cfg=cfg,
            transcript=dest.parent / "transcripts" / "jira-fallback.jsonl",
            timeout_minutes=10, context=f"{key}/jira-fetch",
        )
    ok = res.ok and dest.is_file()
    if not ok:
        log.error("MCP fallback fetch for %s failed: %s", key, res.text[:300])
    return ok


def poll_keys(cfg: Config) -> list[tuple[str, str]]:
    """Ask the agent to list (key, summary) of recent tasks assigned to me via MCP."""
    from .poller import build_jql
    jql = build_jql(cfg)
    prompt = (
        f"Using the Atlassian MCP Jira search tool against {cfg.jira.base_url}, run this JQL: "
        f"{jql} . Reply with ONLY a JSON object of the form "
        f'{{"issues": [{{"key": "ABC-1", "summary": "..."}}]}} and nothing else.'
    )
    with tempfile.TemporaryDirectory(prefix="midas-jira-") as tmp:
        res = agent.run(prompt, cwd=Path(tmp), model=cfg.agents.utility_model, cfg=cfg,
                        timeout_minutes=10, context="jira-poll")
    if not res.ok:
        log.error("MCP fallback poll failed: %s", res.text[:300])
        return []
    try:
        data = agent.extract_json(res.text)
    except agent.AgentError as exc:
        log.error("MCP fallback poll returned no JSON: %s", exc)
        return []
    return [
        (i.get("key", ""), i.get("summary", ""))
        for i in data.get("issues", []) if i.get("key")
    ]
