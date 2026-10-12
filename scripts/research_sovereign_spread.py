#!/usr/bin/env python3
"""On-kayitli ulke riski (Eurobond spread) testi (docs/research/sovereign_spread_preregistration.md).

    python scripts/fetch_eurobond_monthly.py
    python scripts/research_sovereign_spread.py
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

import research_macro_drivers as md  # noqa: E402

RESEARCH = ROOT / "data" / "research"
ALPHA = 0.05 / 3
MIN_YEARS, MAX_YEARS = 3.0, 30.0
UST_TENORS = (("^FVX", 5.0), ("^TNX", 10.0), ("^TYX", 30.0))


def ust_curve(ust_row: pd.Series, years: float) -> float:
    xs = [t for _, t in UST_TENORS]
    ys = [ust_row[c] for c, _ in UST_TENORS]
    return float(np.interp(years, xs, ys))


def spread_series(eb: pd.DataFrame, ust: pd.DataFrame) -> pd.Series:
    out = {}
    ust = ust.sort_index().ffill()
    for m, g in eb.groupby("month"):
        d = g["date"].iloc[0]
        u = ust.loc[:d].iloc[-1] if len(ust.loc[:d]) else None
        if u is None or u.isna().any():
            continue
        yrs = (g["maturity"] - g["date"]).dt.days / 365.25
        g = g[(yrs >= MIN_YEARS) & (yrs <= MAX_YEARS)]
        if g.empty:
            continue
        yrs = (g["maturity"] - g["date"]).dt.days / 365.25
        sp = [y - ust_curve(u, t) for y, t in zip(g["yield"], yrs)]
        out[pd.Timestamp(m)] = float(np.median(sp))
    return pd.Series(out).sort_index()


def main() -> None:
    eb = pd.read_parquet(RESEARCH / "eurobond_monthly.parquet")
    eb["date"] = pd.to_datetime(eb["date"])
    eb["maturity"] = pd.to_datetime(eb["maturity"])
    ust = pd.read_parquet(RESEARCH / "ust_daily.parquet")
    sp = spread_series(eb, ust)

    df = md.build(md.load(refresh=False))
    df.index = pd.to_datetime(df.index).to_period("M").to_timestamp("M")
    sp.index = sp.index.to_period("M").to_timestamp("M")
    df["sp"] = sp.reindex(df.index)
    df["d_sp"] = df["sp"].diff()
    d = df.dropna(subset=["sp"])

    result = {"as_of": date.today().isoformat(), "months": [str(d.index.min().date()), str(d.index.max().date())],
              "spread_pp": {"mean": round(float(d["sp"].mean()), 2), "min": round(float(d["sp"].min()), 2),
                            "max": round(float(d["sp"].max()), 2), "last": round(float(d["sp"].iloc[-1]), 2)},
              "tests": {}}

    # C1 aciklama
    sub = d[["r_usd", "d_sp", "eem_ret"]].dropna()
    res = md.ols_hac(sub["r_usd"], sub[["d_sp", "eem_ret"]], lags=3)
    base = md.ols_hac(sub["r_usd"], sub[["eem_ret"]], lags=3)
    half = len(sub) // 2
    halves = [md.ols_hac(h["r_usd"], h[["d_sp", "eem_ret"]], lags=3).params["d_sp"]
              for h in (sub.iloc[:half], sub.iloc[half:])]
    c1 = {"months": len(sub), "b": round(float(res.params["d_sp"]), 4), "t": round(float(res.tvalues["d_sp"]), 2),
          "b_halves": [round(float(x), 4) for x in halves],
          "r2": round(float(res.rsquared), 3), "r2_eem_only": round(float(base.rsquared), 3)}
    c1["verdict"] = "PASS" if (c1["t"] < -3.0 and all(x < 0 for x in halves)) else "FAIL"
    result["tests"]["C1_explain_same_month"] = c1

    # C2 tahmin
    for name, ycol, h, lags in (("C2a_predict_1m", "y_h1", 1, 1), ("C2b_predict_12m", "y_h12", 12, 12)):
        s = d[[ycol, "sp"]].dropna()
        r = md.ols_hac(s[ycol], s[["sp"]], lags=lags)
        oos = md.oos_test(d["sp"], d[ycol], h)
        b, t = float(r.params["sp"]), float(r.tvalues["sp"])
        ok = b > 0 and t > 3.0 and (oos.get("oos_r2") or -1) > 0 and (oos.get("cw_p") or 1) < ALPHA
        result["tests"][name] = {"in_sample": {"months": len(s), "b": round(b, 4), "t": round(t, 2)},
                                 "oos": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in oos.items()},
                                 "verdict": "PASS" if ok else "FAIL"}
    out = ROOT / "data" / "reports" / f"research_sovereign_spread_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
