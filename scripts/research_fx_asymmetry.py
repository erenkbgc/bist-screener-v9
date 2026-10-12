#!/usr/bin/env python3
"""On-kayitli kur hassasiyeti asimetrisi (docs/research/fx_asymmetry_preregistration.md).

Her ay sonu t: son 36 ayda r_i = a + b_m r_XU100 + b_fx dln(USDTRY) ile hisse basina
kur betasi; besliklere ayrilir; S_{t+1} = Q5 - Q1 sonraki ay getirisi.
X1: S_{t+1} ~ dfx_{t+1} (ayni ay), X2: S_{t+1} ~ dfx_t (gecikmeli).

    python scripts/research_fx_asymmetry.py
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
from diagnose_crashed_picks import month_end  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
WINDOW, MIN_OBS = 36, 24
HLZ_T, HOLDOUT_T = 3.0, 2.0


def ols_nw(y: np.ndarray, x: np.ndarray, lags: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """OLS + Newey-West; x sabitsiz verilir. Doner: katsayilar, t'ler."""
    X = np.column_stack([np.ones(len(y)), x])
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ X.T @ y
    e = y - X @ b
    xe = X * e[:, None]
    s = xe.T @ xe
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        g = xe[lag:].T @ xe[:-lag]
        s += w * (g + g.T)
    se = np.sqrt(np.diag(xtx_inv @ s @ xtx_inv))
    return b, b / se


def fx_betas(ret: pd.DataFrame, mkt: pd.Series, dfx: pd.Series, t: pd.Timestamp, tickers) -> pd.Series:
    win = ret.loc[:t].tail(WINDOW)
    m, f = mkt.reindex(win.index), dfx.reindex(win.index)
    out = {}
    for tk in tickers:
        if tk not in win.columns:
            continue
        y = win[tk]
        ok = y.notna() & m.notna() & f.notna()
        if ok.sum() < MIN_OBS:
            continue
        X = np.column_stack([np.ones(ok.sum()), m[ok], f[ok]])
        out[tk] = np.linalg.lstsq(X, y[ok].to_numpy(), rcond=None)[0][2]
    return pd.Series(out, dtype=float)


def main() -> None:
    px = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    px["date"] = month_end(px["date"])
    adj = px.pivot_table(index="date", columns="ticker", values="adj", aggfunc="last").sort_index()
    ret = np.log(adj).diff()
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"])
    fxm = fx.set_index("date").sort_index().resample("ME").last()
    mkt = np.log(fxm["xu100"]).diff()
    dfx = np.log(fxm["usdtry"]).diff()

    panel = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    panel["date"] = month_end(panel["date"])
    uni = fb.prepare(panel, [], liq_drop_pct=0.3)

    rows, betas = [], []
    for t, g in uni.groupby("date"):
        b = fx_betas(ret, mkt, dfx, t, g["ticker"])
        g = g.set_index("ticker").join(b.rename("b_fx"), how="inner").dropna(subset=["b_fx", "fwd_ret_1m"])
        if len(g) < 30:
            continue
        q = g["b_fx"].rank(pct=True)
        t1 = t + pd.offsets.MonthEnd(1)
        rows.append({"date": t, "hold": t1, "S": g.loc[q > 0.8, "fwd_ret_1m"].mean() - g.loc[q <= 0.2, "fwd_ret_1m"].mean(),
                     "dfx_next": dfx.get(t1, np.nan), "dfx_now": dfx.get(t, np.nan), "n": len(g)})
        betas.append(g[["b_fx", "sector"]].assign(date=t))
    s = pd.DataFrame(rows).dropna()
    bt = pd.concat(betas)

    result = {"as_of": date.today().isoformat(), "months": len(s), "tests": {}, "descriptive": {}}
    for name, col, in (("X1_same_month", "dfx_next"), ("X2_next_month", "dfx_now")):
        res = {}
        for w, sub in (("discovery", s[s["hold"] < SPLIT]), ("holdout", s[s["hold"] >= SPLIT])):
            b, t = ols_nw(sub["S"].to_numpy(), sub[col].to_numpy(), lags=1)
            res[w] = {"months": len(sub), "slope": round(float(b[1]), 3), "t": round(float(t[1]), 2),
                      "intercept_ann_pct": round(1200 * float(b[0]), 2)}
        ok = (res["discovery"]["slope"] > 0 and res["discovery"]["t"] > HLZ_T
              and res["holdout"]["slope"] > 0 and res["holdout"]["t"] > HOLDOUT_T)
        res["verdict"] = "PASS" if ok else "FAIL"
        result["tests"][name] = res
    for w, sub in (("discovery", s[s["hold"] < SPLIT]), ("holdout", s[s["hold"] >= SPLIT])):
        m, t, n = fb.newey_west_t(sub["S"], 1)
        big = sub["dfx_now"] >= s["dfx_now"].quantile(0.75)
        result["descriptive"][w] = {"mean_S_ann_pct": round(1200 * m, 2), "t": round(t, 2),
                                    "S_after_big_lira_fall_pct": round(100 * sub.loc[big, "S"].mean(), 2),
                                    "S_after_other_months_pct": round(100 * sub.loc[~big, "S"].mean(), 2),
                                    "big_fall_months": int(big.sum())}
    by_sec = bt.groupby("sector")["b_fx"].agg(["mean", "count"])
    by_sec = by_sec[by_sec["count"] >= 200].sort_values("mean")
    result["descriptive"]["sector_mean_fx_beta"] = {k: round(v, 3) for k, v in by_sec["mean"].items()}
    out = ROOT / "data" / "reports" / f"research_fx_asymmetry_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
