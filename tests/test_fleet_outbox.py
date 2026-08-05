import base64
import json

import pytest

from midas.fleet import client, outbox
from midas.fleet.client import ClientIdentity


def _identity():
    return ClientIdentity(server_url="http://example.invalid", client_id="cl_test", client_secret="cs_test", private_key_pem="", public_key_pem="")


class TestEnqueueAndList:
    def test_enqueues_with_incrementing_seq(self):
        outbox.enqueue("event", "as_1", {"seq": 0, "at": "2026-01-01T00:00:00Z", "type": "step-completed"})
        outbox.enqueue("usage", "as_1", {"at": "2026-01-01T00:00:01Z", "stepId": "plan", "subscription": "claude", "estimatedUsd": 0.1})
        entries = outbox.list_entries()
        assert [e.kind for e in entries] == ["event", "usage"]
        assert [e.seq for e in entries] == [0, 1]

    def test_depth_reflects_pending_entries(self):
        assert outbox.depth() == 0
        outbox.enqueue("usage", "as_1", {"at": "x", "stepId": "s", "subscription": "claude", "estimatedUsd": None})
        assert outbox.depth() == 1

    def test_rejects_an_unknown_kind(self):
        with pytest.raises(ValueError):
            outbox.enqueue("bogus", "as_1", {})


class TestShed:
    def test_sheds_the_oldest_cli_prefixed_events_only(self):
        outbox.enqueue("event", "as_1", {"seq": 0, "at": "t", "type": "cli:stdout"})
        outbox.enqueue("event", "as_1", {"seq": 1, "at": "t", "type": "cli:stdout"})
        outbox.enqueue("usage", "as_1", {"at": "t", "stepId": "s", "subscription": "claude", "estimatedUsd": None})
        shed = outbox.shed(max_entries=1)
        assert len(shed) == 2
        remaining = outbox.list_entries()
        assert len(remaining) == 1
        assert remaining[0].kind == "usage"

    def test_never_sheds_usage_or_completion_even_under_a_tight_cap(self):
        outbox.enqueue("usage", "as_1", {"at": "t", "stepId": "s", "subscription": "claude", "estimatedUsd": None})
        outbox.enqueue("completion", "as_1", {"outcome": "succeeded", "spendUsd": 1, "batonDigest": "sha"})
        shed = outbox.shed(max_entries=0)
        assert shed == []
        assert len(outbox.list_entries()) == 2

    def test_does_nothing_when_already_under_the_cap(self):
        outbox.enqueue("usage", "as_1", {"at": "t", "stepId": "s", "subscription": "claude", "estimatedUsd": None})
        assert outbox.shed(max_entries=10) == []


class TestDrain(object):
    def _patch(self, monkeypatch, fn_name, result):
        monkeypatch.setattr(client, fn_name, lambda *a, **k: result)

    def test_sent_entries_are_removed(self, monkeypatch):
        outbox.enqueue("usage", "as_1", {"at": "t", "stepId": "s", "subscription": "claude", "estimatedUsd": 0.1})
        self._patch(monkeypatch, "send_usage", client.FleetActionResult(ok=True))
        result = outbox.drain(_identity())
        assert result.sent == 1
        assert outbox.list_entries() == []

    def test_lease_lost_keeps_the_entry_and_skips_the_rest_of_that_assignment(self, monkeypatch):
        outbox.enqueue("usage", "as_1", {"at": "t1", "stepId": "s1", "subscription": "claude", "estimatedUsd": 0.1})
        outbox.enqueue("usage", "as_1", {"at": "t2", "stepId": "s2", "subscription": "claude", "estimatedUsd": 0.2})
        self._patch(monkeypatch, "send_usage", client.FleetActionResult(ok=False, error="lease-lost"))
        result = outbox.drain(_identity())
        assert result.kept == 2
        assert len(outbox.list_entries()) == 2  # nothing deleted

    def test_a_non_retryable_4xx_moves_the_entry_to_dead(self, monkeypatch):
        outbox.enqueue("usage", "as_1", {"at": "t", "stepId": "s", "subscription": "claude", "estimatedUsd": 0.1})
        self._patch(monkeypatch, "send_usage", client.FleetActionResult(ok=False, error="HTTP 400 — bad request"))
        result = outbox.drain(_identity())
        assert result.dead_lettered == 1
        assert outbox.list_entries() == []

    def test_a_network_failure_keeps_the_entry_for_next_drain(self, monkeypatch):
        outbox.enqueue("usage", "as_1", {"at": "t", "stepId": "s", "subscription": "claude", "estimatedUsd": 0.1})
        self._patch(monkeypatch, "send_usage", client.FleetActionResult(ok=False, error="ConnectionError: refused"))
        result = outbox.drain(_identity())
        assert result.kept == 1
        assert len(outbox.list_entries()) == 1

    def test_jira_intent_is_skipped_not_silently_dropped(self, monkeypatch):
        outbox.enqueue("jira_intent", "as_1", {"comment": "done"})
        result = outbox.drain(_identity())
        assert result.skipped == 1
        assert len(outbox.list_entries()) == 1  # still there - not sent, not lost

    def test_completion_entry_dispatches_complete(self, monkeypatch):
        outbox.enqueue("completion", "as_1", {"outcome": "succeeded", "spendUsd": 1.0, "batonDigest": "sha256:abc"})
        self._patch(monkeypatch, "complete", client.FleetActionResult(ok=True))
        result = outbox.drain(_identity())
        assert result.sent == 1

    def test_completion_entry_with_nack_action_dispatches_nack(self, monkeypatch):
        outbox.enqueue("completion", "as_1", {"action": "nack", "reason": "workspace-error", "retryable": True})
        self._patch(monkeypatch, "nack", client.FleetActionResult(ok=True))
        result = outbox.drain(_identity())
        assert result.sent == 1

    def test_artifact_entry_decodes_base64_and_uploads(self, monkeypatch):
        payload = {"sha256": "sha-abc", "dataBase64": base64.b64encode(b"artifact bytes").decode()}
        outbox.enqueue("artifact", "as_1", payload)
        seen = {}

        def fake_upload(identity, assignment_id, sha256, data):
            seen["data"] = data
            return client.FleetActionResult(ok=True)

        monkeypatch.setattr(client, "upload_artifact", fake_upload)
        result = outbox.drain(_identity())
        assert result.sent == 1
        assert seen["data"] == b"artifact bytes"


def test_a_torn_write_is_skipped_not_fatal(tmp_path):
    outbox.enqueue("usage", "as_1", {"at": "t", "stepId": "s", "subscription": "claude", "estimatedUsd": 0.1})
    entries_dir = outbox._outbox_dir()
    torn = entries_dir / "0000000001-usage.json"
    torn.write_text("{not valid json")
    entries = outbox.list_entries()
    assert len(entries) == 1
    assert entries[0].seq == 0
