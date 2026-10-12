"""KAP bildirim sinyali tanimlari (kap_disclosure_signals_preregistration.md)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_kap_disclosure_signals as ks  # noqa: E402


def _fr(ts, rule="3 Aylık", late=False, code="AAA"):
    return {"disclosureClass": "FR", "subject": "Finansal Rapor", "ruleType": rule,
            "published_at": pd.Timestamp(ts), "isLate": late, "stock_code": code}


def test_own_delay_friday_evening_and_late_flags():
    arc = pd.DataFrame([
        _fr("2020-05-01 10:00"), _fr("2021-05-03 10:00"), _fr("2022-05-02 10:00"),  # Q1 ~31-33 gun
        _fr("2023-05-26 19:00", late=True),   # Q1 2023: 56 gun (+~24), Cuma 19:00, gec
        _fr("2023-05-30 10:00"),              # ayni donem duzeltme: sayilmaz
    ])
    s = ks.report_signals(ks.first_filings(arc)).set_index("period_end")
    last = s.loc[pd.Timestamp("2023-03-31")]
    assert bool(last["S1"]) and bool(last["S2"]) and bool(last["S3"])
    assert not s.loc[pd.Timestamp("2022-03-31"), "S2"]  # medyana yakin
    assert pd.isna(s.loc[pd.Timestamp("2020-03-31"), "S2"]) or not s.loc[pd.Timestamp("2020-03-31"), "S2"]
    assert len(s) == 4


def test_buyback_start_needs_180_day_gap():
    arc = pd.DataFrame([{"subject": ks.BUYBACK_SUBJECT, "stock_code": "BBB", "published_at": pd.Timestamp(d)}
                        for d in ("2022-01-10", "2022-02-01", "2022-12-01")])
    starts = ks.buyback_starts(arc)
    assert list(starts["published_at"].dt.strftime("%Y-%m-%d")) == ["2022-01-10", "2022-12-01"]


def test_calendar_portfolio_holds_three_months_vs_control():
    months = pd.date_range("2020-01-31", periods=5, freq="ME")
    panel = pd.DataFrame([{"date": m, "ticker": f"T{i}", "fwd_ret_1m": 0.02 if i < 5 else 0.0}
                          for m in months for i in range(10)])
    ev = pd.DataFrame({"ticker": [f"T{i}" for i in range(5)], "month": months[0]})
    ctl = pd.DataFrame({"ticker": [f"T{i}" for i in range(5, 10)], "month": months[0]})
    p = ks.calendar_portfolio(ev, ctl, panel)
    assert list(p["date"]) == list(months[:3]) and (p["d"] == 0.02).all()
