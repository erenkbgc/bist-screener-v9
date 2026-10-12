#!/usr/bin/env python3
"""On-kayitli sanayi uretimi testi (docs/research/industrial_production_preregistration.md).

    EVDS_API_KEY=... python scripts/research_industrial_production.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import research_macro_drivers as md  # noqa: E402
from core.factor_backtest import newey_west_t  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SERIES = "TP.TSANAY2021.BCD"
SPLIT = pd.Timestamp("2016-01-01")
ALPHA = 0.05 / 3
HLZ_T, HOLDOUT_T = 3.0, 2.0


def load_ipi() -> pd.Series:
    path = RESEARCH / "ipi_tsanay2021.parquet"
    if not path.exists():
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        if not os.environ.get("EVDS_API_KEY"):
            sys.exit("EVDS_API_KEY yok (.env).")
        import borsapy as bp
        h = bp.evds_series(SERIES, start="2004-01-01")
        h.to_parquet(path)
    h = pd.read_parquet(path)
    s = h.iloc[:, 0].astype(float)
    s.index = pd.to_datetime(s.index).to_period("M").to_timestamp("M")
    return s.sort_index()


def signals(ipi: pd.Series) -> pd.DataFrame:
    g = np.log(ipi / ipi.shift(12))
    surprise = g - g.shift(1).rolling(12, min_periods=12).mean()
    return pd.DataFrame({"g": g, "surprise": surprise})


def align(sig: pd.DataFrame, r_usd: pd.Series) -> pd.DataFrame:
    """Veri ayi m -> haber ayi m+2 (I1), tahmin ayi m+3 (I2/I3)."""
    out = sig.copy()
    out["release"] = out.index + pd.offsets.MonthEnd(2)
    out["r_release"] = r_usd.reindex(out["release"]).to_numpy()
    out["r_next"] = r_usd.reindex(out.index + pd.offsets.MonthEnd(3)).to_numpy()
    return out


def nw(y: pd.Series, x: pd.Series, lags: int = 1) -> tuple[float, float, int]:
    d = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    X = np.column_stack([np.ones(len(d)), d["x"]])
    xtx_inv = np.linalg.inv(X.T @ X)
    b = xtx_inv @ X.T @ d["y"].to_numpy()
    e = d["y"].to_numpy() - X @ b
    xe = X * e[:, None]
    s = xe.T @ xe
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        gm = xe[lag:].T @ xe[:-lag]
        s += w * (gm + gm.T)
    se = np.sqrt(np.diag(xtx_inv @ s @ xtx_inv))
    return float(b[1]), float(b[1] / se[1]), len(d)


def main() -> None:
    df = md.build(md.load(refresh=False))
    r_usd = df["r_usd"]
    r_usd.index = pd.to_datetime(r_usd.index).to_period("M").to_timestamp("M")
    a = align(signals(load_ipi()), r_usd)

    result = {"as_of": date.today().isoformat(), "series": SERIES,
              "data_months": [str(a.index.min().date()), str(a.index.max().date())], "tests": {}}
    i1 = {}
    for w, sub in (("discovery", a[a["release"] < SPLIT]), ("holdout", a[a["release"] >= SPLIT])):
        b, t, n = nw(sub["r_release"], sub["surprise"])
        i1[w] = {"months": n, "b": round(b, 3), "t": round(t, 2)}
    i1["verdict"] = "PASS" if (i1["discovery"]["b"] > 0 and i1["discovery"]["t"] > HLZ_T
                               and i1["holdout"]["b"] > 0 and i1["holdout"]["t"] > HOLDOUT_T) else "FAIL"
    result["tests"]["I1_reaction_release_month"] = i1

    for name, col in (("I2_predict_surprise", "surprise"), ("I3_predict_growth", "g")):
        b, t, n = nw(a["r_next"], a[col])
        x = a[col].copy()
        y = a["r_next"].copy()
        oos = md.oos_test(x, y, 1)
        ok = (b > 0 and t > HLZ_T and (oos.get("oos_r2") or -1) > 0 and (oos.get("cw_p") or 1) < ALPHA)
        result["tests"][name] = {"in_sample": {"months": n, "b": round(b, 3), "t": round(t, 2)},
                                 "oos": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in oos.items()},
                                 "verdict": "PASS" if ok else "FAIL"}
    m, t, n = newey_west_t(a["g"].dropna(), 1)
    result["descriptive"] = {"mean_yoy_growth_pct": round(100 * m, 2),
                             "corr_g_r_release": round(float(a[["g", "r_release"]].corr().iloc[0, 1]), 3)}
    out = ROOT / "data" / "reports" / f"research_industrial_production_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
