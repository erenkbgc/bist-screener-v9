#!/usr/bin/env python3
"""Bultendeki "gercekci getiri" referansini uretir: config/realized_returns.json.

    python scripts/realized_return_reference.py

Model hedef fiyati yerine, canli kuralin (value_sn ust %20, aylik) gecmiste
GERCEKLESEN 6 aylik getiri dagilimi gosterilir. Neden: hedef dogrulugu testi
(backtest_target_accuracy) ust dilim icin +25.1% tahmin edilen 6 aylik fazla
getiriye karsi +1.4% gerceklesme buldu; canli "beklenen getiri" ise neredeyse
tamamen CAPM faiz varsayimindan (k_e) geliyordu.

Kaynak: data/research/ paneli (scripts/build_pit_panel.py), ayni portfoy tanimi
(scripts/research_long_term.py). Delist olmus hisselerin fiyati yok; sayilar
survivorship nedeniyle iyimserdir (docs/research/phase1_diagnostics.md).
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

import research_long_term as rlt  # noqa: E402

OUT = ROOT / "config" / "realized_returns.json"


def top_quintile_members(df: pd.DataFrame) -> pd.DataFrame:
    """Her ay value_sn ust %20 (research_long_term.portfolio ile ayni secim)."""
    rows = []
    for _, g in df.groupby("date"):
        g = g[g["fwd_ret_1m"].notna() & g["value_sn_z"].notna()]
        if len(g) < 30:
            continue
        rows.append(g.nlargest(max(1, int(round(len(g) * 0.2))), "value_sn_z"))
    return pd.concat(rows)


def _pct(x: pd.Series) -> dict:
    x = x.dropna() * 100
    return {"median_pct": round(float(x.median()), 1), "p10_pct": round(float(x.quantile(0.1)), 1),
            "p90_pct": round(float(x.quantile(0.9)), 1), "positive_share_pct": round(float((x > 0).mean() * 100), 1),
            "n": int(len(x))}


def summarize(top: pd.DataFrame) -> dict:
    basket = top.groupby("date")["xs_6m"].mean().dropna() * 100
    return {
        "stock_tl_6m": _pct(top["fwd_ret_6m"]),
        "stock_vs_xu100_6m": _pct(top["xs_6m"]),
        "basket_vs_xu100_6m": {
            "mean_pct": round(float(basket.mean()), 1), "median_pct": round(float(basket.median()), 1),
            "p10_pct": round(float(basket.quantile(0.1)), 1), "p90_pct": round(float(basket.quantile(0.9)), 1),
            "positive_share_pct": round(float((basket > 0).mean() * 100), 1), "n_months": int(len(basket)),
        },
    }


def main() -> None:
    df = rlt.load()
    # Yalnizca 6 aylik sonucu gerceklesmis aylar (son 6 ay disarida).
    top = top_quintile_members(df).dropna(subset=["fwd_ret_6m"])
    hold = top[top["date"] >= rlt.SPLIT]
    out = {
        "generated_at": date.today().isoformat(),
        "rule": "value_sn ust %20, aylik",
        "horizon_months": 6,
        "period_start": str(hold["date"].min().date()),
        "period_end": str(hold["date"].max().date()),
        "holdout": summarize(hold),
        "discovery": summarize(top[top["date"] < rlt.SPLIT]),
        "caveat": "Delist olmus hisseler veride yok; sayilar iyimserdir.",
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out["holdout"], ensure_ascii=False))


if __name__ == "__main__":
    main()
