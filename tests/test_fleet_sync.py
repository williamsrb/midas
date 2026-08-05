import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from midas.fleet import sync
from midas.fleet.client import ClientIdentity
from midas.fleet.manifest import ManifestItem, ManifestVerificationError, canonical_payload


class _FakeMorpheus(BaseHTTPRequestHandler):
    manifest_json: dict = {}
    blobs: dict[str, bytes] = {}

    def do_GET(self):  # noqa: N802
        if self.path == "/api/fleet/v1/harness/profiles/gold/manifest":
            payload = json.dumps(self.__class__.manifest_json).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/api/fleet/v1/harness/blobs/"):
            sha = self.path.rsplit("/", 1)[-1]
            body = self.__class__.blobs.get(sha)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/fleet/v1/harness/profiles/missing/manifest":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_morpheus():
    _FakeMorpheus.manifest_json = {}
    _FakeMorpheus.blobs = {}
    server = HTTPServer(("127.0.0.1", 0), _FakeMorpheus)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=2)


def _keypair():
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private_key, public_pem


def _blob(text: str) -> tuple[bytes, str]:
    data = text.encode()
    return data, hashlib.sha256(data).hexdigest()


def _signed_manifest(private_key, version, profile, items, deletions=None):
    item_objs = [ManifestItem(**item) for item in items]
    payload = canonical_payload(version, profile, item_objs, deletions)
    import base64

    signature = base64.b64encode(private_key.sign(payload)).decode()
    manifest = {"version": version, "profile": profile, "items": items, "signature": signature}
    if deletions is not None:
        manifest["deletions"] = deletions
    return manifest


def _identity(url, public_pem):
    return ClientIdentity(
        server_url=url,
        client_id="cl_test",
        client_secret="cs_test",
        private_key_pem="",
        public_key_pem="",
        server_public_key_pem=public_pem,
    )


class TestSyncFromMorpheus:
    def test_projects_a_single_file_rule_item(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        data, sha = _blob("some rule content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        _FakeMorpheus.blobs = {sha: data}

        root = tmp_path / "home"
        identity = _identity(fake_morpheus, public_pem)
        result = sync.sync_from_morpheus(identity, "gold", root=root)

        assert result.version == "v1"
        assert result.applied == ["rule:foo.mdc"]
        assert (root / ".claude" / "rules" / "foo.mdc").read_text() == "some rule content\n"
        assert (root / ".cursor" / "rules" / "foo.mdc").read_text() == "some rule content\n"

    def test_projects_a_multi_file_skill(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        skill_data, skill_sha = _blob("# skill\n")
        script_data, script_sha = _blob("print(1)\n")
        items = [
            {"path": "skills/plan/SKILL.md", "kind": "skill", "sha256": skill_sha, "size": len(skill_data), "mode": "644"},
            {"path": "skills/plan/scripts/run.py", "kind": "skill", "sha256": script_sha, "size": len(script_data), "mode": "644"},
        ]
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        _FakeMorpheus.blobs = {skill_sha: skill_data, script_sha: script_data}

        root = tmp_path / "home"
        result = sync.sync_from_morpheus(_identity(fake_morpheus, public_pem), "gold", root=root)

        assert result.applied == ["skill:plan"]
        assert (root / ".claude" / "skills" / "plan" / "SKILL.md").read_text() == "# skill\n"
        assert (root / ".claude" / "skills" / "plan" / "scripts" / "run.py").read_text() == "print(1)\n"

    def test_second_sync_with_no_changes_reports_unchanged_and_writes_nothing_again(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        _FakeMorpheus.blobs = {sha: data}
        identity = _identity(fake_morpheus, public_pem)
        root = tmp_path / "home"

        sync.sync_from_morpheus(identity, "gold", root=root)
        second = sync.sync_from_morpheus(identity, "gold", root=root)

        assert second.applied == []
        assert second.unchanged == ["rule:foo.mdc"]

    def test_a_removed_item_is_reported_as_removed(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        _FakeMorpheus.blobs = {sha: data}
        identity = _identity(fake_morpheus, public_pem)
        root = tmp_path / "home"
        sync.sync_from_morpheus(identity, "gold", root=root)

        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v2", "gold", [])
        result = sync.sync_from_morpheus(identity, "gold", root=root)
        assert result.removed == ["rule:foo.mdc"]

    def test_dry_run_writes_nothing(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        _FakeMorpheus.blobs = {sha: data}
        root = tmp_path / "home"

        result = sync.sync_from_morpheus(_identity(fake_morpheus, public_pem), "gold", root=root, dry_run=True)
        assert result.applied == ["rule:foo.mdc"]
        assert not (root / ".claude" / "rules" / "foo.mdc").exists()

    def test_mcp_and_cli_items_are_recorded_but_not_projected(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        data, sha = _blob('{"servers":{}}')
        items = [{"path": "mcp/mcp.template.json", "kind": "mcp", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        _FakeMorpheus.blobs = {sha: data}
        root = tmp_path / "home"

        result = sync.sync_from_morpheus(_identity(fake_morpheus, public_pem), "gold", root=root)
        assert result.applied == []  # not auto-projected
        assert not any(root.rglob("mcp.template.json"))

    def test_refuses_a_manifest_with_a_bad_signature(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        other_key, _ = _keypair()
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = _signed_manifest(other_key, "v1", "gold", items)  # signed by the WRONG key
        _FakeMorpheus.blobs = {sha: data}

        with pytest.raises(ManifestVerificationError):
            sync.sync_from_morpheus(_identity(fake_morpheus, public_pem), "gold", root=tmp_path / "home")

    def test_refuses_to_sync_without_a_recorded_server_public_key_by_default(self, fake_morpheus, tmp_path):
        private_key, _ = _keypair()
        items = []
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        identity = _identity(fake_morpheus, "")

        with pytest.raises(sync.SyncError):
            sync.sync_from_morpheus(identity, "gold", root=tmp_path / "home")

    def test_refuses_a_blob_that_fails_hash_verification(self, fake_morpheus, tmp_path):
        private_key, public_pem = _keypair()
        data, sha = _blob("content\n")
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        _FakeMorpheus.manifest_json = _signed_manifest(private_key, "v1", "gold", items)
        _FakeMorpheus.blobs = {sha: b"tampered bytes"}  # doesn't hash to `sha`

        with pytest.raises(sync.SyncError):
            sync.sync_from_morpheus(_identity(fake_morpheus, public_pem), "gold", root=tmp_path / "home")

    def test_unknown_profile_raises(self, fake_morpheus, tmp_path):
        with pytest.raises(sync.SyncError):
            sync.sync_from_morpheus(_identity(fake_morpheus, "x"), "missing", root=tmp_path / "home")


class TestItemIdentity:
    def test_groups_skill_files_by_their_top_level_directory(self):
        from midas.fleet.manifest import ManifestItem

        a = sync._item_identity(ManifestItem(path="skills/plan/SKILL.md", kind="skill", sha256="x", size=1, mode="644"))
        b = sync._item_identity(ManifestItem(path="skills/plan/scripts/run.py", kind="skill", sha256="y", size=1, mode="644"))
        assert a == b == "skill:plan"

    def test_treats_every_other_kind_as_one_file_deep(self):
        from midas.fleet.manifest import ManifestItem

        item = sync._item_identity(ManifestItem(path="kb/implementation/foo.md", kind="kb", sha256="x", size=1, mode="644"))
        assert item == "kb:implementation/foo.md"
