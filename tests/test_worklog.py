"""B0: durable per-run state, orphan detection, and the 30-day archive."""

from datetime import datetime, timedelta, timezone

import pytest

from midas import worklog


@pytest.fixture
def runs(tmp_path, monkeypatch):
    root = tmp_path / "runs"
    root.mkdir()
    monkeypatch.setattr(worklog.paths, "runs_dir", lambda: root)
    return root


def _open(runs, run_id="run-1", assignment_id="as_1", **kw):
    d = runs / run_id
    worklog.start(d, run_id=run_id, assignment_id=assignment_id, **kw)
    return d


def _age(run_dir, days):
    """Backdate the log so archiving can be tested without waiting 30 days."""
    meta = worklog.read_front_matter(run_dir)
    meta["updatedAt"] = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    body = worklog._body(run_dir)
    worklog._write(run_dir, meta, body)


class TestProgressLog:
    def test_start_creates_a_readable_log_with_parseable_front_matter(self, runs):
        d = _open(runs, task_key="RFD-1", playbook_id="jira-to-commit")
        text = worklog.progress_path(d).read_text()
        assert "# Run run-1" in text and "RFD-1" in text
        meta = worklog.read_front_matter(d)
        assert meta["status"] == "active" and meta["assignmentId"] == "as_1"

    def test_each_step_advances_the_resume_point(self, runs):
        d = _open(runs)
        worklog.step(d, "clone-repo", "started")
        worklog.step(d, "branch-repo", "started")
        meta = worklog.read_front_matter(d)
        assert meta["steps"] == 2
        assert meta["resumePoint"] == "branch-repo"
        assert "clone-repo" in worklog.progress_path(d).read_text()

    def test_finish_closes_it(self, runs):
        d = _open(runs)
        worklog.finish(d, "succeeded")
        meta = worklog.read_front_matter(d)
        assert meta["status"] == "finished" and meta["outcome"] == "succeeded"

    def test_reopening_keeps_history_and_counts_the_attempt(self, runs):
        d = _open(runs)
        worklog.step(d, "clone-repo", "started")
        _open(runs)  # same run, second attempt
        meta = worklog.read_front_matter(d)
        assert meta["attempts"] == 2
        assert meta["steps"] == 1  # history preserved, not reset
        assert "clone-repo" in worklog.progress_path(d).read_text()

    def test_step_on_a_log_that_was_never_opened_is_a_no_op(self, runs):
        worklog.step(runs / "ghost", "x", "started")  # must not raise
        assert not worklog.progress_path(runs / "ghost").exists()


class TestMemory:
    def test_facts_round_trip(self, runs):
        d = _open(runs)
        worklog.remember(d, "repoUrl", "https://git.example.com/team/x.git")
        worklog.remember(d, "branch", "feature/RFD-1")
        assert worklog.read_memory(d) == {
            "repoUrl": "https://git.example.com/team/x.git",
            "branch": "feature/RFD-1",
        }

    def test_no_memory_file_is_an_empty_dict(self, runs):
        assert worklog.read_memory(runs / "nope") == {}


class TestOrphans:
    def test_an_unfinished_run_with_no_lease_is_an_orphan(self, runs):
        _open(runs)
        assert [o.run_id for o in worklog.orphans()] == ["run-1"]

    def test_a_run_someone_still_holds_is_not_an_orphan(self, runs):
        _open(runs)
        assert worklog.orphans(held_assignment_ids={"as_1"}) == []

    def test_a_finished_run_is_not_an_orphan(self, runs):
        d = _open(runs)
        worklog.finish(d, "succeeded")
        assert worklog.orphans() == []


class TestArchive:
    def test_a_fresh_orphan_is_left_alone(self, runs):
        _open(runs)
        assert worklog.archive_abandoned() == []

    def test_an_orphan_past_the_cutoff_is_archived(self, runs):
        d = _open(runs)
        _age(d, 31)
        archived = worklog.archive_abandoned()
        assert [a.run_id for a in archived] == ["run-1"]
        assert worklog.read_front_matter(d)["status"] == "archived"
        assert "Archived" in worklog.progress_path(d).read_text()

    def test_a_held_assignment_is_never_archived_however_old(self, runs):
        d = _open(runs)
        _age(d, 400)
        assert worklog.archive_abandoned(held_assignment_ids={"as_1"}) == []

    def test_archiving_is_idempotent(self, runs):
        d = _open(runs)
        _age(d, 31)
        worklog.archive_abandoned()
        assert worklog.archive_abandoned() == []  # already archived, not re-reported

    def test_archived_runs_are_listable(self, runs):
        d = _open(runs)
        _age(d, 31)
        worklog.archive_abandoned()
        assert [s.run_id for s in worklog.list_archived()] == ["run-1"]


class TestDiscard:
    def test_only_an_archived_run_can_be_discarded(self, runs):
        _open(runs)
        assert worklog.discard("run-1") is False
        assert (runs / "run-1").is_dir()

    def test_discarding_an_archived_run_removes_it(self, runs):
        d = _open(runs)
        worklog.remember(d, "repoUrl", "x")
        _age(d, 31)
        worklog.archive_abandoned()
        assert worklog.discard("run-1") is True
        assert not d.exists()

    def test_discarding_something_that_does_not_exist_is_false(self, runs):
        assert worklog.discard("nope") is False


class TestDiscardIsNotTraversable:
    """`discard()` deletes a directory tree and `run_id` reaches it from an operator action in
    morpheus — i.e. from off-machine. The first version of this function resolved
    `runs_dir() / "../precious"` and deleted it. Same class as the blob/profile traversal."""

    def test_discard_refuses_a_traversing_run_id(self, runs, tmp_path):
        outside = tmp_path / "precious"
        outside.mkdir()
        (outside / "important.txt").write_text("do not delete")
        # Make it look exactly like an archived run, so only the segment check can save it.
        worklog.start(outside, run_id="x", assignment_id="a")
        meta = worklog.read_front_matter(outside)
        meta["status"] = "archived"
        worklog._write(outside, meta, worklog._body(outside))

        assert worklog.discard("../precious") is False
        assert (outside / "important.txt").exists()

    @pytest.mark.parametrize("bad", ["..", ".", "", "a/b", "a\\b", "../../etc"])
    def test_every_non_segment_is_refused(self, runs, bad):
        assert worklog.discard(bad) is False

    def test_a_symlinked_run_directory_is_refused(self, runs, tmp_path):
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        worklog.start(outside, run_id="x", assignment_id="a")
        meta = worklog.read_front_matter(outside)
        meta["status"] = "archived"
        worklog._write(outside, meta, worklog._body(outside))
        (runs / "sneaky").symlink_to(outside)

        assert worklog.discard("sneaky") is False
        assert outside.exists()
