import os

import pytest

from midas import paths, policy


def allowed_assignment(**overrides) -> policy.Assignment:
    base = dict(
        node_types=["definition"],
        uses_shell=False,
        actions=["git.clone"],
        permission="edits",
        repo="git@git.seeds.no:seeds/foo.git",
        workspace=str(paths.state_dir()),
        budget_usd=1.0,
    )
    base.update(overrides)
    return policy.Assignment(**base)


def node_policy(**overrides) -> policy.Policy:
    base = dict(
        repo_allowlist=["git@git.seeds.no:seeds/*"],
        workspace_roots=[str(paths.state_dir())],
    )
    base.update(overrides)
    return policy.Policy(**base)


class TestWriteDefault:
    def test_creates_a_node_profile_with_the_documented_safe_defaults(self):
        path = policy.write_default("node", workspace_root="/tmp/ws")
        assert path.is_file()
        loaded = policy.load()
        assert loaded.shell is False
        assert loaded.permission_ceiling == "edits"
        assert loaded.max_usd_per_run == 5.0
        assert loaded.workspace_roots == ["/tmp/ws"]

    def test_host_profile_is_more_permissive_but_shell_stays_false(self):
        policy.write_default("host", workspace_root="/tmp/host-ws")
        loaded = policy.load()
        assert loaded.shell is False  # D14 - not unconditional
        assert loaded.permission_ceiling == "full"

    def test_never_overwrites_an_existing_policy(self):
        policy.write_default("node", workspace_root="/tmp/first")
        policy.write_default("host", workspace_root="/tmp/second")
        loaded = policy.load()
        assert loaded.workspace_roots == ["/tmp/first"]

    def test_load_without_a_policy_raises(self):
        with pytest.raises(policy.PolicyError):
            policy.load()


class TestCheckAssignment:
    def test_allows_a_well_formed_assignment(self):
        decision = policy.check_assignment(allowed_assignment(), node_policy())
        assert decision.allowed
        assert decision.reason is None

    def test_refuses_an_unlisted_node_type(self):
        decision = policy.check_assignment(allowed_assignment(node_types=["shell_direct"]), node_policy())
        assert not decision.allowed
        assert decision.reason == "policy-denied-node-type"

    def test_refuses_a_shell_node_by_default(self):
        decision = policy.check_assignment(allowed_assignment(uses_shell=True), node_policy())
        assert decision.reason == "policy-denied-shell"

    def test_allows_shell_only_when_explicitly_enabled(self):
        decision = policy.check_assignment(allowed_assignment(uses_shell=True), node_policy(shell=True))
        assert decision.allowed

    def test_refuses_a_known_action_the_operator_did_not_allow(self):
        decision = policy.check_assignment(
            allowed_assignment(actions=["jira.intent"]), node_policy(actions=["git.clone"])
        )
        assert decision.reason == "policy-denied-action"

    def test_refuses_an_action_midas_does_not_implement_at_all(self):
        decision = policy.check_assignment(allowed_assignment(actions=["delete.everything"]), node_policy())
        assert decision.reason == "policy-unsupported-action"

    def test_refuses_full_permission_when_ceiling_is_edits(self):
        decision = policy.check_assignment(allowed_assignment(permission="full"), node_policy(permission_ceiling="edits"))
        assert decision.reason == "policy-permission-ceiling"

    def test_allows_full_permission_when_ceiling_is_full(self):
        decision = policy.check_assignment(allowed_assignment(permission="full"), node_policy(permission_ceiling="full"))
        assert decision.allowed

    def test_refuses_a_repo_outside_the_allowlist(self):
        decision = policy.check_assignment(allowed_assignment(repo="git@evil.example:not/allowed.git"), node_policy())
        assert decision.reason == "policy-repo-not-allowed"

    def test_allows_a_repo_matching_the_wildcard_pattern(self):
        decision = policy.check_assignment(
            allowed_assignment(repo="git@git.seeds.no:seeds/anything.git"), node_policy()
        )
        assert decision.allowed

    def test_a_missing_repo_is_not_itself_a_refusal(self):
        decision = policy.check_assignment(allowed_assignment(repo=None), node_policy())
        assert decision.allowed

    def test_refuses_a_workspace_outside_the_roots(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        decision = policy.check_assignment(allowed_assignment(workspace=str(outside)), node_policy(workspace_roots=[str(tmp_path / "roots")]))
        assert decision.reason == "policy-workspace-outside-roots"

    def test_refuses_a_dotdot_escape_from_an_allowed_root(self, tmp_path):
        root = tmp_path / "roots" / "project"
        root.mkdir(parents=True)
        escaping = str(root / ".." / ".." / "etc")
        decision = policy.check_assignment(allowed_assignment(workspace=escaping), node_policy(workspace_roots=[str(tmp_path / "roots")]))
        assert decision.reason == "policy-workspace-outside-roots"

    def test_refuses_a_symlink_escape_from_an_allowed_root(self, tmp_path):
        real_outside = tmp_path / "outside"
        real_outside.mkdir()
        root = tmp_path / "roots"
        root.mkdir()
        link = root / "escape-link"
        os.symlink(real_outside, link)
        decision = policy.check_assignment(allowed_assignment(workspace=str(link)), node_policy(workspace_roots=[str(root)]))
        assert decision.reason == "policy-workspace-outside-roots"

    def test_allows_a_workspace_nested_inside_an_allowed_root(self, tmp_path):
        root = tmp_path / "roots"
        nested = root / "a" / "b"
        nested.mkdir(parents=True)
        decision = policy.check_assignment(allowed_assignment(workspace=str(nested)), node_policy(workspace_roots=[str(root)]))
        assert decision.allowed

    def test_refuses_a_budget_over_the_cap(self):
        decision = policy.check_assignment(allowed_assignment(budget_usd=100.0), node_policy(max_usd_per_run=5.0))
        assert decision.reason == "policy-budget-exceeded"

    def test_no_budget_named_is_not_a_refusal(self):
        decision = policy.check_assignment(allowed_assignment(budget_usd=None), node_policy(max_usd_per_run=5.0))
        assert decision.allowed


class TestSummary:
    def test_reports_the_fields_the_server_linter_needs(self):
        p = node_policy(shell=False, permission_ceiling="edits", max_usd_per_run=5.0)
        summary = p.summary()
        assert summary == {
            "shell": False,
            "permissionCeiling": "edits",
            "repoAllowlist": ["git@git.seeds.no:seeds/*"],
            "maxUsdPerRun": 5.0,
        }
