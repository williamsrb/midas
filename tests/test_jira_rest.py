import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from midas.jira_rest import JiraClient, JiraError, render_task_md

ISSUE = {
    "key": "RFD-123",
    "fields": {
        "summary": "Fix booking button",
        "description": "Button is broken.\n\nRepo: https://git.seeds.no/seeds/rfd",
        "status": {"name": "To Do"},
        "issuetype": {"name": "Bug"},
        "priority": {"name": "High"},
        "assignee": {"displayName": "Williams Ramos"},
        "reporter": {"displayName": "Analyst A"},
        "created": "2026-07-01T10:00:00.000+0000",
        "updated": "2026-07-15T10:00:00.000+0000",
        "project": {"name": "Rondane", "key": "RFD"},
        "labels": ["midas"],
        "comment": {"comments": [
            {"id": "1", "author": {"displayName": "Analyst A"},
             "created": "2026-07-02T09:00:00.000+0000",
             "body": "Review env: https://review.rfd.k8s.seeds.no/"},
        ]},
    },
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/rest/api/2/myself"):
            self._json(200, {"accountId": "abc", "displayName": "Williams Ramos"})
        elif self.path.startswith("/rest/api/2/issue/RFD-123"):
            self._json(200, ISSUE)
        elif self.path.startswith("/rest/api/3/search/jql"):
            self._json(200, {"issues": [{"key": "RFD-123", "fields": {"summary": "Fix booking button"}}]})
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_myself(server):
    client = JiraClient(server, "dev@example.com", "token")
    assert client.myself()["accountId"] == "abc"


def test_issue_and_render(server):
    client = JiraClient(server, "dev@example.com", "token")
    issue = client.issue("RFD-123")
    md = render_task_md(issue, server)
    assert md.startswith("# RFD-123 - Fix booking button")
    assert "https://git.seeds.no/seeds/rfd" in md
    assert "## Comments (1)" in md
    assert "review.rfd.k8s.seeds.no" in md


def test_search(server):
    client = JiraClient(server, "dev@example.com", "token")
    issues = client.search("assignee = currentUser()")
    assert issues[0]["key"] == "RFD-123"


def test_missing_issue_raises(server):
    client = JiraClient(server, "dev@example.com", "token")
    with pytest.raises(JiraError):
        client.issue("NOPE-1")
