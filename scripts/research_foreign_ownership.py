#!/usr/bin/env python3
"""On-kayitli yabanci payi testi (docs/research/foreign_ownership_preregistration.md).

    python scripts/fetch_foreign_ownership.py     # once (foreign_monthly.parquet)
    python scripts/research_foreign_ownership.py

F1: dfor3 ust %20 vs evren. F2: 0.5 value_sn_z + 0.5 dfor3_z vs value_sn.
F3 (kesifsel): yabanci payi seviyesi ust %20. Gecme kurali on-kayitta.
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

from core import factor_backtest as fb  # noqa: E402
from core import long_term_research as ltr  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_long_term import RESEARCH, SPLIT, load  # noqa: E402

HLZ_T, HOLDOUT_T = 3.0, 2.0


def pass_standalone(disc: dict, hold: dict, hold_usd: dict) -> str:
    if disc.get("active_ann_pct", 0) > 0 and disc.get("t", 0) > HLZ_T \
            and hold.get("active_ann_pct", 0) > 0 and hold.get("t", 0) > HOLDOUT_T \
            and hold_usd.get("active_ann_pct", 0) > 0:
        return "PASS"
    if disc.get("active_ann_pct", 0) > 0 and hold.get("active_ann_pct", 0) > 0 \
            and disc.get("t", 0) > 2 and hold.get("t", 0) > 2:
        return "SUPPORTED_NOT_CONFIRMED"
    return "FAIL"


def pass_vs_base(disc: dict, hold: dict, usd_ok: bool) -> str:
    if disc.get("diff_ann_pct", 0) > 0 and disc.get("t", 0) > HLZ_T \
            and hold.get("diff_ann_pct", 0) > 0 and hold.get("t", 0) > HOLDOUT_T and usd_ok:
        return "PASS"
    if disc.get("diff_ann_pct", 0) > 0 and hold.get("diff_ann_pct", 0) > 0 \
            and disc.get("t", 0) > 2 and hold.get("t", 0) > 2:
        return "SUPPORTED_NOT_CONFIRMED"
    return "FAIL"


def main() -> None:
    df = load()
    sig = ltr.foreign_signals(pd.read_parquet(RESEARCH / "foreign_monthly.parquet"))
    df = df.merge(sig, on=["date", "ticker"], how="left")
    df["dfor3_z"] = df.groupby("date")["dfor3"].transform(fb.winsorize_z)
    df["for_lvl_z"] = df.groupby("date")["for_lvl"].transform(fb.winsorize_z)
    df["f2"] = ltr.composite(df, "dfor3_z")

    prices = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    prices["date"] = month_end(prices["date"])
    prices = prices.sort_values(["ticker", "date"])
    prices["ret3"] = prices.groupby("ticker")["adj"].pct_change(3)
    df = df.merge(prices[["date", "ticker", "ret3"]], on=["date", "ticker"], how="left")

    first = df.loc[df["dfor3"].notna(), "date"].min()
    df = df[df["date"] >= first]
    periods = {"discovery": df["date"] < SPLIT, "holdout": df["date"] >= SPLIT}

    ic = fb.rank_ic(df, "dfor3_z", "fwd_ret_1m")
    result = {
        "as_of": date.today().isoformat(), "first_month": str(first.date()),
        "last_month": str(df["date"].max().date()),
        "coverage_dfor3_pct": round(100 * float(df["dfor3"].notna().mean()), 1),
        "rank_ic": {w: dict(zip(("mean", "t", "n"), fb.newey_west_t(ic[(ic.index < SPLIT) if w == "discovery"
                                                                       else (ic.index >= SPLIT)], 6)))
                    for w in periods},
        "corr_dfor3_mom_12_1": round(float(df[["dfor3", "mom_12_1"]].corr(method="spearman").iloc[0, 1]), 3),
        "corr_dfor3_ret3": round(float(df[["dfor3", "ret3"]].corr(method="spearman").iloc[0, 1]), 3),
        "base": {}, "tests": {},
    }

    base = {w: ltr.portfolio(df[m], "value_sn_z") for w, m in periods.items()}
    for w, p in base.items():
        result["base"][w] = {"tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}

    for name, col in (("F1", "dfor3_z"), ("F3", "for_lvl_z")):
        e = {}
        for w, m in periods.items():
            p = ltr.portfolio(df[m], col)
            e[w] = {"tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}
        e["verdict"] = pass_standalone(e["discovery"]["tl"], e["holdout"]["tl"], e["holdout"]["usd"]) \
            if name == "F1" else "EXPLORATORY"
        result["tests"][name] = e

    e = {}
    for w, m in periods.items():
        p = ltr.portfolio(df[m], "f2")
        e[w] = {"diff": ltr.diff_stats(base[w], p), "diff_usd": ltr.diff_stats(base[w], p, "active_fwd_ret_1m_usd"),
                "tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}
    usd_ok = e["holdout"]["usd"].get("active_ann_pct", -1e9) >= result["base"]["holdout"]["usd"].get("active_ann_pct", 1e9)
    e["verdict"] = pass_vs_base(e["discovery"]["diff"], e["holdout"]["diff"], usd_ok)
    result["tests"]["F2"] = e

    out = ROOT / "data" / "reports" / f"research_foreign_ownership_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    print(f"Aylar {result['first_month']} .. {result['last_month']}; dfor3 kapsama %{result['coverage_dfor3_pct']}")
    print("rank IC (ort, t, n):", {w: tuple(round(x, 3) for x in v.values()) for w, v in result["rank_ic"].items()})
    print("Spearman dfor3 ~ mom_12_1:", result["corr_dfor3_mom_12_1"], "| ~ ret3:", result["corr_dfor3_ret3"])
    for w in periods:
        b = result["base"][w]["tl"]
        print(f"value_sn {w:9s}: {b['active_ann_pct']}%/yil t={b['t']} ay={b['months']}")
    for name in ("F1", "F3"):
        t = result["tests"][name]
        print(f"{name}: kesif {t['discovery']['tl']['active_ann_pct']}% (t {t['discovery']['tl']['t']}) | "
              f"holdout {t['holdout']['tl']['active_ann_pct']}% (t {t['holdout']['tl']['t']}) | "
              f"holdout USD {t['holdout']['usd']['active_ann_pct']}% | {t['verdict']}")
    t = result["tests"]["F2"]
    print(f"F2: kesif D {t['discovery']['diff']['diff_ann_pct']}% (t {t['discovery']['diff']['t']}) | "
          f"holdout D {t['holdout']['diff']['diff_ann_pct']}% (t {t['holdout']['diff']['t']}) | {t['verdict']}")
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
