#!/usr/bin/env python3
"""Kisa vadeli borc karsilama filtresi (docs/research/st_debt_coverage_preregistration.md).

cov = (nakit + kisa vadeli finansal yatirimlar) / kisa vadeli finansal borc.
D1: ayin evreninde (kisa vadeli borcu olanlar) en dusuk %10 cov dislanir; kalanlar
icinde value_sn_z ust %20. H1a ile ayni portfoy, fark istatistigi ve karar kurali.

    python scripts/research_st_debt_coverage.py
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import long_term_research as ltr  # noqa: E402
from core import pit_panel  # noqa: E402
from research_long_term import RESEARCH, load, period, verdict  # noqa: E402

FLAG_PCT = 0.10
NEW_ITEMS = {"st_fin_debt": ("Finansal Borçlar",), "st_fin_inv": ("Finansal Yatırımlar",)}


def short_term_items() -> pd.DataFrame:
    """(ticker, period, st_fin_debt, st_fin_inv): ilk eslesen satir = kisa vade."""
    rows = []
    for f in sorted((RESEARCH / "raw").glob("*.pkl")):
        bs = pickle.loads(f.read_bytes()).get("bs")
        if bs is None or bs.empty:
            continue
        cols = {k: s for k, labels in NEW_ITEMS.items()
                if (s := pit_panel._pick(bs, labels, sum_dupes=False)) is not None}
        if cols:
            rows.append(pd.DataFrame(cols).rename_axis("period").reset_index().assign(ticker=f.stem))
    out = pd.concat(rows, ignore_index=True)
    out["period"] = out["period"].astype(str)
    return out


def coverage(df: pd.DataFrame) -> pd.DataFrame:
    q = pd.read_parquet(RESEARCH / "quarterly.parquet")[["ticker", "period", "cash"]]
    q["period"] = q["period"].astype(str)
    q = q.merge(short_term_items(), on=["ticker", "period"], how="left")
    d = df.merge(q.rename(columns={"period": "stmt_period"}), on=["ticker", "stmt_period"],
                 how="left", validate="many_to_one")
    assert len(d) == len(df)
    d.index = df.index
    has_debt = d["st_fin_debt"] > 0
    d["cov"] = ((d["cash"] + d["st_fin_inv"].fillna(0.0)) / d["st_fin_debt"]).where(has_debt & d["cash"].notna())
    return d


def flag_d1(d: pd.DataFrame) -> pd.Series:
    """True = disla. Kisa vadeli borcu olmayan veya verisi eksik hisse dislanmaz."""
    cut = d.groupby("date")["cov"].transform(lambda s: s.quantile(FLAG_PCT))
    return (d["cov"] < cut).fillna(False)


def main() -> None:
    d = coverage(load())
    flag = flag_d1(d)

    base_p, alt_p, entry = {}, {}, {}
    for w in ("discovery", "holdout"):
        sub = d[period(d, w)]
        base_p[w] = ltr.portfolio(sub, "value_sn_z")
        alt_p[w] = ltr.portfolio(sub, "value_sn_z", flag.loc[sub.index])
        entry[w] = {
            "diff": ltr.diff_stats(base_p[w], alt_p[w]),
            "diff_usd": ltr.diff_stats(base_p[w], alt_p[w], "active_fwd_ret_1m_usd"),
            "base_tl": ltr.summarize(base_p[w]),
            "base_usd": ltr.summarize(base_p[w], "active_fwd_ret_1m_usd"),
            "tl": ltr.summarize(alt_p[w]),
            "usd": ltr.summarize(alt_p[w], "active_fwd_ret_1m_usd"),
        }
    usd_ok = entry["holdout"]["usd"].get("active_ann_pct", -1e9) >= entry["holdout"]["base_usd"].get("active_ann_pct", 1e9)
    v = verdict("D1", entry["discovery"]["diff"], entry["holdout"]["diff"], usd_ok)

    # Tanimlayici: bayrak paylari ve log(cov) rank IC'si
    top_flagged = []
    for dt, g in d[d["fwd_ret_1m"].notna() & d["value_sn_z"].notna()].groupby("date"):
        top = g.nlargest(max(1, int(round(len(g) * 0.2))), "value_sn_z")
        top_flagged.append(float(flag.loc[top.index].mean()))
    d["log_cov"] = np.log(d["cov"].where(d["cov"] > 0))
    ic = fb.rank_ic(d, "log_cov", "fwd_ret_1m")
    ic_stats = {}
    for w, m in (("discovery", ic.index < pd.Timestamp("2021-01-01")), ("holdout", ic.index >= pd.Timestamp("2021-01-01"))):
        mean, t, n = fb.newey_west_t(ic[m], 6)
        ic_stats[w] = {"mean_ic": round(float(mean), 4), "t": round(float(t), 2), "months": int(n)}

    result = {
        "as_of": date.today().isoformat(),
        "data": [str(d["date"].min().date()), str(d["date"].max().date())],
        "descriptive": {
            "rows": len(d),
            "with_st_debt_pct": round(100 * float((d["st_fin_debt"] > 0).mean()), 1),
            "cov_known_pct": round(100 * float(d["cov"].notna().mean()), 1),
            "cov_below_1_pct_of_known": round(100 * float((d["cov"] < 1).sum() / d["cov"].notna().sum()), 1),
            "flagged_pct": round(100 * float(flag.mean()), 1),
            "base_top20_flagged_pct": round(100 * float(np.mean(top_flagged)), 1),
            "log_cov_rank_ic": ic_stats,
        },
        "D1": entry,
        "usd_ok": bool(usd_ok),
        "verdict_D1": v,
    }
    out = ROOT / "data" / "reports" / f"research_st_debt_coverage_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
