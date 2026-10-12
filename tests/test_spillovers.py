"""Sektor yayilimi: kume-dayanikli OLS, gecikmeli yayilim ve bilgi aktarimi mekanigi."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_spillovers as sp  # noqa: E402


def test_cluster_ols_recovers_slope():
    rng = np.random.default_rng(0)
    x = rng.normal(size=400)
    y = 0.5 * x + rng.normal(scale=0.1, size=400)
    b, t, G = sp.cluster_ols(y, x, np.repeat(np.arange(40), 10))
    assert abs(b - 0.5) < 0.02 and t > 20 and G == 40


def test_lead_lag_detects_planted_big_to_small_effect():
    rng = np.random.default_rng(1)
    days = pd.bdate_range("2019-01-01", periods=400)
    n_sec = 8
    big_r = rng.normal(0, 0.02, (len(days), n_sec))
    cols, uni = {}, []
    for s in range(n_sec):
        wk = pd.Series(big_r[:, s], index=days)
        # kucukler bir hafta (5 gun) gecikmeli buyukleri izler
        small = 0.8 * wk.shift(5).fillna(0) + rng.normal(0, 0.005, len(days))
        for j in range(2):
            cols[f"B{s}{j}"] = 100 * (1 + wk).cumprod()
            cols[f"S{s}{j}"] = 100 * (1 + small).cumprod()
            for m in pd.date_range("2018-12-31", periods=20, freq="ME"):
                uni.append({"date": m, "ticker": f"B{s}{j}", "sector": f"s{s}", "mcap": 1e9})
                uni.append({"date": m, "ticker": f"S{s}{j}", "sector": f"s{s}", "mcap": 1e6})
    ll = sp.lead_lag(pd.DataFrame(cols, index=days), pd.DataFrame(uni))
    assert ll["b"].mean() > 0.3


def test_transfer_event_picks_first_reporter_and_late_peers():
    days = pd.bdate_range("2020-04-01", periods=40)
    flat = [f"Q{i}" for i in range(6)]  # piyasa ortalamasini sabitleyen baska sektor
    close = pd.DataFrame(100.0, index=days, columns=["A", "P1", "P2", *flat])
    close.loc[days[5]:, "A"] = 110.0    # aciklayan t0'da +%10
    close.loc[days[5]:, "P1"] = 105.0   # kardesler ayni gun +%5
    close.loc[days[5]:, "P2"] = 105.0
    uni = pd.DataFrame([{"date": pd.Timestamp("2020-03-31"), "ticker": t, "sector": "x", "mcap": 1.0}
                        for t in ["A", "P1", "P2"]] + [{"date": pd.Timestamp("2020-03-31"), "ticker": q,
                                                         "sector": "y", "mcap": 1.0} for q in flat])
    dates = pd.DataFrame({"ticker": ["A", "P1", "P2"], "period": "2020Q1",
                          "kap_available_at": [days[5], days[20], days[25]]})
    ev = sp.transfer_events(close, uni, dates)
    assert len(ev) == 1 and ev.iloc[0]["n_peers"] == 2
    assert ev.iloc[0]["ar_ann"] > ev.iloc[0]["ar_peer0"] > 0
