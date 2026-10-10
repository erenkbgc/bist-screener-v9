#!/usr/bin/env python3
"""Teshis: skorun ust listesine "cokmus" hisseler ne siklikla giriyor ve sonra ne oluyor?

Level-up plani Faz 1. Kullanicinin supesinin sayisal karsiligi: 5 yilda %70+
dusmus hisseler firsat olarak cikiyor. Bu script iki soruyu olcer:
  1. Her ay mevcut skor vekiline gore ust 4 (ve ust dilim) hissenin kaci,
     5 yillik zirvesinin %70+ altinda?
  2. Bu hisselerin sonraki 6 ay USD getirisi ve XU100'e gore fazla getirisi,
     ayni ust dilimdeki cokmemis hisselerle kiyasla.

Bu bir on-kayitli test DEGIL, tanimlayici teshistir. Karar mantigini
degistirmez. Resmi test Faz 2 on-kaydinda (H1 sikinti, H2 dusus x kalite).

Skor vekili: scripts/backtest_factor_model.py::add_composites ile ayni
(weights.yaml degerleme/momentum/dusuk-vol agirliklari; katalizor ve ortaklik
icin gecmis veri yok).

Sinirlar:
  - Hayatta kalma yanliligi: panel bugunku listedir. Cokup borsadan cikan
    hisseler yok; cokmus grubun getirisi YUKARI yanlidir.
  - 6 aylik ileri getiriler aylik orneklemde ortusur; t istatistigi Newey-West
    (6 gecikme) ile hesaplanir.
  - Dusus aylik kapanisla olculur (gun ici dip gorunmez); en az 36 ay gecmis istenir.

    python scripts/diagnose_crashed_picks.py
    python scripts/diagnose_crashed_picks.py --since 2016-01-01 --top 4
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from backtest_factor_model import FACTORS, add_composites  # noqa: E402

RESEARCH = ROOT / "data" / "research"
CRASH_PCT = -70.0
PEAK_MONTHS = 60
MIN_HISTORY_MONTHS = 36


def drawdown_from_peak(prices: pd.DataFrame) -> pd.DataFrame:
    p = prices.sort_values(["ticker", "date"]).copy()
    g = p.groupby("ticker")["adj"]
    peak = g.transform(lambda s: s.rolling(PEAK_MONTHS, min_periods=MIN_HISTORY_MONTHS).max())
    p["dd_5y_pct"] = (p["adj"] / peak - 1) * 100
    return p[["date", "ticker", "dd_5y_pct"]]


def month_end(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp("M")


def macro_6m() -> pd.DataFrame:
    m = pd.read_parquet(RESEARCH / "macro_monthly.parquet")[["xu100", "usdtry"]].dropna()
    m.index = m.index.to_period("M").to_timestamp("M")
    out = pd.DataFrame(index=m.index)
    out["fx_6m"] = m["usdtry"].shift(-6) / m["usdtry"] - 1
    out["xu_6m"] = m["xu100"].shift(-6) / m["xu100"] - 1
    return out


def live_picks(prices: pd.DataFrame) -> dict:
    """Canli DB'deki uzun vade tahminleri: her hisse son panel ayindaki 5 yillik
    zirveden dususe gore. Durum her (tarih, hisse) satiri icin ayri sayilir."""
    db = ROOT / "data" / "bist_history.db"
    if not db.exists():
        return {}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = pd.read_sql(
        "SELECT p.as_of_date, p.ticker, s.candidate_state FROM predictions p "
        "JOIN scores s ON s.as_of_date=p.as_of_date AND s.ticker=p.ticker AND s.bucket=p.bucket "
        "WHERE p.bucket='long_term'", con)
    con.close()
    dd = drawdown_from_peak(prices).dropna().sort_values("date").groupby("ticker").tail(1)
    q = q.merge(dd[["ticker", "dd_5y_pct"]], on="ticker", how="inner")
    q["crashed"] = q["dd_5y_pct"] <= CRASH_PCT
    by_state = {st: {"rows": int(len(g)), "tickers": int(g["ticker"].nunique()),
                     "crash_share_pct": round(100 * float(g["crashed"].mean()), 1),
                     "crashed_tickers": sorted(g.loc[g["crashed"], "ticker"].unique().tolist())}
                for st, g in q.groupby("candidate_state")}
    universe = dd[dd["date"] == dd["date"].max()]
    return {"dates": sorted(q["as_of_date"].unique().tolist()), "by_state": by_state,
            "panel_universe_crash_share_pct": round(100 * float((universe["dd_5y_pct"] <= CRASH_PCT).mean()), 1),
            "note": "Drawdown measured at last panel month, not at prediction date."}


def summarize(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"n": 0}
    monthly = sub.groupby("date")[["ret_usd_6m", "excess_6m"]].mean()
    out = {"n": int(len(sub)), "months": int(len(monthly))}
    for col in ("ret_usd_6m", "excess_6m"):
        m, t, _ = fb.newey_west_t(monthly[col].dropna(), lags=6)
        out[f"mean_{col}_pct"] = round(100 * m, 2)
        out[f"median_{col}_pct"] = round(100 * float(sub[col].median()), 2)
        out[f"{col}_nw_t"] = round(t, 2)
    out["share_negative_excess_pct"] = round(100 * float((sub["excess_6m"] < 0).mean()), 1)
    out["share_excess_below_minus30_pct"] = round(100 * float((sub["excess_6m"] < -0.30).mean()), 1)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2023-01-01", help="Ust liste sayiminin baslangici (son 3 yil)")
    ap.add_argument("--top", type=int, default=4)
    ap.add_argument("--top-quantile", type=float, default=0.2)
    ap.add_argument("--liq-drop", type=float, default=0.3)
    args = ap.parse_args()

    raw = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    raw["date"] = month_end(raw["date"])
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=args.liq_drop))
    df = df[df["model_proxy_z"].notna()]

    prices = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    prices["date"] = month_end(prices["date"])
    df = df.merge(drawdown_from_peak(prices), on=["date", "ticker"], how="left")
    df = df.merge(macro_6m(), left_on="date", right_index=True, how="left")
    df["ret_usd_6m"] = (1 + df["fwd_ret_6m"]) / (1 + df["fx_6m"]) - 1
    df["excess_6m"] = df["fwd_ret_6m"] - df["xu_6m"]
    df["crashed"] = df["dd_5y_pct"] <= CRASH_PCT

    df["rank"] = df.groupby("date")["model_proxy_z"].rank(ascending=False, method="first")
    df["n_month"] = df.groupby("date")["model_proxy_z"].transform("size")
    top_q = df[df["rank"] <= np.ceil(df["n_month"] * args.top_quantile)]
    top_n = df[df["rank"] <= args.top]

    since = pd.Timestamp(args.since)
    recent_top_n = top_n[top_n["date"] >= since]
    with_hist = df["dd_5y_pct"].notna()

    def share(sub):
        s = sub[sub["dd_5y_pct"].notna()]
        return round(100 * float(s["crashed"].mean()), 1) if len(s) else None

    evaluable = lambda s: s.dropna(subset=["ret_usd_6m", "excess_6m"])  # noqa: E731
    result = {
        "as_of": date.today().isoformat(),
        "panel": {"start": str(df["date"].min().date()), "end": str(df["date"].max().date()),
                  "tickers": int(df["ticker"].nunique())},
        "params": {"crash_pct": CRASH_PCT, "peak_months": PEAK_MONTHS, "min_history_months": MIN_HISTORY_MONTHS,
                   "top": args.top, "top_quantile": args.top_quantile, "since": args.since,
                   "liq_drop": args.liq_drop},
        "crash_share_pct": {
            "universe_all_months": share(df[with_hist]),
            "top_quantile_all_months": share(top_q),
            f"top{args.top}_all_months": share(top_n),
            f"top{args.top}_since": share(recent_top_n),
        },
        f"top{args.top}_since_crashed_picks": [
            {"date": str(r.date.date()), "ticker": r.ticker, "dd_5y_pct": round(r.dd_5y_pct, 1),
             "ret_usd_6m_pct": None if pd.isna(r.ret_usd_6m) else round(100 * r.ret_usd_6m, 1),
             "excess_6m_pct": None if pd.isna(r.excess_6m) else round(100 * r.excess_6m, 1)}
            for r in recent_top_n[recent_top_n["crashed"]].itertuples()
        ],
        "forward_6m": {
            "top_quantile_crashed": summarize(evaluable(top_q[top_q["crashed"]])),
            "top_quantile_not_crashed": summarize(evaluable(top_q[with_hist.loc[top_q.index] & ~top_q["crashed"]])),
            f"top{args.top}_crashed": summarize(evaluable(top_n[top_n["crashed"]])),
            f"top{args.top}_not_crashed": summarize(evaluable(top_n[with_hist.loc[top_n.index] & ~top_n["crashed"]])),
            "universe_crashed": summarize(evaluable(df[df["crashed"]])),
            "universe_not_crashed": summarize(evaluable(df[with_hist & ~df["crashed"]])),
        },
        "live_db_long_term_picks": live_picks(prices),
        "caveats": [
            "Survivorship: panel excludes delisted names; crashed-group returns are biased upward.",
            "Descriptive diagnostic, not a pre-registered test; does not change live scoring.",
            "6-month forward windows overlap; t-stats are Newey-West with 6 lags on monthly group means.",
        ],
    }
    out = ROOT / "data" / "reports" / f"diagnose_crashed_picks_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in result.items() if not k.endswith("_crashed_picks")}, indent=2, ensure_ascii=False))
    print(f"\n{len(result[f'top{args.top}_since_crashed_picks'])} cokmus ust-{args.top} secimi -> {out}")


if __name__ == "__main__":
    main()
