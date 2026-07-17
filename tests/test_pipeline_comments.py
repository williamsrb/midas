"""Midas-posted Jira comments: group restriction + self-requeue prevention."""

from midas import config as config_mod, jira_rest, state
from midas.pipeline import Pipeline


class FakeJira:
    """Captures add_comment calls; returns a Jira-like created timestamp."""
    calls: list[tuple[str, str, str]] = []

    def __init__(self, *args, **kwargs):
        pass

    def add_comment(self, key, body, visibility_group=""):
        FakeJira.calls.append((key, body, visibility_group))
        return {"id": "1", "created": "2026-07-17T10:00:00.000+0200"}


def _pipeline(cfg, monkeypatch, key="CMT-1"):
    cfg.jira.comment_group = "midas-watchers"
    config_mod.save_credential("JIRA_API_TOKEN", "tok")
    monkeypatch.setattr(jira_rest, "JiraClient", FakeJira)
    FakeJira.calls = []
    st = state.create(key, "a task")
    st.task_md.parent.mkdir(parents=True, exist_ok=True)
    st.task_md.write_text("# task")
    return Pipeline(cfg, st)


def test_spec_questions_posted_restricted_and_no_self_requeue(cfg, monkeypatch):
    p = _pipeline(cfg, monkeypatch)
    p._request_spec(["What browser?", "Which page?"])

    key, body, group = FakeJira.calls[0]
    assert group == "midas-watchers"           # never public
    assert "What browser?" in body
    st = state.load("CMT-1")
    assert st.stage == "awaiting_spec"
    assert (st.dir / "SPEC_QUESTIONS.md").is_file()
    # the posted comment's timestamp is recorded, so the poller will not
    # mistake midas' own comment for analyst activity
    assert st.data["last_seen_updated"] == "2026-07-17T10:00:00.000+0200"


def test_no_group_means_no_post_but_saved_locally(cfg, monkeypatch):
    p = _pipeline(cfg, monkeypatch, key="CMT-2")
    p.cfg.jira.comment_group = ""
    p._request_spec(["Question?"])
    assert FakeJira.calls == []
    st = state.load("CMT-2")
    assert st.stage == "awaiting_spec"
    assert (st.dir / "SPEC_QUESTIONS.md").is_file()


def test_posted_comment_timestamp_prevents_requeue(cfg, monkeypatch):
    from midas.poller import poll

    p = _pipeline(cfg, monkeypatch, key="CMT-3")
    p._request_spec(["Q?"])

    class FakeSearch:
        def search(self, jql, max_results=20):
            # Jira reports the issue updated exactly by midas' own comment
            return [{"key": "CMT-3", "fields": {
                "summary": "a task",
                "updated": "2026-07-17T10:00:00.000+0200",
                "status": {"name": "To Do", "statusCategory": {"key": "new"}},
            }}]

    assert poll(FakeSearch(), cfg) == []          # no self-requeue
    assert state.load("CMT-3").stage == "awaiting_spec"

    class AnalystReplied(FakeSearch):
        def search(self, jql, max_results=20):
            issues = super().search(jql, max_results)
            issues[0]["fields"]["updated"] = "2026-07-17T11:30:00.000+0200"
            return issues

    picked = poll(AnalystReplied(), cfg)          # real activity does requeue
    assert [s.key for s in picked] == ["CMT-3"]
    assert state.load("CMT-3").stage == "discovered"
