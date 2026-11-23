"""Cron date drift & month-boundary rebalance tests (Task 1)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import run as run_mod
from core import db, forward_record, rotation
from core.run_date import ISTANBUL_TZ, resolve_run_date


def _c(ticker: str, z: float, **kw) -> dict:
    return {
        "ticker": ticker,
        "bucket": "long_term",
        "candidate_state": "WATCHLIST",
        "confidence": "high",
        "valuation_z": z,
        "tl_vol_med60": 1e9,
        **kw,
    }


def test_resolve_run_date_on_time_and_late_past_midnight_istanbul():
    # On time: 2026-11-03 18:35 Europe/Istanbul (15:35 UTC) -> 2026-11-03
    dt_on_time = datetime(2026, 11, 3, 18, 35, tzinfo=ISTANBUL_TZ)
    assert resolve_run_date(now=dt_on_time, schedule="30 15 * * *") == "2026-11-03"
    assert resolve_run_date(now=dt_on_time) == "2026-11-03"

    # Delayed 6h past midnight Istanbul (2026-11-04 00:30+03:00 = 2026-11-03 21:30 UTC) -> 2026-11-03
    dt_late_1 = datetime(2026, 11, 4, 0, 30, tzinfo=ISTANBUL_TZ)
    assert resolve_run_date(now=dt_late_1, schedule="30 15 * * *") == "2026-11-03"
    assert resolve_run_date(now=dt_late_1) == "2026-11-03"

    # Delayed 8h past both Istanbul and UTC midnight (2026-11-04 04:30+03:00 = 2026-11-04 01:30 UTC) -> 2026-11-03
    dt_late_2 = datetime(2026, 11, 4, 4, 30, tzinfo=ISTANBUL_TZ)
    assert resolve_run_date(now=dt_late_2, schedule="30 15 * * *") == "2026-11-03"
    assert resolve_run_date(now=dt_late_2) == "2026-11-03"

    # Daytime manual run at 10:00 Istanbul without schedule -> same day
    dt_day = datetime(2026, 11, 4, 10, 0, tzinfo=ISTANBUL_TZ)
    assert resolve_run_date(now=dt_day) == "2026-11-04"


def test_resolve_run_date_explicit_override():
    dt_late = datetime(2026, 12, 1, 1, 0, tzinfo=ISTANBUL_TZ)
    assert resolve_run_date(now=dt_late, schedule="30 15 * * *", explicit_date="2026-11-28") == "2026-11-28"
    with pytest.raises(ValueError):
        resolve_run_date(explicit_date="not-a-date")


def test_month_boundary_nov30_starting_dec1_0100_and_dec1_starting_dec2_0200(temp_db, tmp_path, monkeypatch):
    """Month boundary test required by Task 1:
    - Run for Nov 30 starting Dec 1 01:00 Istanbul must resolve to 2026-11-30 and reuse
      November's rebalance (must NOT trigger an early December rebalance on Nov 30's delayed run).
    - Run for Dec 1 starting Dec 2 02:00 Istanbul must resolve to 2026-12-01 and trigger
      the December monthly rebalance (R0-2026-10-12) exactly once.
    - Subsequent run for Dec 2 must reuse 2026-12-01 and never double-rebalance.
    """
    db.init_db()
    decisions_path = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(forward_record, "RECORD_PATH", decisions_path)
    monkeypatch.setattr(forward_record, "_production_live", lambda: True)

    # 1. Initial November rebalance on 2026-11-01: T9, T8 selected
    nov1_cands = [_c(f"T{i}", float(i)) for i in range(10)]
    r_nov1 = rotation.monthly_rotation("2026-11-01", nov1_cands)
    assert r_nov1["rebalance_date"] == "2026-11-01"
    assert [h["ticker"] for h in r_nov1["buy"]] == ["T9", "T8"]

    # 2. Run for Nov 30 starting Dec 1 01:00 Europe/Istanbul
    start_nov30_late = datetime(2026, 12, 1, 1, 0, tzinfo=ISTANBUL_TZ)
    date_nov30_cron = resolve_run_date(now=start_nov30_late, schedule="30 15 * * *")
    date_nov30_cutoff = resolve_run_date(now=start_nov30_late)
    assert date_nov30_cron == "2026-11-30"
    assert date_nov30_cutoff == "2026-11-30"

    # Even if candidate scores totally inverted on Nov 30, it must stay in November and reuse 2026-11-01
    nov30_cands = [_c(f"T{i}", float(10 - i)) for i in range(10)]
    r_nov30 = rotation.monthly_rotation(date_nov30_cron, nov30_cands)
    assert r_nov30["rebalance_date"] == "2026-11-01"
    assert [h["ticker"] for h in r_nov30["buy"]] == ["T9", "T8"]
    assert len(forward_record.load_decisions(decisions_path)) == 1

    # 3. Run for Dec 1 starting Dec 2 02:00 Europe/Istanbul
    start_dec1_late = datetime(2026, 12, 2, 2, 0, tzinfo=ISTANBUL_TZ)
    date_dec1_cron = resolve_run_date(now=start_dec1_late, schedule="30 15 * * *")
    date_dec1_cutoff = resolve_run_date(now=start_dec1_late)
    assert date_dec1_cron == "2026-12-01"
    assert date_dec1_cutoff == "2026-12-01"

    dec1_cands = [_c(f"T{i}", float(10 - i)) for i in range(10)]  # T0, T1 now top
    r_dec1 = rotation.monthly_rotation(date_dec1_cron, dec1_cands)
    assert r_dec1["rebalance_date"] == "2026-12-01"
    assert r_dec1["previous_rebalance_date"] == "2026-11-01"
    assert [h["ticker"] for h in r_dec1["buy"]] == ["T0", "T1"]
    assert r_dec1["sell"] == ["T8", "T9"]

    decisions = forward_record.load_decisions(decisions_path)
    assert [d["rebalance_date"] for d in decisions] == ["2026-11-01", "2026-12-01"]
    assert [d["holdings"] for d in decisions] == [["T8", "T9"], ["T0", "T1"]]

    # 4. Run for Dec 2 starting Dec 2 20:00 (or Dec 3 01:30) Istanbul -> 2026-12-02
    start_dec2_late = datetime(2026, 12, 3, 1, 30, tzinfo=ISTANBUL_TZ)
    date_dec2 = resolve_run_date(now=start_dec2_late, schedule="30 15 * * *")
    assert date_dec2 == "2026-12-02"

    dec2_cands = [_c(f"T{i}", float(i)) for i in range(10)]
    r_dec2 = rotation.monthly_rotation(date_dec2, dec2_cands)
    assert r_dec2["rebalance_date"] == "2026-12-01"
    assert [h["ticker"] for h in r_dec2["buy"]] == ["T0", "T1"]
    # forward_record must not double-record within 2026-12
    assert len(forward_record.load_decisions(decisions_path)) == 2
    assert not forward_record.append_decision("2026-12-02", ["T9", "T8"], ["T9", "T8"], path=decisions_path, force=True)


def test_full_run_applies_resolved_date_to_runs_health_reports_and_rotation(temp_db, monkeypatch):
    """End-to-end mock run invoked without explicit date at Dec 1 01:00 Istanbul
    must label runs, run_health, reports, and rotation with 2026-11-30."""
    monkeypatch.setenv("GITHUB_EVENT_SCHEDULE", "30 15 * * *")
    monkeypatch.setattr(
        run_mod.run_date_mod,
        "resolve_run_date",
        lambda schedule=None, explicit_date=None: resolve_run_date(
            now=datetime(2026, 12, 1, 1, 0, tzinfo=ISTANBUL_TZ),
            schedule=schedule,
            explicit_date=explicit_date,
        ),
    )
    res = run_mod.run()
    assert res["as_of_date"] == "2026-11-30"
    assert db.query("SELECT as_of_date FROM runs")[0]["as_of_date"] == "2026-11-30"
    assert db.query("SELECT as_of_date FROM run_health")[0]["as_of_date"] == "2026-11-30"
    assert (run_mod.REPORTS_DIR / "2026-11-30_payload.json").exists()
    assert (run_mod.REPORTS_DIR / "2026-11-30.html").exists()
