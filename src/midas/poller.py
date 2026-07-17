"""Task pickup: build JQL, query Jira, register new tasks in the state store."""

from __future__ import annotations

from . import logging_setup, state
from .config import Config
from .jira_rest import JiraClient

log = logging_setup.get("poller")


def build_jql(cfg: Config) -> str:
    if cfg.jira.pickup == "label":
        return (
            f'assignee = currentUser() AND labels = "{cfg.jira.label}" '
            f"AND statusCategory != Done ORDER BY updated DESC"
        )
    statuses = ", ".join(f'"{s}"' for s in cfg.jira.statuses)
    return (
        f"assignee = currentUser() AND status in ({statuses}) "
        f"AND updated >= {cfg.jira.recent_window} ORDER BY updated DESC"
    )


def poll(client: JiraClient, cfg: Config) -> list[state.TaskState]:
    """Query Jira and create state entries for tasks not seen before."""
    jql = build_jql(cfg)
    log.info("polling with JQL: %s", jql)
    issues = client.search(jql, max_results=cfg.jira.max_results)
    new_states = []
    for issue in issues:
        key = issue.get("key", "")
        if not key:
            continue
        if state.exists(key):
            continue
        summary = issue.get("fields", {}).get("summary", "")
        log.info("discovered new task %s: %s", key, summary)
        new_states.append(state.create(key, summary))
    if not new_states:
        log.info("no new tasks (%d matched, all known)", len(issues))
    return new_states
