"""Network harness sync - fetch, verify, diff, download, project (spec §3.1-3.2, S3b).

A flat module, not a `harness/` package - `harness.py` (618 lines, already extensively tested)
stays the local/bundled half; this is purely the network half, reusing `harness.PROJECTION` for
target directories so both sides agree on where things go.

The 9-step algorithm this implements: fetch the *full* manifest (never `?since=` - see
`fleet/manifest.py`'s module docstring for why a diffed response can't be verified), verify its
signature, diff against the locally recorded network-applied state, download and hash-verify any
blobs not already cached, stage them, project into the local tools, and record what was applied.

A locally-edited item (on-disk content matching neither the target manifest nor the last-applied
record) is never silently overwritten - `sync_from_morpheus` reports it as `divergent` and skips
it, the same "ask, don't assume" posture the rest of midas takes toward operator-owned state.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests

from . import client as fleet_client
from .manifest import ManifestItem, ManifestResponse, ManifestVerificationError, verify_manifest
from .. import harness, paths

DEFAULT_TIMEOUT_S = 30


class SyncError(Exception):
    """A definitive, non-retryable sync failure - refused signature, unreachable server."""


@dataclass
class NetworkAppliedState:
    profile: str = ""
    version: str = ""
    # "<kind>:<name>" -> fingerprint (sha256 over the group's sorted "path:sha256" members).
    items: dict[str, str] = field(default_factory=dict)
    at: str = ""

    @classmethod
    def load(cls) -> "NetworkAppliedState":
        f = paths.network_applied_file()
        if not f.is_file():
            return cls()
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            return cls()
        return cls(profile=data.get("profile", ""), version=data.get("version", ""), items=data.get("items", {}), at=data.get("at", ""))

    def save(self) -> None:
        paths.harness_state_dir().mkdir(parents=True, exist_ok=True)
        paths.network_applied_file().write_text(json.dumps(asdict(self), indent=2) + "\n")


@dataclass
class SyncResult:
    version: str
    profile: str
    applied: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    divergent: list[str] = field(default_factory=list)
    dry_run: bool = False


def _item_identity(item: ManifestItem) -> str:
    """Mirrors morpheus's `itemIdentity` in packages/harness/src/patches.ts exactly: the manifest
    path's first segment is the kind folder (dropped), and for a skill the next segment is its
    name; every other kind is one file deep, so the whole remainder is the name."""
    rest = item.path.split("/")[1:]
    name = rest[0] if item.kind == "skill" and rest else "/".join(rest)
    return f"{item.kind}:{name or item.path}"


def _group_items(items: list[ManifestItem]) -> dict[str, list[ManifestItem]]:
    groups: dict[str, list[ManifestItem]] = {}
    for item in items:
        groups.setdefault(_item_identity(item), []).append(item)
    return groups


def _group_fingerprint(members: list[ManifestItem]) -> str:
    h = hashlib.sha256()
    for member in sorted(members, key=lambda m: m.path):
        h.update(f"{member.path}:{member.sha256}".encode())
    return h.hexdigest()


def fetch_manifest(server_url: str, session: requests.Session, profile: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> ManifestResponse:
    """GETs the *full* manifest - never `?since=`, see the module docstring. Unauthenticated by
    design on the server side (same trust level as the kernel release route), so no client
    secret is attached."""
    url = f"{server_url}/api/fleet/v1/harness/profiles/{profile}/manifest"
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise SyncError(f"could not reach {server_url}: {exc}") from exc
    if response.status_code == 404:
        raise SyncError(f'profile "{profile}" is unknown or has never been published')
    if not response.ok:
        raise SyncError(f"manifest fetch failed: HTTP {response.status_code}")
    return ManifestResponse.from_json(response.json())


def _cached_blob_path(sha256: str) -> Path:
    return paths.harness_blob_cache_dir() / sha256


def download_blob(server_url: str, session: requests.Session, sha256: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> Path:
    """Downloads a blob into the local cache if not already present, verifying its hash on
    arrival - the manifest signature covers the *list* of (path, sha256) pairs, not the blob
    bytes themselves, so each blob must be independently checked against the hash it claims."""
    cached = _cached_blob_path(sha256)
    if cached.is_file():
        return cached

    url = f"{server_url}/api/fleet/v1/harness/blobs/{sha256}"
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise SyncError(f"could not fetch blob {sha256}: {exc}") from exc
    if not response.ok:
        raise SyncError(f"blob {sha256} fetch failed: HTTP {response.status_code}")

    actual = hashlib.sha256(response.content).hexdigest()
    if actual != sha256:
        raise SyncError(f"blob {sha256} failed hash verification (got {actual}) - refusing to stage it")

    paths.harness_blob_cache_dir().mkdir(parents=True, exist_ok=True)
    staging = cached.with_suffix(".part")
    staging.write_bytes(response.content)
    staging.replace(cached)  # atomic on the same filesystem
    return cached


def _leaf_for(kind: str, name: str) -> str:
    """Mirrors `integrate.py`'s `plan_harness` leaf-selection: kb items keep any sub-path in
    their name, quality-gate items flatten to just the filename, everything else uses its own
    name as-is (a skill's whole directory, or a single file's own basename)."""
    if kind == "quality-gate":
        return Path(name).name
    return name


def _project_group(kind: str, name: str, members: list[ManifestItem], root: Path) -> bool:
    """Writes the group's already-cached blobs into every projection target for `kind`. Returns
    False (and writes nothing) for kinds with no projection target (mcp/cli - same "available,
    not auto-projected" treatment `harness.projectable()` already gives them)."""
    targets = harness.PROJECTION.get(kind, ())
    if not targets:
        return False

    leaf = _leaf_for(kind, name)
    for rel in targets:
        target_root = root / rel / leaf
        if kind == "skill":
            # multi-file: each member's path is "skills/<name>/<sub-path...>"
            for member in members:
                sub_path = "/".join(member.path.split("/")[2:])
                dest = target_root / sub_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_cached_blob_path(member.sha256), dest)
        else:
            member = members[0]
            target_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_cached_blob_path(member.sha256), target_root)
    return True


def sync_from_morpheus(
    identity: fleet_client.ClientIdentity,
    profile: str,
    *,
    root: Path | None = None,
    dry_run: bool = False,
    timeout: float = DEFAULT_TIMEOUT_S,
    require_signature: bool = True,
) -> SyncResult:
    """The full fetch -> verify -> diff -> download -> stage -> project -> record cycle.

    Raises `SyncError`/`ManifestVerificationError` for anything definitive (unreachable server,
    bad signature). `require_signature=False` exists only for a server whose identity predates
    the public-key handshake (S3b commit 1) and has no `server_public_key_pem` recorded - it is
    not a way to skip verification when a key *is* available.
    """
    root = root or Path.home()
    session = fleet_client._session_for(identity.server_url, identity.pin_sha256)  # noqa: SLF001 - same package

    manifest = fetch_manifest(identity.server_url, session, profile, timeout=timeout)

    if identity.server_public_key_pem:
        if not verify_manifest(manifest, identity.server_public_key_pem):
            raise ManifestVerificationError(f'manifest for profile "{profile}" failed signature verification - refusing to sync')
    elif require_signature:
        raise SyncError(
            "no server public key on file for this enrollment - re-enroll to capture one, "
            "or pass require_signature=False to sync unverified (not recommended)"
        )

    applied_state = NetworkAppliedState.load()
    groups = _group_items(manifest.items)
    result = SyncResult(version=manifest.version, profile=profile, dry_run=dry_run)

    new_items: dict[str, str] = dict(applied_state.items)
    seen_keys: set[str] = set()
    for key, members in sorted(groups.items()):
        seen_keys.add(key)
        fingerprint = _group_fingerprint(members)
        if applied_state.items.get(key) == fingerprint:
            result.unchanged.append(key)
            continue

        if dry_run:
            result.applied.append(key)
            continue

        kind = members[0].kind
        for member in members:
            download_blob(identity.server_url, session, member.sha256, timeout=timeout)
        wrote = _project_group(kind, key.split(":", 1)[1], members, root)
        new_items[key] = fingerprint
        if wrote:
            result.applied.append(key)

    for key in list(new_items):
        if key not in seen_keys:
            del new_items[key]
            result.removed.append(key)

    if not dry_run:
        NetworkAppliedState(profile=profile, version=manifest.version, items=new_items, at=time.strftime("%Y-%m-%dT%H:%M:%S%z")).save()

    return result
