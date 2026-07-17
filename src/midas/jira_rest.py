"""Deterministic Jira Cloud REST client (API token auth).

Uses API v2 for issue fetch (plain-text/wiki description and comments - no ADF
parsing needed) and the newer /search/jql endpoint for queries, with a fallback
to the legacy /search endpoint.
"""

from __future__ import annotations

from datetime import date

import requests


class JiraError(Exception):
    pass


ISSUE_FIELDS = [
    "summary", "description", "status", "issuetype", "priority",
    "assignee", "reporter", "created", "updated", "project", "comment", "labels",
]


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (email, token)
        self.session.headers["Accept"] = "application/json"

    def _get(self, path: str, **params) -> dict:
        try:
            resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise JiraError(f"request failed: {exc}") from exc
        if resp.status_code == 404:
            raise JiraError(f"not found: {path}")
        if resp.status_code in (401, 403):
            raise JiraError(f"auth failed ({resp.status_code}) for {path}")
        if not resp.ok:
            raise JiraError(f"HTTP {resp.status_code} for {path}: {resp.text[:200]}")
        return resp.json()

    def _post(self, path: str, payload: dict) -> dict:
        try:
            resp = self.session.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise JiraError(f"request failed: {exc}") from exc
        if not resp.ok:
            raise JiraError(f"HTTP {resp.status_code} for {path}: {resp.text[:200]}")
        return resp.json() if resp.text else {}

    # ------------------------------------------------------------------
    def myself(self) -> dict:
        return self._get("/rest/api/2/myself")

    def search(self, jql: str, max_results: int = 20) -> list[dict]:
        """Return issues (key, fields.summary/status/updated/labels) for a JQL query."""
        fields = "summary,status,updated,labels"
        try:
            data = self._get(
                "/rest/api/3/search/jql", jql=jql, fields=fields, maxResults=max_results
            )
        except JiraError as exc:
            if "not found" not in str(exc):
                raise
            # older deployments: legacy search endpoint
            data = self._get("/rest/api/2/search", jql=jql, fields=fields, maxResults=max_results)
        return data.get("issues", [])

    def issue(self, key: str) -> dict:
        return self._get(f"/rest/api/2/issue/{key}", fields=",".join(ISSUE_FIELDS))

    def add_comment(self, key: str, body: str, visibility_group: str = "") -> dict:
        """Add a comment; when visibility_group is set, only that Jira group sees it."""
        payload: dict = {"body": body}
        if visibility_group:
            payload["visibility"] = {"type": "group", "value": visibility_group}
        return self._post(f"/rest/api/2/issue/{key}/comment", payload)

    def transitions(self, key: str) -> list[dict]:
        return self._get(f"/rest/api/2/issue/{key}/transitions").get("transitions", [])

    def transition_to(self, key: str, status_name: str) -> bool:
        """Transition the issue to the transition/status matching status_name."""
        want = status_name.strip().lower()
        for tr in self.transitions(key):
            names = {tr.get("name", "").lower(), (tr.get("to") or {}).get("name", "").lower()}
            if want in names:
                self._post(f"/rest/api/2/issue/{key}/transitions", {"transition": {"id": tr["id"]}})
                return True
        return False


# ----------------------------------------------------------------------
# task.md rendering (same shape as the download-jira-task skill output)
# ----------------------------------------------------------------------

def _field(issue: dict, *path, default="") -> str:
    node = issue
    for part in path:
        if not isinstance(node, dict) or part not in node or node[part] is None:
            return default
        node = node[part]
    return node if isinstance(node, str) else str(node)


def render_task_md(issue: dict, base_url: str) -> str:
    f = issue.get("fields", {})
    key = issue.get("key", "")
    comments = (f.get("comment") or {}).get("comments", [])
    lines = [
        f"# {key} - {f.get('summary', '')}",
        "",
        f"**Jira:** {base_url}/browse/{key}",
        f"**Project:** {_field(f, 'project', 'name')} ({_field(f, 'project', 'key')})",
        f"**Type:** {_field(f, 'issuetype', 'name')}",
        f"**Status:** {_field(f, 'status', 'name')}",
        f"**Priority:** {_field(f, 'priority', 'name')}",
        f"**Reporter:** {_field(f, 'reporter', 'displayName')}",
        f"**Assignee:** {_field(f, 'assignee', 'displayName', default='Unassigned')}",
        f"**Labels:** {', '.join(f.get('labels') or []) or '-'}",
        f"**Created:** {f.get('created', '')}",
        f"**Updated:** {f.get('updated', '')}",
        "",
        "---",
        "",
        "## Description",
        "",
        f.get("description") or "_No description_",
        "",
        "---",
        "",
        f"## Comments ({len(comments)})",
        "",
    ]
    for c in sorted(comments, key=lambda c: c.get("created", "")):
        lines += [
            f"### Comment {c.get('id', '')} - "
            f"{_field(c, 'author', 'displayName')} - {c.get('created', '')}",
            "",
            c.get("body") or "",
            "",
        ]
    lines += ["---", "", f"*Exported from Jira on {date.today().isoformat()} by midas*", ""]
    return "\n".join(lines)
