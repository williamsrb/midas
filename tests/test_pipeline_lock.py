"""The per-task lock prevents processing the same task twice concurrently."""

import fcntl

from midas import state
from midas.pipeline import Pipeline


def test_locked_task_is_skipped(cfg):
    st = state.create("LOCK-1", "locked task")
    st.dir.mkdir(parents=True, exist_ok=True)
    holder = open(st.dir / ".lock", "w")
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        final = Pipeline(cfg, st, dry_run=True).run()
        # untouched: still in its initial stage, no error recorded
        assert final.stage == "discovered"
        assert final.error == ""
    finally:
        fcntl.flock(holder, fcntl.LOCK_UN)
        holder.close()


def test_lock_released_after_run(cfg, tmp_path):
    st = state.create("LOCK-2", "runs and releases")
    st.task_md.parent.mkdir(parents=True, exist_ok=True)
    st.task_md.write_text("# LOCK-2\n\nno repo anywhere")
    st.advance("fetched")
    cfg.git.clone_url_template = f"file://{tmp_path}/nowhere/{{project}}.git"

    Pipeline(cfg, st, dry_run=True).run()  # blocks on missing repo

    probe = open(st.dir / ".lock", "w")
    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)  # must not raise
    fcntl.flock(probe, fcntl.LOCK_UN)
    probe.close()
