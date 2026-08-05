import json
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from midas.fleet.client import ClientIdentity
from midas.fleet.lease import LeaseRenewer, _seconds_until


class _FakeRenewServer(BaseHTTPRequestHandler):
    responses: list[tuple[int, dict]] = []
    seen: list[str] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        self.rfile.read(length) if length else None
        self.__class__.seen.append(self.path)
        status, body = self.__class__.responses.pop(0) if self.__class__.responses else (200, {"leaseUntil": _future(60)})
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def _future(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


@pytest.fixture
def fake_server():
    _FakeRenewServer.responses = []
    _FakeRenewServer.seen = []
    server = HTTPServer(("127.0.0.1", 0), _FakeRenewServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=2)


def _identity(url):
    return ClientIdentity(server_url=url, client_id="cl_test", client_secret="cs_test", private_key_pem="", public_key_pem="")


class TestSecondsUntil:
    def test_positive_for_a_future_deadline(self):
        assert _seconds_until(_future(60)) > 50

    def test_negative_for_a_past_deadline(self):
        assert _seconds_until(_future(-60)) < 0


class TestLeaseRenewer:
    def test_renews_before_a_short_lease_expires(self, fake_server):
        _FakeRenewServer.responses = [(200, {"leaseUntil": _future(60)})]
        renewer = LeaseRenewer(_identity(fake_server), "as_1", _future(0.3)).start()
        time.sleep(0.6)
        renewer.stop()
        assert len(_FakeRenewServer.seen) >= 1
        assert not renewer.lease_lost

    def test_lease_lost_sets_the_flag_and_calls_the_callback_once(self, fake_server):
        _FakeRenewServer.responses = [(409, {"error": "lease-lost"})]
        called = []
        renewer = LeaseRenewer(_identity(fake_server), "as_1", _future(0.2), on_lease_lost=lambda: called.append(1)).start()
        time.sleep(0.6)
        renewer.stop()
        assert renewer.lease_lost is True
        assert called == [1]

    def test_stops_renewing_after_lease_lost(self, fake_server):
        _FakeRenewServer.responses = [(409, {"error": "lease-lost"})]
        renewer = LeaseRenewer(_identity(fake_server), "as_1", _future(0.2)).start()
        time.sleep(0.6)
        seen_after_loss = len(_FakeRenewServer.seen)
        time.sleep(0.5)
        renewer.stop()
        assert len(_FakeRenewServer.seen) == seen_after_loss  # no further renew attempts

    def test_a_transient_network_failure_does_not_set_lease_lost(self, fake_server):
        _FakeRenewServer.responses = [(500, {"error": "internal"}), (200, {"leaseUntil": _future(60)})]
        renewer = LeaseRenewer(_identity(fake_server), "as_1", _future(0.2)).start()
        time.sleep(1.2)
        renewer.stop()
        assert renewer.lease_lost is False
        assert len(_FakeRenewServer.seen) >= 2

    def test_stop_joins_the_thread_and_no_more_renewals_happen(self, fake_server):
        _FakeRenewServer.responses = [(200, {"leaseUntil": _future(60)})]
        renewer = LeaseRenewer(_identity(fake_server), "as_1", _future(60)).start()
        renewer.stop()
        count_at_stop = len(_FakeRenewServer.seen)
        time.sleep(0.3)
        assert len(_FakeRenewServer.seen) == count_at_stop
