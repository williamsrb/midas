"""Git operations over SSH: agent discovery, clone, branch, commit."""

from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path

from . import logging_setup

log = logging_setup.get("gitops")


class GitError(Exception):
    pass


def find_ssh_auth_sock() -> str:
    """Locate a live ssh-agent socket. Cron does not inherit SSH_AUTH_SOCK,
    so fall back to well-known locations (GNOME keyring, gcr, ssh-agent tmp)."""
    candidates = []
    if os.environ.get("SSH_AUTH_SOCK"):
        candidates.append(os.environ["SSH_AUTH_SOCK"])
    uid = os.getuid()
    candidates += [
        f"/run/user/{uid}/keyring/ssh",
        f"/run/user/{uid}/gcr/ssh",
    ]
    candidates += sorted(glob.glob("/tmp/ssh-*/agent.*"))

    fallback = ""
    for sock in candidates:
        if not os.path.exists(sock):
            continue
        rc = subprocess.run(
            ["ssh-add", "-l"],
            env={**os.environ, "SSH_AUTH_SOCK": sock},
            capture_output=True,
            timeout=10,
        ).returncode
        if rc == 0:  # agent alive, has keys
            return sock
        if rc == 1 and not fallback:  # agent alive, no keys yet
            fallback = sock
    return fallback


def git_env() -> dict[str, str]:
    env = dict(os.environ)
    sock = find_ssh_auth_sock()
    if sock:
        env["SSH_AUTH_SOCK"] = sock
    env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
    return env


def _git(
    args: list[str], cwd: Path | None = None, timeout: int = 300,
    extra_env: dict[str, str] | None = None,
) -> str:
    env = git_env()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:500]}")
    return proc.stdout.strip()


def ls_remote_ok(url: str) -> bool:
    try:
        subprocess.run(
            ["git", "ls-remote", "--heads", url],
            env=git_env(), capture_output=True, text=True, timeout=60, check=True,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def clone_or_update(url: str, dest: Path) -> Path:
    if (dest / ".git").is_dir():
        log.info("repo already cloned at %s, fetching", dest)
        _git(["fetch", "--prune", "origin"], cwd=dest)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("cloning %s -> %s", url, dest)
    _git(["clone", url, str(dest)], timeout=1800)
    return dest


def default_branch(repo: Path) -> str:
    try:
        ref = _git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=repo)
        return ref.rsplit("/", 1)[-1]
    except GitError:
        for name in ("main", "master", "develop"):
            try:
                _git(["show-ref", "--verify", f"refs/remotes/origin/{name}"], cwd=repo)
                return name
            except GitError:
                continue
    raise GitError(f"cannot determine default branch of {repo}")


def prepare_branch(repo: Path, branch: str) -> str:
    """Checkout the task branch: reuse remote/local branch, else create from default."""
    _git(["fetch", "--prune", "origin"], cwd=repo)
    remote_exists = bool(
        subprocess.run(
            ["git", "show-ref", "--verify", f"refs/remotes/origin/{branch}"],
            cwd=repo, env=git_env(), capture_output=True,
        ).returncode == 0
    )
    local_exists = bool(
        subprocess.run(
            ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
            cwd=repo, env=git_env(), capture_output=True,
        ).returncode == 0
    )
    if local_exists:
        _git(["checkout", branch], cwd=repo)
        if remote_exists:
            _git(["merge", "--ff-only", f"origin/{branch}"], cwd=repo)
        source = "local"
    elif remote_exists:
        _git(["checkout", "-b", branch, f"origin/{branch}"], cwd=repo)
        source = "remote"
    else:
        base = default_branch(repo)
        _git(["checkout", "-B", branch, f"origin/{base}"], cwd=repo)
        source = f"created from origin/{base}"
    log.info("branch %s ready (%s)", branch, source)
    return source


def is_dirty(repo: Path) -> bool:
    return bool(_git(["status", "--porcelain"], cwd=repo))


def commit_all(repo: Path, message: str, force_date: str | None = None) -> str | None:
    """Stage everything and commit. Returns the commit sha, or None if no changes.

    force_date (git date string) clamps author+committer dates, used to keep
    commits inside the company working-time bracket.
    """
    if not is_dirty(repo):
        return None
    extra = {"GIT_AUTHOR_DATE": force_date, "GIT_COMMITTER_DATE": force_date} if force_date else None
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-m", message], cwd=repo, extra_env=extra)
    return _git(["rev-parse", "HEAD"], cwd=repo)


def current_branch(repo: Path) -> str:
    return _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
