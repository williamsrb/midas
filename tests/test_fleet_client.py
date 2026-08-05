import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from midas.fleet import client


class _FakeFleetServer(BaseHTTPRequestHandler):
    """A real local HTTP server standing in for Morpheus's /api/fleet/v1 - exercised over
    plain HTTP, since this environment has no way to stand up a real TLS server. The
    cert-pinning code path (`_pinned_adapter`) is therefore covered by its own unit tests
    below, not by an end-to-end HTTPS round trip through this fixture."""

    enroll_responses: list[tuple[int, dict]] = []
    heartbeat_response: tuple[int, dict] = (200, {"serverTime": "now", "directives": [], "heartbeatSeconds": 30})
    seen_requests: list[dict] = []

    def _reply(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler's naming convention
        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        self.__class__.seen_requests.append(
            {"path": self.path, "headers": dict(self.headers), "body": json.loads(raw) if raw else {}}
        )
        if self.path == "/api/fleet/v1/enroll":
            status, body = self.__class__.enroll_responses.pop(0)
            self._reply(status, body)
            return
        if "/heartbeat" in self.path:
            status, body = self.__class__.heartbeat_response
            self._reply(status, body)
            return
        self._reply(404, {"error": "not found"})

    def log_message(self, *args):  # silence stdout during tests
        pass


@pytest.fixture
def fake_server():
    _FakeFleetServer.enroll_responses = []
    _FakeFleetServer.seen_requests = []
    server = HTTPServer(("127.0.0.1", 0), _FakeFleetServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=2)


class TestEnroll:
    def test_stores_and_returns_the_identity(self, fake_server, tmp_path, monkeypatch):
        server, url = fake_server
        _FakeFleetServer.enroll_responses = [
            (201, {"clientId": "cl_test", "clientSecret": "cs_test", "profile": "gold", "serverTime": "now", "heartbeatSeconds": 30, "claimWaitSeconds": 25})
        ]
        identity = client.enroll(url, "me1_faketoken", profile="node", capabilities={"actions": []})
        assert identity.client_id == "cl_test"
        assert identity.client_secret == "cs_test"
        assert identity.server_url == url
        assert identity.pin_sha256 == ""  # plain http - no cert to pin

        reloaded = client.ClientIdentity.load()
        assert reloaded is not None
        assert reloaded.client_id == "cl_test"

    def test_sends_the_invite_token_as_a_bearer_and_the_documented_body_shape(self, fake_server):
        server, url = fake_server
        _FakeFleetServer.enroll_responses = [(201, {"clientId": "cl_x", "clientSecret": "cs_x"})]
        client.enroll(url, "me1_sometoken", profile="node", capabilities={"actions": ["git.clone"]})

        request = _FakeFleetServer.seen_requests[0]
        assert request["headers"]["authorization"] == "Bearer me1_sometoken"
        assert set(request["body"].keys()) == {"hostname", "os", "arch", "midasVersion", "capabilities", "publicKey"}
        assert request["body"]["capabilities"] == {"actions": ["git.clone"]}

    def test_raises_on_a_refused_invite(self, fake_server):
        server, url = fake_server
        _FakeFleetServer.enroll_responses = [(401, {"error": "invite expired"})]
        with pytest.raises(client.FleetError, match="invite expired"):
            client.enroll(url, "me1_expired", profile="node", capabilities={})

    def test_host_profile_refuses_a_non_loopback_url(self):
        with pytest.raises(client.FleetError, match="loopback"):
            client.enroll("https://morpheus.example.com", "me1_x", profile="host", capabilities={})

    def test_host_profile_accepts_a_loopback_url(self, fake_server):
        server, url = fake_server  # already 127.0.0.1
        _FakeFleetServer.enroll_responses = [(201, {"clientId": "cl_host", "clientSecret": "cs_host"})]
        identity = client.enroll(url, "me1_x", profile="host", capabilities={})
        assert identity.client_id == "cl_host"


class TestHeartbeat:
    def _identity(self, url: str) -> client.ClientIdentity:
        return client.ClientIdentity(server_url=url, client_id="cl_hb", client_secret="cs_hb", private_key_pem="", public_key_pem="")

    def test_returns_directives_on_success(self, fake_server):
        server, url = fake_server
        _FakeFleetServer.heartbeat_response = (200, {"serverTime": "now", "directives": [{"kind": "upgrade-kernel", "version": "1.2.3"}], "heartbeatSeconds": 30})
        result = client.heartbeat(self._identity(url), state="idle", capabilities={})
        assert result.ok
        assert result.directives == [{"kind": "upgrade-kernel", "version": "1.2.3"}]
        assert result.heartbeat_seconds == 30

    def test_sends_the_client_id_header_and_bearer_secret(self, fake_server):
        server, url = fake_server
        client.heartbeat(self._identity(url), state="idle", capabilities={})
        request = _FakeFleetServer.seen_requests[0]
        assert request["headers"]["authorization"] == "Bearer cs_hb"
        assert request["headers"]["x-midas-client"] == "cl_hb"

    def test_a_revoked_client_gets_a_quiet_result_not_an_exception(self, fake_server):
        server, url = fake_server
        _FakeFleetServer.heartbeat_response = (401, {"error": "client-revoked"})
        result = client.heartbeat(self._identity(url), state="idle", capabilities={})
        assert not result.ok
        assert result.error == "client-revoked-or-invalid"

    def test_a_quarantined_client_gets_423(self, fake_server):
        server, url = fake_server
        _FakeFleetServer.heartbeat_response = (423, {"error": "client-quarantined"})
        result = client.heartbeat(self._identity(url), state="idle", capabilities={})
        assert not result.ok
        assert result.error == "client-quarantined"

    def test_an_unreachable_server_returns_a_result_never_raises(self):
        identity = self._identity("http://127.0.0.1:1")  # nothing listens here
        result = client.heartbeat(identity, state="idle", capabilities={}, timeout=1)
        assert not result.ok
        assert result.error is not None


class TestClientIdentity:
    def test_round_trips_and_is_written_private(self, tmp_path):
        identity = client.ClientIdentity(server_url="http://x", client_id="cl_1", client_secret="cs_1", private_key_pem="priv", public_key_pem="pub")
        identity.save()

        from midas import paths
        mode = paths.fleet_client_file().stat().st_mode & 0o777
        assert mode == 0o600

        reloaded = client.ClientIdentity.load()
        assert reloaded == identity

    def test_load_returns_none_when_never_enrolled(self):
        assert client.ClientIdentity.load() is None

    def test_clear_removes_the_identity(self):
        client.ClientIdentity(server_url="x", client_id="y", client_secret="z", private_key_pem="", public_key_pem="").save()
        client.ClientIdentity.clear()
        assert client.ClientIdentity.load() is None
        client.ClientIdentity.clear()  # idempotent - no error on an already-clear state


class TestKeypairAndBackoff:
    def test_generates_a_distinct_ed25519_keypair_each_time(self):
        priv1, pub1 = client._generate_keypair()
        priv2, pub2 = client._generate_keypair()
        assert "BEGIN PRIVATE KEY" in priv1
        assert "BEGIN PUBLIC KEY" in pub1
        assert priv1 != priv2
        assert pub1 != pub2

    def test_backoff_is_bounded_and_within_the_exponential_ceiling(self):
        for attempt in range(6):
            delay = client.backoff_seconds(attempt, base=1.0, cap=30.0)
            assert 0 <= delay <= min(30.0, 2**attempt)


class TestPinnedAdapter:
    def test_normalizes_the_pin_and_sets_it_on_the_connection_bypassing_ca_verification(self):
        adapter = client._pinned_adapter("AA:BB:CC")

        class FakeConn:
            assert_fingerprint = None

        conn = FakeConn()
        # cert_verify's superclass implementation only inspects `verify` for CA-bundle-path
        # logic when verify is truthy; passing False (what our override always does) short
        # -circuits that entirely, so this is safe to call directly without a live socket.
        adapter.cert_verify(conn, "https://example.com", verify=True, cert=None)
        assert conn.assert_fingerprint == "AABBCC"
