#!/usr/bin/env python3
"""On-kayitli ogrenilen agirlik testi (docs/research/learned_weights_preregistration.md).

    python scripts/research_learned_weights.py

H-LW: genisleyen pencere IC agirlikli kompozit vs duz value_sn. E1/E2 kesifsel.
Gecme kurali on-kayitta; burada yalnizca uygulanir.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import long_term_research as ltr  # noqa: E402
from research_long_term import SPLIT, load  # noqa: E402

HLZ_T, HOLDOUT_T = 3.0, 2.0


def verdict(disc: dict, hold: dict, usd_ok: bool) -> str:
    if disc.get("diff_ann_pct", 0) > 0 and disc.get("t", 0) > HLZ_T \
            and hold.get("diff_ann_pct", 0) > 0 and hold.get("t", 0) > HOLDOUT_T and usd_ok:
        return "PASS"
    if disc.get("diff_ann_pct", 0) > 0 and hold.get("diff_ann_pct", 0) > 0 \
            and disc.get("t", 0) > 2 and hold.get("t", 0) > 2:
        return "SUPPORTED_NOT_CONFIRMED"
    return "FAIL"


def main() -> None:
    df = load()
    ics = ltr.monthly_ics(df, ltr.LW_FACTORS)
    weights = ltr.learned_ic_weights(ics, df["date"])
    df["hlw"] = ltr.weighted_composite(df, weights)
    df["e1"] = ltr.composite(df, "mom_12_1_z")
    df["e2"] = ((df["value_sn_z"] + df["gpa_z"].fillna(0) + df["mom_12_1_z"].fillna(0)) / 3) \
        .where(df["value_sn_z"].notna())

    live = weights.dropna().index
    df = df[df["date"].isin(live)]
    result = {"as_of": date.today().isoformat(), "split": str(SPLIT.date()),
              "first_month": str(live.min().date()), "last_month": str(live.max().date()),
              "full_sample_mean_ic": ics.mean().round(4).to_dict(),
              "weights_december": {str(d.date()): w.round(3).to_dict()
                                   for d, w in weights.dropna().iterrows() if d.month == 12},
              "weight_range": {f: [round(float(weights[f].min()), 3), round(float(weights[f].max()), 3)]
                               for f in weights.columns},
              "base": {}, "tests": {}}

    periods = {"discovery": df["date"] < SPLIT, "holdout": df["date"] >= SPLIT}
    base = {w: ltr.portfolio(df[m], "value_sn_z") for w, m in periods.items()}
    for w, p in base.items():
        result["base"][w] = {"tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}

    for name, col in (("H-LW", "hlw"), ("E1", "e1"), ("E2", "e2")):
        entry = {}
        for w, m in periods.items():
            p = ltr.portfolio(df[m], col)
            entry[w] = {"diff": ltr.diff_stats(base[w], p),
                        "diff_usd": ltr.diff_stats(base[w], p, "active_fwd_ret_1m_usd"),
                        "tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}
        usd_ok = entry["holdout"]["usd"].get("active_ann_pct", -1e9) >= \
            result["base"]["holdout"]["usd"].get("active_ann_pct", 1e9)
        entry["verdict"] = verdict(entry["discovery"]["diff"], entry["holdout"]["diff"], usd_ok) \
            if name == "H-LW" else "EXPLORATORY"
        result["tests"][name] = entry

    out = ROOT / "data" / "reports" / f"research_learned_weights_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    print(f"Aylar {result['first_month']} .. {result['last_month']}")
    print("Tum orneklem ortalama IC:", result["full_sample_mean_ic"])
    print("Agirlik araligi:", result["weight_range"])
    for w in periods:
        b = result["base"][w]["tl"]
        print(f"value_sn {w:9s}: {b['active_ann_pct']}%/yil t={b['t']} ay={b['months']}")
    print("\nTest  kesif D %/yil (t)   holdout D %/yil (t)   holdout aktif TL / USD   devir%   sonuc")
    for name, e in result["tests"].items():
        d, o = e["discovery"]["diff"], e["holdout"]["diff"]
        print(f"{name:5s} {d['diff_ann_pct']:7.2f} ({d['t']:5.2f})   {o['diff_ann_pct']:7.2f} ({o['t']:5.2f})   "
              f"{e['holdout']['tl']['active_ann_pct']:6.2f} / {e['holdout']['usd']['active_ann_pct']:6.2f}   "
              f"{e['holdout']['tl']['turnover_pct']:5.1f}   {e['verdict']}")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
