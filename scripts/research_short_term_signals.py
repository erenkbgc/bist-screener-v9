#!/usr/bin/env python3
"""Kisa vade kural aramasi -- docs/research/short_term_preregistration.md'yi
BIREBIR uygular (sinyaller, esikler, bolme, gecme kurali orada sabit).

    python scripts/research_short_term_signals.py

Buradaki sabitleri degistirmek on-kaydi bozar; degisiklik yeni bir on-kayit ister.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
import backtest_short_term as bst  # noqa: E402

LIQ_DROP = 0.30
STEP = 5                      # her 5. islem gunu secim
NW_LAGS = 4                   # 20 gun / haftalik ornekleme
DISCOVERY_END = pd.Timestamp("2021-01-01")
T_DISCOVERY, T_HOLDOUT = 3.0, 2.0
SIGNALS = ["S1_rev_1w", "S2_rev_1m", "S3_52w_high", "S4_low_vol", "S5_value_sn", "S6_value_lowvol"]


def build() -> pd.DataFrame:
    tickers = sorted(p.stem for p in bst.RAW.glob("*.pkl"))
    d = bst.add_signals(bst.load_daily(tickers))
    g = d.groupby("ticker", group_keys=False)
    d["S1_rev_1w"] = -(d["Close"] / g["Close"].shift(5) - 1)
    d["S2_rev_1m"] = -(d["Close"] / g["Close"].shift(20) - 1)
    d["S3_52w_high"] = d["Close"] / g["High"].transform(lambda s: s.rolling(252, min_periods=200).max())
    d["S4_low_vol"] = -d["ret1"].groupby(d["ticker"]).transform(lambda s: s.rolling(60, min_periods=40).std())
    d = d[(d["date"] >= "2013-01-01") & d["tlvol"].notna() & d["fwd20"].notna()]
    cut = d.groupby("date")["tlvol"].transform(lambda s: s.quantile(LIQ_DROP))
    d = d[d["tlvol"] >= cut]
    d = d[d.groupby("date")["ticker"].transform("size") >= 30].copy()
    d["excess20"] = d["fwd20"] - d.groupby("date")["fwd20"].transform("mean")

    v = bst.value_scores().rename(columns={"date": "vdate"})
    v["vdate"] = v["vdate"].astype("datetime64[ns]")
    d["date"] = d["date"].astype("datetime64[ns]")
    d = pd.merge_asof(d.sort_values("date"), v.sort_values("vdate"), left_on="date", right_on="vdate",
                      by="ticker", direction="backward")
    d.loc[(d["date"] - d["vdate"]).dt.days > 62, "value_sn"] = np.nan
    d["S5_value_sn"] = d["value_sn"]

    def z(col):
        grp = d.groupby("date")[col]
        return (d[col] - grp.transform("mean")) / grp.transform("std")
    d["S6_value_lowvol"] = (5 * z("S5_value_sn") + z("S4_low_vol")) / 6
    d.loc[d["S5_value_sn"].isna() | d["S4_low_vol"].isna(), "S6_value_lowvol"] = np.nan

    days = np.sort(d["date"].unique())
    d = d[d["date"].isin(set(days[::STEP]))].reset_index(drop=True)
    return d


def main() -> None:
    d = build()
    # Islem simulasyonu gunluk seri ister: build() haftalik ornekler; simulasyon
    # icin gunluk seriyi yeniden kurup yalnizca secim gunlerinde islem acilir.
    tickers = sorted(p.stem for p in bst.RAW.glob("*.pkl"))
    daily = bst.add_signals(bst.load_daily(tickers))
    daily["date"] = daily["date"].astype("datetime64[ns]")
    daily = daily.sort_values(["ticker", "date"]).reset_index(drop=True)
    key = d[["date", "ticker"]].assign(_take=True)
    daily = daily.merge(key, on=["date", "ticker"], how="left")
    daily["_take"] = daily["_take"].fillna(False).astype(bool)
    daily["trade"] = bst.simulate(daily)
    d = d.merge(daily[["date", "ticker", "trade"]], on=["date", "ticker"], how="left")

    periods = {"discovery": d["date"] < DISCOVERY_END, "holdout": d["date"] >= DISCOVERY_END}
    base_trade = {k: d[m]["trade"].mean() for k, m in periods.items()}
    results = []
    for s in SIGNALS:
        sub = d[d[s].notna()]
        q = sub.groupby("date")[s].transform(lambda x: x >= x.quantile(0.8))
        top = sub[q]
        r = {"signal": s}
        for k, m in periods.items():
            t = top[m.reindex(top.index)]
            daily_ex = t.groupby("date")["excess20"].mean()
            mean, tt, n = fb.newey_west_t(daily_ex, NW_LAGS)
            r[f"{k}_excess20_pct"] = round(100 * mean, 2)
            r[f"{k}_t"] = round(tt, 2)
            r[f"{k}_trade_net_pct"] = round(100 * t["trade"].mean(), 2)
            r[f"{k}_base_trade_pct"] = round(100 * base_trade[k], 2)
            r[f"{k}_dates"] = n
        r["pass"] = bool(
            abs(r["discovery_t"]) > T_DISCOVERY and r["discovery_t"] > 0
            and r["holdout_excess20_pct"] > 0 and r["holdout_t"] > T_HOLDOUT
            and r["holdout_trade_net_pct"] > r["holdout_base_trade_pct"])
        results.append(r)

    res = pd.DataFrame(results)
    print(f"Haftalik secim: {d['date'].nunique()} tarih, {d['ticker'].nunique()} hisse; "
          f"kesif < {DISCOVERY_END.date()} <= saklama\n")
    with pd.option_context("display.width", 250, "display.max_columns", 20):
        print(res[["signal", "discovery_excess20_pct", "discovery_t", "discovery_trade_net_pct",
                   "discovery_base_trade_pct", "holdout_excess20_pct", "holdout_t", "holdout_trade_net_pct",
                   "holdout_base_trade_pct", "pass"]].to_string(index=False))
    passed = res[res["pass"]].sort_values("holdout_t", ascending=False)
    print("\nGecen: " + (", ".join(passed["signal"]) if len(passed) else "YOK -> kisa vade kurali bulunamadi"))

    out = ROOT / "data" / "reports" / f"research_short_term_signals_{date.today().isoformat()}.json"
    out.write_text(json.dumps({"preregistration": "docs/research/short_term_preregistration.md",
                               "results": results,
                               "chosen": passed["signal"].iloc[0] if len(passed) else None},
                              ensure_ascii=False, indent=2,
                              default=lambda x: None if isinstance(x, float) and math.isnan(x) else str(x)),
                   encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
