"""Lease renewal (spec §4.3, R5, S4b).

Runs on a background thread for the duration of a claimed assignment's kernel execution -
`kernel.run()` blocks the calling thread reading NDJSON frames, and a single node's execution
(one long LLM turn) can easily outlast a renewal interval with no natural callback to hook a
renewal into, so a real timer thread is the only place this can live.

Renews at half the *remaining* interval, not a fixed period (spec §4.3): each renewal
recomputes "half of what's left until expiry now," so a delayed renewal (a slow HTTP round
trip, a busy thread) doesn't compound into ever-later renewals.

R5 (clock skew): the server's `leaseUntil` is an absolute wall-clock deadline, but this converts
it to a remaining-seconds figure exactly once per renewal and tracks it from then on via
`time.monotonic()` - immune to a wall-clock adjustment (NTP correction, DST) landing mid-run and
scrambling the renewal schedule that a repeated wall-clock diff would be vulnerable to.

On lease-lost (spec §4.4/D10): this does *not* kill the running kernel subprocess. Terminating a
node mid-execution to "stop immediately" would abandon a half-modified working tree - worse than
finishing it. It flags `lease_lost` and calls `on_lease_lost` once; the caller's job is to let the
current kernel run finish naturally, then report through the outbox as usual (D10 already makes a
late report acceptable if nobody re-claimed the assignment since).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Callable

from .. import logging_setup
from . import client as fleet_client

log = logging_setup.get("lease")

MIN_WAIT_S = 0.05


def _seconds_until(lease_until_iso: str) -> float:
    deadline = datetime.fromisoformat(lease_until_iso.replace("Z", "+00:00"))
    return (deadline - datetime.now(timezone.utc)).total_seconds()


class LeaseRenewer:
    def __init__(
        self,
        identity: fleet_client.ClientIdentity,
        assignment_id: str,
        lease_until: str,
        *,
        on_lease_lost: Callable[[], None] | None = None,
    ) -> None:
        self._identity = identity
        self._assignment_id = assignment_id
        self._on_lease_lost = on_lease_lost
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._monotonic_anchor = time.monotonic()
        self._remaining_at_anchor = _seconds_until(lease_until)
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"lease-renew-{assignment_id}")

    def start(self) -> "LeaseRenewer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    @property
    def lease_lost(self) -> bool:
        return self._lost.is_set()

    def _remaining(self) -> float:
        elapsed = time.monotonic() - self._monotonic_anchor
        return self._remaining_at_anchor - elapsed

    def _loop(self) -> None:
        while not self._stop.is_set():
            wait = max(self._remaining() / 2, MIN_WAIT_S)
            if self._stop.wait(timeout=wait):
                return

            result = fleet_client.renew(self._identity, self._assignment_id)
            if not result.ok:
                if result.error == "lease-lost":
                    log.warning("assignment %s: lease lost - letting the current step finish, then reporting", self._assignment_id)
                    self._lost.set()
                    if self._on_lease_lost is not None:
                        self._on_lease_lost()
                    return
                log.warning("assignment %s: lease renewal failed (%s) - retrying next interval", self._assignment_id, result.error)
                continue  # transient - the old deadline still stands, try again off the old clock

            self._monotonic_anchor = time.monotonic()
            self._remaining_at_anchor = _seconds_until(result.lease_until)
