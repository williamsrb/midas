"""LLM usage ledger: one JSONL line per interaction (midas stages + hooked
interactive claude/cursor sessions), stored at logs/llm-usage.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import paths


def record(
    source: str,
    agent: str = "",
    model: str = "",
    context: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
    num_turns: int = 0,
    session_id: str = "",
) -> None:
    entry = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,          # "midas" | "claude-interactive" | "cursor-interactive"
        "agent": agent,
        "model": model,
        "context": context,        # e.g. "RFD-123/planned"
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cost_usd": round(cost_usd, 6),
        "duration_ms": duration_ms,
        "num_turns": num_turns,
        "session_id": session_id,
    }
    ledger = paths.usage_ledger()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def load(days: int = 7) -> list[dict]:
    ledger = paths.usage_ledger()
    if not ledger.is_file():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    entries = []
    for line in ledger.read_text().splitlines():
        try:
            entry = json.loads(line)
            at = datetime.fromisoformat(entry["at"]).timestamp()
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if at >= cutoff:
            entries.append(entry)
    return entries


def summarize(days: int = 7) -> dict:
    """Totals overall and per (source, model)."""
    entries = load(days)
    total = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    groups: dict[str, dict] = {}
    for e in entries:
        key = f"{e.get('source', '?')}/{e.get('model') or '?'}"
        g = groups.setdefault(key, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        for bucket in (total, g):
            bucket["calls"] += 1
            bucket["input_tokens"] += e.get("input_tokens", 0)
            bucket["output_tokens"] += e.get("output_tokens", 0)
            bucket["cost_usd"] += e.get("cost_usd", 0.0)
    return {"days": days, "total": total, "groups": groups}
