#!/usr/bin/env python3
"""Adapts Claude Code hook payloads to history.py's schema, so Claude Code and
Cursor log into the same history directory (../history from this hooks dir)
using one shared script.

Usage: claude-history-adapter.py prompt|stop   (reads Claude Code's hook JSON on stdin)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HISTORY_PY = Path(__file__).with_name("history.py")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    if not isinstance(payload, dict):
        payload = {}

    conversation_id = payload.get("session_id", "")
    generation_id = payload.get("prompt_id", "")

    if mode == "prompt":
        mapped = {
            "prompt": payload.get("prompt", ""),
            "conversation_id": conversation_id,
            "generation_id": generation_id,
            "hook_event_name": "UserPromptSubmit",
            "workspace_roots": [payload["cwd"]] if payload.get("cwd") else [],
        }
        history_mode = "prompt"
    else:
        mapped = {
            "text": payload.get("last_assistant_message", ""),
            "conversation_id": conversation_id,
            "generation_id": generation_id,
            "hook_event_name": "Stop",
            "status": "completed",
        }
        history_mode = "response"

    result = subprocess.run(
        [sys.executable, str(HISTORY_PY), history_mode],
        input=json.dumps(mapped),
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout or "{}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
