#!/usr/bin/env python3
"""TMS 29 (enflasyon muhasebesi) rejiminde value_sn (docs/research/ias29_regime_preregistration.md).

Satir rejimi stmt_period'dan: N <= 2023Q3, T 2023Q4..2024Q3, I >= 2024Q4. Ay rejimi:
evren satirlarinin >= %80'i ayni rejimde; digerleri karisik (disarida).
Pencereler: NOM (2021+ N aylari), ADJ (T + I, birincil), I-only, kesif (2013-2020).
Portfoy tum panelde bir kez kurulur (ltr.portfolio), aylar sonra rejime gore secilir.

    python scripts/research_ias29_regime.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import long_term_research as ltr  # noqa: E402
from core import pit_panel  # noqa: E402
from research_survivorship import BASELINES, RESEARCH, SPLIT, prepared  # noqa: E402

MONTH_SHARE = 0.8
RATIOS = ["bm", "ep", "sp", "ey"]


def row_regime(period: str) -> str:
    if period <= "2023Q3":
        return "N"
    return "T" if period <= "2024Q3" else "I"


def month_regimes(df: pd.DataFrame) -> pd.Series:
    share = df.groupby("date")["regime"].value_counts(normalize=True).unstack(fill_value=0.0)
    top = share.idxmax(axis=1)
    return top.where(share.max(axis=1) >= MONTH_SHARE, "mixed")


def nw(series: pd.Series) -> dict:
    m, t, n = fb.newey_west_t(series, 6)
    se = abs(m / t) if t and math.isfinite(t) and t != 0 else float("nan")
    return {"mean": m, "t": t, "n": n, "se": se}


def window_stats(p: pd.DataFrame, ics: dict[str, pd.Series], months: pd.Index) -> dict:
    sub = p[p["date"].isin(months)]
    out = {"months": len(sub), "first": str(months.min().date()) if len(months) else None,
           "last": str(months.max().date()) if len(months) else None,
           "top_quintile": ltr.summarize(sub)}
    for name, ic in ics.items():
        s = nw(ic[ic.index.isin(months)])
        out[f"ic_{name}"] = {"mean": round(s["mean"], 4), "t": round(s["t"], 2), "months": s["n"]}
    return out


def diff(p: pd.DataFrame, a: pd.Index, b: pd.Index) -> dict:
    """ADJ - NOM ust dilim net aktif farki; t = fark / sqrt(se_a^2 + se_b^2), NW se."""
    x = nw(p.loc[p["date"].isin(a), "active_fwd_ret_1m"].dropna())
    y = nw(p.loc[p["date"].isin(b), "active_fwd_ret_1m"].dropna())
    d = x["mean"] - y["mean"]
    return {"diff_ann_pct": round(1200 * d, 2), "t": round(d / math.sqrt(x["se"] ** 2 + y["se"] ** 2), 2)}


def verdict(adj: dict, d: dict) -> str:
    ic = adj["ic_value_sn"]
    if ic["mean"] <= 0 or d["t"] < -2:
        return "REGIME_BREAK"
    if ic["t"] > 2 and adj["top_quintile"].get("active_ann_pct", 0) > 0:
        return "CONSISTENT"
    return "WEAKER_NOT_SIGNIFICANT"


def main() -> None:
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    result = {"as_of": date.today().isoformat(), "primary": "kapdates", "panels": {}}
    for variant, (fname, _) in BASELINES.items():
        df = prepared(pd.read_parquet(RESEARCH / fname), market_m)
        df["regime"] = df["stmt_period"].map(row_regime)
        reg = month_regimes(df)
        p = ltr.portfolio(df, "value_sn_z")
        ics = {"value_sn": fb.rank_ic(df, "value_sn_z", "fwd_ret_1m")}
        ics.update({r: fb.rank_ic(df, f"{r}_z", "fwd_ret_1m") for r in RATIOS})
        months = {
            "discovery": reg.index[(reg.index < SPLIT)],
            "NOM": reg.index[(reg.index >= SPLIT) & (reg == "N")],
            "ADJ": reg.index[reg.isin(["T", "I"])],
            "I_only": reg.index[reg == "I"],
            "T_only": reg.index[reg == "T"],
        }
        res = {"month_regimes": reg.value_counts().to_dict(),
               "mixed_months": [str(d.date()) for d in reg.index[reg == "mixed"]],
               "windows": {w: window_stats(p, ics, m) for w, m in months.items()}}
        res["diff_ADJ_minus_NOM"] = diff(p, months["ADJ"], months["NOM"])
        res["diff_I_minus_NOM"] = diff(p, months["I_only"], months["NOM"])
        res["verdict"] = verdict(res["windows"]["ADJ"], res["diff_ADJ_minus_NOM"])
        result["panels"][variant] = res

        print(f"\n== {variant} ({fname}) | ay rejimleri {res['month_regimes']}")
        for w, s in res["windows"].items():
            tq = s["top_quintile"]
            ic_txt = " ".join(f"{k[3:]} {v['mean']:+.3f} ({v['t']:+.2f})" for k, v in s.items() if k.startswith("ic_"))
            print(f"  {w:9s} {s['first']}..{s['last']} n={s['months']:3d}  aktif {tq.get('active_ann_pct')} "
                  f"(t {tq.get('t')})  IC: {ic_txt}")
        print(f"  ADJ-NOM {res['diff_ADJ_minus_NOM']}  I-NOM {res['diff_I_minus_NOM']}  -> {res['verdict']}")
    result["verdict"] = result["panels"]["kapdates"]["verdict"]
    out = ROOT / "data" / "reports" / f"research_ias29_regime_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"\nKarar (kapdates): {result['verdict']}\nJSON: {out}")


if __name__ == "__main__":
    main()
