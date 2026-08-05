"""Wire-contract mirror for morpheus's harness manifest/patch shapes (spec §3.1-3.2, S3b).

There is no codegen pipeline from `@morpheus/fleet-contract`'s Zod schemas to Python, so these
dataclasses are hand-written and must be kept in sync by hand with
`morpheus/packages/fleet-contract/src/harness.ts`. `canonical_payload()` in particular must stay
byte-for-byte identical to morpheus's `canonicalPayload()` in `packages/harness/src/manifest.ts` -
it is the exact input the server's ed25519 signature covers, so any drift (key order, whitespace,
field presence) makes every signature fail to verify even though the content is correct.

Verification is only ever run against a full manifest fetch (no `?since=`), never a `since=`-
diffed response - the server's signature always covers the full item list at publish time, so a
diffed response's `items`/`deletions` cannot be reconstructed back into the payload that
signature was computed over. `since=` stays available as a future bandwidth optimization once
morpheus is taught to sign diff responses separately; today it would just fail verification.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# The nine kinds a harness item can be (spec §4.5b, D16) - mirrors HarnessItemKindSchema.
HARNESS_ITEM_KINDS = ("skill", "rule", "hook", "agent", "command", "kb", "quality-gate", "mcp", "cli")


@dataclass
class ManifestItem:
    path: str
    kind: str
    sha256: str
    size: int
    mode: str


@dataclass
class ManifestResponse:
    version: str
    profile: str
    items: list[ManifestItem]
    signature: str
    deletions: list[str] | None = None

    @classmethod
    def from_json(cls, data: dict) -> "ManifestResponse":
        return cls(
            version=str(data["version"]),
            profile=str(data["profile"]),
            items=[ManifestItem(**item) for item in data["items"]],
            signature=str(data["signature"]),
            deletions=list(data["deletions"]) if data.get("deletions") is not None else None,
        )


@dataclass
class PatchItem:
    kind: str
    id: str
    change: str  # added | updated | removed
    mandatory: bool
    sha256: str | None = None
    size: int | None = None
    external: bool | None = None


@dataclass
class Patch:
    patch_id: str
    from_version: str
    to_version: str
    published_at: str
    note: str
    items: list[PatchItem]
    mandatory_count: int
    total_count: int
    bytes: int

    @classmethod
    def from_json(cls, data: dict) -> "Patch":
        return cls(
            patch_id=str(data["patchId"]),
            from_version=str(data["fromVersion"]),
            to_version=str(data["toVersion"]),
            published_at=str(data["publishedAt"]),
            note=str(data["note"]),
            items=[PatchItem(**item) for item in data["items"]],
            mandatory_count=int(data["mandatoryCount"]),
            total_count=int(data["totalCount"]),
            bytes=int(data["bytes"]),
        )


class ManifestVerificationError(Exception):
    """A manifest's signature does not match its own content - never install from it."""


def _item_sort_key(item: ManifestItem) -> str:
    return item.path


def canonical_payload(version: str, profile: str, items: list[ManifestItem], deletions: list[str] | None = None) -> bytes:
    """Byte-for-byte mirror of morpheus's `canonicalPayload` (manifest.ts). Compact JSON (no
    whitespace), sorted items by path, and `deletions` present only when the caller passed it -
    `json.dumps(..., separators=(",", ":"))` matches `JSON.stringify`'s no-whitespace output, and
    dict insertion order matches the field order `JSON.stringify` walks on the TS side."""
    sorted_items = sorted(items, key=_item_sort_key)
    payload: dict = {
        "version": version,
        "profile": profile,
        "items": [asdict(item) for item in sorted_items],
    }
    if deletions is not None:
        payload["deletions"] = sorted(deletions)
    return json.dumps(payload, separators=(",", ":")).encode()


def verify_manifest(manifest: ManifestResponse, public_key_pem: str) -> bool:
    """Re-derives the canonical payload and checks it against `manifest.signature`. Only
    meaningful for a full manifest fetch - see the module docstring on why `since=`-diffed
    responses cannot be verified this way."""
    payload = canonical_payload(manifest.version, manifest.profile, manifest.items, manifest.deletions)
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    if not isinstance(public_key, Ed25519PublicKey):
        raise ManifestVerificationError("server public key is not an ed25519 key")
    try:
        public_key.verify(_b64decode(manifest.signature), payload)
        return True
    except InvalidSignature:
        return False


def _b64decode(value: str) -> bytes:
    import base64

    return base64.b64decode(value)
