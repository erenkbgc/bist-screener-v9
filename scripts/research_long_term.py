#!/usr/bin/env python3
"""Faz 2 on-kayitli uzun vade testleri (docs/research/long_term_preregistration.md).

    python scripts/build_fx_panel.py        # once (fx.parquet)
    python scripts/research_long_term.py

Taban B: value_sn ust dilimi. Her hipotez B'yi dislama veya bilesimle degistirir.
Birincil metrik: aylik D = aktif(B') - aktif(B), NW t (6 gecikme).
Gecme kurali on-kayitta; burada yalnizca uygulanir.
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
from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from diagnose_crashed_picks import drawdown_from_peak, month_end  # noqa: E402
from survivorship_sensitivity import breakeven  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
HLZ_T = 3.0
HOLDOUT_T = 2.0
CONFIRMATORY = ["H1a", "H1b", "H2a", "H2b", "H3a", "H3b", "H4a", "H4b", "H5"]
EXPLORATORY = ["H8"]
TWO_SIDED = {"H2a"}


def extended_quarterly() -> pd.DataFrame:
    cache = RESEARCH / "quarterly_ext.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    longs = []
    for f in sorted((RESEARCH / "raw").glob("*.pkl")):
        raw = pickle.loads(f.read_bytes())
        longs.append(pit_panel.statements_long(f.stem, raw.get("bs"), raw.get("inc")))
    q = pit_panel.quarterly_table(pd.concat([x for x in longs if not x.empty], ignore_index=True))
    q.to_parquet(cache, index=False)
    return q


def load() -> pd.DataFrame:
    raw = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    raw["date"] = month_end(raw["date"])
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    raw = pit_panel.add_usd_returns(raw, market_m)
    mcap_total = raw.groupby("date")["mcap"].sum()
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))

    prices = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    prices["date"] = month_end(prices["date"])
    monthly = ltr.monthly_exret(prices, market_m).merge(drawdown_from_peak(prices), on=["date", "ticker"], how="left")
    stmt = ltr.statement_features(extended_quarterly())
    df = ltr.add_signals(df, stmt, monthly, mcap_total)
    df["xs_6m"] = df["fwd_ret_6m_xs"]
    return df


def period(df: pd.DataFrame, which: str) -> pd.Series:
    return df["date"] < SPLIT if which == "discovery" else df["date"] >= SPLIT


def verdict(h: str, disc: dict, hold: dict, usd_ok: bool) -> str:
    sign_ok = disc.get("t", 0) > 0 or (h in TWO_SIDED and disc.get("t", 0) != 0)
    rule1 = abs(disc.get("t", 0)) > HLZ_T and sign_ok
    rule2 = np.sign(hold.get("t", 0)) == np.sign(disc.get("t", 0)) and abs(hold.get("t", 0)) > HOLDOUT_T
    if rule1 and rule2 and usd_ok:
        return "PASS"
    if disc.get("diff_ann_pct", 0) > 0 and hold.get("diff_ann_pct", 0) > 0 \
            and disc.get("t", 0) > 2 and hold.get("t", 0) > 2:
        return "SUPPORTED_NOT_CONFIRMED"
    return "FAIL"


def main() -> None:
    df = load()
    fl = ltr.flags(df)
    df["h4a"] = ltr.composite(df, "gpa_z")
    df["h5"] = ltr.composite(df, "sue_z")
    variants = {h: ("value_sn_z", fl[h]) for h in fl}
    variants["H4a"] = ("h4a", None)
    variants["H5"] = ("h5", None)

    coverage = {
        "chs_pct": round(100 * float(df["chs"].notna().mean()), 1),
        "altman_pct": round(100 * float(df["altman_em"].notna().mean()), 1),
        "f7_pct": round(100 * float(df["f7"].notna().mean()), 1),
        "dd5y_pct": round(100 * float(df["dd_5y_pct"].notna().mean()), 1),
        "hi52_pct": round(100 * float(df["hi52"].notna().mean()), 1),
        "flag_share_pct": {h: round(100 * float(f.fillna(False).mean()), 1) for h, f in fl.items()},
    }

    result = {"as_of": date.today().isoformat(), "split": str(SPLIT.date()),
              "data_start": str(df["date"].min().date()), "data_end": str(df["date"].max().date()),
              "coverage": coverage, "base": {}, "hypotheses": {}}
    base_p = {w: ltr.portfolio(df[period(df, w)], "value_sn_z") for w in ("discovery", "holdout")}
    for w, p in base_p.items():
        result["base"][w] = {"tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}

    for h in CONFIRMATORY + EXPLORATORY:
        col, excl = variants[h]
        entry = {}
        for w in ("discovery", "holdout"):
            m = period(df, w)
            sub = df[m]
            p = ltr.portfolio(sub, col, excl.loc[sub.index] if excl is not None else None)
            entry[w] = {
                "diff": ltr.diff_stats(base_p[w], p),
                "diff_usd": ltr.diff_stats(base_p[w], p, "active_fwd_ret_1m_usd"),
                "tl": ltr.summarize(p),
                "usd": ltr.summarize(p, "active_fwd_ret_1m_usd"),
            }
            if w == "holdout":
                q = p.rename(columns={"top_fwd_ret_1m": "top", "uni_fwd_ret_1m": "universe"})
                entry["survivorship_breakeven_R-100_k3"] = breakeven(q, 3.0, -1.0)
        usd_ok = entry["holdout"]["usd"].get("active_ann_pct", -1e9) >= result["base"]["holdout"]["usd"].get("active_ann_pct", 1e9)
        entry["verdict"] = verdict(h, entry["discovery"]["diff"], entry["holdout"]["diff"], usd_ok) \
            if h in CONFIRMATORY else "EXPLORATORY"
        result["hypotheses"][h] = entry

    out = ROOT / "data" / "reports" / f"research_long_term_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    print(f"Panel {result['data_start']} .. {result['data_end']}; kapsam {coverage}")
    for w in ("discovery", "holdout"):
        b = result["base"][w]
        print(f"B {w:9s}: TL {b['tl']['active_ann_pct']}%/yil t={b['tl']['t']} | USD {b['usd']['active_ann_pct']}% "
              f"| tuzak %{b['tl']['trap_rate_pct']} | ad {b['tl']['avg_names']}")
    print("\nHip   kesif D %/yil (t)   holdout D %/yil (t)   holdout aktif TL / USD   tuzak%   sonuc")
    for h, e in result["hypotheses"].items():
        d, o = e["discovery"]["diff"], e["holdout"]["diff"]
        print(f"{h:5s} {d['diff_ann_pct']:7.2f} ({d['t']:5.2f})   {o['diff_ann_pct']:7.2f} ({o['t']:5.2f})   "
              f"{e['holdout']['tl']['active_ann_pct']:6.2f} / {e['holdout']['usd']['active_ann_pct']:6.2f}   "
              f"{e['holdout']['tl']['trap_rate_pct']:5.1f}   {e['verdict']}")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
