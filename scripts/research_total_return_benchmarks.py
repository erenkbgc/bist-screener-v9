#!/usr/bin/env python3
"""Toplam getiri ve yatirim yapilabilir benchmark'lar
(docs/research/total_return_benchmarks_preregistration.md).

Strateji: portfoy backtest'inin ana spesifikasyonu (P0, 1M TL, base maliyet, ertesi
kapanis). Benchmark'lar: B1 EW evren (maliyetsiz, PR #43), B2 EW evren ayni
simulator ve maliyetle, B3 BIST 100 getiri (XU100_CFNNTLTL), B4 BIST Tum getiri
(XUTUM_CFNNTLTL). Etiketler on-kayitta; canli kural degismez.

    python scripts/research_total_return_benchmarks.py
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
from core import portfolio_backtest as pb  # noqa: E402
from research_portfolio_backtest import RESEARCH, SPLIT, attach_benchmarks, build  # noqa: E402

TR_PATH = RESEARCH / "tr_indices.parquet"
TR_CODES = {"xu100_tr": "XU100_CFNNTLTL", "xutum_tr": "XUTUM_CFNNTLTL"}
EARLY_START = pd.Timestamp("2018-08-01")


def tr_indices(refresh: bool = False) -> pd.DataFrame:
    """Gunluk getiri endeksi kapanislari (TradingView, borsapy); onbellek tr_indices.parquet."""
    if TR_PATH.exists() and not refresh:
        return pd.read_parquet(TR_PATH)
    import borsapy as bp
    cols = {}
    for name, code in TR_CODES.items():
        h = bp.Index(code).history(period="max")
        idx = pd.to_datetime(h.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        cols[name] = pd.Series(h["Close"].astype(float).to_numpy(), index=idx.normalize())
    out = pd.DataFrame(cols).sort_index()
    out.index.name = "date"
    out.to_parquet(TR_PATH)
    return out


def window_returns(series: pd.Series, p: pd.DataFrame, ctx: dict) -> np.ndarray:
    """Strateji pencereleriyle ayni (d0 -> sonraki kararin d0'i) getiri."""
    months, d0_of = ctx["months"], ctx["d0_of"]
    nxt = {months[k]: months[k + 1] for k in range(len(months) - 1)}
    s = series.reindex(ctx["fx"].index).ffill()
    d0 = p["date"].map(d0_of)
    d1 = p["date"].map(lambda t: d0_of[nxt[t]])
    return s.reindex(d1).to_numpy() / s.reindex(d0).to_numpy() - 1


def compare(port: pd.Series, bench: pd.Series) -> dict:
    a = (port - bench).dropna()
    if len(a) < 3:
        return {"months": len(a)}
    m, t, n = fb.newey_west_t(a, 6)
    te = float(a.std() * np.sqrt(12))
    both = pd.concat([port, bench], axis=1).dropna()
    cagr = lambda r: float((1 + r).prod() ** (12 / len(r)) - 1)  # noqa: E731
    return {"months": n, "active_ann_pct": round(1200 * m, 2), "t": round(t, 2),
            "tracking_error_pct": round(100 * te, 2), "ir": round(12 * m / te, 2) if te > 0 else None,
            "cagr_strategy_pct": round(100 * cagr(both.iloc[:, 0]), 2),
            "cagr_benchmark_pct": round(100 * cagr(both.iloc[:, 1]), 2)}


def label(r: dict) -> str:
    if r.get("months", 0) < 3:
        return "NO_DATA"
    if r["active_ann_pct"] <= 0:
        return "BEHIND"
    return "BEATS" if r["t"] > 2 else "AHEAD_NOT_SIGNIFICANT"


def main() -> None:
    sel, mkt, ctx = build(include_universe=True)
    months = ctx["months"]
    cap = {t: 1e6 * ctx["cpi_rel"][t] for t in months}
    costs = pb.Costs()

    strat = attach_benchmarks(pb.simulate(sel["P0"], months, ctx["d0_of"], mkt, ctx["universe_liq"], cap,
                                          costs=costs), ctx)
    ew_raw = pb.simulate(sel["EW"], months, ctx["d0_of"], mkt, ctx["universe_liq"], cap, costs=costs)
    ew = ew_raw.set_index("date")
    p = strat.set_index("date")
    tr = tr_indices()
    p["b1"] = p["bench"]
    p["b2"] = ew["port"].reindex(p.index)
    for name in TR_CODES:
        p[name] = window_returns(tr[name], strat, ctx)
    p["xu_price"] = p["xu"]
    benches = {"B1_ew_universe_zero_cost": "b1", "B2_ew_universe_costed": "b2",
               "B3_bist100_total_return": "xu100_tr", "B4_bist_all_total_return": "xutum_tr",
               "xu100_price": "xu_price"}
    windows = {"discovery": p.index < SPLIT, "early_2018_08_2020": (p.index >= EARLY_START) & (p.index < SPLIT),
               "holdout": p.index >= SPLIT}

    result = {"as_of": date.today().isoformat(), "months": [str(months[0].date()), str(months[-1].date())],
              "tr_first_date": {k: str(tr[k].first_valid_index().date()) for k in TR_CODES}, "windows": {}}
    for w, m in windows.items():
        sub = p[m]
        result["windows"][w] = {name: compare(sub["port"], sub[col]) for name, col in benches.items()}
        result["windows"][w]["B4_minus_B3"] = compare(sub["xutum_tr"], sub["xu100_tr"])
    h = ew_raw[ew_raw["date"] >= SPLIT]
    result["B2_costs"] = {"cost_ann_pct": round(1200 * float(h["cost"].mean()), 2),
                          "turnover_pct": round(100 * float(h["turnover"].mean()), 1),
                          "avg_names": round(float(h["n"].mean()), 1)}
    result["labels_holdout"] = {name: label(result["windows"]["holdout"][name]) for name in benches}
    # PR #43 ana spesifikasyonuyla ayni mi (regresyon kontrolu)
    result["strategy_holdout_vs_b1"] = result["windows"]["holdout"]["B1_ew_universe_zero_cost"]

    for w, res in result["windows"].items():
        print(f"\n== {w}")
        for name, r in res.items():
            if r.get("months", 0) >= 3:
                print(f"  {name:28s} {r['active_ann_pct']:7.2f}%/yr (t {r['t']:5.2f})  TE {r['tracking_error_pct']:5.1f}"
                      f"  IR {r['ir']}  CAGR {r['cagr_strategy_pct']:6.1f} vs {r['cagr_benchmark_pct']:6.1f}  n={r['months']}")
    print(f"\nB2 maliyet: {result['B2_costs']}")
    print(f"Etiketler (holdout): {json.dumps(result['labels_holdout'], indent=1)}")
    out = ROOT / "data" / "reports" / f"research_total_return_benchmarks_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
