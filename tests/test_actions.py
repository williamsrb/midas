import subprocess

import pytest

from midas import actions, config, gitops, notify, policy
from midas.fleet import outbox


def _run_git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def origin_repo(tmp_path):
    """A real local git repo to clone/branch/commit against - no mocking of git itself."""
    origin = tmp_path / "origin.git"
    _run_git(["init", "--bare", "-b", "main", str(origin)], cwd=tmp_path)

    seed = tmp_path / "seed"
    seed.mkdir()
    _run_git(["init", "-b", "main"], cwd=seed)
    _run_git(["config", "user.email", "seed@example.com"], cwd=seed)
    _run_git(["config", "user.name", "Seed"], cwd=seed)
    (seed / "README.md").write_text("hello\n")
    _run_git(["add", "README.md"], cwd=seed)
    _run_git(["commit", "-m", "seed"], cwd=seed)
    _run_git(["remote", "add", "origin", str(origin)], cwd=seed)
    _run_git(["push", "origin", "main"], cwd=seed)
    return f"file://{origin}"


@pytest.fixture
def ctx(tmp_path, cfg):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifacts = tmp_path / "artifacts"
    return actions.ActionContext(workspace=workspace, artifacts_dir=artifacts, assignment_id="as_1", cfg=cfg)


class TestGit:
    def test_clone_then_branch_then_commit(self, origin_repo, ctx):
        cloned = actions.dispatch("git.clone", {"url": origin_repo, "dest": "repo"}, ctx)
        assert cloned.ok
        repo_dir = ctx.workspace / "repo"
        assert (repo_dir / ".git").is_dir()

        branched = actions.dispatch("git.branch", {"branch": "feature/x", "dest": "repo"}, ctx)
        assert branched.ok
        assert branched.data["branch"] == "feature/x"

        (repo_dir / "NOTES.md").write_text("work\n")
        committed = actions.dispatch("git.commit", {"message": "add notes", "dest": "repo"}, ctx)
        assert committed.ok
        assert committed.data["sha"]

    def test_clone_requires_url(self, ctx):
        result = actions.dispatch("git.clone", {}, ctx)
        assert not result.ok
        assert "url" in result.error

    def test_commit_with_nothing_to_commit_reports_ok_with_no_sha(self, origin_repo, ctx):
        actions.dispatch("git.clone", {"url": origin_repo, "dest": "repo"}, ctx)
        result = actions.dispatch("git.commit", {"message": "noop", "dest": "repo"}, ctx)
        assert result.ok
        assert result.data["sha"] is None

    def test_commit_failure_is_a_result_not_an_exception(self, ctx):
        # No repo at all under ctx.workspace/repo - commit_all raises, dispatch must catch it.
        (ctx.workspace / "repo").mkdir()
        result = actions.dispatch("git.commit", {"message": "x", "dest": "repo"}, ctx)
        assert not result.ok
        assert result.error


class TestFsWorkspace:
    def test_ok_when_within_limits(self, ctx):
        result = actions.dispatch("fs.workspace", {}, ctx)
        assert result.ok
        assert result.data["path"] == str(ctx.workspace)

    def test_reports_disk_issues_as_a_failure_not_an_exception(self, ctx, monkeypatch):
        monkeypatch.setattr("midas.actions.disk.check", lambda *a, **k: ["workspace over quota"])
        result = actions.dispatch("fs.workspace", {}, ctx)
        assert not result.ok
        assert "over quota" in result.error


class TestTestPlaywright:
    def test_missing_plan_dir_is_a_failure_not_an_exception(self, ctx):
        result = actions.dispatch("test.playwright", {"planDir": "nope"}, ctx)
        assert not result.ok
        assert "no Playwright specs" in result.error

    def test_exit_code_zero_is_ok(self, ctx, monkeypatch):
        monkeypatch.setattr("midas.actions.testrun.run_test_plan_at", lambda *a, **k: 0)
        result = actions.dispatch("test.playwright", {}, ctx)
        assert result.ok
        assert result.data["exitCode"] == 0

    def test_nonzero_exit_code_is_not_ok_but_not_an_exception(self, ctx, monkeypatch):
        monkeypatch.setattr("midas.actions.testrun.run_test_plan_at", lambda *a, **k: 1)
        result = actions.dispatch("test.playwright", {}, ctx)
        assert not result.ok
        assert result.data["exitCode"] == 1


class TestEvidenceCapture:
    def test_copies_existing_files_into_the_artifacts_dir(self, ctx):
        (ctx.workspace / "screenshot.png").write_bytes(b"\x89PNG")
        result = actions.dispatch("evidence.capture", {"paths": ["screenshot.png"]}, ctx)
        assert result.ok
        assert len(result.data["artifacts"]) == 1
        assert (ctx.artifacts_dir / "screenshot.png").read_bytes() == b"\x89PNG"

    def test_requires_paths(self, ctx):
        result = actions.dispatch("evidence.capture", {}, ctx)
        assert not result.ok

    def test_all_paths_missing_is_a_failure(self, ctx):
        result = actions.dispatch("evidence.capture", {"paths": ["does-not-exist.png"]}, ctx)
        assert not result.ok


class TestReportWrite:
    def test_writes_content_to_the_artifacts_dir(self, ctx):
        result = actions.dispatch("report.write", {"content": "# hi", "name": "r.md"}, ctx)
        assert result.ok
        assert (ctx.artifacts_dir / "r.md").read_text() == "# hi"

    def test_requires_content(self, ctx):
        result = actions.dispatch("report.write", {}, ctx)
        assert not result.ok


class TestJiraIntent:
    def test_enqueues_into_the_outbox_rather_than_calling_jira_directly(self, ctx):
        result = actions.dispatch("jira.intent", {"issueKey": "RFD-1", "comment": "done"}, ctx)
        assert result.ok
        entries = outbox.list_entries()
        assert len(entries) == 1
        assert entries[0].kind == "jira_intent"


class TestNotifySend:
    def test_delegates_to_notify_send(self, ctx, monkeypatch):
        monkeypatch.setattr(notify, "send", lambda cfg, event, message: ["slack"])
        result = actions.dispatch("notify.send", {"event": "done", "message": "hi"}, ctx)
        assert result.ok
        assert result.data["sentVia"] == ["slack"]


class TestDispatch:
    def test_unknown_action(self, ctx):
        result = actions.dispatch("unknown.verb", {}, ctx)
        assert not result.ok
        assert "unknown-action" in result.error


class TestGitCloneRespectsThePolicy:
    """D4 must bind on the URL actually cloned, not only on `assignment.repo` at claim time.

    The server composes the playbook, so before this it could name an allowed repo in the
    assignment and a different one in the `git.clone` node's `with` — the allowlist was
    advisory. These are negative-path tests: nothing previously asserted that `_git_clone`
    consults the policy at all.
    """

    def _ctx(self, tmp_path, allowlist):
        return actions.ActionContext(
            workspace=tmp_path,
            artifacts_dir=tmp_path / "artifacts",
            assignment_id="as_1",
            cfg=config.Config(),
            policy=policy.Policy(repo_allowlist=allowlist),
        )

    def test_a_url_outside_the_allowlist_is_refused(self, tmp_path):
        ctx = self._ctx(tmp_path, ["https://git.example.com/team/*"])
        result = actions.dispatch("git.clone", {"url": "https://evil.example.net/x.git"}, ctx)
        assert result.ok is False
        assert "policy-repo-not-allowed" in (result.error or "")

    def test_an_empty_allowlist_refuses_every_url(self, tmp_path):
        ctx = self._ctx(tmp_path, [])
        result = actions.dispatch("git.clone", {"url": "https://git.example.com/team/x.git"}, ctx)
        assert result.ok is False
        assert "policy-repo-not-allowed" in (result.error or "")

    def test_a_context_without_a_policy_is_local_exec_and_is_not_gated(self, tmp_path, monkeypatch):
        # `midas exec` runs a playbook the operator chose; the control is for server-pushed work.
        seen = {}
        monkeypatch.setattr(gitops, "clone_or_update", lambda url, dest: seen.update(url=url))
        ctx = actions.ActionContext(
            workspace=tmp_path, artifacts_dir=tmp_path / "artifacts", assignment_id="as_1", cfg=config.Config()
        )
        result = actions.dispatch("git.clone", {"url": "https://anywhere.example/x.git"}, ctx)
        assert result.ok is True
        assert seen["url"] == "https://anywhere.example/x.git"
