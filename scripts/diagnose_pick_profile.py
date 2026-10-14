#!/usr/bin/env python3
"""Tanisal (on-kayitli test DEGIL): value_sn ust %20 ile ayni ayin evreni karsilastirmasi.

Soru: canli kural likiditesi dusuk veya finansal olarak sorunlu hisselerde mi
yogunlasiyor? Panel: research_long_term.load() (finansal disi, likidite alt %30
atilmis). Her ay ust dilim ve evren icin oranlar; aylarin ortalamasi raporlanir.
Her oran yalnizca verisi olan satirlarda hesaplanir ve kapsama (_cov, %) ayrica
raporlanir: eksik veri sorunsuz sayilmaz. Ozkaynak, panelin o ay kullandigi
ceyrekten (ana ortaklik, yoksa toplam) alinir. Canli skoru DEGISTIRMEZ.

    python scripts/diagnose_pick_profile.py
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

from research_long_term import SPLIT, load  # noqa: E402


def rate_and_coverage(series: pd.Series, condition) -> dict:
    """Oran yalnizca verisi olan satirlarda; eksik veri sagliksiz/saglikli sayilmaz."""
    valid = series.notna()
    return {"rate_pct": 100 * float(condition(series[valid]).mean()) if valid.any() else None,
            "coverage_pct": 100 * float(valid.mean())}


def equity_asof(df: pd.DataFrame, q: pd.DataFrame) -> pd.Series:
    """Panelin o ay kullandigi ceyregin ozkaynagi (ana ortaklik, yoksa toplam; pit_panel ile ayni)."""
    qq = q.assign(eq=q["equity_parent"].fillna(q["equity"]),
                  available_at=pd.to_datetime(q["available_at"]).astype("datetime64[ns]"))
    qq = qq[["ticker", "available_at", "eq"]].dropna(subset=["available_at"]).sort_values("available_at")
    left = df[["ticker", "date"]].reset_index()
    left = left.assign(date=pd.to_datetime(left["date"]).astype("datetime64[ns]")).sort_values("date")
    m = pd.merge_asof(left, qq, left_on="date", right_on="available_at", by="ticker", direction="backward")
    return m.set_index("index")["eq"].reindex(df.index)


CHECKS = {
    "net_loss": ("ep", lambda v: v < 0),
    "op_loss": ("ey", lambda v: v < 0),
    "equity_le_0": ("eq", lambda v: v <= 0),
    "altman_em_lt_1.1": ("altman_em", lambda v: v < 1.1),
    "f7_le2": ("f7", lambda v: v <= 2),
    "dd5y_le_-70": ("dd_5y_pct", lambda v: v <= -70),
    "trap_6m_xs_lt_-30": ("xs_6m", lambda v: v < -0.30),
}


def profile(g: pd.DataFrame, chs_cut: float) -> dict:
    out = {"median_tlvol60_mn": g["tlvol60"].median() / 1e6,
           "fwd_6m_xs_mean_pct": 100 * g["xs_6m"].mean()}
    for name, (col, cond) in CHECKS.items():
        rc = rate_and_coverage(g[col], cond)
        out[f"{name}_pct"], out[f"{name}_cov"] = rc["rate_pct"], rc["coverage_pct"]
    rc = rate_and_coverage(g["chs"], lambda v: v >= chs_cut)
    out["chs_worst_decile_pct"], out["chs_worst_decile_cov"] = rc["rate_pct"], rc["coverage_pct"]
    return out


def main() -> None:
    df = load()
    df = df[df["fwd_ret_1m"].notna()].copy()
    df["eq"] = equity_asof(df, pd.read_parquet(ROOT / "data" / "research" / "quarterly.parquet"))
    rows = []
    for dt, g in df.groupby("date"):
        elig = g[g["value_sn_z"].notna()]
        if len(elig) < 30:
            continue
        top = elig.nlargest(max(1, round(0.2 * len(elig))), "value_sn_z")
        chs_cut = g["chs"].quantile(0.9)
        for name, part in (("top20", top), ("universe", g)):
            rows.append({"date": dt, "group": name, **profile(part, chs_cut)})
    p = pd.DataFrame(rows)
    p["period"] = (p["date"] >= SPLIT).map({False: "discovery", True: "holdout"})
    table = p.groupby(["period", "group"]).mean(numeric_only=True).round(2)
    out = ROOT / "data" / "reports" / f"diagnose_pick_profile_{date.today().isoformat()}.json"
    out.write_text(json.dumps({"as_of": date.today().isoformat(), "months": int(p["date"].nunique()),
                               "table": {f"{a}/{b}": r.to_dict() for (a, b), r in table.iterrows()}},
                              indent=2), encoding="utf-8")
    pd.set_option("display.width", 200)
    print(table.T.to_string())
    print(out)


if __name__ == "__main__":
    main()
