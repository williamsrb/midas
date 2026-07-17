"""Preflight guard: ordered checks with auto-interrupt on the first fatal failure."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import config as config_mod
from . import disk, gitops, logging_setup, paths

log = logging_setup.get("preflight")


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    fatal: bool = True


def check_internet(cfg: config_mod.Config) -> CheckResult:
    targets = [cfg.jira.base_url, f"https://{cfg.git.host}"]
    failures = []
    for url in targets:
        try:
            requests.head(url, timeout=10, allow_redirects=True)
        except requests.RequestException as exc:
            failures.append(f"{url}: {type(exc).__name__}")
    if failures:
        return CheckResult("internet", False, "; ".join(failures))
    return CheckResult("internet", True, f"reached {', '.join(targets)}")


def check_disk(cfg: config_mod.Config) -> CheckResult:
    problems = disk.check(
        cfg.workspace_root, cfg.limits.max_workspace_gb, cfg.limits.min_free_disk_gb
    )
    if problems:
        return CheckResult("disk", False, "; ".join(problems))
    return CheckResult("disk", True, disk.summary(cfg.workspace_root))


def check_install_integrity(cfg: config_mod.Config) -> CheckResult:
    manifest = paths.manifest_file()
    if not manifest.is_file():
        return CheckResult("integrity", True, "no manifest (dev install) - skipped", fatal=False)
    pkg_root = manifest.parent
    bad = []
    for line in manifest.read_text().splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        expected, rel = parts[0], parts[1].strip().lstrip("./")
        target = pkg_root / rel
        if not target.is_file():
            bad.append(f"missing {rel}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            bad.append(f"modified {rel}")
    if bad:
        return CheckResult("integrity", False, f"corrupted installation: {', '.join(bad[:5])}")
    return CheckResult("integrity", True, "installation files verified")


def check_ssh_agent(cfg: config_mod.Config) -> CheckResult:
    sock = gitops.find_ssh_auth_sock()
    if not sock:
        return CheckResult(
            "ssh-agent", False,
            "no live ssh-agent socket found (needed for git clone over ssh)",
        )
    import os
    import subprocess
    rc = subprocess.run(
        ["ssh-add", "-l"], env={**os.environ, "SSH_AUTH_SOCK": sock},
        capture_output=True, timeout=10,
    ).returncode
    if rc != 0:
        return CheckResult("ssh-agent", False, f"agent at {sock} has no identities loaded")
    return CheckResult("ssh-agent", True, f"agent at {sock} with keys loaded")


def check_agent_cli(cfg: config_mod.Config) -> CheckResult:
    primary = cfg.agents.primary
    if not shutil.which(primary):
        if shutil.which(cfg.agents.fallback):
            return CheckResult(
                "agent-cli", True,
                f"{primary} missing, will use fallback {cfg.agents.fallback}", fatal=False,
            )
        return CheckResult("agent-cli", False, f"neither {primary} nor {cfg.agents.fallback} found on PATH")
    if cfg.agents.auth == "api_key":
        key_name = "ANTHROPIC_API_KEY" if primary == "claude" else "CURSOR_API_KEY"
        if not config_mod.load_credentials().get(key_name):
            return CheckResult(
                "agent-cli", False,
                f"agents.auth is 'api_key' but {key_name} is not in the credentials file "
                f"(rerun `midas setup`)",
            )
        return CheckResult("agent-cli", True, f"{primary} with {key_name} from credentials")
    if primary == "cursor-agent":
        import subprocess
        try:
            rc = subprocess.run(
                ["cursor-agent", "status"], capture_output=True, timeout=20
            ).returncode
        except (OSError, subprocess.TimeoutExpired):
            rc = -1
        if rc != 0:
            return CheckResult(
                "agent-cli", False,
                "cursor-agent found but not logged in (run `cursor-agent login`)",
            )
        return CheckResult("agent-cli", True, "cursor-agent logged in")
    if primary == "claude":
        claude_json = Path.home() / ".claude.json"
        try:
            data = json.loads(claude_json.read_text())
            email = data.get("oauthAccount", {}).get("emailAddress")
            if email:
                detail = f"claude authenticated as {email}"
                if data.get("primaryApiKey") and not data.get("hasAvailableSubscription"):
                    detail += (
                        " (Console API-key billing - headless runs fail if the org "
                        "credit balance is empty; a Pro/Max subscription login avoids this)"
                    )
                return CheckResult("agent-cli", True, detail)
        except (OSError, json.JSONDecodeError):
            pass
        return CheckResult("agent-cli", False, "claude CLI found but not authenticated (run `claude` once to log in)")
    return CheckResult("agent-cli", True, f"{primary} found on PATH")


def check_jira(cfg: config_mod.Config) -> CheckResult:
    token = config_mod.jira_api_token()
    if not token:
        return CheckResult(
            "jira", True,
            "no API token configured - will use agent+MCP fallback (degraded)", fatal=False,
        )
    from .jira_rest import JiraClient, JiraError
    try:
        me = JiraClient(cfg.jira.base_url, cfg.me.jira_email, token).myself()
        return CheckResult("jira", True, f"REST auth OK as {me.get('displayName', cfg.me.jira_email)}")
    except JiraError as exc:
        return CheckResult("jira", False, f"Jira REST auth failed: {exc}")


ALL_CHECKS = [
    check_internet,
    check_disk,
    check_install_integrity,
    check_ssh_agent,
    check_agent_cli,
    check_jira,
]


def run_all(cfg: config_mod.Config) -> list[CheckResult]:
    """Run every check (for `midas doctor`)."""
    results = []
    for fn in ALL_CHECKS:
        try:
            results.append(fn(cfg))
        except Exception as exc:  # a crashing check is a failing check
            results.append(CheckResult(fn.__name__.replace("check_", ""), False, f"check crashed: {exc}"))
    return results


def guard(cfg: config_mod.Config) -> tuple[bool, list[CheckResult]]:
    """Auto-interrupt guard for `midas run`: stops at the first fatal failure."""
    results = []
    for fn in ALL_CHECKS:
        try:
            res = fn(cfg)
        except Exception as exc:
            res = CheckResult(fn.__name__.replace("check_", ""), False, f"check crashed: {exc}")
        results.append(res)
        log.info("preflight %s: %s - %s", res.name, "OK" if res.ok else "FAIL", res.detail)
        if not res.ok and res.fatal:
            _write_blocked(res)
            return False, results
    _clear_blocked()
    return True, results


def _write_blocked(res: CheckResult) -> None:
    paths.blocked_file().parent.mkdir(parents=True, exist_ok=True)
    paths.blocked_file().write_text(json.dumps({
        "check": res.name,
        "detail": res.detail,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2))
    log.error("BLOCKED by %s: %s", res.name, res.detail)


def _clear_blocked() -> None:
    if paths.blocked_file().is_file():
        paths.blocked_file().unlink()


def blocked_status() -> dict | None:
    if paths.blocked_file().is_file():
        try:
            return json.loads(paths.blocked_file().read_text())
        except json.JSONDecodeError:
            return {"check": "unknown", "detail": "unreadable blocked.json"}
    return None
