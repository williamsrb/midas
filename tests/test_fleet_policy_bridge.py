from midas import policy
from midas.fleet.assignments import Assignment, AssignmentLimits, WorkspaceSpec
from midas.fleet.policy_bridge import build_policy_assignment


def _assignment(nodes=None, runners=None, workspace=None, limits=None, budget=None):
    playbook = {
        "apiVersion": "morpheus/v1",
        "kind": "Playbook",
        "spec": {
            "defaults": {"budget": budget or {}},
            "runners": runners if runners is not None else [{"id": "implementer", "subscription": "claude", "permission": "edits"}],
            "nodes": nodes if nodes is not None else [{"id": "step1", "type": "definition", "runner": "implementer"}],
        },
    }
    return Assignment(
        assignment_id="as_1",
        idempotency_key="k1",
        attempt=1,
        max_attempts=3,
        lease_until="2026-01-01T00:00:00Z",
        priority=50,
        kernel_version="0.2.0",
        harness_version="9a1f",
        playbook=playbook,
        inputs={"vars": {}, "documents": []},
        workspace=workspace or WorkspaceSpec(kind="none", reuse=True),
        limits=limits or AssignmentLimits(),
    )


class TestBuildPolicyAssignment:
    def test_derives_node_types(self):
        nodes = [{"id": "a", "type": "definition"}, {"id": "b", "type": "human_gate"}, {"id": "c", "type": "definition"}]
        result = build_policy_assignment(_assignment(nodes=nodes, runners=[]), "/ws")
        assert result.node_types == ["definition", "human_gate"]

    def test_detects_a_shell_node(self):
        nodes = [{"id": "a", "type": "shell", "command": "ls"}]
        result = build_policy_assignment(_assignment(nodes=nodes, runners=[]), "/ws")
        assert result.uses_shell is True

    def test_detects_a_shell_subscription_runner_even_without_a_shell_node(self):
        runners = [{"id": "r1", "subscription": "shell", "permission": "full"}]
        nodes = [{"id": "a", "type": "definition", "runner": "r1"}]
        result = build_policy_assignment(_assignment(nodes=nodes, runners=runners), "/ws")
        assert result.uses_shell is True

    def test_no_shell_when_neither_is_present(self):
        result = build_policy_assignment(_assignment(), "/ws")
        assert result.uses_shell is False

    def test_actions_is_always_empty_today(self):
        result = build_policy_assignment(_assignment(), "/ws")
        assert result.actions == []

    def test_permission_is_the_maximum_across_referenced_runners(self):
        runners = [
            {"id": "r1", "subscription": "cursor", "permission": "readonly"},
            {"id": "r2", "subscription": "claude", "permission": "full"},
        ]
        nodes = [{"id": "a", "type": "definition", "runner": "r1"}, {"id": "b", "type": "definition", "runner": "r2"}]
        result = build_policy_assignment(_assignment(nodes=nodes, runners=runners), "/ws")
        assert result.permission == "full"

    def test_permission_defaults_to_readonly_with_no_runners(self):
        result = build_policy_assignment(_assignment(nodes=[{"id": "a", "type": "human_gate"}], runners=[]), "/ws")
        assert result.permission == "readonly"

    def test_repo_comes_from_a_git_workspace(self):
        ws = WorkspaceSpec(kind="git", repo_url="git@git.seeds.no:seeds/x.git", branch="main")
        result = build_policy_assignment(_assignment(workspace=ws), "/ws")
        assert result.repo == "git@git.seeds.no:seeds/x.git"

    def test_repo_is_none_for_a_workspace_less_assignment(self):
        result = build_policy_assignment(_assignment(workspace=WorkspaceSpec(kind="none")), "/ws")
        assert result.repo is None

    def test_uses_the_given_workspace_path_not_anything_from_the_wire(self):
        result = build_policy_assignment(_assignment(), "/actual/local/path")
        assert result.workspace == "/actual/local/path"

    def test_budget_prefers_the_assignment_limits_over_the_playbook_default(self):
        result = build_policy_assignment(_assignment(limits=AssignmentLimits(max_usd=3.0), budget={"maxUsd": 5.0}), "/ws")
        assert result.budget_usd == 3.0

    def test_budget_falls_back_to_the_playbook_defaults_budget(self):
        result = build_policy_assignment(_assignment(limits=AssignmentLimits(), budget={"maxUsd": 5.0}), "/ws")
        assert result.budget_usd == 5.0

    def test_budget_is_none_when_neither_is_set(self):
        result = build_policy_assignment(_assignment(), "/ws")
        assert result.budget_usd is None


class TestEndToEndPolicyDecision:
    def test_a_shell_node_is_refused_when_the_policy_forbids_shell(self, tmp_path):
        write_policy = policy.Policy(shell=False, workspace_roots=[str(tmp_path)])
        nodes = [{"id": "a", "type": "shell", "command": "rm -rf /"}]
        assignment = build_policy_assignment(_assignment(nodes=nodes, runners=[]), str(tmp_path / "ws"))
        decision = policy.check_assignment(assignment, write_policy)
        assert decision.allowed is False
        assert decision.reason == "policy-denied-shell"

    def test_a_full_permission_playbook_is_refused_under_an_edits_ceiling(self, tmp_path):
        write_policy = policy.Policy(permission_ceiling="edits", workspace_roots=[str(tmp_path)])
        runners = [{"id": "r1", "subscription": "claude", "permission": "full"}]
        nodes = [{"id": "a", "type": "definition", "runner": "r1"}]
        assignment = build_policy_assignment(_assignment(nodes=nodes, runners=runners), str(tmp_path / "ws"))
        decision = policy.check_assignment(assignment, write_policy)
        assert decision.allowed is False
        assert decision.reason == "policy-permission-ceiling"

    def test_an_ordinary_assignment_within_policy_is_allowed(self, tmp_path):
        write_policy = policy.Policy(permission_ceiling="edits", shell=False, workspace_roots=[str(tmp_path)])
        assignment = build_policy_assignment(_assignment(), str(tmp_path / "ws"))
        decision = policy.check_assignment(assignment, write_policy)
        assert decision.allowed is True
