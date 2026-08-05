import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from midas import kernel, paths, policy
from midas.config import Config
from midas.fleet import agent, client
from midas.fleet.assignments import Assignment, AssignmentLimits, WorkspaceSpec
from midas.fleet.client import ClientIdentity


@dataclass
class _FakeSyncResult:
    applied: list = field(default_factory=list)
    unchanged: list = field(default_factory=list)
    divergent: list = field(default_factory=list)


@pytest.fixture(autouse=True)
def no_real_harness_sync(monkeypatch):
    """Every test in this file runs offline - never let a real HTTP call escape."""
    monkeypatch.setattr(agent.sync_mod, "sync_from_morpheus", lambda *a, **k: _FakeSyncResult())


def _identity():
    return ClientIdentity(server_url="http://127.0.0.1:1", client_id="cl_test", client_secret="cs_test", private_key_pem="", public_key_pem="", profile="gold")


def _cfg(tmp_path) -> Config:
    c = Config()
    c.paths.workspace_root = str(tmp_path / "workspace")
    return c


def _permissive_policy(**overrides) -> policy.Policy:
    """Every test that isn't specifically about the workspace-roots check needs one that
    actually allows the ephemeral workspace `_prepare_workspace` creates - `policy.Policy()`'s
    own default (workspace_roots=[]) refuses every workspace, by design (nothing is in-bounds
    until the operator explicitly allowlists something)."""
    return policy.Policy(workspace_roots=["/"], **overrides)


def _assignment(**overrides):
    playbook = {
        "apiVersion": "morpheus/v1",
        "kind": "Playbook",
        "spec": {"defaults": {}, "runners": [{"id": "r1", "subscription": "claude", "permission": "edits"}], "nodes": [{"id": "a", "type": "definition", "runner": "r1"}]},
    }
    base = dict(
        assignment_id=f"as_{overrides.pop('suffix', '1')}",
        idempotency_key=overrides.pop("idempotency_key", "k1"),
        run_id=None,
        attempt=1,
        max_attempts=3,
        lease_until="2099-01-01T00:00:00Z",
        priority=50,
        kernel_version=overrides.pop("kernel_version", "0.2.0"),
        harness_version="9a1f",
        playbook=overrides.pop("playbook", playbook),
        inputs={"vars": {}, "documents": []},
        workspace=overrides.pop("workspace", WorkspaceSpec(kind="none", reuse=True)),
        limits=AssignmentLimits(),
    )
    base.update(overrides)
    return Assignment(**base)


def _install_fake_kernel(version="0.2.0"):
    version_dir = paths.kernel_dir() / version
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / kernel.BUNDLE_NAME).write_text("// fake kernel")


def _fake_kernel_run_success(request, on_event, **kwargs):
    on_event({"seq": 0, "at": "2026-01-01T00:00:00Z", "type": "run-started"})
    run_dir = Path(request["runDir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(json.dumps({"spendUsd": 1.25}))
    (run_dir / "BATON.md").write_text("# baton\n")
    return kernel.KernelOutcome(kernel.EXIT_SUCCEEDED, "succeeded")


def _fake_kernel_run_gate(request, on_event, **kwargs):
    run_dir = Path(request["runDir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(json.dumps({"spendUsd": 0.5, "gate": {"nodeId": "approve", "prompt": "Approve diff?"}}))
    return kernel.KernelOutcome(kernel.EXIT_GATE, "gate")


def _fake_kernel_run_failed(request, on_event, **kwargs):
    run_dir = Path(request["runDir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(json.dumps({"spendUsd": 0.1}))
    return kernel.KernelOutcome(kernel.EXIT_FAILED, "failed")


class TestExecuteAssignment:
    def test_a_successful_run_reports_a_completion_and_records_it_locally(self, tmp_path):
        _install_fake_kernel()
        result = agent.execute_assignment(_assignment(), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=_fake_kernel_run_success)
        assert result.outcome == "succeeded"

        from midas.fleet.outbox import list_entries

        entries = list_entries()
        completions = [e for e in entries if e.kind == "completion"]
        assert completions[0].payload["outcome"] == "succeeded"
        assert completions[0].payload["spendUsd"] == 1.25

        assert "k1" in agent.load_completed()

    def test_a_gate_outcome_reports_the_gate_details(self, tmp_path):
        _install_fake_kernel()
        result = agent.execute_assignment(_assignment(), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=_fake_kernel_run_gate)
        assert result.outcome == "gate"
        from midas.fleet.outbox import list_entries

        completion = [e for e in list_entries() if e.kind == "completion"][0]
        assert completion.payload["gate"] == {"nodeId": "approve", "prompt": "Approve diff?"}

    def test_a_failed_run_reports_failed(self, tmp_path):
        _install_fake_kernel()
        result = agent.execute_assignment(_assignment(), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=_fake_kernel_run_failed)
        assert result.outcome == "failed"

    def test_an_already_completed_idempotency_key_is_re_sent_not_re_run(self, tmp_path):
        agent._record_completed("k1", {"assignmentId": "as_old", "request": {"outcome": "succeeded", "spendUsd": 9, "batonDigest": "old", "artifacts": []}})
        called = []
        result = agent.execute_assignment(_assignment(), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=lambda *a, **k: called.append(1))
        assert result.outcome == "skipped-duplicate"
        assert called == []  # kernel never invoked
        from midas.fleet.outbox import list_entries

        assert list_entries()[0].payload["spendUsd"] == 9  # the OLD recorded request, not a new run

    def test_a_locked_assignment_is_skipped(self, tmp_path):
        lock_file = agent._acquire_lock("as_1")
        try:
            result = agent.execute_assignment(_assignment(), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
            assert result.outcome == "skipped-locked"
        finally:
            agent._release_lock(lock_file)

    def test_a_shell_node_is_nacked_when_policy_forbids_shell(self, tmp_path):
        playbook = {"apiVersion": "morpheus/v1", "kind": "Playbook", "spec": {"defaults": {}, "runners": [], "nodes": [{"id": "a", "type": "shell", "command": "ls"}]}}
        result = agent.execute_assignment(
            _assignment(playbook=playbook), _identity(), _cfg(tmp_path), _permissive_policy(shell=False), kernel_run=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run"))
        )
        assert result.outcome == "nacked"
        from midas.fleet.outbox import list_entries

        entry = list_entries()[0]
        assert entry.payload["action"] == "nack"
        assert entry.payload["reason"] == "policy-denied-shell"

    def test_an_uninstalled_kernel_version_is_nacked(self, tmp_path):
        result = agent.execute_assignment(
            _assignment(kernel_version="9.9.9"), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run"))
        )
        assert result.outcome == "nacked"
        from midas.fleet.outbox import list_entries

        assert list_entries()[0].payload["reason"] == "kernel-version-unavailable"

    def test_clears_the_lease_file_after_running(self, tmp_path):
        _install_fake_kernel()
        agent.execute_assignment(_assignment(), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=_fake_kernel_run_success)
        assert agent.current_leases() == []

    def test_events_land_in_the_outbox_during_the_run(self, tmp_path):
        _install_fake_kernel()
        agent.execute_assignment(_assignment(), _identity(), _cfg(tmp_path), _permissive_policy(), kernel_run=_fake_kernel_run_success)
        from midas.fleet.outbox import list_entries

        events = [e for e in list_entries() if e.kind == "event"]
        assert events[0].payload["type"] == "run-started"


class TestApplyDirectives:
    def test_drain_sets_the_flag(self):
        outcome = agent.apply_directives([{"kind": "drain"}], _identity())
        assert outcome.drain_requested is True

    def test_no_directives_is_a_no_op(self):
        outcome = agent.apply_directives([], _identity())
        assert outcome.drain_requested is False
        assert outcome.aborts == []

    def test_abort_is_recorded(self):
        outcome = agent.apply_directives([{"kind": "abort", "assignmentId": "as_1"}], _identity())
        assert outcome.aborts == ["as_1"]

    def test_upgrade_kernel_does_not_raise(self):
        agent.apply_directives([{"kind": "upgrade-kernel", "version": "0.3.0"}], _identity())  # just must not raise

    def test_sync_harness_calls_sync_from_morpheus(self, monkeypatch):
        called = []
        monkeypatch.setattr(agent.sync_mod, "sync_from_morpheus", lambda *a, **k: called.append(1) or _FakeSyncResult())
        agent.apply_directives([{"kind": "sync-harness"}], _identity())
        assert called == [1]

    def test_a_sync_harness_failure_does_not_raise(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(agent.sync_mod, "sync_from_morpheus", boom)
        agent.apply_directives([{"kind": "sync-harness"}], _identity())  # must not raise


class TestRunOnce:
    def test_skips_claim_when_heartbeat_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(client, "heartbeat", lambda *a, **k: client.HeartbeatResult(ok=False, error="down"))
        called = []
        monkeypatch.setattr(client, "claim", lambda *a, **k: called.append(1))
        result = agent.run_once(_identity(), _cfg(tmp_path), _permissive_policy())
        assert result.heartbeat_ok is False
        assert called == []

    def test_skips_claim_when_draining(self, tmp_path, monkeypatch):
        monkeypatch.setattr(client, "heartbeat", lambda *a, **k: client.HeartbeatResult(ok=True, directives=[{"kind": "drain"}], heartbeat_seconds=30))
        called = []
        monkeypatch.setattr(client, "claim", lambda *a, **k: called.append(1))
        agent.run_once(_identity(), _cfg(tmp_path), _permissive_policy())
        assert called == []

    def test_skips_claim_when_already_at_max_concurrency(self, tmp_path, monkeypatch):
        agent._record_lease(_assignment())
        try:
            monkeypatch.setattr(client, "heartbeat", lambda *a, **k: client.HeartbeatResult(ok=True, directives=[], heartbeat_seconds=30))
            called = []
            monkeypatch.setattr(client, "claim", lambda *a, **k: called.append(1))
            agent.run_once(_identity(), _cfg(tmp_path), _permissive_policy())
            assert called == []
        finally:
            agent._clear_lease("as_1")

    def test_claims_and_executes(self, tmp_path, monkeypatch):
        _install_fake_kernel()
        monkeypatch.setattr(client, "heartbeat", lambda *a, **k: client.HeartbeatResult(ok=True, directives=[], heartbeat_seconds=30))
        monkeypatch.setattr(client, "claim", lambda *a, **k: client.ClaimResult(ok=True, assignments=[_assignment()]))
        monkeypatch.setattr(kernel, "run", _fake_kernel_run_success)
        result = agent.run_once(_identity(), _cfg(tmp_path), _permissive_policy())
        assert result.claimed == 1
        assert result.executed[0].outcome == "succeeded"

    def test_claim_failure_is_reported_but_does_not_raise(self, tmp_path, monkeypatch):
        monkeypatch.setattr(client, "heartbeat", lambda *a, **k: client.HeartbeatResult(ok=True, directives=[], heartbeat_seconds=30))
        monkeypatch.setattr(client, "claim", lambda *a, **k: client.ClaimResult(ok=False, error="unreachable"))
        result = agent.run_once(_identity(), _cfg(tmp_path), _permissive_policy())
        assert result.claimed == 0
