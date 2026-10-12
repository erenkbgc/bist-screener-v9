#!/usr/bin/env python3
"""On-kayitli yayin tarihi duyarliligi (docs/research/kap_report_dates_preregistration.md).

Onbellekteki ceyreklik tablo, fiyat ve pay olaylariyla paneli uc varyantta yeniden
kurar (A varsayim, B gercek KAP + varsayim, C yalnizca gercek KAP) ve value_sn'i
karsilastirir.

    python scripts/build_pit_panel.py      # quarterly/monthly_prices/share_events onbellegi
    python scripts/research_kap_report_dates.py
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
from core import pit_panel  # noqa: E402
from backtest_factor_model import FACTORS, add_composites, ic_stats, spread_stats  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
COST_BPS = 20.0


def lag_stats(q: pd.DataFrame, dates: pd.DataFrame) -> dict:
    m = q.merge(dates, on=["ticker", "period"], how="left")
    m["assumed"] = m["period"].map(pit_panel.available_at)
    matched = m[m["kap_available_at"].notna()].copy()
    matched["actual_lag"] = (matched["kap_available_at"] - matched["period"].map(pit_panel.period_end)).dt.days
    matched["late_days"] = (matched["kap_available_at"] - matched["assumed"]).dt.days
    out = {"rows": len(m), "matched_pct": round(100 * len(matched) / len(m), 1),
           "late_vs_assumed_pct": round(100 * float((matched["late_days"] > 0).mean()), 1),
           "late_days_median_when_late": float(matched.loc[matched["late_days"] > 0, "late_days"].median()),
           "by_quarter": {}}
    matched["qn"] = matched["period"].str[-1]
    for qn, g in matched.groupby("qn"):
        out["by_quarter"][f"Q{qn}"] = {
            "n": len(g), "lag_p10": float(g["actual_lag"].quantile(0.1)),
            "lag_median": float(g["actual_lag"].median()), "lag_p90": float(g["actual_lag"].quantile(0.9)),
            "late_vs_assumed_pct": round(100 * float((g["late_days"] > 0).mean()), 1)}
    return out


def value_stats(factors: pd.DataFrame) -> dict:
    df = add_composites(fb.prepare(factors, FACTORS, liq_drop_pct=0.3))
    out = {}
    for name, sub in (("discovery", df[df["date"] < SPLIT]), ("holdout", df[df["date"] >= SPLIT])):
        ic = ic_stats(sub, "value_sn_z", "fwd_ret_1m", lags=1)
        sp = spread_stats(sub, "value_sn_z", COST_BPS)
        out[name] = {"months": ic["months"], "ic1": ic["ic_mean"], "ic1_t": ic["ic_t"], **sp}
    return out


def main() -> None:
    q = pd.read_parquet(RESEARCH / "quarterly.parquet")
    q["available_at"] = q["period"].map(pit_panel.available_at)  # A: onbellek hangi surumle kurulmus olursa olsun
    px = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    ev = pd.read_parquet(RESEARCH / "share_events.parquet")
    sectors = {r["ticker"]: r["sektor"] for r in
               json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))}
    dates = pit_panel.kap_report_dates(pd.read_parquet(RESEARCH / "kap_archive.parquet"))

    variants = {"A": q, "B": pit_panel.apply_report_dates(q, dates),
                "C": pit_panel.apply_report_dates(q, dates, strict=True)}
    result = {"as_of": date.today().isoformat(), "lags": lag_stats(q, dates), "value_sn": {}}
    for name, qv in variants.items():
        f = pit_panel.build_monthly_factors(qv, px, ev, sectors)
        result["value_sn"][name] = value_stats(f)
        if name == "B":
            f.to_parquet(RESEARCH / "factors_monthly_kapdates.parquet", index=False)
        print(f"  {name}: {len(f)} satir", flush=True)

    b = result["value_sn"]["B"]
    robust = all(b[w]["top_active_net_ann_pct"] > 0 and b[w]["top_active_net_t"] > 2.0 for w in ("discovery", "holdout"))
    c_flip = np.sign(result["value_sn"]["C"]["holdout"]["top_active_net_ann_pct"]) != \
        np.sign(result["value_sn"]["A"]["holdout"]["top_active_net_ann_pct"])
    result["decision"] = {"B_verdict": "ROBUST" if robust else "LAG_SENSITIVE", "C_holdout_sign_flip": bool(c_flip)}
    print(json.dumps(result, indent=1, ensure_ascii=False, default=float))
    out = ROOT / "data" / "reports" / f"research_kap_report_dates_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=float))
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
