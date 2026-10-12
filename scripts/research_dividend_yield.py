#!/usr/bin/env python3
"""On-kayitli temettu verimi faktoru (docs/research/dividend_yield_preregistration.md).

    python scripts/fetch_dividends.py
    python scripts/research_dividend_yield.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from research_long_term import load  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
COST_BPS = 20.0
HLZ_T, HOLDOUT_T = 3.0, 2.0


def add_dy(df: pd.DataFrame, div: pd.DataFrame, failed: set[str]) -> pd.DataFrame:
    """dy = son 365 gun toplam nakit temettu / ay sonu piyasa degeri."""
    df = df[~df["ticker"].isin(failed)].copy()
    by = {t: g.sort_values("ex_date") for t, g in div.groupby("ticker")}
    vals = []
    for t, d, mcap in zip(df["ticker"], df["date"], df["mcap"]):
        g = by.get(t)
        if g is None or not mcap or mcap <= 0:
            vals.append(0.0 if g is None else np.nan)
            continue
        win = g[(g["ex_date"] > d - pd.Timedelta(days=365)) & (g["ex_date"] <= d)]["total_dividend"]
        vals.append(float(win.sum()) / mcap)
    df["dy"] = vals
    return df.dropna(subset=["dy"])


def long_only(df: pd.DataFrame, pick, bench) -> pd.DataFrame:
    """Ay basina secilen sepet - kiyas sepeti, devir maliyeti dahil (yalnizca secilen bacak)."""
    rows, prev = [], set()
    for t, g in df.groupby("date"):
        g = g.dropna(subset=["fwd_ret_1m"])
        s = set(pick(g))
        b = set(bench(g))
        if len(s) < 5 or len(b) < 5:
            prev = s
            continue
        turnover = 1 - len(s & prev) / len(s) if prev else 1.0
        r = g.set_index("ticker")["fwd_ret_1m"]
        rows.append({"date": t, "d": r[list(s)].mean() - r[list(b)].mean() - 2 * turnover * COST_BPS / 1e4,
                     "turnover": turnover, "n": len(s)})
        prev = s
    return pd.DataFrame(rows)


def top_q(col: str, among=None):
    def f(g):
        h = g if among is None else g[among(g)]
        r = h[col].rank(ascending=False, pct=True)
        return h.loc[r <= 0.2, "ticker"]
    return f


def stats(p: pd.DataFrame) -> dict:
    m, t, n = fb.newey_west_t(p["d"], 1)
    return {"months": n, "d_ann_pct": round(1200 * m, 2), "t": round(t, 2),
            "turnover_pct": round(100 * p["turnover"].mean(), 1), "avg_names": round(p["n"].mean(), 1)}


def main() -> None:
    div = pd.read_parquet(RESEARCH / "dividends.parquet")
    div["ex_date"] = pd.to_datetime(div["ex_date"])
    failed = set(json.loads((RESEARCH / "dividends_failed.json").read_text()))
    df = load()
    df = add_dy(df[df["value_sn_z"].notna()], div, failed)
    df["dy_z"] = df.groupby("date")["dy"].transform(fb.winsorize_z)
    df["comp_z"] = (df["value_sn_z"] + df["dy_z"]) / 2

    everyone = lambda g: g["ticker"]  # noqa: E731
    tests = {
        "Y1_top_dy_payers_vs_universe": long_only(df, top_q("dy", among=lambda g: g["dy"] > 0), everyone),
        "Y2_payers_vs_nonpayers": long_only(df, lambda g: g.loc[g["dy"] > 0, "ticker"],
                                            lambda g: g.loc[g["dy"] == 0, "ticker"]),
        "Y3_value_plus_dy_vs_value": long_only(df, top_q("comp_z"), top_q("value_sn_z")),
    }
    payer_share = df.groupby("date")["dy"].apply(lambda s: (s > 0).mean())
    result = {"as_of": date.today().isoformat(), "rows": len(df), "failed_tickers": len(failed),
              "payer_share_pct": {"discovery": round(100 * payer_share[payer_share.index < SPLIT].mean(), 1),
                                  "holdout": round(100 * payer_share[payer_share.index >= SPLIT].mean(), 1)},
              "corr_dy_value_sn": round(float(df[["dy_z", "value_sn_z"]].corr().iloc[0, 1]), 3), "tests": {}}
    for name, p in tests.items():
        d, h = stats(p[p["date"] < SPLIT]), stats(p[p["date"] >= SPLIT])
        ok = d["d_ann_pct"] > 0 and d["t"] > HLZ_T and h["d_ann_pct"] > 0 and h["t"] > HOLDOUT_T
        result["tests"][name] = {"discovery": d, "holdout": h, "verdict": "PASS" if ok else "FAIL"}
    out = ROOT / "data" / "reports" / f"research_dividend_yield_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
