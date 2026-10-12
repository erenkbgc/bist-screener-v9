#!/usr/bin/env python3
"""On-kayitli Ramazan ve tatil oncesi etkisi (docs/research/ramadan_holiday_preregistration.md).

    pip install -r requirements-research.txt
    python scripts/research_ramadan_holiday.py
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

RESEARCH = ROOT / "data" / "research"
START, END = "2005-01-01", "2026-10-10"
SPLIT = pd.Timestamp("2016-01-01")
NW_LAGS = 5
HLZ_T, HOLDOUT_T = 3.0, 2.0
AH_YEARS = range(1426, 1448)


def load_market() -> pd.DataFrame:
    path = RESEARCH / "xu100_usdtry_yf_daily.parquet"
    if not path.exists():
        import yfinance as yf
        x = yf.download(["XU100.IS", "USDTRY=X"], start=START, end=END, auto_adjust=False, progress=False)["Close"]
        x.index = pd.to_datetime(x.index).tz_localize(None).normalize()
        x.to_parquet(path)
    x = pd.read_parquet(path)
    usd = x["USDTRY=X"].ffill()
    m = pd.DataFrame({"xu": x["XU100.IS"], "usdtry": usd}).dropna(subset=["xu"])
    m = m[(m.index >= START) & (m.index < END)]
    m["r_tl"] = np.log(m["xu"]).diff()
    m["r_usd"] = np.log(m["xu"] / m["usdtry"]).diff()
    return m.dropna(subset=["r_tl", "r_usd"])


def ramadan_ranges() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    from hijridate import Hijri
    out = []
    for y in AH_YEARS:
        start = pd.Timestamp(Hijri(y, 9, 1).to_gregorian().isoformat())
        end = pd.Timestamp(Hijri(y, 10, 1).to_gregorian().isoformat()) - pd.Timedelta(days=1)
        out.append((start, end))
    return out


def ramadan_flag(days: pd.DatetimeIndex, ranges) -> pd.Series:
    f = pd.Series(False, index=days)
    for a, b in ranges:
        f[(days >= a) & (days <= b)] = True
    return f


def pre_holiday_flag(days: pd.DatetimeIndex) -> pd.Series:
    """t'den sonraki ilk hafta ici gun islem gunu degilse 1."""
    trading = set(days)
    nxt = days + pd.offsets.BDay(1)
    return pd.Series([d not in trading for d in nxt], index=days) & (days < days.max())


def dummy_regression(r: pd.Series, d: pd.Series) -> dict:
    """r = a + b D (OLS) ile Newey-West t."""
    y = r.to_numpy()
    x = np.column_stack([np.ones(len(y)), d.astype(float).to_numpy()])
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    e = y - x @ beta
    xe = x * e[:, None]
    s = xe.T @ xe
    for lag in range(1, NW_LAGS + 1):
        w = 1 - lag / (NW_LAGS + 1)
        g = xe[lag:].T @ xe[:-lag]
        s += w * (g + g.T)
    se = np.sqrt(np.diag(xtx_inv @ s @ xtx_inv))
    on, off = r[d], r[~d]
    return {"days_flagged": int(d.sum()), "days": len(r),
            "b_daily_bps": round(1e4 * beta[1], 2), "b_ann_pct": round(100 * 252 * beta[1], 2),
            "t": round(beta[1] / se[1], 2),
            "median_diff_bps": round(1e4 * (on.median() - off.median()), 2),
            "vol_ratio": round(float(on.std() / off.std()), 3)}


def per_ramadan(m: pd.DataFrame, ranges) -> dict:
    above = []
    for a, b in ranges:
        yr = m[m.index.year == a.year]
        inside = yr[(yr.index >= a) & (yr.index <= b)]["r_usd"]
        outside = yr[~((yr.index >= a) & (yr.index <= b))]["r_usd"]
        if len(inside) >= 10:
            above.append(bool(inside.mean() > outside.mean()))
    return {"ramadans": len(above), "above_year_mean": int(sum(above))}


def verdict(res: dict) -> str:
    d, h = res["usd"]["discovery"], res["usd"]["holdout"]
    tl_ok = res["tl"]["discovery"]["b_daily_bps"] > 0 and res["tl"]["holdout"]["b_daily_bps"] > 0
    if d["b_daily_bps"] > 0 and d["t"] > HLZ_T and h["b_daily_bps"] > 0 and h["t"] > HOLDOUT_T and tl_ok:
        return "PASS"
    return "FAIL"


def main() -> None:
    m = load_market()
    ranges = ramadan_ranges()
    flags = {"R1_ramadan": ramadan_flag(m.index, ranges), "R2_pre_holiday": pre_holiday_flag(m.index)}
    result = {"as_of": date.today().isoformat(), "sample": [str(m.index.min().date()), str(m.index.max().date())],
              "tests": {}}
    for name, f in flags.items():
        res = {}
        for cur in ("usd", "tl"):
            r = m[f"r_{cur}"]
            res[cur] = {w: dummy_regression(r[mask], f[mask])
                        for w, mask in (("discovery", m.index < SPLIT), ("holdout", m.index >= SPLIT))}
        res["verdict"] = verdict(res)
        result["tests"][name] = res
    result["tests"]["R1_ramadan"]["per_ramadan_usd"] = per_ramadan(m, ranges)
    out = ROOT / "data" / "reports" / f"research_ramadan_holiday_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
