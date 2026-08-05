"""Durable outbox for fleet reporting (spec §4.2, D9, S4b).

Every fact this client owes the server - a run event, a usage record, an artifact, a completion
or nack - is written here *before* the network call is attempted, and removed only once the
server has actually accepted it. A network blip, a server restart, or a laptop closing its lid
mid-report all look the same from here: the fact stays queued and `drain()` sends it on the next
opportunity. This is what makes "kill the network mid-run, the client finishes, the server is
caught up within one heartbeat of reconnect" (spec §7 Phase 4 acceptance test) possible at all.

One file per entry, `fleet/outbox/<seq>-<kind>.json` (spec §5), so a crash mid-write only ever
loses (or torn-writes) the one entry being appended, never the whole queue.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import logging_setup, paths
from . import client as fleet_client
from .assignments import ArtifactRef, AssignmentEvent, AssignmentUsage, CompleteRequest, Gate, NackRequest

log = logging_setup.get("outbox")

KINDS = ("event", "usage", "artifact", "completion", "jira_intent")

# An event whose type carries raw per-tool-call CLI output (large, low-value if the run already
# succeeded) - the first thing a size-capped outbox sheds. Completions and usage records are
# never shed; they're what a Morpheus operator needs to know a run finished and what it cost.
SHEDDABLE_EVENT_PREFIX = "cli:"


def _outbox_dir() -> Path:
    return paths.fleet_dir() / "outbox"


def _dead_dir() -> Path:
    return _outbox_dir() / "dead"


def _entry_path(seq: int, kind: str) -> Path:
    return _outbox_dir() / f"{seq:010d}-{kind}.json"


@dataclass
class OutboxEntry:
    seq: int
    kind: str
    assignment_id: str
    payload: dict
    created_at: str
    path: Path | None = field(repr=False, default=None)

    @classmethod
    def load(cls, path: Path) -> "OutboxEntry":
        data = json.loads(path.read_text())
        return cls(seq=int(data["seq"]), kind=str(data["kind"]), assignment_id=str(data["assignmentId"]), payload=data["payload"], created_at=str(data["createdAt"]), path=path)


def _next_seq() -> int:
    existing = [int(p.name.split("-", 1)[0]) for p in _outbox_dir().glob("*.json") if p.is_file() and p.name.split("-", 1)[0].isdigit()]
    return (max(existing) + 1) if existing else 0


def enqueue(kind: str, assignment_id: str, payload: dict) -> Path:
    if kind not in KINDS:
        raise ValueError(f"unknown outbox kind {kind!r} - expected one of {KINDS}")
    _outbox_dir().mkdir(parents=True, exist_ok=True)
    seq = _next_seq()
    entry = {"seq": seq, "kind": kind, "assignmentId": assignment_id, "payload": payload, "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    path = _entry_path(seq, kind)
    path.write_text(json.dumps(entry))
    return path


def list_entries() -> list[OutboxEntry]:
    if not _outbox_dir().is_dir():
        return []
    entries = []
    for p in sorted(_outbox_dir().glob("*.json")):
        try:
            entries.append(OutboxEntry.load(p))
        except (OSError, json.JSONDecodeError, KeyError):
            continue  # a torn write from a crash mid-append - skip, not fatal
    return sorted(entries, key=lambda e: e.seq)


def depth() -> int:
    """For the heartbeat's `outboxDepth` field - how much this client is behind on reporting."""
    return len(list_entries())


def shed(max_entries: int) -> list[OutboxEntry]:
    """Drops the oldest `cli:*` raw-frame events until the outbox is at or under `max_entries`.
    Never sheds usage or completion entries - those are the ones a Morpheus operator actually
    needs. Returns what was shed, so the caller can log it (spec: "logs it" - no silent truncation)."""
    entries = list_entries()
    if len(entries) <= max_entries:
        return []
    sheddable = [e for e in entries if e.kind == "event" and str(e.payload.get("type", "")).startswith(SHEDDABLE_EVENT_PREFIX)]
    to_shed = sheddable[: len(entries) - max_entries]
    for entry in to_shed:
        entry.path.unlink(missing_ok=True)
    if to_shed:
        log.warning("outbox over %d entries - shed %d raw cli:* event(s) to stay within the cap", max_entries, len(to_shed))
    return to_shed


def _to_event(payload: dict) -> AssignmentEvent:
    return AssignmentEvent(seq=payload["seq"], at=payload["at"], type=payload["type"], node_id=payload.get("nodeId"), data=payload.get("data"))


def _to_usage(payload: dict) -> AssignmentUsage:
    return AssignmentUsage(at=payload["at"], step_id=payload["stepId"], subscription=payload["subscription"], estimated_usd=payload.get("estimatedUsd"), cost_source=payload.get("costSource"))


def _to_complete(payload: dict) -> CompleteRequest:
    gate = Gate(node_id=payload["gate"]["nodeId"], prompt=payload["gate"]["prompt"]) if payload.get("gate") else None
    artifacts = [ArtifactRef(**a) for a in payload.get("artifacts", [])]
    return CompleteRequest(outcome=payload["outcome"], spend_usd=payload["spendUsd"], baton_digest=payload["batonDigest"], artifacts=artifacts, gate=gate)


def _to_nack(payload: dict) -> NackRequest:
    return NackRequest(reason=payload["reason"], retryable=payload["retryable"], detail=payload.get("detail"))


def _send_one(identity: fleet_client.ClientIdentity, entry: OutboxEntry) -> fleet_client.FleetActionResult:
    if entry.kind == "event":
        return fleet_client.send_events(identity, entry.assignment_id, [_to_event(entry.payload)])
    if entry.kind == "usage":
        return fleet_client.send_usage(identity, entry.assignment_id, _to_usage(entry.payload))
    if entry.kind == "artifact":
        data = base64.b64decode(entry.payload["dataBase64"])
        return fleet_client.upload_artifact(identity, entry.assignment_id, entry.payload["sha256"], data)
    if entry.kind == "completion":
        if entry.payload.get("action") == "nack":
            return fleet_client.nack(identity, entry.assignment_id, _to_nack(entry.payload))
        return fleet_client.complete(identity, entry.assignment_id, _to_complete(entry.payload))
    if entry.kind == "jira_intent":
        # No consumer exists yet for this kind - nothing in midas posts a queued Jira intent back
        # out (pipeline_comments.py's own posting path is synchronous and unrelated). Accepted
        # into the schema so a caller can enqueue one, but drain() below explicitly refuses to
        # silently pretend to have handled it.
        raise NotImplementedError("jira_intent has no drain consumer yet - not implemented")
    raise ValueError(f"unknown outbox kind {entry.kind!r}")


@dataclass
class DrainResult:
    sent: int = 0
    kept: int = 0  # network failure or lease-lost - stays queued, tried again next drain
    dead_lettered: int = 0
    skipped: int = 0  # e.g. jira_intent, no consumer


def drain(identity: fleet_client.ClientIdentity) -> DrainResult:
    """Sends every entry in seq order. Deletes only on success (2xx). `lease-lost` (409) keeps
    the entry and stops draining *that assignment's* remaining entries this pass (the lease is
    gone - piling more reports against it won't help) while continuing with other assignments'
    entries. Any other failure (network down, non-2xx) keeps the entry for the next drain."""
    result = DrainResult()
    lease_lost_assignments: set[str] = set()

    for entry in list_entries():
        if entry.assignment_id in lease_lost_assignments:
            result.kept += 1
            continue

        if entry.kind == "jira_intent":
            result.skipped += 1
            continue

        try:
            outcome = _send_one(identity, entry)
        except NotImplementedError:
            result.skipped += 1
            continue

        if outcome.ok:
            entry.path.unlink(missing_ok=True)
            result.sent += 1
            continue

        if outcome.error == "lease-lost":
            log.warning("outbox: assignment %s lease-lost while draining - keeping entries, not retrying against a dead lease this pass", entry.assignment_id)
            lease_lost_assignments.add(entry.assignment_id)
            result.kept += 1
            continue

        if outcome.error and outcome.error.startswith("HTTP 4") and not outcome.error.startswith("HTTP 409"):
            _dead_dir().mkdir(parents=True, exist_ok=True)
            entry.path.rename(_dead_dir() / entry.path.name)
            result.dead_lettered += 1
            log.warning("outbox: entry %s moved to dead/ (non-retryable: %s)", entry.path.name, outcome.error)
            continue

        result.kept += 1  # network error / 5xx - try again next drain

    return result
