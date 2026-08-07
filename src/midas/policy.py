"""Client-side consent policy (`ARCHITECTURE_SPLIT_PLAN.md` §6.2, D4 - the safety invariant).

Midas is not obedient. Every assignment from a Morpheus server is checked against a policy
the operator owns and the server can neither read nor write. A violation is a refusal with
a machine-readable reason, never a silent downgrade: if midas quietly ran a `full`-permission
step as `edits`, the operator would see a green run that did not do what the playbook said.
The reason string is what drives the server's fallback decision, so the taxonomy below is a
wire contract, not just a log message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomlkit

from . import paths

# The closed, versioned action vocabulary midas implements (spec §4.2). An action outside
# this list is one midas has never heard of, distinct from one it knows but isn't allowed.
KNOWN_ACTIONS = [
    "git.clone", "git.branch", "git.commit", "fs.workspace",
    "test.playwright", "evidence.capture", "report.write", "jira.intent",
    "notify.send",
]

DEFAULT_NODE_TYPES = [
    # Mirrors @morpheus/ir's real NODE_TYPES (schema.ts) exactly, plus `client_action` - the one
    # entry with no corresponding schema type yet (Phase 5). Found stale during S4b: this list
    # was missing `shell` (a real, existing node type) entirely, which meant any playbook with a
    # shell node was refused as policy-denied-node-type before the dedicated shell-permission
    # check (`policy.shell`) below ever ran.
    "definition", "skill_invoke", "decision", "emit",
    "human_gate", "critique", "shell", "client_action",
]

PERMISSION_RANK = {"readonly": 0, "edits": 1, "full": 2}


class PolicyError(Exception):
    pass


@dataclass
class Assignment:
    """What a delegated unit of work needs checked against policy.

    Phase 4 (the real assignment wire format a claimed server task carries) is not built
    yet - this is the minimal shape `check_assignment` needs today, derived from what the
    refusal taxonomy in §2.4 implies it must check. Treat this as provisional: it will need
    to grow once Phase 4 defines the actual wire format.
    """

    node_types: list[str] = field(default_factory=list)
    uses_shell: bool = False
    actions: list[str] = field(default_factory=list)
    permission: str = "readonly"  # "readonly" | "edits" | "full"
    repo: str | None = None
    workspace: str = ""
    budget_usd: float | None = None


@dataclass
class Decision:
    allowed: bool
    reason: str | None = None  # one of the policy-* codes below, when refused


@dataclass
class Policy:
    server_url: str = ""
    pin_sha256: str = ""
    node_types: list[str] = field(default_factory=lambda: list(DEFAULT_NODE_TYPES))
    shell: bool = False
    actions: list[str] = field(default_factory=lambda: list(KNOWN_ACTIONS))
    permission_ceiling: str = "edits"
    max_usd_per_run: float = 5.0
    max_minutes: int = 90
    repo_allowlist: list[str] = field(default_factory=list)
    workspace_roots: list[str] = field(default_factory=list)
    auto_apply_harness: bool = True
    require_harness_signature: bool = True
    harness_profiles: list[str] = field(default_factory=lambda: ["gold"])
    auto_upgrade_kernel: bool = True
    require_kernel_signature: bool = True

    def summary(self) -> dict:
        """For capability advertisement (§4.2) - lets the server's linter warn at authoring time."""
        return {
            "shell": self.shell,
            "permissionCeiling": self.permission_ceiling,
            "repoAllowlist": list(self.repo_allowlist),
            "maxUsdPerRun": self.max_usd_per_run,
        }


def _profile_defaults(profile: str, workspace_root: str) -> Policy:
    """The two shipped profiles (§2.4's table). `shell` is `false` in both - the host profile
    is more permissive, not unconditional (D14): if the host accepted server-authored shell
    nodes, a compromised Morpheus could run arbitrary commands on itself via its own queue."""
    if profile == "host":
        return Policy(shell=False, permission_ceiling="full", max_usd_per_run=5.0, workspace_roots=[workspace_root])
    return Policy(shell=False, permission_ceiling="edits", max_usd_per_run=5.0, workspace_roots=[workspace_root])


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _toml_list(values: list[str]) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


TOML_TEMPLATE = """\
# Midas consent policy.
#
# The operator owns this file. The Morpheus server can neither read nor write it - every
# assignment is checked here before anything runs, and a refusal is always a nack with a
# reason, never a silent downgrade.

[server]
url = "{server_url}"
pin_sha256 = "{pin_sha256}"  # certificate/pubkey pin - a changed server identity halts everything

[accept]
node_types = {node_types}
shell = {shell}  # server-authored shell nodes: DENIED by default
actions = {actions}
permission_ceiling = "{permission_ceiling}"  # a higher-permission runner is refused, never downgraded
max_usd_per_run = {max_usd_per_run}
max_minutes = {max_minutes}

[workspace]
repo_allowlist = {repo_allowlist}
roots = {workspace_roots}  # nothing outside these paths is ever touched

[harness]
auto_apply = {auto_apply_harness}
require_signature = {require_harness_signature}
profiles = {harness_profiles}

[kernel]
auto_upgrade = {auto_upgrade_kernel}
require_signature = {require_kernel_signature}
"""


def write_default(profile: str = "node", workspace_root: str = "~/Workspace/Automated") -> Path:
    """Create policy.toml with the safe defaults for `profile`, unless one already exists.

    Never overwrites - the operator may have hand-edited it, and clobbering that on a
    `midas setup` re-run would be exactly the kind of silent damage this file exists to
    prevent everywhere else in the system.
    """
    path = paths.policy_file()
    if path.is_file():
        return path
    policy = _profile_defaults(profile, workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        TOML_TEMPLATE.format(
            server_url=policy.server_url,
            pin_sha256=policy.pin_sha256,
            node_types=_toml_list(policy.node_types),
            shell=_toml_bool(policy.shell),
            actions=_toml_list(policy.actions),
            permission_ceiling=policy.permission_ceiling,
            max_usd_per_run=policy.max_usd_per_run,
            max_minutes=policy.max_minutes,
            repo_allowlist=_toml_list(policy.repo_allowlist),
            workspace_roots=_toml_list(policy.workspace_roots),
            auto_apply_harness=_toml_bool(policy.auto_apply_harness),
            require_harness_signature=_toml_bool(policy.require_harness_signature),
            harness_profiles=_toml_list(policy.harness_profiles),
            auto_upgrade_kernel=_toml_bool(policy.auto_upgrade_kernel),
            require_kernel_signature=_toml_bool(policy.require_kernel_signature),
        )
    )
    return path


def load() -> Policy:
    path = paths.policy_file()
    if not path.is_file():
        raise PolicyError(f"no policy at {path} - run `midas setup` first")
    doc = tomlkit.parse(path.read_text())
    server = doc.get("server", {})
    accept = doc.get("accept", {})
    workspace = doc.get("workspace", {})
    harness = doc.get("harness", {})
    kernel = doc.get("kernel", {})
    return Policy(
        server_url=str(server.get("url", "")),
        pin_sha256=str(server.get("pin_sha256", "")),
        node_types=list(accept.get("node_types", DEFAULT_NODE_TYPES)),
        shell=bool(accept.get("shell", False)),
        actions=list(accept.get("actions", KNOWN_ACTIONS)),
        permission_ceiling=str(accept.get("permission_ceiling", "edits")),
        max_usd_per_run=float(accept.get("max_usd_per_run", 5.0)),
        max_minutes=int(accept.get("max_minutes", 90)),
        repo_allowlist=list(workspace.get("repo_allowlist", [])),
        workspace_roots=list(workspace.get("roots", [])),
        auto_apply_harness=bool(harness.get("auto_apply", True)),
        require_harness_signature=bool(harness.get("require_signature", True)),
        harness_profiles=list(harness.get("profiles", ["gold"])),
        auto_upgrade_kernel=bool(kernel.get("auto_upgrade", True)),
        require_kernel_signature=bool(kernel.get("require_signature", True)),
    )


def _within_roots(workspace: str, roots: list[str]) -> bool:
    """True iff `workspace` resolves - symlinks and `..` both included - to a path under one
    of `roots`. Resolving both sides catches a `..` escape in the path text and a symlink
    that points outside the allowed roots the same way, since `Path.resolve()` walks both."""
    if not workspace:
        return False
    try:
        resolved = Path(workspace).expanduser().resolve()
    except OSError:
        return False
    for root in roots:
        try:
            root_resolved = Path(root).expanduser().resolve()
        except OSError:
            continue
        if resolved == root_resolved or root_resolved in resolved.parents:
            return True
    return False


def repo_allowed(repo: str | None, allowlist: list[str]) -> bool:
    """Does `repo` match the operator's allowlist?

    An assignment with no repo at all is not itself a refusal (see
    `test_a_missing_repo_is_not_itself_a_refusal`) — plenty of work touches no repository. That
    used to leave a hole, because the allowlist was only ever consulted here, against
    `assignment.repo`. It is now also consulted in `actions._git_clone` against the URL actually
    being cloned, so an assignment that omits `repo` no longer buys unchecked cloning.
    """
    if repo is None:
        return True
    for pattern in allowlist:
        if pattern.endswith("/*") and repo.startswith(pattern[:-1]):
            return True
        if repo == pattern:
            return True
    return False


def check_assignment(assignment: Assignment, policy: Policy | None = None) -> Decision:
    """Allow, or refuse with one of the `policy-*` reason codes (spec §2.4)."""
    policy = policy or load()

    for node_type in assignment.node_types:
        if node_type not in policy.node_types:
            return Decision(False, "policy-denied-node-type")

    if assignment.uses_shell and not policy.shell:
        return Decision(False, "policy-denied-shell")

    for action in assignment.actions:
        if action not in KNOWN_ACTIONS:
            return Decision(False, "policy-unsupported-action")
        if action not in policy.actions:
            return Decision(False, "policy-denied-action")

    if PERMISSION_RANK.get(assignment.permission, 0) > PERMISSION_RANK.get(policy.permission_ceiling, 1):
        return Decision(False, "policy-permission-ceiling")

    if not repo_allowed(assignment.repo, policy.repo_allowlist):
        return Decision(False, "policy-repo-not-allowed")

    if not _within_roots(assignment.workspace, policy.workspace_roots):
        return Decision(False, "policy-workspace-outside-roots")

    if assignment.budget_usd is not None and assignment.budget_usd > policy.max_usd_per_run:
        return Decision(False, "policy-budget-exceeded")

    return Decision(True)
