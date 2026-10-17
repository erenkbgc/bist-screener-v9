#!/usr/bin/env python3
"""value_sn kac oranla calisiyor (tani, hipotez testi DEGIL).

value_sn = sektor-notr ortalama z(E/P, B/M, S/P, EBIT/EV); eksik oran ortalamaya
girmez. Bu script secilen ust %20'nin skorunun kac orana dayandigini gosterir:

1. Gecerli oran sayisi dagilimi: evren vs secilen hisseler (kesif / holdout).
2. Oran bazinda eksiklik: evren vs secilen; yillara gore secilenlerde.
3. Sektor notrlestirme: secilenlerin kaci kucuk sektorde (< 5 hisse, ay ortalamasina gore).
4. Bir oran cikarilinca: ust %20'nin ne kadari ayni kalir, siralama korelasyonu,
   portfoy getirisi (bilgi; secim yapilmaz).
5. Oran sayisina gore secilen hisselerin aktif getirisi (bilgi).
6. Canli: son dengelemede tutulan hisselerin valid_metric_count / metrics_used.

Hicbir sonuc canli kurali degistirmez; minimum oran sarti gibi bir kural ancak
yeni on-kayitla test edilir. Panel ve secim research_survivorship.py ile ayni
(prepare, alt %30 likidite kesimi, add_composites).

    python scripts/diagnose_ratio_coverage.py
"""
from __future__ import annotations

import json
import sqlite3
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
from backtest_factor_model import VALUE  # noqa: E402
from research_survivorship import BASELINES, RESEARCH, SPLIT, prepared  # noqa: E402

DB = ROOT / "data" / "bist_history.db"
WINDOWS = {"discovery": lambda d: d < SPLIT, "holdout": lambda d: d >= SPLIT}


def mark_picks(df: pd.DataFrame, col: str = "value_sn_z") -> pd.Series:
    """ltr.portfolio ile ayni secim: fwd_ret_1m'li >= 30 hisseli aylarda col'a gore ust %20."""
    pick = pd.Series(False, index=df.index)
    for _, g in df.groupby("date"):
        g = g[g["fwd_ret_1m"].notna()]
        if len(g) < 30:
            continue
        elig = g[g[col].notna()]
        if len(elig) < 5:
            continue
        pick.loc[elig.nlargest(max(1, int(round(len(elig) * 0.2))), col).index] = True
    return pick


def shares(s: pd.Series) -> dict:
    return {str(k): round(100 * float(v), 1) for k, v in s.value_counts(normalize=True).sort_index().items()}


def coverage(df: pd.DataFrame, pick: pd.Series) -> dict:
    uni = df[df["value_sn_z"].notna() & df["fwd_ret_1m"].notna()]
    sel = df[pick]
    return {
        "universe_rows": len(uni), "pick_rows": len(sel),
        "n_valid_universe_pct": shares(uni["n_valid"]), "n_valid_picks_pct": shares(sel["n_valid"]),
        "missing_universe_pct": {r: round(100 * float(uni[r].isna().mean()), 1) for r in VALUE},
        "missing_picks_pct": {r: round(100 * float(sel[r].isna().mean()), 1) for r in VALUE},
        "picks_small_sector_pct": round(100 * float(sel["small_sector"].mean()), 1),
        "universe_small_sector_pct": round(100 * float(uni["small_sector"].mean()), 1),
    }


def by_year(df: pd.DataFrame, pick: pd.Series) -> dict:
    sel = df[pick]
    out = {}
    for y, g in sel.groupby(sel["date"].dt.year):
        out[int(y)] = {"picks": len(g), "mean_n_valid": round(float(g["n_valid"].mean()), 2),
                       "all_four_pct": round(100 * float((g["n_valid"] == 4).mean()), 1),
                       **{f"{r}_missing_pct": round(100 * float(g[r].isna().mean()), 1) for r in VALUE}}
    return out


def leave_one_out(df: pd.DataFrame, base_pick: pd.Series) -> dict:
    out = {}
    for r in VALUE:
        rest = [f + "_z" for f in VALUE if f != r]
        d = df.assign(value_z=df[rest].mean(axis=1))
        col = f"value_sn_wo_{r}_z"
        d[col] = fb.sector_neutralize(d, "value_z")
        p = mark_picks(d, col)
        kept, rho = [], []
        for _, g in d.groupby("date"):
            b, n = base_pick.loc[g.index], p.loc[g.index]
            if b.any():
                kept.append(float((b & n).sum() / b.sum()))
            both = g[["value_sn_z", col]].dropna()
            if len(both) >= 30:
                rho.append(both["value_sn_z"].rank().corr(both[col].rank()))
        res = {"picks_kept_pct": round(100 * float(np.mean(kept)), 1),
               "rank_corr": round(float(np.mean(rho)), 3)}
        for w, f in WINDOWS.items():
            m = f(d["date"])
            res[w] = ltr.summarize(ltr.portfolio(d[m], col))
        out[f"without_{r}"] = res
    out["all_four"] = {w: ltr.summarize(ltr.portfolio(df[f(df["date"])], "value_sn_z")) for w, f in WINDOWS.items()}
    return out


def active_by_n_valid(df: pd.DataFrame, pick: pd.Series) -> dict:
    """Secilen hisselerde oran sayisina gore aylik ortalama aktif getiri (brut, evren ortalamasina gore)."""
    d = df[df["fwd_ret_1m"].notna()].copy()
    d["active"] = d["fwd_ret_1m"] - d.groupby("date")["fwd_ret_1m"].transform("mean")
    sel = d[pick.loc[d.index]]
    out = {}
    for w, f in WINDOWS.items():
        s = sel[f(sel["date"])]
        out[w] = {}
        for k, g in s.groupby("n_valid"):
            monthly = g.groupby("date")["active"].mean()
            m, t, n = fb.newey_west_t(monthly, 6)
            out[w][str(int(k))] = {"picks": len(g), "months": n,
                                   "active_ann_pct": round(1200 * m, 2) if n >= 3 else None,
                                   "t": round(t, 2) if n >= 3 else None}
    return out


def live_snapshot() -> dict:
    """Son dengelemenin tutulan hisseleri, valid_metric_count'un yazildigi en son kosuda
    (kolon 2026-10-14'ten beri dolu). Evren: value_sn oranlariyla skorlanan uzun vade adaylari."""
    if not DB.exists():
        return {}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        reb = con.execute("SELECT MAX(rebalance_date) FROM rotation_holdings").fetchone()[0]
        day = con.execute("SELECT MAX(as_of_date) FROM scores WHERE valid_metric_count IS NOT NULL").fetchone()[0]
        if reb is None or day is None:
            return {}
        held = {r[0] for r in con.execute("SELECT ticker FROM rotation_holdings WHERE rebalance_date=?", (reb,))}
        rows = pd.read_sql_query(
            "SELECT ticker, valid_metric_count, metrics_used FROM scores "
            "WHERE as_of_date=? AND bucket='long_term' AND valuation_z IS NOT NULL", con, params=(day,))
    finally:
        con.close()
    rows["used"] = rows["metrics_used"].fillna("").map(lambda u: [m for m in u.split(",") if m])
    rows = rows[rows["used"].map(lambda u: set(u) <= set(VALUE))]  # banka/sigorta profilleri haric
    sel = rows[rows["ticker"].isin(held)]
    return {"rebalance_date": reb, "scores_date": day, "holdings": len(held), "holdings_with_scores": len(sel),
            "n_valid_holdings_pct": shares(sel["valid_metric_count"]),
            "n_valid_value_sn_universe_pct": shares(rows["valid_metric_count"]),
            "missing_holdings_pct": {r: round(100 * float((~sel["used"].map(lambda u, r=r: r in u)).mean()), 1)
                                     for r in VALUE} if len(sel) else {},
            "missing_universe_pct": {r: round(100 * float((~rows["used"].map(lambda u, r=r: r in u)).mean()), 1)
                                     for r in VALUE} if len(rows) else {},
            "holdings_below_four": sorted(sel.loc[sel["valid_metric_count"] < 4, "ticker"].tolist())}


def main() -> None:
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    result = {"as_of": date.today().isoformat(), "primary": "kapdates", "panels": {}}
    for variant, (fname, _) in BASELINES.items():
        df = prepared(pd.read_parquet(RESEARCH / fname), market_m)
        df["n_valid"] = df[VALUE].notna().sum(axis=1)
        n_sector = df[df["value_z"].notna()].groupby(["date", "sector"])["ticker"].transform("count")
        df["small_sector"] = n_sector.reindex(df.index).fillna(0) < 5
        pick = mark_picks(df)
        res = {"coverage": {w: coverage(df[f(df["date"])], pick[f(df["date"])]) for w, f in WINDOWS.items()},
               "picks_by_year": by_year(df, pick),
               "leave_one_out": leave_one_out(df, pick),
               "active_by_n_valid": active_by_n_valid(df, pick)}
        result["panels"][variant] = res
        print(f"\n== {variant} ({fname})")
        for w, c in res["coverage"].items():
            print(f"{w}: oran sayisi evren {c['n_valid_universe_pct']} | secilen {c['n_valid_picks_pct']}")
            print(f"   eksik % evren {c['missing_universe_pct']} | secilen {c['missing_picks_pct']}"
                  f" | kucuk sektor % secilen {c['picks_small_sector_pct']} evren {c['universe_small_sector_pct']}")
        for k, v in res["leave_one_out"].items():
            extra = f"kalan %{v['picks_kept_pct']} rho {v['rank_corr']} " if "picks_kept_pct" in v else ""
            print(f"{k:12s} {extra}kesif {v['discovery'].get('active_ann_pct')} ({v['discovery'].get('t')})"
                  f" holdout {v['holdout'].get('active_ann_pct')} ({v['holdout'].get('t')})")
        print(f"oran sayisina gore secilen aktif: {json.dumps(res['active_by_n_valid'])}")
    result["live"] = live_snapshot()
    print(f"\nCanli: {json.dumps(result['live'], ensure_ascii=False)}")
    out = ROOT / "data" / "reports" / f"diagnose_ratio_coverage_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
