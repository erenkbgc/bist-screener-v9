#!/usr/bin/env python3
"""Canli karar ile test edilen panel ayni stratejiyi mi uretiyor (denetim, test degil).

1. Zamanlama: her ay icin backtest karar gunu (onceki ayin son islem gunu, panel
   ay sonu) ile canlinin ayin ilk basarili kosusu; aradaki islem gunu farki.
2. Siralama: panelin son ay sonundaki value_sn_z siralamasi ile canli valuation_z
   (value_sn profilleri, valid_metric_count dolu ilk kosular) ortak hisselerde:
   sira korelasyonu ve ust %20 ortusmesi. Fark kaynaklari: canli yillik tablo vs
   panel ceyreklik TTM, fiyat tarihi farki, saglayici F/K ve PD/DD.
3. Panelin son ayinda kullanilan tablo donemi dagilimi.

    python scripts/audit_live_vs_panel.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import pit_panel  # noqa: E402
from research_survivorship import RESEARCH, prepared  # noqa: E402

DB = ROOT / "data" / "bist_history.db"
PANEL = "factors_monthly_kapdates.parquet"
FINANCIAL_METRICS = ("pb", "roe", "roa", "nim", "npl_ratio", "car", "combined_ratio")


def timing(con: sqlite3.Connection, days: pd.DatetimeIndex) -> list[dict]:
    """Ay basina canlinin ilk basarili kosusu ve backtest'in karar gunune gore gecikmesi."""
    runs = pd.read_sql_query("SELECT as_of_date FROM runs WHERE status != 'halted' ORDER BY as_of_date", con)
    runs["d"] = pd.to_datetime(runs["as_of_date"])
    out = []
    for m, g in runs.groupby(runs["d"].dt.to_period("M")):
        first = g["d"].min()
        bt = days[days < m.start_time][-1]  # onceki ayin son islem gunu (panel ay sonu verisi)
        live_d0 = days[days <= first][-1]   # canlinin gordugu son kapanis
        out.append({"month": str(m), "backtest_signal_day": str(bt.date()), "live_first_run": str(first.date()),
                    "live_last_close": str(live_d0.date()),
                    "trading_days_late": int(((days > bt) & (days <= live_d0)).sum())})
    return out


def ranking_agreement(panel: pd.DataFrame, con: sqlite3.Connection) -> list[dict]:
    last = panel["date"].max()
    p = panel.loc[panel["date"] == last, ["ticker", "value_sn_z"]].dropna()
    out = []
    days = [r[0] for r in con.execute(
        "SELECT DISTINCT as_of_date FROM scores WHERE valid_metric_count IS NOT NULL ORDER BY as_of_date")]
    for day in days:
        live = pd.read_sql_query(
            "SELECT ticker, valuation_z, metrics_used FROM scores "
            "WHERE as_of_date=? AND bucket='long_term' AND valuation_z IS NOT NULL", con, params=(day,))
        live = live[~live["metrics_used"].fillna("").str.split(",").map(lambda u: bool(set(u) & set(FINANCIAL_METRICS)))]
        m = p.merge(live, on="ticker")
        n = max(1, round(len(m) * 0.2))
        top_p = set(m.nlargest(n, "value_sn_z")["ticker"])
        top_l = set(m.nlargest(n, "valuation_z")["ticker"])
        out.append({"live_day": day, "panel_month_end": str(last.date()), "panel_names": len(p),
                    "live_names": len(live), "common": len(m),
                    "rank_corr": round(float(m["value_sn_z"].rank().corr(m["valuation_z"].rank())), 3),
                    "top20_size": n, "top20_overlap": len(top_p & top_l),
                    "top20_overlap_pct": round(100 * len(top_p & top_l) / n, 1),
                    "only_panel": sorted(top_p - top_l), "only_live": sorted(top_l - top_p)})
    return out


def panel_drift(panel: pd.DataFrame) -> dict:
    """Ayni panelde ardisik iki ay sonu arasindaki ust %20 ortusmesi (fiyat/tablo guncellemesi kaynakli dogal degisim)."""
    months = sorted(panel["date"].unique())[-2:]
    a, b = (panel[panel["date"] == d][["ticker", "value_sn_z"]].dropna() for d in months)
    m = a.merge(b, on="ticker", suffixes=("_a", "_b"))
    n = max(1, round(len(m) * 0.2))
    keep = len(set(m.nlargest(n, "value_sn_z_a")["ticker"]) & set(m.nlargest(n, "value_sn_z_b")["ticker"]))
    return {"months": [str(pd.Timestamp(d).date()) for d in months], "common": len(m),
            "rank_corr": round(float(m["value_sn_z_a"].rank().corr(m["value_sn_z_b"].rank())), 3),
            "top20_overlap_pct": round(100 * keep / n, 1)}


def main() -> None:
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    raw = pd.read_parquet(RESEARCH / PANEL)
    panel = prepared(raw, market_m)
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    days = pd.DatetimeIndex(pd.to_datetime(fx["date"]).dt.normalize()).sort_values()
    # fx serisi bittiyse is gunleriyle uzat (yalnizca zamanlama sayimi icin)
    days = days.append(pd.bdate_range(days[-1] + pd.Timedelta(days=1), date.today()))
    last = raw[pd.to_datetime(raw["date"]) == pd.to_datetime(raw["date"]).max()]
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        result = {"as_of": date.today().isoformat(), "panel_file": PANEL,
                  "panel_last_stmt_period": last["stmt_period"].value_counts().to_dict(),
                  "timing": timing(con, days), "ranking": ranking_agreement(panel, con),
                  "panel_month_to_month": panel_drift(panel)}
    finally:
        con.close()
    print(json.dumps({k: v for k, v in result.items() if k != "ranking"}, indent=1, ensure_ascii=False))
    for r in result["ranking"]:
        print({k: v for k, v in r.items() if k not in ("only_panel", "only_live")})
    out = ROOT / "data" / "reports" / f"audit_live_vs_panel_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
