"""Which Jira task keys does the fleet already own on this machine? (R11)

`ARCHITECTURE_SPLIT_PLAN.md` §8 R11 — "Half-migrated state: new queue plus old pipeline both
acting on one Jira task" — is rated **high**, and its stated mitigation is "one owner per task
key; the old poller refuses tasks that have a fleet assignment".

Nothing implemented that. `poller.poll()` only ever checked `state.exists(key)`, which is the
*legacy* pipeline's own local state and says nothing about the fleet. A machine can have the
crontab poller installed (`midas enable --legacy`) and the delegated agent installed
(`midas enable`) at the same time, and morpheus can be running a work source over the same Jira
project — so the same ticket gets picked up twice, by two systems, with two sets of commits.

This module answers the question locally, from state the agent already writes:

* `<fleet>/leases/*.json`  — assignments this machine currently holds
* `<fleet>/completed.json` — assignments it has finished, keyed by idempotency key

Server-generated idempotency keys for work-source items are `source:<sourceId>:<KEY>:round<N>`
(morpheus `packages/harness/src/sources.ts`), so the task key is recoverable from them. Leases
carry the assignment payload, whose `inputs.vars.jiraIssueKey` is what the seed playbook reads.

Deliberately local-only: no network call, so the poller stays usable offline and this can never
become a reason polling fails.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .. import logging_setup, paths

log = logging_setup.get("fleet.ownership")

#: `source:<sourceId>:<issueKey>:round<N>` — the issue key is the second-to-last segment.
_SOURCE_KEY = re.compile(r"^source:[^:]+:([^:]+):round\d+$")


def _keys_from_completed() -> set[str]:
    path = paths.fleet_dir() / "completed.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return set()
    found = set()
    for idempotency_key in data:
        match = _SOURCE_KEY.match(str(idempotency_key))
        if match:
            found.add(match.group(1))
    return found


def _keys_from_leases() -> set[str]:
    lease_dir = paths.fleet_dir() / "leases"
    if not lease_dir.is_dir():
        return set()
    found = set()
    for path in sorted(lease_dir.glob("*.json")):
        try:
            data = json.loads(Path(path).read_text())
        except (json.JSONDecodeError, OSError):
            continue  # a torn write is not a reason to stop polling
        match = _SOURCE_KEY.match(str(data.get("idempotencyKey", "")))
        if match:
            found.add(match.group(1))
        key = ((data.get("inputs") or {}).get("vars") or {}).get("jiraIssueKey")
        if key:
            found.add(str(key))
    return found


def fleet_owned_keys() -> set[str]:
    """Task keys the fleet has claimed or completed on this machine.

    Best-effort by design: a key this misses is a key the legacy poller may double-own, which is
    the pre-existing behaviour, so a parse failure degrades to today rather than to a crash.
    """
    return _keys_from_leases() | _keys_from_completed()
