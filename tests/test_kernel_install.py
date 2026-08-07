"""B1: fetch, verify and install a signed kernel release.

Before this, `upgrade-kernel` logged a line telling the operator to run `midas kernel install` —
a command that did not exist — while any assignment needing that version nacked forever.

The signature check has to reproduce, byte for byte, what morpheus's `scripts/bundle-kernel.mjs`
signed: the literal contents of `MANIFEST.sha256`, i.e. `JSON.stringify(manifest, null, 2) + "\n"`.
These tests build a release with a real ed25519 key so a canonicalisation drift fails here rather
than in the field.
"""

import base64
import hashlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from midas import kernel


@pytest.fixture
def kernels(tmp_path, monkeypatch):
    root = tmp_path / "kernels"
    monkeypatch.setattr(kernel.paths, "kernel_dir", lambda: root)
    return root


@pytest.fixture
def signer():
    key = Ed25519PrivateKey.generate()
    pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return key, pem


def make_release(key, *, version="0.3.0", body=b"console.log('kernel')\n", tamper_manifest=False):
    manifest = {
        "version": version,
        "file": kernel.BUNDLE_NAME,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "builtAt": "2026-08-07T00:00:00.000Z",
    }
    # Exactly what bundle-kernel.mjs writes to MANIFEST.sha256 and signs.
    signed_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    signature = base64.b64encode(key.sign(signed_bytes)).decode()
    if tamper_manifest:
        manifest = {**manifest, "bytes": len(body) + 1}
    return {
        "version": version,
        "manifest": manifest,
        "signature": signature,
        "bundleBase64": base64.b64encode(body).decode(),
    }


class TestVerify:
    def test_a_genuine_release_verifies(self, signer):
        key, pem = signer
        kernel.verify_release(make_release(key), pem)  # must not raise

    def test_a_tampered_manifest_is_refused(self, signer):
        key, pem = signer
        with pytest.raises(kernel.KernelSignatureError):
            kernel.verify_release(make_release(key, tamper_manifest=True), pem)

    def test_a_swapped_bundle_is_refused(self, signer):
        key, pem = signer
        release = make_release(key)
        release["bundleBase64"] = base64.b64encode(b"malicious()\n").decode()
        with pytest.raises(kernel.KernelSignatureError, match="does not match the signed manifest"):
            kernel.verify_release(release, pem)

    def test_another_key_cannot_sign_a_release(self, signer):
        _, pem = signer
        attacker = Ed25519PrivateKey.generate()
        with pytest.raises(kernel.KernelSignatureError):
            kernel.verify_release(make_release(attacker), pem)

    def test_a_release_missing_its_signature_is_refused(self, signer):
        key, pem = signer
        release = make_release(key)
        del release["signature"]
        with pytest.raises(kernel.KernelSignatureError):
            kernel.verify_release(release, pem)


class TestInstallRelease:
    def test_installs_and_activates(self, kernels, signer):
        key, pem = signer
        assert kernel.install_release(make_release(key), pem) == "0.3.0"
        assert kernel.installed_versions() == ["0.3.0"]
        assert kernel.active_version() == "0.3.0"
        assert kernel.verify("0.3.0") == []

    def test_a_bad_release_writes_nothing(self, kernels, signer):
        key, pem = signer
        with pytest.raises(kernel.KernelSignatureError):
            kernel.install_release(make_release(key, tamper_manifest=True), pem)
        # Verification runs before any write, so there is no half-installed version to clean up.
        assert kernel.installed_versions() == []

    def test_install_refuses_a_signed_bundle_smuggled_past_verification(self, kernels):
        with pytest.raises(kernel.KernelError, match="install_release"):
            kernel.install("0.3.0", {kernel.BUNDLE_NAME: b"x"}, signature=b"sig", pubkey=b"key")
