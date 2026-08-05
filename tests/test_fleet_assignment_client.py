import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from midas.fleet import client
from midas.fleet.assignments import AssignmentEvent, AssignmentUsage, CompleteRequest, Gate, NackRequest
from midas.fleet.client import ClientIdentity


class _FakeAssignmentServer(BaseHTTPRequestHandler):
    responses: dict[str, tuple[int, dict | bytes]] = {}
    seen_requests: list[dict] = []

    def _reply(self, status: int, body) -> None:
        payload = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        if status != 204:
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)
        else:
            self.end_headers()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw and self.headers.get("content-type") == "application/json" else raw
        except json.JSONDecodeError:
            body = raw
        self.__class__.seen_requests.append({"path": self.path, "headers": dict(self.headers), "body": body})

        key = self.path.split("?")[0]
        status, response_body = self.__class__.responses.get(key, (404, {"error": "not found"}))
        self._reply(status, response_body)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_server():
    _FakeAssignmentServer.responses = {}
    _FakeAssignmentServer.seen_requests = []
    server = HTTPServer(("127.0.0.1", 0), _FakeAssignmentServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=2)


def _identity(url):
    return ClientIdentity(server_url=url, client_id="cl_test", client_secret="cs_test", private_key_pem="", public_key_pem="")


ASSIGNMENT_JSON = {
    "assignmentId": "as_1",
    "idempotencyKey": "jira:RFD-1:round1",
    "attempt": 1,
    "maxAttempts": 3,
    "leaseUntil": "2026-08-04T09:42:00Z",
    "priority": 50,
    "kernelVersion": "0.2.0",
    "harnessVersion": "9a1f",
    "playbook": {},
    "inputs": {"vars": {}, "documents": []},
    "workspace": {"kind": "none", "reuse": True},
    "limits": {},
    "routing": {},
}


class TestClaim:
    def test_returns_claimed_assignments(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/clients/cl_test/claim"] = (200, {"assignments": [ASSIGNMENT_JSON]})
        result = client.claim(_identity(fake_server), capabilities={"actions": ["git.clone"]}, wait_seconds=1)
        assert result.ok is True
        assert result.assignments[0].assignment_id == "as_1"

    def test_204_means_nothing_available(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/clients/cl_test/claim"] = (204, b"")
        result = client.claim(_identity(fake_server), capabilities={}, wait_seconds=1)
        assert result.ok is True
        assert result.assignments == []

    def test_client_quarantined(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/clients/cl_test/claim"] = (423, {"error": "client-quarantined"})
        result = client.claim(_identity(fake_server), capabilities={}, wait_seconds=1)
        assert result.ok is False
        assert result.error == "client-quarantined"

    def test_sends_x_midas_client_and_capabilities(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/clients/cl_test/claim"] = (204, b"")
        client.claim(_identity(fake_server), capabilities={"actions": ["git.clone"], "subscriptions": {"claude": {}}}, wait_seconds=1)
        seen = _FakeAssignmentServer.seen_requests[0]
        assert seen["headers"]["x-midas-client"] == "cl_test"
        assert seen["body"]["actions"] == ["git.clone"]
        assert seen["body"]["subscriptions"] == ["claude"]


class TestRenew:
    def test_returns_the_new_lease(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/renew"] = (200, {"leaseUntil": "2026-08-04T10:00:00Z"})
        result = client.renew(_identity(fake_server), "as_1")
        assert result.ok is True
        assert result.lease_until == "2026-08-04T10:00:00Z"

    def test_409_is_lease_lost(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/renew"] = (409, {"error": "lease-lost"})
        result = client.renew(_identity(fake_server), "as_1")
        assert result.ok is False
        assert result.error == "lease-lost"


class TestComplete:
    def test_completes_successfully(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/complete"] = (200, {"ok": True, "state": "succeeded"})
        result = client.complete(_identity(fake_server), "as_1", CompleteRequest(outcome="succeeded", spend_usd=1.0, baton_digest="sha"))
        assert result.ok is True

    def test_gate_outcome_serializes_the_gate(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/complete"] = (200, {"ok": True})
        client.complete(_identity(fake_server), "as_1", CompleteRequest(outcome="gate", spend_usd=0, baton_digest="sha", gate=Gate(node_id="approve", prompt="ok?")))
        seen = _FakeAssignmentServer.seen_requests[0]
        assert seen["body"]["gate"] == {"nodeId": "approve", "prompt": "ok?"}

    def test_409_is_lease_lost(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/complete"] = (409, {"error": "lease-lost"})
        result = client.complete(_identity(fake_server), "as_1", CompleteRequest(outcome="succeeded", spend_usd=0, baton_digest="sha"))
        assert result.ok is False
        assert result.error == "lease-lost"


class TestNack:
    def test_sends_the_documented_shape(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/nack"] = (200, {"ok": True})
        result = client.nack(_identity(fake_server), "as_1", NackRequest(reason="policy-denied", retryable=True))
        assert result.ok is True
        assert _FakeAssignmentServer.seen_requests[0]["body"] == {"reason": "policy-denied", "retryable": True}


class TestEvents:
    def test_sends_a_batch(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/events"] = (200, {"ok": True})
        events = [AssignmentEvent(seq=0, at="2026-08-04T09:00:00Z", type="step-completed", node_id="plan")]
        result = client.send_events(_identity(fake_server), "as_1", events)
        assert result.ok is True
        assert _FakeAssignmentServer.seen_requests[0]["body"]["events"][0]["nodeId"] == "plan"


class TestUsage:
    def test_sends_a_usage_record(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/usage"] = (200, {"ok": True})
        usage = AssignmentUsage(at="2026-08-04T09:00:00Z", step_id="plan", subscription="claude", estimated_usd=0.05)
        result = client.send_usage(_identity(fake_server), "as_1", usage)
        assert result.ok is True


class TestUploadArtifact:
    def test_uploads_raw_bytes(self, fake_server):
        _FakeAssignmentServer.responses["/api/fleet/v1/assignments/as_1/artifacts"] = (201, {"ok": True})
        result = client.upload_artifact(_identity(fake_server), "as_1", "sha-abc", b"artifact bytes")
        assert result.ok is True
        seen = _FakeAssignmentServer.seen_requests[0]
        assert seen["path"] == "/api/fleet/v1/assignments/as_1/artifacts?sha256=sha-abc"
        assert seen["body"] == b"artifact bytes"
