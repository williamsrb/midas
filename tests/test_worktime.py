from datetime import datetime, timezone

from midas.worktime import clamp_commit_datetime, git_date


def _cfg(cfg, enforce=True, start="09:00", end="17:00", days=None):
    cfg.worktime.enforce = enforce
    cfg.worktime.start = start
    cfg.worktime.end = end
    cfg.worktime.days = days or ["mon", "tue", "wed", "thu", "fri"]
    return cfg


# 2026-07-16 is a Thursday
THU_NOON = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
THU_NIGHT = datetime(2026, 7, 16, 23, 30, tzinfo=timezone.utc)
THU_DAWN = datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc)
SAT = datetime(2026, 7, 18, 14, 0, tzinfo=timezone.utc)


def test_disabled_returns_none(cfg):
    assert clamp_commit_datetime(_cfg(cfg, enforce=False), THU_NIGHT) is None


def test_inside_bracket_untouched(cfg):
    assert clamp_commit_datetime(_cfg(cfg), THU_NOON) is None


def test_after_hours_clamped_to_today_end(cfg):
    forced = clamp_commit_datetime(_cfg(cfg), THU_NIGHT)
    assert forced.date() == THU_NIGHT.date()
    assert forced.hour == 16 and forced.minute == 56  # 17:00 - 4min margin


def test_before_hours_goes_to_previous_working_day(cfg):
    forced = clamp_commit_datetime(_cfg(cfg), THU_DAWN)
    assert forced.date().isoformat() == "2026-07-15"  # Wednesday
    assert forced.hour == 16


def test_weekend_goes_back_to_friday(cfg):
    forced = clamp_commit_datetime(_cfg(cfg), SAT)
    assert forced.date().isoformat() == "2026-07-17"  # Friday
    assert forced.hour == 16


def test_git_date_format(cfg):
    forced = clamp_commit_datetime(_cfg(cfg), THU_NIGHT)
    assert git_date(forced) == "2026-07-16T16:56:00+0000"
