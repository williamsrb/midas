import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from click.testing import CliRunner

from midas import config as config_mod, paths
from midas.cli import main
from midas.config import Config
from midas.fleet.client import ClientIdentity


@pytest.fixture(autouse=True)
def a_saved_config(tmp_path):
    """`enroll`/`fleet status`/`fleet ping` all load a config from disk, same as every other
    command in this CLI - `midas setup` normally creates it; here a minimal one is enough."""
    cfg = Config()
    cfg.me.jira_email = "dev@example.com"
    cfg.paths.workspace_root = str(tmp_path / "workspace")
    config_mod.save(cfg)


class _FakeFleetServer(BaseHTTPRequestHandler):
    enroll_response: tuple[int, dict] = (201, {"clientId": "cl_cli", "clientSecret": "cs_cli"})
    heartbeat_response: tuple[int, dict] = (200, {"serverTime": "now", "directives": [], "heartbeatSeconds": 30})

    def _reply(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        self.rfile.read(length) if length else None
        if self.path == "/api/fleet/v1/enroll":
            self._reply(*self.__class__.enroll_response)
            return
        if "/heartbeat" in self.path:
            self._reply(*self.__class__.heartbeat_response)
            return
        self._reply(404, {"error": "not found"})

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_server():
    _FakeFleetServer.enroll_response = (201, {"clientId": "cl_cli", "clientSecret": "cs_cli"})
    _FakeFleetServer.heartbeat_response = (200, {"serverTime": "now", "directives": [], "heartbeatSeconds": 30})
    server = HTTPServer(("127.0.0.1", 0), _FakeFleetServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=2)


def test_enroll_writes_policy_and_identity(fake_server):
    runner = CliRunner()
    result = runner.invoke(main, ["enroll", fake_server, "me1_faketoken", "--label", "test-box"])
    assert result.exit_code == 0, result.output
    assert "Enrolled as cl_cli" in result.output
    assert paths.policy_file().is_file()
    assert ClientIdentity.load().client_id == "cl_cli"


def test_enroll_does_not_overwrite_an_existing_policy(fake_server):
    from midas import policy

    policy.write_default("node", workspace_root="/custom/root")
    runner = CliRunner()
    runner.invoke(main, ["enroll", fake_server, "me1_faketoken"])
    assert policy.load().workspace_roots == ["/custom/root"]


def test_label_host_refuses_a_non_loopback_url():
    runner = CliRunner()
    result = runner.invoke(main, ["enroll", "https://morpheus.example.com", "me1_x", "--label", "host"])
    assert result.exit_code != 0
    assert "loopback" in result.output


def test_label_host_against_a_loopback_url_succeeds_and_writes_the_host_policy_profile(fake_server):
    from midas import policy

    runner = CliRunner()
    # fake_server binds 127.0.0.1 - matches the installer's own worked example exactly
    # (`midas enroll ... --label host --profile gold`).
    result = runner.invoke(main, ["enroll", fake_server, "me1_faketoken", "--label", "host", "--profile", "gold"])
    assert result.exit_code == 0, result.output
    assert policy.load().permission_ceiling == "full"  # the host profile's shipped default


def test_enroll_refused_invite_fails_cleanly(fake_server):
    _FakeFleetServer.enroll_response = (401, {"error": "invite expired"})
    runner = CliRunner()
    result = runner.invoke(main, ["enroll", fake_server, "me1_expired"])
    assert result.exit_code != 0
    assert "invite expired" in result.output


def test_fleet_status_when_not_enrolled():
    runner = CliRunner()
    result = runner.invoke(main, ["fleet", "status"])
    assert result.exit_code == 0
    assert "not enrolled" in result.output


def test_fleet_status_after_enrolling_reports_all_three_axes(fake_server):
    runner = CliRunner()
    runner.invoke(main, ["enroll", fake_server, "me1_faketoken"])
    result = runner.invoke(main, ["fleet", "status"])
    assert result.exit_code == 0
    assert "connectivity : online" in result.output
    assert "harness      :" in result.output
    assert "reconciled   : n/a" in result.output


def test_fleet_ping_reachable(fake_server):
    runner = CliRunner()
    runner.invoke(main, ["enroll", fake_server, "me1_faketoken"])
    result = runner.invoke(main, ["fleet", "ping"])
    assert result.exit_code == 0
    assert "ok -" in result.output


def test_fleet_ping_unreachable_fails():
    runner = CliRunner()
    server = HTTPServer(("127.0.0.1", 0), _FakeFleetServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        runner.invoke(main, ["enroll", url, "me1_faketoken"])
    finally:
        server.shutdown()
        thread.join(timeout=2)

    result = runner.invoke(main, ["fleet", "ping"])
    assert result.exit_code != 0
    assert "unreachable" in result.output


def test_unsubscribe_when_not_enrolled():
    runner = CliRunner()
    result = runner.invoke(main, ["unsubscribe"])
    assert result.exit_code == 0
    assert "not enrolled" in result.output


def test_unsubscribe_clears_the_identity(fake_server):
    runner = CliRunner()
    runner.invoke(main, ["enroll", fake_server, "me1_faketoken"])
    assert ClientIdentity.load() is not None
    result = runner.invoke(main, ["unsubscribe"])
    assert result.exit_code == 0
    assert ClientIdentity.load() is None
