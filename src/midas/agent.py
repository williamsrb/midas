"""CLI agent runner: headless claude / cursor-agent.

Providers (both must be supported): `claude` and `cursor-agent`, each in
subscription mode (login reused, no API key) or api_key mode (key stored in
the midas credentials file). Auto-approval is intentional; runs are confined
to the task's repo working directory, fully transcripted, and every call is
recorded in the LLM usage ledger.

Token economy (see docs/TOKEN_OPTIMIZATION.md): terse-output rules appended to
every prompt, thinking-effort cap, cheap models for glue work, and a subagent
spawn limit.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import logging_setup, paths, usage
from .config import Config, load_credentials

log = logging_setup.get("agent")

# MAX_THINKING_TOKENS caps Claude Code's thinking budget per request.
EFFORT_THINKING_TOKENS = {"low": 1024, "medium": 8192, "high": 31999}

TOKEN_RULES = """
## Output economy rules (midas)
- Be terse. No preamble, no restating instructions or file contents, no closing summary fluff.
- Reply with only what was asked; bullet fragments beat prose.
- Read files selectively (targeted ranges, grep) instead of whole files; never re-read unchanged files.
- Spawn at most {max_subagents} subagents, and only when clearly cheaper than doing the work inline.
"""


class AgentError(Exception):
    pass


@dataclass
class AgentResult:
    ok: bool
    text: str
    returncode: int
    agent: str
    meta: dict = field(default_factory=dict)  # usage/cost from the result message


def _subprocess_env(cfg: Config, agent_name: str) -> dict[str, str]:
    """Environment for nested agent CLIs.

    - Scrub harness variables (ANTHROPIC_BASE_URL, CLAUDE_CODE_*) that redirect
      a nested `claude` onto a parent agent session's proxy.
    - subscription auth: also scrub API keys so billing stays on the login.
    - api_key auth: inject the key stored in the midas credentials file.
    """
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("CLAUDE_CODE_") and k not in ("ANTHROPIC_BASE_URL", "CLAUDECODE")
    }
    if cfg.agents.auth == "subscription":
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("CURSOR_API_KEY", None)
    else:
        creds = load_credentials()
        if agent_name == "claude" and creds.get("ANTHROPIC_API_KEY"):
            env["ANTHROPIC_API_KEY"] = creds["ANTHROPIC_API_KEY"]
        if agent_name == "cursor-agent" and creds.get("CURSOR_API_KEY"):
            env["CURSOR_API_KEY"] = creds["CURSOR_API_KEY"]
    if agent_name == "claude":
        env["MAX_THINKING_TOKENS"] = str(
            EFFORT_THINKING_TOKENS.get(cfg.agents.effort, EFFORT_THINKING_TOKENS["medium"])
        )
    return env


def _claude_cmd(prompt: str, model: str, extra_dirs: list[Path]) -> list[str]:
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    for d in extra_dirs:
        cmd += ["--add-dir", str(d)]
    if paths.mcp_file().is_file():
        cmd += ["--mcp-config", str(paths.mcp_file())]
    return cmd


def _cursor_cmd(prompt: str) -> list[str]:
    return ["cursor-agent", "-p", prompt, "--output-format", "text", "--force"]


def run(
    prompt: str,
    cwd: Path,
    model: str,
    cfg: Config,
    transcript: Path | None = None,
    timeout_minutes: int | None = None,
    extra_dirs: list[Path] | None = None,
    context: str = "",
) -> AgentResult:
    """Run one headless agent turn; returns the agent's final text output."""
    timeout = (timeout_minutes or cfg.agents.stage_timeout_minutes) * 60
    extra_dirs = list(extra_dirs or []) + [paths.skills_dir(), paths.state_dir()]
    if paths.user_skills_dir().is_dir():
        extra_dirs.append(paths.user_skills_dir())
    if cfg.agents.token_saver:
        prompt = prompt + TOKEN_RULES.format(max_subagents=cfg.agents.max_subagents)
    order = [cfg.agents.primary, cfg.agents.fallback]
    last_error = ""

    for agent_name in order:
        if not agent_name or not shutil.which(agent_name):
            continue
        if agent_name == "claude":
            cmd = _claude_cmd(prompt, model, extra_dirs)
        else:
            cmd = _cursor_cmd(prompt)
        log.info("running %s (model=%s, cwd=%s, timeout=%ss)", agent_name, model, cwd, timeout)
        try:
            proc = subprocess.run(
                cmd, cwd=cwd, env=_subprocess_env(cfg, agent_name),
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            last_error = f"{agent_name} timed out after {timeout}s"
            log.error(last_error)
            continue
        except OSError as exc:
            last_error = f"{agent_name} failed to start: {exc}"
            log.error(last_error)
            continue

        if transcript is not None:
            transcript.parent.mkdir(parents=True, exist_ok=True)
            transcript.write_text(proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else ""))

        if agent_name == "claude":
            text, meta = _parse_stream_json_result(proc.stdout)
        else:
            text, meta = proc.stdout.strip(), {}

        _record_usage(agent_name, model, context, meta)

        if proc.returncode == 0 and text:
            return AgentResult(True, text, proc.returncode, agent_name, meta)
        last_error = (
            f"{agent_name} exited {proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()[:300]}"
        )
        log.error(last_error)

    return AgentResult(False, last_error or "no agent CLI available", -1, "none")


def _parse_stream_json_result(stdout: str) -> tuple[str, dict]:
    """Extract the final result text + usage meta from claude stream-json output."""
    result, meta = "", {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("type") == "result":
            result = msg.get("result") or ""
            meta = {
                "cost_usd": msg.get("total_cost_usd", 0.0) or 0.0,
                "duration_ms": msg.get("duration_ms", 0) or 0,
                "num_turns": msg.get("num_turns", 0) or 0,
                "session_id": msg.get("session_id", ""),
                "usage": msg.get("usage", {}) or {},
            }
    return result.strip(), meta


def _record_usage(agent_name: str, model: str, context: str, meta: dict) -> None:
    try:
        u = meta.get("usage", {})
        usage.record(
            source="midas",
            agent=agent_name,
            model=model,
            context=context,
            input_tokens=u.get("input_tokens", 0),
            output_tokens=u.get("output_tokens", 0),
            cache_read_tokens=u.get("cache_read_input_tokens", 0),
            cost_usd=meta.get("cost_usd", 0.0),
            duration_ms=meta.get("duration_ms", 0),
            num_turns=meta.get("num_turns", 0),
            session_id=meta.get("session_id", ""),
        )
    except OSError as exc:  # ledger writes must never break a run
        log.warning("usage ledger write failed: %s", exc)


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict:
    """Pull the last JSON object out of an agent's text answer."""
    match = None
    for match_ in _JSON_BLOCK_RE.finditer(text):
        match = match_
    if not match:
        raise AgentError(f"no JSON object found in agent output: {text[:200]}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise AgentError(f"invalid JSON in agent output: {exc}") from exc
