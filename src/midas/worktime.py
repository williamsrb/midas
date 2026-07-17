"""Working-time bracket for commit dates.

When enforcement is on and the pipeline commits outside company hours, the
git author/committer dates are clamped to the most recent moment inside the
bracket (a few minutes before closing time, on the last working day).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from .config import Config

_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_MARGIN_MINUTES = 4  # commit "just before closing", not at 17:00:00 sharp


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def clamp_commit_datetime(cfg: Config, now: datetime | None = None) -> datetime | None:
    """Return the forced commit datetime, or None when `now` is already fine.

    Rules (local time):
    - inside the bracket on a working day -> None (no forcing)
    - after closing on a working day     -> today at end - margin
    - before opening on a working day    -> previous working day at end - margin
    - on a non-working day               -> previous working day at end - margin
    """
    if not cfg.worktime.enforce:
        return None
    now = now or datetime.now().astimezone()
    start = _parse_hhmm(cfg.worktime.start)
    end = _parse_hhmm(cfg.worktime.end)
    days = set(cfg.worktime.days)

    def is_working(d: datetime) -> bool:
        return _DAY_KEYS[d.weekday()] in days

    if is_working(now) and start <= now.time() <= end:
        return None

    candidate = now
    if not (is_working(now) and now.time() > end):
        # before opening or non-working day: walk back to the last working day
        candidate = now - timedelta(days=1)
        while not is_working(candidate):
            candidate -= timedelta(days=1)
    return candidate.replace(
        hour=end.hour, minute=end.minute, second=0, microsecond=0
    ) - timedelta(minutes=_MARGIN_MINUTES)


def git_date(dt: datetime) -> str:
    """Format for GIT_AUTHOR_DATE / GIT_COMMITTER_DATE."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")
