from midas import state
from midas.poller import build_jql, poll


class FakeClient:
    def __init__(self, issues):
        self.issues = issues

    def search(self, jql, max_results=20):
        return self.issues


def test_jql_status_mode(cfg):
    jql = build_jql(cfg)
    assert "assignee = currentUser()" in jql
    assert '"To Do"' in jql and "updated >= -2d" in jql


def test_jql_label_mode(cfg):
    cfg.jira.pickup = "label"
    jql = build_jql(cfg)
    assert 'labels = "midas"' in jql
    assert "statusCategory != Done" in jql


def _issue(key, summary="s"):
    return {"key": key, "fields": {"summary": summary}}


def test_poll_creates_new_tasks(cfg):
    client = FakeClient([_issue("RFD-1", "first"), _issue("RFD-2", "second")])
    new = poll(client, cfg)
    assert [s.key for s in new] == ["RFD-1", "RFD-2"]
    assert state.exists("RFD-1") and state.exists("RFD-2")


def test_poll_dedupes_known_tasks(cfg):
    state.create("RFD-1")
    client = FakeClient([_issue("RFD-1"), _issue("RFD-3")])
    new = poll(client, cfg)
    assert [s.key for s in new] == ["RFD-3"]
