from midas.fleet.assignments import (
    Assignment,
    ClaimResponse,
    CompleteRequest,
    Gate,
    NackRequest,
)


def _raw_assignment(**overrides):
    base = {
        "assignmentId": "as_1",
        "idempotencyKey": "jira:RFD-1:round1",
        "attempt": 1,
        "maxAttempts": 3,
        "leaseUntil": "2026-08-04T09:42:00Z",
        "priority": 50,
        "kernelVersion": "0.2.0",
        "harnessVersion": "9a1f",
        "playbook": {"apiVersion": "morpheus/v1", "kind": "Playbook"},
        "inputs": {"vars": {"issueKey": "RFD-1"}, "documents": [{"path": "task.md", "sha256": "abc", "size": 12}]},
        "workspace": {"kind": "git", "repoUrl": "git@git.seeds.no:seeds/x.git", "branch": "RFD-1", "reuse": True},
        "limits": {"maxUsd": 5, "maxMinutes": 90, "permissionCeiling": "edits"},
        "routing": {"plan": {"subscription": "claude", "model": "opus"}},
    }
    base.update(overrides)
    return base


class TestAssignmentFromJson:
    def test_round_trips_the_documented_wire_shape(self):
        a = Assignment.from_json(_raw_assignment())
        assert a.assignment_id == "as_1"
        assert a.idempotency_key == "jira:RFD-1:round1"
        assert a.inputs["vars"] == {"issueKey": "RFD-1"}
        assert a.inputs["documents"][0].sha256 == "abc"
        assert a.workspace.kind == "git"
        assert a.workspace.repo_url == "git@git.seeds.no:seeds/x.git"
        assert a.limits.permission_ceiling == "edits"
        assert a.routing["plan"].model == "opus"

    def test_a_workspace_less_assignment_parses(self):
        a = Assignment.from_json(_raw_assignment(workspace={"kind": "none", "reuse": True}))
        assert a.workspace.kind == "none"
        assert a.workspace.repo_url is None

    def test_missing_limits_defaults_to_all_none(self):
        a = Assignment.from_json(_raw_assignment(limits={}))
        assert a.limits.max_usd is None
        assert a.limits.permission_ceiling is None

    def test_a_gate_resume_assignment_carries_run_id(self):
        a = Assignment.from_json(_raw_assignment(runId="run_abc"))
        assert a.run_id == "run_abc"

    def test_no_run_id_defaults_to_none(self):
        a = Assignment.from_json(_raw_assignment())
        assert a.run_id is None


class TestClaimResponse:
    def test_parses_a_list_of_assignments(self):
        response = ClaimResponse.from_json({"assignments": [_raw_assignment(), _raw_assignment(assignmentId="as_2")]})
        assert len(response.assignments) == 2
        assert response.assignments[1].assignment_id == "as_2"

    def test_empty_assignments_list(self):
        assert ClaimResponse.from_json({"assignments": []}).assignments == []


class TestCompleteRequest:
    def test_to_json_matches_the_documented_shape(self):
        req = CompleteRequest(outcome="succeeded", spend_usd=1.5, baton_digest="sha256:abc")
        assert req.to_json() == {"outcome": "succeeded", "spendUsd": 1.5, "batonDigest": "sha256:abc", "artifacts": []}

    def test_gate_outcome_includes_the_gate_object(self):
        req = CompleteRequest(outcome="gate", spend_usd=0.5, baton_digest="sha", gate=Gate(node_id="approve", prompt="Approve diff?"))
        assert req.to_json()["gate"] == {"nodeId": "approve", "prompt": "Approve diff?"}


class TestNackRequest:
    def test_to_json_omits_detail_when_absent(self):
        assert NackRequest(reason="policy-denied", retryable=True).to_json() == {"reason": "policy-denied", "retryable": True}

    def test_to_json_includes_detail_when_given(self):
        req = NackRequest(reason="workspace-error", retryable=True, detail="disk full")
        assert req.to_json() == {"reason": "workspace-error", "retryable": True, "detail": "disk full"}
