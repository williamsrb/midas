"""The delegated-work agent loop (spec §4.1, S4b).

One cycle: drain the outbox (report anything left over from a previous crash or dropped
connection first) -> heartbeat -> apply directives -> claim (unless draining or already at max
concurrency) -> for each claimed assignment: check for an already-completed idempotencyKey (D10,
re-send rather than re-run), acquire a per-assignment lock (R4 - one owner per assignment),
policy-check the actual IR demand (not the server's declared ceiling - D4), sync harness/verify
kernel availability, run the kernel with a background lease renewer, report the outcome through
the outbox -> drain the outbox again.

The kernel is not fully autonomous: a `client_action` node in the playbook makes it block on
stdin waiting for us (spec §5.1, D7) - `_client_action_handler` below wires that request straight
through to `actions.dispatch`, the versioned verb vocabulary (`git.*`/`fs.workspace`/
`test.playwright`/`evidence.capture`/`report.write`/`jira.intent`/`notify.send`). This is the
"agents never run git writes themselves" invariant made structural: the kernel has no git verb at
all, only this handler can mutate a repository.

Deliberately not built here: auto-fetching and installing a kernel version this client doesn't
have. `kernel.install()` already refuses a signed bundle (`NotImplementedError`) pending a real
fetch+verify pipeline - wiring that up is separate work, so a kernel-version mismatch nacks the
assignment (`kernel-version-unavailable`, retryable) rather than pretending to self-heal.
Similarly, an `abort` directive for a kernel already mid-execution cannot interrupt it cleanly
(the same "never abandon a half-modified working tree" reasoning as a lost lease) - it's logged,
not silently ignored, but not enforced either.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import actions, gitops, kernel, logging_setup, paths, policy
from ..config import Config
from . import capabilities as capabilities_mod
from . import client as fleet_client
from . import outbox as outbox_mod
from . import sync as sync_mod
from .assignments import Assignment, CompleteRequest, Gate
from .lease import LeaseRenewer
from .policy_bridge import build_policy_assignment

log = logging_setup.get("agent")

DEFAULT_CLAIM_WAIT_S = 25
DEFAULT_SLEEP_BETWEEN_S = 5.0


def _subscriptions_for_kernel() -> dict:
    """Mirrors cli.py's `_default_subscriptions()` for `midas exec` - kept as its own small copy
    rather than importing from `cli.py`, which carries click/argument-parsing baggage this
    module has no business depending on."""
    return {
        "claude": {"enabled": shutil.which("claude") is not None, "bin": "claude", "extraArgs": []},
        "cursor": {"enabled": shutil.which("cursor-agent") is not None, "bin": "cursor-agent", "extraArgs": []},
        "shell": {"enabled": True, "bin": "sh", "extraArgs": []},
    }


# --- local state: completed idempotency keys (D10) and currently-held leases ------------------


def _completed_path() -> Path:
    return paths.fleet_dir() / "completed.json"


def load_completed() -> dict:
    p = _completed_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def _record_completed(idempotency_key: str, record: dict) -> None:
    data = load_completed()
    data[idempotency_key] = record
    _completed_path().parent.mkdir(parents=True, exist_ok=True)
    _completed_path().write_text(json.dumps(data, indent=2))


def _lease_path(assignment_id: str) -> Path:
    return paths.fleet_dir() / "leases" / f"{assignment_id}.json"


def _record_lease(assignment: Assignment) -> None:
    _lease_path(assignment.assignment_id).parent.mkdir(parents=True, exist_ok=True)
    _lease_path(assignment.assignment_id).write_text(json.dumps({"assignmentId": assignment.assignment_id, "leaseUntil": assignment.lease_until}))


def _clear_lease(assignment_id: str) -> None:
    _lease_path(assignment_id).unlink(missing_ok=True)


def current_leases() -> list[dict]:
    """For the heartbeat's `leases` field - what this client is currently holding."""
    d = paths.fleet_dir() / "leases"
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out


# --- per-assignment lock (R4 - one owner per assignment) --------------------------------------


def _acquire_lock(assignment_id: str):
    paths.locks_dir().mkdir(parents=True, exist_ok=True)
    lock_path = paths.locks_dir() / f"assignment-{assignment_id}.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return None
    return lock_file


def _release_lock(lock_file) -> None:
    if lock_file is None:
        return
    fcntl.flock(lock_file, fcntl.LOCK_UN)
    lock_file.close()


# --- workspace preparation ----------------------------------------------------------------------


def _prepare_workspace(assignment: Assignment, cfg: Config) -> Path:
    if assignment.workspace.kind == "none":
        ws = paths.runs_dir() / assignment.assignment_id / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    repo_url = assignment.workspace.repo_url
    branch = assignment.workspace.branch
    assert repo_url and branch  # WorkspaceSpecSchema (morpheus) requires both when kind == "git"
    slug = repo_url.rsplit("/", 1)[-1].removesuffix(".git")
    dest = cfg.paths.workspace_root / slug
    gitops.clone_or_update(repo_url, dest)
    gitops.prepare_branch(dest, branch)
    return dest


# --- directives -----------------------------------------------------------------------------


@dataclass
class DirectiveOutcome:
    drain_requested: bool = False
    aborts: list[str] = field(default_factory=list)


def apply_directives(directives: list[dict], identity: fleet_client.ClientIdentity) -> DirectiveOutcome:
    outcome = DirectiveOutcome()
    for directive in directives:
        kind = directive.get("kind")
        if kind == "sync-harness":
            try:
                result = sync_mod.sync_from_morpheus(identity, identity.profile or "gold")
                log.info("sync-harness directive: applied=%d unchanged=%d divergent=%d", len(result.applied), len(result.unchanged), len(result.divergent))
            except Exception as exc:  # best-effort - a sync failure must never crash the agent loop
                log.warning("sync-harness directive failed: %s", exc)
        elif kind == "upgrade-kernel":
            log.warning(
                "upgrade-kernel directive (target %s) - no auto-install path yet: kernel.install() "
                "refuses a signed bundle pending a fetch+verify pipeline. Run `midas kernel install` manually.",
                directive.get("version"),
            )
        elif kind == "drain":
            outcome.drain_requested = True
        elif kind == "abort":
            assignment_id = directive.get("assignmentId", "")
            outcome.aborts.append(assignment_id)
            if any(lease.get("assignmentId") == assignment_id for lease in current_leases()):
                log.warning(
                    "abort directive for assignment %s, which is currently executing - cannot interrupt a running "
                    "kernel mid-step without risking a half-modified workspace; it will finish and report normally",
                    assignment_id,
                )
    return outcome


# --- executing one claimed assignment ----------------------------------------------------------


@dataclass
class ExecutionResult:
    assignment_id: str
    outcome: str  # "succeeded" | "failed" | "gate" | "nacked" | "skipped-duplicate" | "skipped-locked"


def _read_run_outputs(run_dir: Path) -> tuple[float, str]:
    status_path = run_dir / "status.json"
    status: dict = {}
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text())
        except json.JSONDecodeError:
            status = {}
    spend_usd = float(status.get("spendUsd") or 0.0)
    baton_path = run_dir / "BATON.md"
    baton_digest = hashlib.sha256(baton_path.read_bytes()).hexdigest() if baton_path.is_file() else ""
    return spend_usd, baton_digest


def _client_action_handler(assignment_id: str, workspace_path: Path, run_dir: Path, cfg: Config):
    """Builds the `on_client_action` callback `kernel.run()` calls for a `client_action_call`
    frame (spec §5.1). One `ActionContext` per assignment, reused across every client_action
    node the run hits."""
    ctx = actions.ActionContext(workspace=workspace_path, artifacts_dir=run_dir / "artifacts", assignment_id=assignment_id, cfg=cfg)

    def handle(frame: dict) -> dict:
        action = frame.get("action", "")
        params = frame.get("with") or {}
        result = actions.dispatch(action, params, ctx)
        reply: dict = {"ok": result.ok}
        if result.data:
            reply["data"] = result.data
        if result.error:
            reply["error"] = result.error
        return reply

    return handle


def execute_assignment(
    assignment: Assignment,
    identity: fleet_client.ClientIdentity,
    cfg: Config,
    active_policy: policy.Policy,
    *,
    kernel_run=kernel.run,
) -> ExecutionResult:
    completed = load_completed()
    existing = completed.get(assignment.idempotency_key)
    if existing is not None:
        log.info("assignment %s: idempotencyKey %s already completed locally - re-sending, not re-running (D10)", assignment.assignment_id, assignment.idempotency_key)
        outbox_mod.enqueue("completion", assignment.assignment_id, existing["request"])
        return ExecutionResult(assignment.assignment_id, "skipped-duplicate")

    lock_file = _acquire_lock(assignment.assignment_id)
    if lock_file is None:
        log.warning("assignment %s is already locked by another process - skipping this cycle", assignment.assignment_id)
        return ExecutionResult(assignment.assignment_id, "skipped-locked")

    try:
        workspace_path = _prepare_workspace(assignment, cfg)
        policy_assignment = build_policy_assignment(assignment, str(workspace_path))
        decision = policy.check_assignment(policy_assignment, active_policy)
        if not decision.allowed:
            log.warning("assignment %s refused by policy: %s", assignment.assignment_id, decision.reason)
            outbox_mod.enqueue("completion", assignment.assignment_id, {"action": "nack", "reason": decision.reason, "retryable": True})
            return ExecutionResult(assignment.assignment_id, "nacked")

        if active_policy.auto_apply_harness:
            try:
                sync_mod.sync_from_morpheus(identity, identity.profile or "gold", require_signature=active_policy.require_harness_signature)
            except Exception as exc:  # best-effort - proceed with whatever harness is already applied
                log.warning("assignment %s: harness sync failed, continuing (%s)", assignment.assignment_id, exc)

        if assignment.kernel_version not in kernel.installed_versions():
            log.warning("assignment %s needs kernel %s, which is not installed here", assignment.assignment_id, assignment.kernel_version)
            outbox_mod.enqueue(
                "completion",
                assignment.assignment_id,
                {"action": "nack", "reason": "kernel-version-unavailable", "retryable": True, "detail": f"kernel {assignment.kernel_version} is not installed"},
            )
            return ExecutionResult(assignment.assignment_id, "nacked")

        run_id = assignment.run_id or assignment.assignment_id
        run_dir = paths.runs_dir() / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        request = {
            "runId": run_id,
            "playbook": assignment.playbook,
            "workspace": str(workspace_path),
            "runDir": str(run_dir),
            "vars": assignment.inputs.get("vars", {}),
            "subscriptions": _subscriptions_for_kernel(),
            "limits": {"defaultTimeoutMs": 600_000, "killGraceMs": 5_000},
        }

        _record_lease(assignment)
        renewer = LeaseRenewer(identity, assignment.assignment_id, assignment.lease_until).start()
        try:
            def on_event(event: dict) -> None:
                outbox_mod.enqueue("event", assignment.assignment_id, event)

            on_client_action = _client_action_handler(assignment.assignment_id, workspace_path, run_dir, cfg)
            outcome = kernel_run(request, on_event, version=assignment.kernel_version, on_client_action=on_client_action)
        finally:
            renewer.stop()
            _clear_lease(assignment.assignment_id)

        spend_usd, baton_digest = _read_run_outputs(run_dir)

        if outcome.exit_code == kernel.EXIT_GATE:
            status_path = run_dir / "status.json"
            gate_data = {}
            if status_path.is_file():
                try:
                    gate_data = json.loads(status_path.read_text()).get("gate") or {}
                except json.JSONDecodeError:
                    gate_data = {}
            complete_req = CompleteRequest(outcome="gate", spend_usd=spend_usd, baton_digest=baton_digest, gate=Gate(node_id=gate_data.get("nodeId", ""), prompt=gate_data.get("prompt", "")))
        elif outcome.exit_code == kernel.EXIT_SUCCEEDED:
            complete_req = CompleteRequest(outcome="succeeded", spend_usd=spend_usd, baton_digest=baton_digest)
        else:
            complete_req = CompleteRequest(outcome="failed", spend_usd=spend_usd, baton_digest=baton_digest)

        outbox_mod.enqueue("completion", assignment.assignment_id, complete_req.to_json())
        _record_completed(assignment.idempotency_key, {"assignmentId": assignment.assignment_id, "request": complete_req.to_json(), "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
        return ExecutionResult(assignment.assignment_id, complete_req.outcome)
    finally:
        _release_lock(lock_file)


# --- the cycle ---------------------------------------------------------------------------------


@dataclass
class CycleResult:
    heartbeat_ok: bool = True
    claimed: int = 0
    executed: list[ExecutionResult] = field(default_factory=list)
    drained: outbox_mod.DrainResult = field(default_factory=outbox_mod.DrainResult)


def run_once(identity: fleet_client.ClientIdentity, cfg: Config, active_policy: policy.Policy, *, wait_seconds: int = DEFAULT_CLAIM_WAIT_S) -> CycleResult:
    """One full agent cycle. Safe to call repeatedly (`--once`) or from a loop (`--foreground`)."""
    result = CycleResult()
    result.drained = outbox_mod.drain(identity)

    caps = capabilities_mod.build(cfg)
    heartbeat = fleet_client.heartbeat(identity, state="idle", capabilities=caps, leases=current_leases(), outbox_depth=outbox_mod.depth())
    result.heartbeat_ok = heartbeat.ok
    if not heartbeat.ok:
        log.warning("heartbeat failed (%s) - skipping claim this cycle", heartbeat.error)
        return result

    directive_outcome = apply_directives(heartbeat.directives, identity)
    if directive_outcome.drain_requested:
        log.info("drain directive received - not claiming new work this cycle")
        return result

    max_concurrent = int(caps.get("limits", {}).get("maxConcurrentRuns", 1))
    available = max_concurrent - len(current_leases())
    if available <= 0:
        log.info("already at max concurrency (%d) - not claiming", max_concurrent)
        return result

    claim_result = fleet_client.claim(identity, capabilities=caps, wait_seconds=wait_seconds, max_assignments=available)
    if not claim_result.ok:
        log.warning("claim failed: %s", claim_result.error)
        return result

    result.claimed = len(claim_result.assignments)
    for assignment in claim_result.assignments:
        result.executed.append(execute_assignment(assignment, identity, cfg, active_policy))

    outbox_mod.drain(identity)  # flush whatever this cycle just produced
    return result


def run_loop(
    identity: fleet_client.ClientIdentity,
    cfg: Config,
    active_policy: policy.Policy,
    *,
    once: bool = False,
    wait_seconds: int = DEFAULT_CLAIM_WAIT_S,
    sleep_between_s: float = DEFAULT_SLEEP_BETWEEN_S,
    max_iterations: int | None = None,
) -> None:
    iterations = 0
    while True:
        run_once(identity, cfg, active_policy, wait_seconds=wait_seconds)
        iterations += 1
        if once or (max_iterations is not None and iterations >= max_iterations):
            return
        time.sleep(sleep_between_s)
