import base64
import hashlib
import json
import tarfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from midas import config as config_mod
from midas.cli import main
from midas.config import Config
from midas.fleet.manifest import ManifestItem, canonical_payload


@pytest.fixture(autouse=True)
def a_saved_config(tmp_path):
    cfg = Config()
    cfg.me.jira_email = "dev@example.com"
    cfg.paths.workspace_root = str(tmp_path / "workspace")
    config_mod.save(cfg)


def _keypair():
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private_key, public_pem


def _blob(text: str):
    data = text.encode()
    return data, hashlib.sha256(data).hexdigest()


class _FakeMorpheus(BaseHTTPRequestHandler):
    private_key = None
    public_pem = ""
    manifest_json: dict = {}
    blobs: dict[str, bytes] = {}
    patches_json: dict = {"patches": []}

    def _reply(self, status, body, raw=False):
        payload = body if raw else json.dumps(body).encode()
        self.send_response(status)
        if not raw:
            self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", 0))
        self.rfile.read(length) if length else None
        if self.path == "/api/fleet/v1/enroll":
            self._reply(201, {"clientId": "cl_x", "clientSecret": "cs_x", "profile": "gold", "publicKeyPem": self.__class__.public_pem})
            return
        self._reply(404, {"error": "not found"})

    def do_GET(self):  # noqa: N802
        if self.path == "/api/fleet/v1/harness/profiles/gold/manifest":
            self._reply(200, self.__class__.manifest_json)
            return
        if self.path.startswith("/api/fleet/v1/harness/blobs/"):
            sha = self.path.rsplit("/", 1)[-1]
            body = self.__class__.blobs.get(sha)
            if body is None:
                self._reply(404, b"", raw=True)
                return
            self._reply(200, body, raw=True)
            return
        if self.path.startswith("/api/fleet/v1/harness/profiles/gold/patches"):
            self._reply(200, self.__class__.patches_json)
            return
        self._reply(404, {"error": "not found"})

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_morpheus():
    private_key, public_pem = _keypair()
    _FakeMorpheus.private_key = private_key
    _FakeMorpheus.public_pem = public_pem
    _FakeMorpheus.manifest_json = {}
    _FakeMorpheus.blobs = {}
    _FakeMorpheus.patches_json = {"patches": []}
    server = HTTPServer(("127.0.0.1", 0), _FakeMorpheus)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", private_key, public_pem
    server.shutdown()
    thread.join(timeout=2)


def _sign(private_key, version, profile, items):
    payload = canonical_payload(version, profile, [ManifestItem(**i) for i in items])
    return base64.b64encode(private_key.sign(payload)).decode()


class TestInstallFromServer:
    def test_installs_after_enroll_using_the_enrolled_profile(self, fake_morpheus, tmp_path):
        url, private_key, _ = fake_morpheus
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = {"version": "v1", "profile": "gold", "items": items, "signature": _sign(private_key, "v1", "gold", items)}
        _FakeMorpheus.blobs = {sha: data}

        runner = CliRunner()
        runner.invoke(main, ["enroll", url, "me1_x"])
        root = tmp_path / "home"
        result = runner.invoke(main, ["install", "--root", str(root)])

        assert result.exit_code == 0, result.output
        assert "applied   : 1" in result.output
        assert (root / ".claude" / "rules" / "foo.mdc").read_text() == "content\n"

    def test_fails_cleanly_when_not_enrolled_and_no_from_bundle(self):
        runner = CliRunner()
        result = runner.invoke(main, ["install"])
        assert result.exit_code != 0
        assert "not enrolled" in result.output


class TestInstallFromBundle:
    def _bundle(self, tmp_path, private_key, items, blobs):
        payload = canonical_payload("v1", "gold", [ManifestItem(**i) for i in items])
        signature = base64.b64encode(private_key.sign(payload)).decode()
        manifest = {"version": "v1", "profile": "gold", "items": items, "signature": signature}
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "manifest.json").write_text(json.dumps(manifest))
        (staging / "blobs").mkdir()
        for sha, data in blobs.items():
            (staging / "blobs" / sha).write_bytes(data)
        archive = tmp_path / "bundle.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(staging / "manifest.json", arcname="manifest.json")
            tar.add(staging / "blobs", arcname="blobs")
        return archive

    def test_installs_from_a_local_bundle_with_a_public_key(self, tmp_path):
        private_key, public_pem = _keypair()
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        archive = self._bundle(tmp_path, private_key, items, {sha: data})
        keyfile = tmp_path / "server.pub"
        keyfile.write_text(public_pem)

        runner = CliRunner()
        root = tmp_path / "home"
        result = runner.invoke(main, ["install", "--from", str(archive), "--public-key", str(keyfile), "--root", str(root)])
        assert result.exit_code == 0, result.output
        assert (root / ".claude" / "rules" / "foo.mdc").read_text() == "content\n"

    def test_refuses_a_bundle_without_a_public_key_and_no_no_verify(self, tmp_path):
        private_key, _ = _keypair()
        archive = self._bundle(tmp_path, private_key, [], {})
        runner = CliRunner()
        result = runner.invoke(main, ["install", "--from", str(archive)])
        assert result.exit_code != 0


class TestHarnessShow:
    def test_fails_cleanly_before_any_install(self, fake_morpheus):
        url, _, _ = fake_morpheus
        runner = CliRunner()
        runner.invoke(main, ["enroll", url, "me1_x"])
        result = runner.invoke(main, ["harness", "show", "abc..def"])
        assert result.exit_code != 0
        assert "never run" in result.output

    def test_shows_a_patch_after_installing(self, fake_morpheus, tmp_path):
        url, private_key, _ = fake_morpheus
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = {"version": "v1", "profile": "gold", "items": items, "signature": _sign(private_key, "v1", "gold", items)}
        _FakeMorpheus.blobs = {sha: data}
        _FakeMorpheus.patches_json = {
            "patches": [
                {
                    "patchId": "abc..def",
                    "fromVersion": "v1",
                    "toVersion": "v2",
                    "publishedAt": "2026-01-01T00:00:00.000Z",
                    "note": "added a rule",
                    "items": [{"kind": "rule", "id": "bar.mdc", "change": "added", "mandatory": False}],
                    "mandatoryCount": 0,
                    "totalCount": 1,
                    "bytes": 10,
                }
            ]
        }

        runner = CliRunner()
        runner.invoke(main, ["enroll", url, "me1_x"])
        runner.invoke(main, ["install", "--root", str(tmp_path / "home")])
        result = runner.invoke(main, ["harness", "show", "abc..def"])
        assert result.exit_code == 0, result.output
        assert "added a rule" in result.output
        assert "bar.mdc" in result.output


class TestTouchDeprecationNotice:
    def test_shows_no_notice_when_not_enrolled(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, ["touch", "--dry-run", "--no-mcp", "--root", str(tmp_path / "home")])
        assert "midas install" not in result.output

    def test_shows_a_notice_when_enrolled(self, fake_morpheus, tmp_path):
        url, _, _ = fake_morpheus
        runner = CliRunner()
        runner.invoke(main, ["enroll", url, "me1_x"])
        result = runner.invoke(main, ["touch", "--dry-run", "--no-mcp", "--root", str(tmp_path / "home")])
        assert "midas install" in result.output
