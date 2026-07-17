"""Deterministic detectors over task text (description + comments)."""

from __future__ import annotations

import re

# git.seeds.no/seeds/rfd, https://git.seeds.no/seeds/rfd.git, git@git.seeds.no:seeds/rfd.git
_GIT_URL_RE = re.compile(
    r"(?:git@|https?://)?(?P<host>git\.[\w.-]+)[:/](?P<path>[\w./-]+?)(?:\.git)?(?=[\s)\]\"'<>,;|]|$)",
    re.MULTILINE,
)

_REVIEW_URL_RE = re.compile(
    r"https?://[\w.-]*(?:review|staging|qa|test)[\w.-]*(?:\.k8s)?[\w.-]*(?::\d+)?(?:/[\w./?=&%#-]*)?",
    re.IGNORECASE,
)


def detect_repo_url(text: str, host: str = "git.seeds.no") -> str:
    """Find a repo reference in task text and normalize to the ssh clone form."""
    for m in _GIT_URL_RE.finditer(text):
        if m.group("host") != host:
            continue
        path = m.group("path").strip("/")
        # drop web-UI suffixes like /-/merge_requests/1, /-/tree/x, /blob/...
        path = re.split(r"/-/|/(?:blob|tree|commit|merge_requests|pipelines)(?:/|$)", path)[0]
        path = path.strip("/")
        if "/" in path:
            return f"git@{host}:{path}.git"
    return ""


def detect_review_url(text: str) -> str:
    m = _REVIEW_URL_RE.search(text)
    if not m:
        return ""
    return m.group(0).rstrip(".,;)")


def project_from_url(ssh_url: str) -> str:
    """git@git.seeds.no:seeds/rfd.git -> rfd"""
    tail = ssh_url.rsplit("/", 1)[-1] if "/" in ssh_url else ssh_url.rsplit(":", 1)[-1]
    return tail.removesuffix(".git")


def project_key_from_issue(issue_key: str) -> str:
    """RFD-123 -> rfd (candidate project name for the clone-url template)."""
    return issue_key.split("-", 1)[0].lower()
