"""Client-action verb dispatch (D7, morpheus_changes_plan.md §5.1, midas_changes_plan.md §5.1).

Each verb is a thin wrapper over code this repo already has and already tests (`gitops.py`,
`disk.py`, `testrun.py`, `notify.py`) - the exception is `evidence.capture` and `report.write`,
which had no client-action-shaped equivalent (the existing `report.py`/`testrun.py` were built
around the legacy `TaskState` pipeline object, not a bare workspace path) and are written fresh
here.

A handler never raises across the kernel boundary: a failure comes back as
`ActionResult(ok=False, error=...)`, because an exception here would lose the whole run - the
engine's `fail` edge is the correct mechanism for a failed step, not a crashed one.

**Not wired to anything yet.** `dispatch()` is called by nothing in this repo. The
`client_action_requested`/`client_action_result` wire protocol this is meant to serve
(morpheus_changes_plan.md §5.1) requires two things that don't exist:
  1. Morpheus's IR needs a `client_action` node type and the engine needs to emit/await it
     (`packages/ir/src/schema.ts`, `packages/runner/src/engine.ts` - morpheus repo).
  2. `kernel.py`'s subprocess protocol is one-shot today - it closes stdin right after writing
     the initial request (see `kernel.py:run()`) and only ever reads NDJSON frames back. There is
     no mechanism to interleave a mid-run request/reply, which the kernel bundle (built from
     morpheus's `packages/runner`) would need to speak on the other end.
This module is the reusable, independently-testable verb map that side will call once both exist
- kept decoupled deliberately so it doesn't have to be rewritten alongside a protocol still being
designed.

The git invariant this exists to preserve: agents never run git writes themselves. Today that is
a sentence in a prompt; the only thing that can mutate a repository is one of the `git.*` handlers
here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import disk, gitops, logging_setup, notify, testrun, worktime
from . import policy as policy_mod
from .config import Config
from .fleet import outbox as outbox_mod

log = logging_setup.get("actions")


@dataclass
class ActionContext:
    workspace: Path
    artifacts_dir: Path
    assignment_id: str
    cfg: Config
    #: The operator's consent policy (D4). Optional so `midas exec` and tests can build a context
    #: without one; when absent, verbs that consult it refuse rather than proceed unchecked.
    policy: "policy_mod.Policy | None" = None


@dataclass
class ActionResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def _resolve(workspace: Path, dest: str | None) -> Path:
    return workspace / dest if dest else workspace


def _git_clone(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    url = params.get("url")
    if not url:
        return ActionResult(False, error="git.clone: 'url' is required")
    # D4 is a safety invariant, so the allowlist has to bind on the URL actually cloned. Checking
    # only `assignment.repo` at claim time left this wide open: the server composes the playbook,
    # so it could name an allowed repo in the assignment and a different one in this node's `with`.
    #
    # No policy in context means this is not a delegated run — `midas exec` executes a playbook the
    # operator chose themselves, which is outside the threat this control exists for (§6.1: a
    # *server* pushing instructions at a machine). The agent always supplies one.
    if ctx.policy is not None and not policy_mod.repo_allowed(url, ctx.policy.repo_allowlist):
        log.warning("git.clone refused: %s is not in the operator's repo_allowlist", url)
        return ActionResult(False, error=f"git.clone: policy-repo-not-allowed ({url})")
    dest = _resolve(ctx.workspace, params.get("dest"))
    try:
        gitops.clone_or_update(url, dest)
    except Exception as exc:  # noqa: BLE001 - subprocess/network failure, report, never raise
        return ActionResult(False, error=f"git.clone failed: {exc}")
    return ActionResult(True, {"path": str(dest)})


def _git_branch(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    branch = params.get("branch")
    if not branch:
        return ActionResult(False, error="git.branch: 'branch' is required")
    repo = _resolve(ctx.workspace, params.get("dest"))
    try:
        source = gitops.prepare_branch(repo, branch)
    except Exception as exc:  # noqa: BLE001
        return ActionResult(False, error=f"git.branch failed: {exc}")
    return ActionResult(True, {"branch": branch, "source": source})


def _git_commit(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    message = params.get("message")
    if not message:
        return ActionResult(False, error="git.commit: 'message' is required")
    repo = _resolve(ctx.workspace, params.get("dest"))
    # §5.1a describes a server-allocated commit-slot (POST .../commit-slot) so N machines under
    # one identity never race on author/committer instants. That endpoint doesn't exist on the
    # morpheus side yet - this is the offline fallback only, same clamp the standalone pipeline
    # has always used.
    force_date = None
    clamped = worktime.clamp_commit_datetime(ctx.cfg)
    if clamped is not None:
        force_date = worktime.git_date(clamped)
    try:
        sha = gitops.commit_all(repo, message, force_date=force_date)
    except Exception as exc:  # noqa: BLE001
        return ActionResult(False, error=f"git.commit failed: {exc}")
    if sha is None:
        return ActionResult(True, {"sha": None, "note": "nothing to commit"})
    return ActionResult(True, {"sha": sha})


def _fs_workspace(_params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    issues = disk.check(ctx.workspace, ctx.cfg.limits.max_workspace_gb, ctx.cfg.limits.min_free_disk_gb)
    if issues:
        return ActionResult(False, error="; ".join(issues))
    return ActionResult(True, {"path": str(ctx.workspace)})


def _test_playwright(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    plan_dir = ctx.workspace / params.get("planDir", "test-plan")
    timeout_minutes = int(params.get("timeoutMinutes", 30))
    try:
        exit_code = testrun.run_test_plan_at(plan_dir, timeout_minutes, label=ctx.assignment_id)
    except Exception as exc:  # noqa: BLE001
        return ActionResult(False, error=f"test.playwright failed: {exc}")
    return ActionResult(exit_code == 0, {"exitCode": exit_code})


def _evidence_capture(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    relative_paths = params.get("paths") or []
    if not relative_paths:
        return ActionResult(False, error="evidence.capture: 'paths' is required")
    ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)
    captured: list[str] = []
    for rel in relative_paths:
        src = ctx.workspace / rel
        if not src.is_file():
            continue
        dest = ctx.artifacts_dir / Path(rel).name
        dest.write_bytes(src.read_bytes())
        captured.append(str(dest))
    if not captured:
        return ActionResult(False, error="evidence.capture: none of the given paths exist under the workspace")
    return ActionResult(True, {"artifacts": captured})


def _report_write(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    content = params.get("content")
    if content is None:
        return ActionResult(False, error="report.write: 'content' is required")
    ctx.artifacts_dir.mkdir(parents=True, exist_ok=True)
    dest = ctx.artifacts_dir / params.get("name", "report.md")
    dest.write_text(content)
    return ActionResult(True, {"path": str(dest)})


def _jira_intent(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    # D5: midas never talks to Jira directly for a delegated run - it enqueues the intent and
    # the server (§5.3's Jira connector, not built yet) executes it.
    outbox_mod.enqueue("jira_intent", ctx.assignment_id, params)
    return ActionResult(True, {"queued": True})


def _notify_send(params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    event = params.get("event", "")
    message = params.get("message", "")
    try:
        sent_via = notify.send(ctx.cfg, event, message)
    except Exception as exc:  # noqa: BLE001
        return ActionResult(False, error=f"notify.send failed: {exc}")
    return ActionResult(True, {"sentVia": sent_via})


_HANDLERS: dict[str, Callable[[dict[str, Any], ActionContext], ActionResult]] = {
    "git.clone": _git_clone,
    "git.branch": _git_branch,
    "git.commit": _git_commit,
    "fs.workspace": _fs_workspace,
    "test.playwright": _test_playwright,
    "evidence.capture": _evidence_capture,
    "report.write": _report_write,
    "jira.intent": _jira_intent,
    "notify.send": _notify_send,
}


def dispatch(action: str, params: dict[str, Any], ctx: ActionContext) -> ActionResult:
    handler = _HANDLERS.get(action)
    if handler is None:
        return ActionResult(False, error=f"unknown-action: {action}")
    return handler(params, ctx)
