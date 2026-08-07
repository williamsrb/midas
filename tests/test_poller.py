import json

from midas import poller, state
from midas.fleet import ownership
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


class TestFleetOwnershipGuard:
    """R11: one owner per task key.

    The crontab poller and the delegated agent can both be installed on one machine, and morpheus
    can run a work source over the same Jira project. Before this guard, `poll()` consulted only
    the legacy pipeline's own state, so the same ticket could be picked up by both systems.
    """

    def _issue(self, key):
        return {"key": key, "fields": {"summary": key, "updated": "2026-08-07T10:00:00.000+0000"}}

    def test_a_key_the_fleet_owns_is_skipped(self, cfg, monkeypatch):
        monkeypatch.setattr(poller.ownership, "fleet_owned_keys", lambda: {"RFD-1"})
        picked = poll(FakeClient([self._issue("RFD-1"), self._issue("RFD-2")]), cfg)
        assert [st.key for st in picked] == ["RFD-2"]

    def test_nothing_is_skipped_when_the_fleet_owns_nothing(self, cfg, monkeypatch):
        monkeypatch.setattr(poller.ownership, "fleet_owned_keys", lambda: set())
        picked = poll(FakeClient([self._issue("RFD-3")]), cfg)
        assert [st.key for st in picked] == ["RFD-3"]


class TestOwnedKeyExtraction:
    def test_reads_the_issue_key_out_of_a_source_idempotency_key(self, tmp_path, monkeypatch):
        fleet = tmp_path / "fleet"
        fleet.mkdir()
        monkeypatch.setattr(ownership.paths, "fleet_dir", lambda: fleet)
        (fleet / "completed.json").write_text(
            json.dumps({"source:jira-main:RFD-9:round1": {}, "manual:whatever:123": {}})
        )
        assert ownership.fleet_owned_keys() == {"RFD-9"}

    def test_reads_the_issue_key_out_of_a_held_lease(self, tmp_path, monkeypatch):
        fleet = tmp_path / "fleet"
        (fleet / "leases").mkdir(parents=True)
        monkeypatch.setattr(ownership.paths, "fleet_dir", lambda: fleet)
        (fleet / "leases" / "as_1.json").write_text(
            json.dumps({"idempotencyKey": "manual:x:1", "inputs": {"vars": {"jiraIssueKey": "RFD-4"}}})
        )
        assert ownership.fleet_owned_keys() == {"RFD-4"}

    def test_a_torn_lease_file_does_not_stop_polling(self, tmp_path, monkeypatch):
        fleet = tmp_path / "fleet"
        (fleet / "leases").mkdir(parents=True)
        monkeypatch.setattr(ownership.paths, "fleet_dir", lambda: fleet)
        (fleet / "leases" / "as_1.json").write_text("{not json")
        assert ownership.fleet_owned_keys() == set()

    def test_no_fleet_state_at_all_owns_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ownership.paths, "fleet_dir", lambda: tmp_path / "nope")
        assert ownership.fleet_owned_keys() == set()
