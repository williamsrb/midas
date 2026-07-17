"""Task pickup: build JQL, query Jira, register new tasks, detect rework rounds.

Rework: a task midas already finished (awaiting_human / awaiting_spec /
answered / blocked) that the analyst moved back into the pickup set and
updated (new comments, edited spec). The task is requeued from 'discovered';
the triage stage then classifies the new feedback (requirements change vs
complementary info) before re-planning. Tasks bounce back and forth multiple
times - each round is archived as task.round<N>.md / plan.round<N>.md.
"""

from __future__ import annotations

from datetime import datetime

from . import logging_setup, state
from .config import Config
from .jira_rest import JiraClient

log = logging_setup.get("poller")

REWORKABLE = {"awaiting_human", "awaiting_spec", "answered", "blocked"}


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


def _newer(a: str, b: str) -> bool:
    """True when Jira timestamp `a` is newer than stored `b` (missing b = newer)."""
    if not b:
        return True
    try:
        return datetime.fromisoformat(a) > datetime.fromisoformat(b)
    except (ValueError, TypeError):  # unparsable or naive/aware mix
        return a > b  # same-format string compare fallback


def _back_in_todo(issue: dict, cfg: Config) -> bool:
    """The issue's status is (again) in the pickup set / To Do category."""
    status = (issue.get("fields", {}).get("status") or {})
    if status.get("name") in cfg.jira.statuses:
        return True
    return (status.get("statusCategory") or {}).get("key") == "new"


def requeue_for_rework(st: state.TaskState, updated: str) -> None:
    """Archive the previous round's artifacts and restart from 'discovered'."""
    round_no = int(st.data.get("rework_round", 0)) + 1
    for src, name in ((st.task_md, "task"), (st.plan_md, "plan")):
        if src.is_file():
            src.rename(st.dir / f"{name}.round{round_no}.md")
    st.data["rework_round"] = round_no
    st.data["prev_stage"] = st.stage
    st.data["last_seen_updated"] = updated
    st.advance("discovered", f"rework round {round_no} (was {st.data['prev_stage']})")
    log.info("requeued %s for rework round %d", st.key, round_no)


def poll(client: JiraClient, cfg: Config) -> list[state.TaskState]:
    """Query Jira; create states for new tasks, requeue finished ones that changed."""
    jql = build_jql(cfg)
    log.info("polling with JQL: %s", jql)
    issues = client.search(jql, max_results=cfg.jira.max_results)
    picked = []
    for issue in issues:
        key = issue.get("key", "")
        if not key:
            continue
        fields = issue.get("fields", {})
        if state.exists(key):
            st = state.load(key)
            if (
                st.stage in REWORKABLE
                and _back_in_todo(issue, cfg)
                and _newer(fields.get("updated", ""), st.data.get("last_seen_updated", ""))
            ):
                requeue_for_rework(st, fields.get("updated", ""))
                picked.append(st)
            continue
        summary = fields.get("summary", "")
        log.info("discovered new task %s: %s", key, summary)
        st = state.create(key, summary)
        st.data["last_seen_updated"] = fields.get("updated", "")
        st.save()
        picked.append(st)
    if not picked:
        log.info("no new or reworked tasks (%d matched)", len(issues))
    return picked
