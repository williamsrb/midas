import base64
import hashlib
import json
import tarfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from midas.fleet import sync
from midas.fleet.manifest import ManifestItem, ManifestVerificationError, canonical_payload


def _keypair():
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private_key, public_pem


def _make_bundle(tmp_path, private_key, version, profile, blobs: dict[str, bytes], items: list[dict]):
    """Builds a tarball matching morpheus's `exportManifestBundle` format exactly:
    manifest.json + blobs/<sha256> at the tar root."""
    item_objs = [ManifestItem(**item) for item in items]
    payload = canonical_payload(version, profile, item_objs)
    signature = base64.b64encode(private_key.sign(payload)).decode() if private_key else "unsigned"
    manifest = {"version": version, "profile": profile, "items": items, "signature": signature}

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


class TestSyncFromBundle:
    def test_installs_from_a_signed_bundle(self, tmp_path):
        private_key, public_pem = _keypair()
        data = b"some rule content\n"
        sha = hashlib.sha256(data).hexdigest()
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        archive = _make_bundle(tmp_path, private_key, "v1", "gold", {sha: data}, items)

        root = tmp_path / "home"
        result = sync.sync_from_bundle(archive, "gold", public_key_pem=public_pem, root=root)

        assert result.applied == ["rule:foo.mdc"]
        assert (root / ".claude" / "rules" / "foo.mdc").read_text() == "some rule content\n"

    def test_refuses_a_bundle_with_a_bad_signature(self, tmp_path):
        private_key, public_pem = _keypair()
        other_key, _ = _keypair()
        data = b"content\n"
        sha = hashlib.sha256(data).hexdigest()
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        archive = _make_bundle(tmp_path, other_key, "v1", "gold", {sha: data}, items)  # signed by the wrong key

        with pytest.raises(ManifestVerificationError):
            sync.sync_from_bundle(archive, "gold", public_key_pem=public_pem, root=tmp_path / "home")

    def test_refuses_without_a_public_key_by_default(self, tmp_path):
        private_key, _ = _keypair()
        archive = _make_bundle(tmp_path, private_key, "v1", "gold", {}, [])

        with pytest.raises(sync.SyncError):
            sync.sync_from_bundle(archive, "gold", root=tmp_path / "home")

    def test_allows_explicitly_unverified_install(self, tmp_path):
        private_key, _ = _keypair()
        data = b"content\n"
        sha = hashlib.sha256(data).hexdigest()
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        archive = _make_bundle(tmp_path, private_key, "v1", "gold", {sha: data}, items)

        result = sync.sync_from_bundle(archive, "gold", root=tmp_path / "home", require_signature=False)
        assert result.applied == ["rule:foo.mdc"]

    def test_refuses_a_bundle_whose_blob_fails_hash_verification(self, tmp_path):
        private_key, public_pem = _keypair()
        data = b"content\n"
        sha = hashlib.sha256(data).hexdigest()
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": len(data), "mode": "644"}]
        archive = _make_bundle(tmp_path, private_key, "v1", "gold", {sha: b"tampered"}, items)

        with pytest.raises(sync.SyncError):
            sync.sync_from_bundle(archive, "gold", public_key_pem=public_pem, root=tmp_path / "home")

    def test_refuses_a_missing_blob(self, tmp_path):
        private_key, public_pem = _keypair()
        sha = hashlib.sha256(b"content\n").hexdigest()
        items = [{"path": "rules/foo.mdc", "kind": "rule", "sha256": sha, "size": 8, "mode": "644"}]
        archive = _make_bundle(tmp_path, private_key, "v1", "gold", {}, items)  # blob not included

        with pytest.raises(sync.SyncError):
            sync.sync_from_bundle(archive, "gold", public_key_pem=public_pem, root=tmp_path / "home")

    def test_rejects_a_tarball_with_no_manifest(self, tmp_path):
        archive = tmp_path / "empty.tar.gz"
        with tarfile.open(archive, "w:gz"):
            pass
        with pytest.raises(sync.SyncError):
            sync.sync_from_bundle(archive, "gold", require_signature=False, root=tmp_path / "home")
