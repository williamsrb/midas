"""Bridges a wire `Assignment` (its opaque playbook IR) to `policy.Assignment` (S4b, closes G9
from the S4 grounding pass).

`policy.check_assignment` needs `node_types`, `uses_shell`, `actions`, `permission` derived from
the *actual demand* of the playbook - trusting `assignment.limits.permissionCeiling` (the
server's own declared ceiling) instead of walking the IR would defeat D4, the one policy control
marked irreversible: a server could simply declare a low ceiling while shipping a playbook that
needs more, and nothing would catch the mismatch.

`actions` is always empty today: the IR's node types (`@morpheus/ir`'s `NODE_TYPES`) do not yet
include a `client_action` node - that's Phase 5. There is nothing to derive an action list from
until that node type exists; returning `[]` is honest, not a shortcut.
"""

from __future__ import annotations

from .. import policy
from .assignments import Assignment


def build_policy_assignment(assignment: Assignment, workspace_path: str) -> policy.Assignment:
    """Walks `assignment.playbook`'s IR to build the `policy.Assignment` `check_assignment`
    checks against. `workspace_path` is the actual local directory the caller plans to run in -
    not derivable from the wire assignment alone, since the wire shape only carries a
    `WorkspaceSpec` (kind/repoUrl/branch), not a resolved local path."""
    spec = assignment.playbook.get("spec", {})
    nodes = spec.get("nodes", [])
    runners = {r.get("id"): r for r in spec.get("runners", []) if r.get("id")}

    node_types = sorted({str(n["type"]) for n in nodes if n.get("type")})
    uses_shell = any(n.get("type") == "shell" for n in nodes) or any(r.get("subscription") == "shell" for r in runners.values())

    permission = "readonly"
    for node in nodes:
        runner = runners.get(node.get("runner"))
        if not runner:
            continue
        candidate = runner.get("permission")
        if candidate and policy.PERMISSION_RANK.get(candidate, 0) > policy.PERMISSION_RANK.get(permission, 0):
            permission = candidate

    repo = assignment.workspace.repo_url if assignment.workspace.kind == "git" else None

    budget_usd = assignment.limits.max_usd
    if budget_usd is None:
        budget_usd = spec.get("defaults", {}).get("budget", {}).get("maxUsd")

    return policy.Assignment(
        node_types=node_types,
        uses_shell=uses_shell,
        actions=[],
        permission=permission,
        repo=repo,
        workspace=workspace_path,
        budget_usd=budget_usd,
    )
