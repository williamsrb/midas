"""Rework detection: finished tasks that analysts send back get requeued."""

from midas import state
from midas.poller import poll, requeue_for_rework


class FakeClient:
    def __init__(self, issues):
        self.issues = issues

    def search(self, jql, max_results=20):
        return self.issues


def _issue(key, updated, status="To Do", category="new"):
    return {
        "key": key,
        "fields": {
            "summary": "s",
            "updated": updated,
            "status": {"name": status, "statusCategory": {"key": category}},
        },
    }


def _finished_task(key, last_seen, stage="awaiting_human"):
    st = state.create(key, "old summary")
    st.task_md.parent.mkdir(parents=True, exist_ok=True)
    st.task_md.write_text("# old task round")
    st.plan_md.write_text("# old plan")
    st.data["last_seen_updated"] = last_seen
    st.advance(stage)
    return st


def test_finished_task_updated_gets_requeued(cfg):
    _finished_task("RFD-1", "2026-07-15T10:00:00.000+0200")
    client = FakeClient([_issue("RFD-1", "2026-07-16T09:00:00.000+0200")])

    picked = poll(client, cfg)

    assert [s.key for s in picked] == ["RFD-1"]
    st = state.load("RFD-1")
    assert st.stage == "discovered"
    assert st.data["rework_round"] == 1
    assert st.data["prev_stage"] == "awaiting_human"
    assert (st.dir / "task.round1.md").is_file()
    assert (st.dir / "plan.round1.md").is_file()
    assert not st.task_md.is_file()  # forces a fresh download next cycle


def test_finished_task_not_updated_is_left_alone(cfg):
    _finished_task("RFD-2", "2026-07-16T09:00:00.000+0200")
    client = FakeClient([_issue("RFD-2", "2026-07-16T09:00:00.000+0200")])
    assert poll(client, cfg) == []
    assert state.load("RFD-2").stage == "awaiting_human"


def test_in_flight_task_never_requeued(cfg):
    st = state.create("RFD-3")
    st.advance("planned")
    client = FakeClient([_issue("RFD-3", "2026-07-16T09:00:00.000+0200")])
    assert poll(client, cfg) == []
    assert state.load("RFD-3").stage == "planned"


def test_awaiting_spec_requeued_after_analyst_reply(cfg):
    _finished_task("RFD-4", "2026-07-15T08:00:00.000+0200", stage="awaiting_spec")
    client = FakeClient([_issue("RFD-4", "2026-07-15T09:00:00.000+0200")])
    picked = poll(client, cfg)
    assert picked and state.load("RFD-4").stage == "discovered"


def test_status_not_todo_blocks_requeue_in_label_mode(cfg):
    cfg.jira.pickup = "label"
    _finished_task("RFD-5", "2026-07-15T08:00:00.000+0200")
    client = FakeClient([
        _issue("RFD-5", "2026-07-16T09:00:00.000+0200", status="In Review", category="indeterminate"),
    ])
    assert poll(client, cfg) == []


def test_multiple_rounds_archive_separately(cfg):
    st = _finished_task("RFD-6", "old")
    requeue_for_rework(st, "2026-07-16T09:00:00.000+0200")
    st.task_md.write_text("# round 2 content")
    st.plan_md.write_text("# plan 2")
    st.advance("awaiting_human")
    requeue_for_rework(st, "2026-07-17T09:00:00.000+0200")
    assert (st.dir / "task.round1.md").is_file()
    assert (st.dir / "task.round2.md").is_file()
    assert st.data["rework_round"] == 2
