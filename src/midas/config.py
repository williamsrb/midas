"""Configuration: load/validate/save config.toml, credentials, defaults detection."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomlkit

from . import paths


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


@dataclass
class MeConfig:
    jira_email: str = ""
    jira_account_id: str = ""
    git_name: str = ""
    git_email: str = ""
    slack_user: str = ""


@dataclass
class JiraConfig:
    base_url: str = "https://seeds.atlassian.net"
    pickup: str = "status"  # "status" | "label"
    statuses: list[str] = field(default_factory=lambda: ["To Do", "Selected for Development", "Open"])
    label: str = "midas"
    recent_window: str = "-2d"  # JQL relative date for `updated >=`
    max_results: int = 20
    auto_transition: bool = False        # move the issue to in_progress_status when work starts
    in_progress_status: str = "In Progress"
    comment_group: str = ""              # Jira group that may see midas comments; empty = never post
    spec_check: bool = True              # verify spec sufficiency before planning


@dataclass
class GitConfig:
    host: str = "git.seeds.no"
    clone_url_template: str = "git@git.seeds.no:seeds/{project}.git"
    review_branch: str = "review"


@dataclass
class AgentsConfig:
    primary: str = "claude"          # "claude" | "cursor-agent"
    fallback: str = "cursor-agent"
    auth: str = "subscription"       # "subscription" | "api_key"
    planner_model: str = "opus"      # expensive: plans (the 10-80-10 "orchestrator")
    implementer_model: str = "sonnet"  # mid-tier: executes
    validator_model: str = "sonnet"  # reviews/validates the delivery
    utility_model: str = "haiku"     # cheap: env-detect fallback, jira fallback, glue
    effort: str = "medium"           # "low" | "medium" | "high" - thinking budget cap
    token_saver: bool = True         # append output-economy rules to every prompt
    max_subagents: int = 2           # hard cap agents may spawn per stage
    permission_mode: str = "skip"    # "skip" (auto-approve) | "docker" (reserved)
    stage_timeout_minutes: int = 40


@dataclass
class LimitsConfig:
    max_workspace_gb: float = 50.0
    min_free_disk_gb: float = 10.0
    max_concurrent_tasks: int = 1


@dataclass
class PathsConfig:
    workspace_root: str = str(Path.home() / "Workspace" / "Automated")


@dataclass
class CronConfig:
    interval_minutes: int = 15


@dataclass
class ReportConfig:
    post_jira_comment: bool = False


@dataclass
class WorktimeConfig:
    """Company working-time bracket; commits outside it get their git dates clamped."""
    enforce: bool = False
    start: str = "09:00"
    end: str = "17:00"
    days: list[str] = field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])


@dataclass
class NotifyConfig:
    """Outbound notifications (Slack webhook + WhatsApp via Meta Cloud API).

    Inbound commands are future work; see `midas docs notifications`.
    WHATSAPP_TOKEN lives in the credentials file, not here.
    """
    enabled: bool = False
    events: list[str] = field(default_factory=lambda: [
        "blocked", "awaiting_human", "spec_questions", "answered", "rework",
    ])
    slack_webhook: str = ""
    whatsapp_phone_id: str = ""   # Meta Cloud API phone-number ID (sender)
    whatsapp_to: str = ""         # your phone, E.164 without '+' (e.g. 4790000000)


@dataclass
class Config:
    me: MeConfig = field(default_factory=MeConfig)
    jira: JiraConfig = field(default_factory=JiraConfig)
    git: GitConfig = field(default_factory=GitConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    cron: CronConfig = field(default_factory=CronConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    worktime: WorktimeConfig = field(default_factory=WorktimeConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)

    @property
    def workspace_root(self) -> Path:
        return Path(self.paths.workspace_root).expanduser()


_SECTIONS = {
    "me": MeConfig,
    "jira": JiraConfig,
    "git": GitConfig,
    "agents": AgentsConfig,
    "limits": LimitsConfig,
    "paths": PathsConfig,
    "cron": CronConfig,
    "report": ReportConfig,
    "worktime": WorktimeConfig,
    "notify": NotifyConfig,
}


def load(path: Path | None = None) -> Config:
    path = path or paths.config_file()
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}. Run `midas setup` first.")
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc

    cfg = Config()
    for section, cls in _SECTIONS.items():
        data = raw.get(section, {})
        if not isinstance(data, dict):
            raise ConfigError(f"[{section}] must be a table in {path}")
        obj = getattr(cfg, section)
        for key, value in data.items():
            if not hasattr(obj, key):
                raise ConfigError(f"Unknown key '{key}' in [{section}] of {path}")
            default = getattr(cls(), key)
            if default is not None and not isinstance(value, type(default)) and not (
                isinstance(default, float) and isinstance(value, int)
            ):
                raise ConfigError(
                    f"Bad type for {section}.{key} in {path}: expected {type(default).__name__}"
                )
            setattr(obj, key, float(value) if isinstance(default, float) else value)
    validate(cfg)
    return cfg


def validate(cfg: Config) -> None:
    if cfg.jira.pickup not in ("status", "label"):
        raise ConfigError("jira.pickup must be 'status' or 'label'")
    if not cfg.jira.base_url.startswith("http"):
        raise ConfigError("jira.base_url must be an http(s) URL")
    if "{project}" not in cfg.git.clone_url_template:
        raise ConfigError("git.clone_url_template must contain {project}")
    if cfg.agents.permission_mode not in ("skip", "docker"):
        raise ConfigError("agents.permission_mode must be 'skip' or 'docker'")
    if cfg.agents.primary not in ("claude", "cursor-agent"):
        raise ConfigError("agents.primary must be 'claude' or 'cursor-agent'")
    if cfg.agents.auth not in ("subscription", "api_key"):
        raise ConfigError("agents.auth must be 'subscription' or 'api_key'")
    if cfg.agents.effort not in ("low", "medium", "high"):
        raise ConfigError("agents.effort must be 'low', 'medium' or 'high'")
    if cfg.cron.interval_minutes < 1 or cfg.cron.interval_minutes > 59:
        raise ConfigError("cron.interval_minutes must be between 1 and 59")
    if not cfg.me.jira_email:
        raise ConfigError("me.jira_email is required")
    hhmm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    if not hhmm.match(cfg.worktime.start) or not hhmm.match(cfg.worktime.end):
        raise ConfigError("worktime.start/end must be HH:MM")
    if cfg.worktime.start >= cfg.worktime.end:
        raise ConfigError("worktime.start must be before worktime.end")
    bad_days = set(cfg.worktime.days) - {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    if bad_days or not cfg.worktime.days:
        raise ConfigError("worktime.days must be a non-empty list of mon..sun")


def save(cfg: Config, path: Path | None = None) -> Path:
    path = path or paths.config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = tomlkit.document()
    doc.add(tomlkit.comment("Midas configuration - edit freely, then run `midas doctor`."))
    for section in _SECTIONS:
        table = tomlkit.table()
        obj = getattr(cfg, section)
        for key, value in vars(obj).items():
            table[key] = value
        doc[section] = table
    path.write_text(tomlkit.dumps(doc))
    return path


# --------------------------------------------------------------------------
# Credentials (KEY=VALUE file, chmod 600)
# --------------------------------------------------------------------------

def load_credentials() -> dict[str, str]:
    creds: dict[str, str] = {}
    path = paths.credentials_file()
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                creds[key.strip()] = value.strip()
    return creds


def _write_private(path: Path, content: str) -> None:
    """Write a secret-bearing file created 0600 from the start (no umask window)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    path.chmod(0o600)  # also fix pre-existing files with looser modes


def save_credential(key: str, value: str) -> None:
    creds = load_credentials()
    creds[key] = value
    _write_private(paths.credentials_file(), "".join(f"{k}={v}\n" for k, v in creds.items()))


def jira_api_token() -> str:
    return os.environ.get("MIDAS_JIRA_TOKEN") or load_credentials().get("JIRA_API_TOKEN", "")


# --------------------------------------------------------------------------
# Defaults detection
# --------------------------------------------------------------------------

def _git_config(key: str) -> str:
    try:
        out = subprocess.run(
            ["git", "config", "--global", key], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _claude_oauth_email() -> str:
    claude_json = Path.home() / ".claude.json"
    if claude_json.is_file():
        try:
            data = json.loads(claude_json.read_text())
            return data.get("oauthAccount", {}).get("emailAddress", "") or ""
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def detect_defaults() -> Config:
    """Build a Config pre-filled from the local environment."""
    cfg = Config()
    cfg.me.git_name = _git_config("user.name")
    cfg.me.git_email = _git_config("user.email")
    cfg.me.jira_email = _claude_oauth_email() or cfg.me.git_email
    if not shutil.which(cfg.agents.primary) and shutil.which(cfg.agents.fallback):
        cfg.agents.primary, cfg.agents.fallback = cfg.agents.fallback, cfg.agents.primary
    return cfg


def import_mcp_servers() -> list[str]:
    """Copy known MCP server definitions (e.g. from Cursor) into the midas MCP config.

    Returns the list of imported server names.
    """
    sources = [Path.home() / ".cursor" / "mcp.json"]
    servers: dict[str, dict] = {}
    for src in sources:
        if not src.is_file():
            continue
        try:
            data = json.loads(src.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for name, spec in data.get("mcpServers", {}).items():
            servers.setdefault(name, spec)

    existing: dict[str, dict] = {}
    if paths.mcp_file().is_file():
        try:
            existing = json.loads(paths.mcp_file().read_text()).get("mcpServers", {})
        except (json.JSONDecodeError, OSError):
            existing = {}
    merged = {**servers, **existing}  # user's own midas edits win
    if merged:
        # MCP specs can embed tokens (e.g. GitLab) - private from creation.
        _write_private(paths.mcp_file(), json.dumps({"mcpServers": merged}, indent=2))
    return sorted(merged)


ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")


def valid_issue_key(key: str) -> bool:
    return bool(ISSUE_KEY_RE.fullmatch(key))
