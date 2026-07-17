"""Completion reporting: completed/<KEY>.md + optional Jira comment."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import config as config_mod, logging_setup, paths
from .config import Config
from .state import TaskState

log = logging_setup.get("report")


def write_completed(st: TaskState, cfg: Config) -> Path:
    env = st.env()
    verdict = env.get("validation_verdict", "").strip()
    lines = [
        f"# {st.key} - completed by midas",
        "",
        f"**Summary:** {st.summary}",
        f"**Jira:** {cfg.jira.base_url}/browse/{st.key}",
        f"**Repository:** {env.get('repo_url', '?')}",
        f"**Branch:** {env.get('branch', st.key)}",
        f"**Commit:** {env.get('commit_sha', '?')}",
        f"**Stack:** {env.get('stack', '?')}" + (" (Enonic)" if env.get("enonic") else ""),
        f"**Review URL:** {env.get('review_url', '-')}",
        f"**Completed at:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Next steps (human)",
        "",
        f"1. Review the commit on branch `{env.get('branch', st.key)}` in "
        f"`{env.get('repo_path', '?')}`",
        f"2. If OK, merge into `{cfg.git.review_branch}` and push to trigger the pipeline",
        (f"3. After the pipeline finishes, run `midas test {st.key}` to execute the "
         f"Playwright test plan") if st.test_plan_dir.is_dir() else
        "3. No automated test plan was generated for this task",
        "",
        "## Validation verdict",
        "",
        verdict or "_not captured_",
        "",
        "## Artifacts",
        "",
        f"- Task: {st.task_md}",
        f"- Plan: {st.plan_md}",
        f"- Transcripts: {st.transcripts_dir}",
        f"- Test plan: {st.test_plan_dir if st.test_plan_dir.is_dir() else '-'}",
        f"- State: {st.dir / 'state.json'}",
        "",
    ]
    paths.completed_dir().mkdir(parents=True, exist_ok=True)
    path = paths.completed_dir() / f"{st.key}.md"
    path.write_text("\n".join(lines))
    log.info("completion report written: %s", path)
    return path


def maybe_post_jira_comment(st: TaskState, cfg: Config) -> None:
    if not cfg.report.post_jira_comment:
        return
    token = config_mod.jira_api_token()
    if not token:
        log.warning("post_jira_comment enabled but no API token - skipping")
        return
    from .jira_rest import JiraClient, JiraError
    env = st.env()
    body = (
        f"Midas completed an automated implementation for {st.key}.\n"
        f"Branch: {env.get('branch', st.key)}\n"
        f"Commit: {env.get('commit_sha', '?')}\n"
        f"Awaiting human validation and merge to {cfg.git.review_branch}."
    )
    try:
        JiraClient(cfg.jira.base_url, cfg.me.jira_email, token).add_comment(st.key, body)
        log.info("posted completion comment on %s", st.key)
    except JiraError as exc:
        log.error("failed to post Jira comment on %s: %s", st.key, exc)
