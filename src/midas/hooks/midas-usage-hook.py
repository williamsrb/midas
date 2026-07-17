#!/usr/bin/env python3
"""Midas LLM-usage hook - standalone (no midas import; runs under any python3).

Appends one JSONL line per finished agent turn to the midas usage ledger
(~/.local/state/midas/logs/llm-usage.jsonl), so interactive Claude Code and
Cursor sessions are tracked alongside midas' own headless runs. Same idea as
the ~/.cursor/hooks worklog scripts, but feeding the midas ledger.

Usage (registered by `midas touch`):
  Claude Code  settings.json  Stop hook:        midas-usage-hook.py stop
  Cursor       hooks.json     stop hook:        midas-usage-hook.py cursor-stop

Never fails the hosting agent: always prints {} and exits 0.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def ledger_path() -> Path:
    state = os.environ.get("MIDAS_STATE_DIR") or os.path.join(
        os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")), "midas"
    )
    return Path(state) / "logs" / "llm-usage.jsonl"


def write_entry(entry: dict) -> None:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def claude_transcript_usage(transcript_path: str) -> dict:
    """Sum output tokens across assistant turns; keep the last turn's context size."""
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "num_turns": 0}
    try:
        with open(transcript_path) as fh:
            for line in fh:
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                u = (msg.get("message") or {}).get("usage")
                if not isinstance(u, dict):
                    continue
                totals["num_turns"] += 1
                totals["output_tokens"] += u.get("output_tokens", 0) or 0
                totals["input_tokens"] = u.get("input_tokens", 0) or 0
                totals["cache_read_tokens"] = u.get("cache_read_input_tokens", 0) or 0
    except OSError:
        pass
    return totals


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "stop"
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}

        entry = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "agent": "claude" if mode == "stop" else "cursor-agent",
            "source": "claude-interactive" if mode == "stop" else "cursor-interactive",
            "model": payload.get("model", ""),
            "context": payload.get("cwd", "") or "",
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cost_usd": 0.0,
            "duration_ms": 0,
            "num_turns": 0,
            "session_id": payload.get("session_id", "") or payload.get("conversation_id", ""),
        }
        if mode == "stop" and payload.get("transcript_path"):
            entry.update(claude_transcript_usage(payload["transcript_path"]))
        write_entry(entry)
    except Exception:
        pass  # never break the hosting agent
    sys.stdout.write("{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
