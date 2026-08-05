import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from midas.fleet.manifest import ManifestItem, ManifestResponse, canonical_payload, verify_manifest


class TestCanonicalPayload:
    def test_matches_morpheus_s_canonicalpayload_byte_for_byte(self):
        # Fixture hand-verified against packages/harness/src/manifest.ts's canonicalPayload:
        # sorted-by-path items, compact JSON, key order version/profile/items/deletions.
        items = [
            ManifestItem(path="b.md", kind="skill", sha256="aaa", size=1, mode="644"),
            ManifestItem(path="a.md", kind="rule", sha256="bbb", size=2, mode="644"),
        ]
        payload = canonical_payload("v1", "gold", items, deletions=["z.md", "a.md"])
        expected = (
            b'{"version":"v1","profile":"gold","items":'
            b'[{"path":"a.md","kind":"rule","sha256":"bbb","size":2,"mode":"644"},'
            b'{"path":"b.md","kind":"skill","sha256":"aaa","size":1,"mode":"644"}],'
            b'"deletions":["a.md","z.md"]}'
        )
        assert payload == expected

    def test_omits_deletions_key_entirely_when_not_given(self):
        items = [ManifestItem(path="a.md", kind="rule", sha256="bbb", size=2, mode="644")]
        payload = canonical_payload("v1", "gold", items)
        assert b"deletions" not in payload

    def test_item_order_in_the_input_list_does_not_affect_the_payload(self):
        a = ManifestItem(path="a.md", kind="rule", sha256="bbb", size=2, mode="644")
        b = ManifestItem(path="b.md", kind="skill", sha256="aaa", size=1, mode="644")
        assert canonical_payload("v1", "gold", [a, b]) == canonical_payload("v1", "gold", [b, a])


class TestVerifyManifest:
    def _keypair(self):
        private_key = Ed25519PrivateKey.generate()
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        return private_key, public_pem

    def _sign(self, private_key, manifest: ManifestResponse) -> str:
        payload = canonical_payload(manifest.version, manifest.profile, manifest.items, manifest.deletions)
        return base64.b64encode(private_key.sign(payload)).decode()

    def test_accepts_a_correctly_signed_manifest(self):
        private_key, public_pem = self._keypair()
        manifest = ManifestResponse(
            version="v1", profile="gold", items=[ManifestItem(path="a.md", kind="rule", sha256="bbb", size=2, mode="644")], signature=""
        )
        manifest.signature = self._sign(private_key, manifest)
        assert verify_manifest(manifest, public_pem) is True

    def test_rejects_a_manifest_whose_content_was_tampered_with_after_signing(self):
        private_key, public_pem = self._keypair()
        manifest = ManifestResponse(
            version="v1", profile="gold", items=[ManifestItem(path="a.md", kind="rule", sha256="bbb", size=2, mode="644")], signature=""
        )
        manifest.signature = self._sign(private_key, manifest)
        manifest.items[0].sha256 = "tampered"
        assert verify_manifest(manifest, public_pem) is False

    def test_rejects_a_manifest_signed_by_a_different_key(self):
        _, public_pem = self._keypair()
        other_private_key, _ = self._keypair()
        manifest = ManifestResponse(
            version="v1", profile="gold", items=[ManifestItem(path="a.md", kind="rule", sha256="bbb", size=2, mode="644")], signature=""
        )
        manifest.signature = self._sign(other_private_key, manifest)
        assert verify_manifest(manifest, public_pem) is False


class TestManifestResponseFromJson:
    def test_round_trips_the_documented_wire_shape(self):
        data = {
            "version": "v1",
            "profile": "gold",
            "items": [{"path": "a.md", "kind": "rule", "sha256": "bbb", "size": 2, "mode": "644"}],
            "deletions": ["z.md"],
            "signature": "sig",
        }
        manifest = ManifestResponse.from_json(data)
        assert manifest.version == "v1"
        assert manifest.items[0].path == "a.md"
        assert manifest.deletions == ["z.md"]

    def test_deletions_defaults_to_none_when_absent(self):
        data = {"version": "v1", "profile": "gold", "items": [], "signature": "sig"}
        assert ManifestResponse.from_json(data).deletions is None
