"""HTTP client for `/api/fleet/v1` (spec §2.1, `ARCHITECTURE_SPLIT_PLAN.md` §4.1-4.3, §6.3).

Every network failure is normal, not exceptional: a client that logs a stack trace every 30
seconds while its server is down is unusable. `heartbeat()` never raises for a connection
problem - it returns a result the caller can act on quietly. `enroll()` is the one call that
does raise, because there is no sensible "keep going" for an enrollment that never completed.
"""

from __future__ import annotations

import json
import platform
import random
from dataclasses import asdict, dataclass, field
from typing import Any

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .. import __version__, paths
from ..config import _write_private
from .assignments import AssignmentEvent, AssignmentUsage, ClaimResponse, CompleteRequest, NackRequest

DEFAULT_TIMEOUT_S = 15
BASE_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

LOOPBACK_PREFIXES = ("http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost")


class FleetError(Exception):
    """A definitive, non-retryable outcome - a refused enroll, or a config error."""


@dataclass
class ClientIdentity:
    """`~/.local/state/midas/fleet/client.json` (spec §2.1) - 0600, written with the same
    `_write_private()` config.py already uses for credentials, so there is no umask window."""

    server_url: str
    client_id: str
    client_secret: str
    private_key_pem: str
    public_key_pem: str
    pin_sha256: str = ""
    # The server's ed25519 signing public key, TOFU-captured at enroll — same trust model as
    # `pin_sha256` above. Harness manifest/patch signatures (S3b) are meaningless without it, and
    # there is no other way for a client to obtain it (`morpheus fleet keygen` only prints to an
    # operator's terminal).
    server_public_key_pem: str = ""
    # The harness profile this client was enrolled under (echoed back on the enroll response) —
    # `midas install`'s default profile when none is given on the command line.
    profile: str = ""

    @classmethod
    def load(cls) -> "ClientIdentity | None":
        path = paths.fleet_client_file()
        if not path.is_file():
            return None
        return cls(**json.loads(path.read_text()))

    def save(self) -> None:
        _write_private(paths.fleet_client_file(), json.dumps(asdict(self), indent=2))

    @staticmethod
    def clear() -> None:
        paths.fleet_client_file().unlink(missing_ok=True)


@dataclass
class HeartbeatResult:
    ok: bool
    directives: list[dict] = field(default_factory=list)
    heartbeat_seconds: int | None = None
    error: str | None = None


def backoff_seconds(attempt: int, *, base: float = BASE_BACKOFF_S, cap: float = MAX_BACKOFF_S) -> float:
    """Exponential backoff with full jitter, `attempt` 0-indexed (spec §2.1). Used by `enroll()`'s
    own retry of transient connection failures, and available to the agent loop (Phase 4) for
    pacing retries between heartbeats after a server outage."""
    ceiling = min(cap, base * (2**attempt))
    return random.uniform(0, ceiling)


def _generate_keypair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


def _pinned_adapter(pin_sha256: str) -> "requests.adapters.HTTPAdapter":
    """A requests HTTPAdapter that trusts no CA and instead refuses any TLS connection whose
    certificate fingerprint does not match `pin_sha256` (spec §6.3: "self-signed is fine; the
    client pins the cert/pubkey and refuses on change"). `assert_fingerprint` replaces hostname
    and CA verification entirely, which is the point - a self-signed cert has neither."""
    from requests.adapters import HTTPAdapter

    fingerprint = pin_sha256.replace(":", "")

    class PinnedAdapter(HTTPAdapter):
        def cert_verify(self, conn, url, verify, cert):
            super().cert_verify(conn, url, verify=False, cert=cert)
            conn.assert_fingerprint = fingerprint

    return PinnedAdapter()


def _session_for(server_url: str, pin_sha256: str | None) -> requests.Session:
    session = requests.Session()
    if pin_sha256 and server_url.startswith("https://"):
        session.mount("https://", _pinned_adapter(pin_sha256))
    return session


def _peer_cert_fingerprint(response: requests.Response) -> str:
    """The SHA256 fingerprint of the certificate the server just presented, captured on the
    enroll response itself - this reaches into `requests`/urllib3 internals because the public
    API has no supported way to read the peer certificate of a completed request. If this ever
    breaks on a `requests`/urllib3 upgrade, the fallback is `pin_sha256 = ""` (no pin captured),
    not a crash - see the try/except at the one call site."""
    import hashlib

    sock = response.raw._connection.sock  # noqa: SLF001 - see docstring
    cert_bytes = sock.getpeercert(binary_form=True)
    return hashlib.sha256(cert_bytes).hexdigest()


def _error_detail(response: requests.Response) -> str:
    try:
        body: Any = response.json()
        if isinstance(body, dict) and "error" in body:
            return str(body["error"])
    except (ValueError, json.JSONDecodeError):
        pass
    return response.text[:200]


def enroll(
    server_url: str,
    invite_token: str,
    *,
    host_worker: bool = False,
    capabilities: dict,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_attempts: int = 3,
) -> ClientIdentity:
    """Enroll against a Morpheus server, store the resulting identity, and return it.

    `host_worker=True` is for the one case Morpheus's own installer uses when provisioning
    its loopback fallback worker (D12) - it is refused against anything but a loopback
    `server_url` (D14), since the whole point of that profile being more permissive is that
    it can only ever be reached from the same machine.

    Raises `FleetError` for anything definitive (bad token, a host enrollment against a
    non-loopback URL) - there is no sensible "keep going" for an enrollment that never
    completed. Transient connection failures (server not up yet, DNS blip) get
    `max_attempts` retries with backoff.
    """
    if host_worker and not server_url.startswith(LOOPBACK_PREFIXES):
        raise FleetError(f'a host-worker enrollment requires a loopback server_url, got "{server_url}" (spec D12/D14)')

    private_pem, public_pem = _generate_keypair()
    # Matches the wire contract exactly (`ARCHITECTURE_SPLIT_PLAN.md` §4.1). The server derives
    # the client's label from `hostname`, falling back to the invite's own label if that's blank.
    body = {
        "hostname": platform.node(),
        "os": platform.system().lower(),
        "arch": platform.machine(),
        "midasVersion": __version__,
        "capabilities": capabilities,
        "publicKey": public_pem,
    }
    headers = {"authorization": f"Bearer {invite_token}"}
    session = _session_for(server_url, None)  # no pin yet - this call is what establishes one

    last_exc: requests.RequestException | None = None
    response: requests.Response | None = None
    for attempt in range(max_attempts):
        try:
            response = session.post(f"{server_url}/api/fleet/v1/enroll", json=body, headers=headers, timeout=timeout)
            break
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                import time

                time.sleep(backoff_seconds(attempt))
    if response is None:
        raise FleetError(f"could not reach {server_url}: {last_exc}")

    if response.status_code != 201:
        raise FleetError(f"enroll refused: HTTP {response.status_code} — {_error_detail(response)}")

    data = response.json()
    pin = ""
    if server_url.startswith("https://"):
        try:
            pin = _peer_cert_fingerprint(response)
        except (AttributeError, OSError):
            pin = ""  # see _peer_cert_fingerprint's docstring - degrade, don't crash

    identity = ClientIdentity(
        server_url=server_url,
        client_id=data["clientId"],
        client_secret=data["clientSecret"],
        private_key_pem=private_pem,
        public_key_pem=public_pem,
        pin_sha256=pin,
        server_public_key_pem=data.get("publicKeyPem", ""),
        profile=data.get("profile", ""),
    )
    identity.save()
    return identity


def heartbeat(
    identity: ClientIdentity,
    *,
    state: str,
    capabilities: dict,
    leases: list[dict] | None = None,
    outbox_depth: int = 0,
    health: list[dict] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> HeartbeatResult:
    """One heartbeat. Never raises for a network problem - every failure mode below is
    something a laptop-that-closed-its-lid produces routinely, not an exceptional event."""
    body = {"state": state, "capabilities": capabilities, "leases": leases or [], "outboxDepth": outbox_depth, "health": health or []}
    headers = {"authorization": f"Bearer {identity.client_secret}", "x-midas-client": identity.client_id}
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/clients/{identity.client_id}/heartbeat"

    try:
        response = session.post(url, json=body, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return HeartbeatResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    if response.status_code == 401:
        return HeartbeatResult(ok=False, error="client-revoked-or-invalid")
    if response.status_code == 423:
        return HeartbeatResult(ok=False, error="client-quarantined")
    if not response.ok:
        return HeartbeatResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")

    data = response.json()
    return HeartbeatResult(ok=True, directives=data.get("directives", []), heartbeat_seconds=data.get("heartbeatSeconds"))


@dataclass
class ClaimResult:
    ok: bool
    assignments: list = field(default_factory=list)
    error: str | None = None


@dataclass
class FleetActionResult:
    """Generic ok/error result for the assignment-lifecycle calls below (renew/complete/nack/
    events/usage/artifacts) - none of them have a payload worth a bespoke type."""

    ok: bool
    error: str | None = None


@dataclass
class RenewResult(FleetActionResult):
    lease_until: str | None = None


def _assignment_headers(identity: ClientIdentity) -> dict:
    return {"authorization": f"Bearer {identity.client_secret}", "x-midas-client": identity.client_id}


def claim(
    identity: ClientIdentity,
    *,
    capabilities: dict,
    wait_seconds: int = 25,
    max_assignments: int = 1,
    timeout: float | None = None,
) -> ClaimResult:
    """`POST /clients/:id/claim?wait=<wait_seconds>` - a real long-poll, so `timeout` must exceed
    `wait_seconds` (defaults to `wait_seconds + 10` if not given) or every call would time out
    locally before the server ever gets to answer with "nothing yet"."""
    body = {
        "actions": capabilities.get("actions"),
        "subscriptions": list(capabilities["subscriptions"].keys()) if isinstance(capabilities.get("subscriptions"), dict) else capabilities.get("subscriptions"),
        "labels": capabilities.get("labels"),
        "max": max_assignments,
    }
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/clients/{identity.client_id}/claim?wait={wait_seconds}"

    try:
        response = session.post(url, json=body, headers=_assignment_headers(identity), timeout=timeout or wait_seconds + 10)
    except requests.RequestException as exc:
        return ClaimResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    if response.status_code == 204:
        return ClaimResult(ok=True, assignments=[])
    if response.status_code == 401:
        return ClaimResult(ok=False, error="client-revoked-or-invalid")
    if response.status_code == 423:
        return ClaimResult(ok=False, error="client-quarantined")
    if not response.ok:
        return ClaimResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")

    return ClaimResult(ok=True, assignments=ClaimResponse.from_json(response.json()).assignments)


def renew(identity: ClientIdentity, assignment_id: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> RenewResult:
    """`POST /assignments/:id/renew`. A `409` means the lease is lost - per spec §4.4/D10, the
    caller must finish its current step, stop, and report; never keep working against a lease
    that's gone."""
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/assignments/{assignment_id}/renew"
    try:
        response = session.post(url, headers=_assignment_headers(identity), timeout=timeout)
    except requests.RequestException as exc:
        return RenewResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if response.status_code == 409:
        return RenewResult(ok=False, error="lease-lost")
    if not response.ok:
        return RenewResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")
    return RenewResult(ok=True, lease_until=response.json().get("leaseUntil"))


def complete(identity: ClientIdentity, assignment_id: str, request: CompleteRequest, *, timeout: float = DEFAULT_TIMEOUT_S) -> FleetActionResult:
    """`POST /assignments/:id/complete`. Idempotent on the server side (D10) - safe for the
    outbox to retry this exact call after a dropped response without double-reporting."""
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/assignments/{assignment_id}/complete"
    try:
        response = session.post(url, json=request.to_json(), headers=_assignment_headers(identity), timeout=timeout)
    except requests.RequestException as exc:
        return FleetActionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if response.status_code == 409:
        return FleetActionResult(ok=False, error="lease-lost")
    if not response.ok:
        return FleetActionResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")
    return FleetActionResult(ok=True)


def nack(identity: ClientIdentity, assignment_id: str, request: NackRequest, *, timeout: float = DEFAULT_TIMEOUT_S) -> FleetActionResult:
    """`POST /assignments/:id/nack`."""
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/assignments/{assignment_id}/nack"
    try:
        response = session.post(url, json=request.to_json(), headers=_assignment_headers(identity), timeout=timeout)
    except requests.RequestException as exc:
        return FleetActionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if response.status_code == 409:
        return FleetActionResult(ok=False, error="lease-lost")
    if not response.ok:
        return FleetActionResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")
    return FleetActionResult(ok=True)


def send_events(identity: ClientIdentity, assignment_id: str, events: list[AssignmentEvent], *, timeout: float = DEFAULT_TIMEOUT_S) -> FleetActionResult:
    """`POST /assignments/:id/events` - batched, idempotent on `(assignmentId, seq)` server-side,
    so the outbox may safely resend a batch it isn't sure landed."""
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/assignments/{assignment_id}/events"
    body = {"events": [e.to_json() for e in events]}
    try:
        response = session.post(url, json=body, headers=_assignment_headers(identity), timeout=timeout)
    except requests.RequestException as exc:
        return FleetActionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if response.status_code == 409:
        return FleetActionResult(ok=False, error="lease-lost")
    if not response.ok:
        return FleetActionResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")
    return FleetActionResult(ok=True)


def send_usage(identity: ClientIdentity, assignment_id: str, usage: AssignmentUsage, *, timeout: float = DEFAULT_TIMEOUT_S) -> FleetActionResult:
    """`POST /assignments/:id/usage` - one record per call, same bucket discipline as the local
    vault usage ledger."""
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/assignments/{assignment_id}/usage"
    try:
        response = session.post(url, json=usage.to_json(), headers=_assignment_headers(identity), timeout=timeout)
    except requests.RequestException as exc:
        return FleetActionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if response.status_code == 409:
        return FleetActionResult(ok=False, error="lease-lost")
    if not response.ok:
        return FleetActionResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")
    return FleetActionResult(ok=True)


def fetch_kernel(identity: ClientIdentity, version: str = "latest", *, timeout: float = 120.0) -> dict:
    """`GET /api/fleet/v1/kernel/:version` — the release payload, unverified.

    The caller verifies (`kernel.install_release`); this only fetches. Generous timeout because
    the bundle is ~1 MB base64-encoded over whatever link a laptop happens to be on.
    """
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/kernel/{version}"
    response = session.get(url, headers=_assignment_headers(identity), timeout=timeout)
    if not response.ok:
        raise FleetError(f"fetching kernel {version}: HTTP {response.status_code} — {_error_detail(response)}")
    return response.json()


def report_abandoned(identity: ClientIdentity, assignment_id: str, payload: dict, *, timeout: float = DEFAULT_TIMEOUT_S) -> FleetActionResult:
    """`POST /clients/:id/abandoned` — this machine archived a run nobody came back for.

    Client-keyed rather than assignment-keyed on purpose: the assignment's lease is long gone by
    the time a run is 30 days stale, so `assignmentGuard` would have nothing to match against.
    The server only *lists* what arrives here; discarding is an explicit operator act (D17).
    """
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/clients/{identity.client_id}/abandoned"
    body = {**payload, "assignmentId": payload.get("assignmentId") or assignment_id}
    try:
        response = session.post(url, json=body, headers=_assignment_headers(identity), timeout=timeout)
    except requests.RequestException as exc:
        return FleetActionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if not response.ok:
        return FleetActionResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")
    return FleetActionResult(ok=True)


def upload_artifact(identity: ClientIdentity, assignment_id: str, sha256: str, data: bytes, *, timeout: float = DEFAULT_TIMEOUT_S) -> FleetActionResult:
    """`POST /assignments/:id/artifacts?sha256=<sha256>` - content-addressed; the server
    independently hashes the body and refuses a mismatch, so this never trusts `sha256` alone."""
    session = _session_for(identity.server_url, identity.pin_sha256)
    url = f"{identity.server_url}/api/fleet/v1/assignments/{assignment_id}/artifacts?sha256={sha256}"
    headers = {**_assignment_headers(identity), "content-type": "application/octet-stream"}
    try:
        response = session.post(url, data=data, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return FleetActionResult(ok=False, error=f"{type(exc).__name__}: {exc}")
    if response.status_code == 409:
        return FleetActionResult(ok=False, error="lease-lost")
    if not response.ok:
        return FleetActionResult(ok=False, error=f"HTTP {response.status_code} — {_error_detail(response)}")
    return FleetActionResult(ok=True)


def unsubscribe(*, keep_harness: bool = True) -> None:
    """Demote to standalone. `keep_harness` is accepted for forward compatibility but is
    currently a no-op: harness-sync-over-the-wire (Phase 3) isn't built yet, so there is
    nothing server-managed to keep or discard - the bundled harness is untouched either way."""
    ClientIdentity.clear()
