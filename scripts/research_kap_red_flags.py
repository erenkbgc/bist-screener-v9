#!/usr/bin/env python3
"""KAP kirmizi bayrak on-kayitli testi (docs/research/kap_red_flags_preregistration.md).

    python scripts/research_kap_red_flags.py

Girdi: data/research/kap_archive.parquet (scripts/build_kap_archive.py) ve
Faz 2 paneli (research_long_term.load). Cikti:
data/reports/research_kap_red_flags_<tarih>.json.
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

from core import long_term_research as ltr  # noqa: E402
from core.kap_red_flags import classify  # noqa: E402
import research_long_term as rlt  # noqa: E402

ARCHIVE = ROOT / "data" / "research" / "kap_archive.parquet"
SEVERE = {"insolvency", "going_concern", "auditor_adverse", "regulatory_sanction", "market_sanction"}
MIN_EVENTS = 60


def red_flags() -> pd.DataFrame:
    k = pd.read_parquet(ARCHIVE, columns=["stock_code", "published_at", "subject", "summary"])
    k["flag"] = [classify(s, m) for s, m in zip(k["subject"], k["summary"])]
    k = k[k["flag"].notna()].copy()
    k["day"] = k["published_at"].dt.normalize()
    return k[["stock_code", "day", "flag"]]


def flagged(df: pd.DataFrame, flags: pd.DataFrame, window_days: int) -> pd.Series:
    """Ay sonu t icin [t - window, t) araliginda bayrak var mi? t gunu dahil degil."""
    days = {t: np.sort(g["day"].values) for t, g in flags.groupby("stock_code")}
    out = np.zeros(len(df), dtype=bool)
    for i, (t, tk) in enumerate(zip(df["date"].values, df["ticker"].values)):
        a = days.get(tk)
        if a is None:
            continue
        lo = np.searchsorted(a, t - np.timedelta64(window_days, "D"), side="left")
        hi = np.searchsorted(a, t, side="left")
        out[i] = hi > lo
    return pd.Series(out, index=df.index)


def in_top_quintile(df: pd.DataFrame) -> pd.Series:
    """B'nin uyeleri (portfolio() ile ayni secim, dislama yok)."""
    mask = pd.Series(False, index=df.index)
    for _, g in df.groupby("date"):
        g = g[g["fwd_ret_1m"].notna() & g["value_sn_z"].notna()]
        if len(g) < 30:
            continue
        mask.loc[g.nlargest(max(1, int(round(len(g) * 0.2))), "value_sn_z").index] = True
    return mask


def spearman_by_month(df: pd.DataFrame, cols: list[str]) -> dict:
    out = {}
    for c in cols:
        rs = []
        for _, g in df.groupby("date"):
            g = g[["value_sn_z", c]].dropna()
            if len(g) >= 30 and g[c].nunique() > 1:
                rs.append(g["value_sn_z"].rank().corr(g[c].astype(float).rank()))
        out[c] = {"mean_rho": round(float(np.mean(rs)), 3), "months": len(rs)} if rs else {"months": 0}
    return out


def main() -> None:
    df = rlt.load()
    flags = red_flags()
    any90 = flagged(df, flags, 90)
    sev90 = flagged(df, flags[flags["flag"].isin(SEVERE)], 90)
    any180 = flagged(df, flags, 180)
    sev180 = flagged(df, flags[flags["flag"].isin(SEVERE)], 180)
    top = in_top_quintile(df)

    result = {"as_of": date.today().isoformat(), "split": str(rlt.SPLIT.date()),
              "data_start": str(df["date"].min().date()), "data_end": str(df["date"].max().date()),
              "events_in_top_quintile": {}, "base": {}, "hypotheses": {}, "sensitivity_180d": {}}
    for w in ("discovery", "holdout"):
        m = rlt.period(df, w) & top
        result["events_in_top_quintile"][w] = {"K1": int(any90[m].sum()), "K2": int(sev90[m].sum()),
                                               "K3": int((any90 & (df["dd_5y_pct"] <= -70))[m].sum())}

    base_p = {w: ltr.portfolio(df[rlt.period(df, w)], "value_sn_z") for w in ("discovery", "holdout")}
    for w, p in base_p.items():
        result["base"][w] = {"tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}

    def run(excl: pd.Series) -> dict:
        entry = {}
        for w in ("discovery", "holdout"):
            sub = df[rlt.period(df, w)]
            p = ltr.portfolio(sub, "value_sn_z", excl.loc[sub.index])
            entry[w] = {"diff": ltr.diff_stats(base_p[w], p),
                        "diff_usd": ltr.diff_stats(base_p[w], p, "active_fwd_ret_1m_usd"),
                        "tl": ltr.summarize(p), "usd": ltr.summarize(p, "active_fwd_ret_1m_usd")}
        return entry

    for h, excl in (("K1", any90), ("K2", sev90)):
        e = run(excl)
        powered = all(result["events_in_top_quintile"][w][h] >= MIN_EVENTS for w in ("discovery", "holdout"))
        usd_ok = e["holdout"]["usd"].get("active_ann_pct", -1e9) >= result["base"]["holdout"]["usd"].get("active_ann_pct", 1e9)
        e["verdict"] = rlt.verdict(h, e["discovery"]["diff"], e["holdout"]["diff"], usd_ok) if powered else "UNDERPOWERED"
        result["hypotheses"][h] = e
    for h, excl in (("K1", any180), ("K2", sev180)):
        e = run(excl)
        result["sensitivity_180d"][h] = {w: e[w]["diff"] for w in ("discovery", "holdout")}

    # K3 (kesifsel): cokmus ust dilim uyelerinde bayrakli - bayraksiz 6 aylik XU100 fazlasi.
    k3 = {}
    for w in ("discovery", "holdout"):
        m = rlt.period(df, w) & top & (df["dd_5y_pct"] <= -70) & df["xs_6m"].notna()
        a, b = df.loc[m & any90, "xs_6m"], df.loc[m & ~any90, "xs_6m"]
        k3[w] = {"flagged_n": int(len(a)), "unflagged_n": int(len(b)),
                 "flagged_mean_pct": round(100 * float(a.mean()), 1) if len(a) else None,
                 "unflagged_mean_pct": round(100 * float(b.mean()), 1) if len(b) else None}
    result["hypotheses"]["K3"] = {"exploratory": k3, "verdict": "EXPLORATORY"}

    d = df.assign(any_flag_90d=any90.astype(float))
    result["descriptive_spearman_value_sn"] = spearman_by_month(d, ["any_flag_90d", "chs", "f7", "dd_5y_pct"])

    out = ROOT / "data" / "reports" / f"research_kap_red_flags_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    print(f"Panel {result['data_start']} .. {result['data_end']}; ust dilimde olay {result['events_in_top_quintile']}")
    for w in ("discovery", "holdout"):
        b = result["base"][w]
        print(f"B {w:9s}: TL {b['tl']['active_ann_pct']}%/yil t={b['tl']['t']} | USD {b['usd']['active_ann_pct']}%")
    print("\nHip  kesif D %/yil (t)   holdout D %/yil (t)   holdout aktif TL / USD   sonuc")
    for h in ("K1", "K2"):
        e = result["hypotheses"][h]
        dd, o = e["discovery"]["diff"], e["holdout"]["diff"]
        print(f"{h:4s} {dd['diff_ann_pct']:7.2f} ({dd['t']:5.2f})   {o['diff_ann_pct']:7.2f} ({o['t']:5.2f})   "
              f"{e['holdout']['tl']['active_ann_pct']:6.2f} / {e['holdout']['usd']['active_ann_pct']:6.2f}   {e['verdict']}")
    print(f"\n180 gun duyarlilik: {result['sensitivity_180d']}")
    print(f"K3 (kesifsel): {k3}")
    print(f"Spearman value_sn: {result['descriptive_spearman_value_sn']}")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
