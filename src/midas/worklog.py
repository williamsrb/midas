"""Durable per-run state: `PROGRESS.md` and `MEMORY.md` in the run directory.

A delegated run today leaves `status.json`, `events.ndjson` and `BATON.md` — all written by the
kernel, all describing the *playbook*. None of them answer the questions an operator actually has
when a machine is rebooted mid-run, loses the network, or is simply found with work sitting in it:

* what did this run already finish, and where would it pick up?
* is anyone still working on this, or is it orphaned?
* how long has it been like this?

So each run also gets two human-readable files, written by Midas rather than the kernel:

`PROGRESS.md` — an append-only log. One entry per step, plus a machine-readable front-matter block
carrying the fields orphan detection and archiving need. Markdown because a human finding this
directory at 2am is the primary reader; front matter because `orphans()` has to parse it.

`MEMORY.md` — durable facts a second attempt should not re-derive (resolved repo URL, branch,
ticket key, discovered environment). Free-form below its own heading.

Both live in the run directory next to `status.json`, which is already the per-run durable store —
they travel with the run, get cleaned up with it, and need no new location or lifecycle.

Lifecycle: `active` → `finished` | `archived`. A run that is unfinished, unlocked and untouched for
`ARCHIVE_AFTER_DAYS` is abandoned; `archive_abandoned()` marks it and Midas reports it upward, where
morpheus lists it for an operator to discard. Archiving deliberately does **not** consume the
assignment's attempt budget: it is a local judgement that nobody is coming back, not a verdict on
the work.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import logging_setup, paths

log = logging_setup.get("worklog")

ARCHIVE_AFTER_DAYS = 30

PROGRESS_FILE = "PROGRESS.md"
MEMORY_FILE = "MEMORY.md"

_FRONT_MATTER = re.compile(r"\A<!--\s*midas:progress\s*(\{.*?\})\s*-->", re.DOTALL)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class RunState:
    run_id: str
    assignment_id: str
    status: str  # active | finished | archived
    updated_at: datetime | None
    steps: int
    resume_point: str
    path: Path

    @property
    def unfinished(self) -> bool:
        return self.status == "active"


def progress_path(run_dir: Path) -> Path:
    return run_dir / PROGRESS_FILE


def memory_path(run_dir: Path) -> Path:
    return run_dir / MEMORY_FILE


def _render_front_matter(data: dict) -> str:
    return f"<!-- midas:progress {json.dumps(data, sort_keys=True)} -->"


def read_front_matter(run_dir: Path) -> dict:
    path = progress_path(run_dir)
    if not path.is_file():
        return {}
    try:
        match = _FRONT_MATTER.match(path.read_text())
    except OSError:
        return {}
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def _write(run_dir: Path, meta: dict, body: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    progress_path(run_dir).write_text(f"{_render_front_matter(meta)}\n{body}")


def start(run_dir: Path, *, run_id: str, assignment_id: str, playbook_id: str = "", task_key: str = "") -> None:
    """Opens the log. Safe to call again on a resumed run — the existing history is kept."""
    existing = read_front_matter(run_dir)
    meta = {
        "runId": run_id,
        "assignmentId": assignment_id,
        "playbookId": playbook_id or existing.get("playbookId", ""),
        "taskKey": task_key or existing.get("taskKey", ""),
        "status": "active",
        "startedAt": existing.get("startedAt") or _iso(_now()),
        "updatedAt": _iso(_now()),
        "steps": int(existing.get("steps", 0)),
        "resumePoint": existing.get("resumePoint", "not started"),
        "attempts": int(existing.get("attempts", 0)) + 1,
    }

    if progress_path(run_dir).is_file():
        body = _body(run_dir)
        body += f"\n### Attempt {meta['attempts']} — resumed {_iso(_now())}\n"
    else:
        body = (
            f"\n# Run {run_id}\n\n"
            f"Assignment `{assignment_id}`"
            + (f" · task `{task_key}`" if task_key else "")
            + (f" · playbook `{playbook_id}`" if playbook_id else "")
            + f"\n\nStarted {meta['startedAt']}.\n\n"
            "## Steps\n"
        )
    _write(run_dir, meta, body)


def _body(run_dir: Path) -> str:
    text = progress_path(run_dir).read_text()
    match = _FRONT_MATTER.match(text)
    return text[match.end() :].lstrip("\n") and text[match.end() :] if match else text


def step(run_dir: Path, node_id: str, outcome: str, *, detail: str = "", resume_point: str = "") -> None:
    """Records one completed step and advances the resume point.

    Called per kernel event rather than per run, so a machine that dies mid-run still leaves a log
    that ends at the last thing it actually finished.
    """
    meta = read_front_matter(run_dir)
    if not meta:
        return  # never opened; nothing to append to
    meta["steps"] = int(meta.get("steps", 0)) + 1
    meta["updatedAt"] = _iso(_now())
    meta["resumePoint"] = resume_point or node_id
    line = f"- `{_iso(_now())}` **{node_id}** → {outcome}"
    if detail:
        line += f" — {detail}"
    _write(run_dir, meta, f"{_body(run_dir).rstrip()}\n{line}\n")


def finish(run_dir: Path, outcome: str) -> None:
    meta = read_front_matter(run_dir)
    if not meta:
        return
    meta["status"] = "finished"
    meta["outcome"] = outcome
    meta["updatedAt"] = _iso(_now())
    meta["resumePoint"] = "complete"
    _write(run_dir, meta, f"{_body(run_dir).rstrip()}\n\nFinished {_iso(_now())} — **{outcome}**.\n")


def remember(run_dir: Path, key: str, value: str) -> None:
    """Appends a durable fact the next attempt should not have to re-derive."""
    path = memory_path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(
            "# Run memory\n\n"
            "Facts established once, so a resumed attempt does not re-derive them.\n\n"
        )
    path.write_text(f"{path.read_text().rstrip()}\n- **{key}:** {value}\n")


def read_memory(run_dir: Path) -> dict[str, str]:
    path = memory_path(run_dir)
    if not path.is_file():
        return {}
    facts = {}
    for line in path.read_text().splitlines():
        match = re.match(r"^- \*\*(.+?):\*\* (.*)$", line.strip())
        if match:
            facts[match.group(1)] = match.group(2)
    return facts


def _run_dirs() -> list[Path]:
    runs = paths.runs_dir()
    if not runs.is_dir():
        return []
    return [d for d in sorted(runs.iterdir()) if d.is_dir()]


def _state_of(run_dir: Path) -> RunState | None:
    meta = read_front_matter(run_dir)
    if not meta:
        return None
    return RunState(
        run_id=str(meta.get("runId", run_dir.name)),
        assignment_id=str(meta.get("assignmentId", "")),
        status=str(meta.get("status", "active")),
        updated_at=_parse_iso(meta.get("updatedAt")),
        steps=int(meta.get("steps", 0)),
        resume_point=str(meta.get("resumePoint", "")),
        path=run_dir,
    )


def orphans(held_assignment_ids: set[str] | None = None) -> list[RunState]:
    """Unfinished runs nobody is working on.

    `held_assignment_ids` is what the agent currently holds a lease for; anything unfinished that
    is *not* in that set has no live worker, which is the definition of orphaned here.
    """
    held = held_assignment_ids or set()
    found = []
    for run_dir in _run_dirs():
        state = _state_of(run_dir)
        if state and state.unfinished and state.assignment_id not in held:
            found.append(state)
    return found


def archive_abandoned(after_days: int = ARCHIVE_AFTER_DAYS, held_assignment_ids: set[str] | None = None) -> list[RunState]:
    """Marks long-untouched orphans `archived` and returns them for reporting upward."""
    cutoff = _now() - timedelta(days=after_days)
    archived = []
    for state in orphans(held_assignment_ids):
        if state.updated_at is None or state.updated_at > cutoff:
            continue
        meta = read_front_matter(state.path)
        meta["status"] = "archived"
        meta["archivedAt"] = _iso(_now())
        _write(
            state.path,
            meta,
            f"{_body(state.path).rstrip()}\n\n"
            f"Archived {_iso(_now())} — unfinished and untouched for {after_days} days. "
            "Reported to morpheus for the operator to discard or keep.\n",
        )
        state.status = "archived"
        archived.append(state)
        log.info("archived abandoned run %s (assignment %s)", state.run_id, state.assignment_id)
    return archived


def list_archived() -> list[RunState]:
    return [s for s in (_state_of(d) for d in _run_dirs()) if s and s.status == "archived"]


def is_run_id(value: str) -> bool:
    """A run id is one path segment, never a traversal.

    This function deletes a directory tree, and `run_id` reaches it from an operator action in
    morpheus — i.e. from off-machine. Without this, `discard("../../something")` resolves outside
    the runs directory and removes whatever is there: the same unvalidated-`join` class as the
    traversal fixed in `blobs.ts`/`profiles.ts`. Verified by
    `test_discard_refuses_a_traversing_run_id`.
    """
    return bool(value) and value not in (".", "..") and "/" not in value and "\\" not in value and "\0" not in value


def discard(run_id: str) -> bool:
    """Deletes an archived run directory. Only ever called after an operator says so in morpheus."""
    if not is_run_id(run_id):
        log.warning("refusing to discard %r - not a single path segment", run_id)
        return False
    runs_root = paths.runs_dir().resolve()
    run_dir = paths.runs_dir() / run_id
    # Belt and braces: a symlinked run directory would pass the segment check above and still
    # resolve elsewhere.
    if not run_dir.is_dir() or run_dir.resolve().parent != runs_root:
        return False
    state = _state_of(run_dir)
    if not state or state.status != "archived":
        return False
    for child in sorted(run_dir.rglob("*"), reverse=True):
        child.unlink() if child.is_file() or child.is_symlink() else child.rmdir()
    run_dir.rmdir()
    log.info("discarded archived run %s", run_id)
    return True
