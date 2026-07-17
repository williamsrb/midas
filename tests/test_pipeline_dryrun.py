"""End-to-end dry run of the deterministic stages against a local git remote:
fetch(file) -> env_detect(template) -> clone -> branch, stopping before agents.
"""

import subprocess

import pytest

from midas import state
from midas.pipeline import Pipeline

TASK_MD = """# FAKE-1 - Add a friendly greeting

## Description
Add a "Hello from midas" section to README.md.

## Comments (1)
Review environment: https://review.fake.k8s.seeds.no/
"""


def git(*args, cwd=None):
    subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


@pytest.fixture
def local_remote(tmp_path):
    """A bare repo named 'fake' with one commit on main."""
    remotes = tmp_path / "remotes"
    seed = tmp_path / "seed"
    bare = remotes / "fake.git"
    bare.mkdir(parents=True)
    git("init", "--bare", "-b", "main", str(bare))
    seed.mkdir()
    git("init", "-b", "main", str(seed))
    (seed / "README.md").write_text("# fake project\n")
    (seed / "package.json").write_text("{}")
    git("add", "-A", cwd=seed)
    git("commit", "-m", "init", cwd=seed)
    git("remote", "add", "origin", str(bare), cwd=seed)
    git("push", "origin", "main", cwd=seed)
    return remotes


def test_dry_run_reaches_branch_ready(cfg, local_remote, tmp_path):
    cfg.git.clone_url_template = f"file://{local_remote}/{{project}}.git"

    st = state.create("FAKE-1", "Add a friendly greeting")
    st.task_md.parent.mkdir(parents=True, exist_ok=True)
    st.task_md.write_text(TASK_MD)
    st.advance("fetched", "from test")

    final = Pipeline(cfg, st, dry_run=True).run()

    assert final.stage == "branch_ready", final.error
    env = final.env()
    assert env["project"] == "fake"
    assert env["sources"]["repo_url"] == "template"
    assert env["review_url"].startswith("https://review.fake")
    assert env["stack"] == "node"
    repo = cfg.workspace_root / "fake"
    assert (repo / ".git").is_dir()
    head = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    assert head == "FAKE-1"


def test_no_repo_blocks_task(cfg, tmp_path):
    cfg.git.clone_url_template = f"file://{tmp_path}/nowhere/{{project}}.git"
    st = state.create("GONE-9", "mystery task")
    st.task_md.parent.mkdir(parents=True, exist_ok=True)
    st.task_md.write_text("# GONE-9\n\nNo repo mentioned anywhere.")
    st.advance("fetched", "from test")

    final = Pipeline(cfg, st, dry_run=True).run()
    assert final.stage == "blocked"
    assert "repository" in final.error
