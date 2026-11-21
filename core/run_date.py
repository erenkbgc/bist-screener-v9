"""Intended trading / run date resolution for daily scheduled and manual runs.

GitHub Actions cron "30 15 * * *" (18:30 Europe/Istanbul, UTC+3) frequently starts
4-8 hours late, past 00:00 Europe/Istanbul (21:00 UTC). Computing the run date via
`TZ=Europe/Istanbul date +%F` at job start labeled those runs D+1, causing missing
dates and idempotent skips on the following day (and risking an early monthly
rebalance on month-end rollover).

Resolution order:
1. Explicit date (`--as-of-date` / `INPUT_AS_OF_DATE`) if given.
2. Scheduled cron expression (`GITHUB_EVENT_SCHEDULE`, e.g. "30 15 * * *"): find the
   most recent scheduled firing <= now (+5 min early-trigger grace) in UTC, then
   return its Europe/Istanbul calendar date.
3. Fallback (manual / local CLI without explicit date): Europe/Istanbul local date,
   rolling back one day if started before `ROLLOVER_CUTOFF_HOUR` (06:00 Istanbul),
   which is after the prior BIST close (18:00) and before the next market open.
"""
from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
except Exception:  # pragma: no cover - fallback when tzdata is absent
    ISTANBUL_TZ = timezone(timedelta(hours=3))

ROLLOVER_CUTOFF_HOUR = 6
CRON_EARLY_GRACE_MINUTES = 5


def _parse_daily_cron_utc(schedule: str | None) -> tuple[int, int] | None:
    """Parse minute/hour from a 5-field UTC cron expression like '30 15 * * *'."""
    if not schedule:
        return None
    parts = schedule.strip().split()
    if len(parts) != 5:
        return None
    try:
        minute = int(parts[0])
        hour = int(parts[1])
    except ValueError:
        return None
    if not (0 <= minute <= 59 and 0 <= hour <= 23):
        return None
    return hour, minute


def resolve_run_date(
    now: datetime | None = None,
    schedule: str | None = None,
    explicit_date: str | None = None,
    cutoff_hour: int = ROLLOVER_CUTOFF_HOUR,
) -> str:
    """Return the intended YYYY-MM-DD run date in Europe/Istanbul."""
    if explicit_date and explicit_date.strip():
        cleaned = explicit_date.strip()
        date.fromisoformat(cleaned)  # validate YYYY-MM-DD
        return cleaned

    if now is None:
        now_dt = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now_dt = now.replace(tzinfo=ISTANBUL_TZ)
    else:
        now_dt = now

    cron_hm = _parse_daily_cron_utc(schedule)
    if cron_hm is not None:
        cron_h, cron_m = cron_hm
        now_utc = now_dt.astimezone(timezone.utc)
        sched_today = datetime(
            now_utc.year, now_utc.month, now_utc.day, cron_h, cron_m, tzinfo=timezone.utc
        )
        if sched_today <= now_utc + timedelta(minutes=CRON_EARLY_GRACE_MINUTES):
            intended_utc = sched_today
        else:
            intended_utc = sched_today - timedelta(days=1)
        return intended_utc.astimezone(ISTANBUL_TZ).date().isoformat()

    now_ist = now_dt.astimezone(ISTANBUL_TZ)
    if now_ist.hour < cutoff_hour:
        return (now_ist.date() - timedelta(days=1)).isoformat()
    return now_ist.date().isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve intended BIST run date (YYYY-MM-DD)")
    parser.add_argument("--explicit-date", default=os.environ.get("INPUT_AS_OF_DATE", ""))
    parser.add_argument("--schedule", default=os.environ.get("GITHUB_EVENT_SCHEDULE", ""))
    parser.add_argument("--now", default=None, help="ISO-8601 timestamp override for testing")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.now) if args.now else None
    print(resolve_run_date(now=now, schedule=args.schedule or None, explicit_date=args.explicit_date or None))


if __name__ == "__main__":
    main()
