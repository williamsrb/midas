"""Per-task state machine persistence (tasks/<KEY>/state.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import paths

# Pipeline stages, in order. A task advances through these; `awaiting_human`
# is the resting state after Midas commits and reports.
STAGES = [
    "discovered",
    "fetched",
    "env_detected",
    "cloned",
    "branch_ready",
    "planned",
    "implemented",
    "validated",
    "committed",
    "reported",
    "awaiting_human",
]

# Terminal states (no further automatic processing).
TERMINAL = {"awaiting_human", "done", "skipped_dotnet", "blocked"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class TaskState:
    key: str
    stage: str = "discovered"
    summary: str = ""
    error: str = ""
    data: dict = field(default_factory=dict)  # env, repo path, commit sha, ...
    history: list[dict] = field(default_factory=list)

    @property
    def dir(self) -> Path:
        return task_dir(self.key)

    @property
    def is_terminal(self) -> bool:
        return self.stage in TERMINAL

    def advance(self, stage: str, detail: str = "") -> None:
        if stage not in STAGES and stage not in TERMINAL:
            raise ValueError(f"Unknown stage: {stage}")
        self.stage = stage
        self.error = ""
        self.history.append({"stage": stage, "at": _now(), "detail": detail})
        self.save()

    def block(self, reason: str) -> None:
        self.error = reason
        self.stage = "blocked"
        self.history.append({"stage": "blocked", "at": _now(), "detail": reason})
        self.save()

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "key": self.key,
            "stage": self.stage,
            "summary": self.summary,
            "error": self.error,
            "data": self.data,
            "history": self.history,
        }
        (self.dir / "state.json").write_text(json.dumps(payload, indent=2))

    # Convenience file accessors -------------------------------------------
    @property
    def task_md(self) -> Path:
        return self.dir / "task.md"

    @property
    def env_json(self) -> Path:
        return self.dir / "env.json"

    @property
    def plan_md(self) -> Path:
        return self.dir / "plan.md"

    @property
    def commit_msg_file(self) -> Path:
        return self.dir / "COMMIT_MSG.txt"

    @property
    def transcripts_dir(self) -> Path:
        return self.dir / "transcripts"

    @property
    def test_plan_dir(self) -> Path:
        return self.dir / "test-plan"

    def env(self) -> dict:
        if self.env_json.is_file():
            return json.loads(self.env_json.read_text())
        return {}

    def save_env(self, env: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.env_json.write_text(json.dumps(env, indent=2))


def task_dir(key: str) -> Path:
    return paths.tasks_dir() / key


def exists(key: str) -> bool:
    return (task_dir(key) / "state.json").is_file()


def load(key: str) -> TaskState:
    path = task_dir(key) / "state.json"
    if not path.is_file():
        raise FileNotFoundError(f"No state for task {key}")
    raw = json.loads(path.read_text())
    return TaskState(
        key=raw["key"],
        stage=raw.get("stage", "discovered"),
        summary=raw.get("summary", ""),
        error=raw.get("error", ""),
        data=raw.get("data", {}),
        history=raw.get("history", []),
    )


def create(key: str, summary: str = "") -> TaskState:
    st = TaskState(key=key, summary=summary)
    st.history.append({"stage": "discovered", "at": _now(), "detail": "picked up"})
    st.save()
    return st


def list_all() -> list[TaskState]:
    if not paths.tasks_dir().is_dir():
        return []
    states = []
    for d in sorted(paths.tasks_dir().iterdir()):
        if (d / "state.json").is_file():
            try:
                states.append(load(d.name))
            except (json.JSONDecodeError, KeyError):
                continue
    return states


def pending() -> list[TaskState]:
    """Tasks that still need automatic processing."""
    return [s for s in list_all() if not s.is_terminal]
