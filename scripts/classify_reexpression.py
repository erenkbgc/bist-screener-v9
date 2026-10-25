#!/usr/bin/env python3
"""Hangi sirketlerin rakamlari Is Yatirim'de TMS 29 ile yeniden ifade ediliyor?

docs/research/first_published_panel.md: Is Yatirim TMS 29 doneminde bir donemi, onu
onceki-donem kolonunda gosteren en son raporun birimine tasiyor (TUFE orani). TL
raporlayanlarda Q2 gelir tablosu kalemleri ertesi yil Q2 raporu gelince x CPI(P+4)/CPI(P),
yabanci fonksiyonel para birimli sirketlerde x 1. Her sirket icin bir 6 aylik rapor
(2025Q2, yoksa 2024Q2) ilk yayini ile Is Yatirim karsilastirilir.

    python scripts/classify_reexpression.py
Cikti: data/research/reexpression_class.parquet (ticker, period, ratio, factor, cls)
"""
from __future__ import annotations

import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_restatements import kap_text  # noqa: E402
from audit_vendor_vs_kap import vendor  # noqa: E402
from build_first_published import parse, targets  # noqa: E402
from core import pit_panel  # noqa: E402

RESEARCH = ROOT / "data" / "research"
OUT = RESEARCH / "reexpression_class.parquet"
TOL = 0.01
WINDOWS = {"2025Q2": ("2025-07-01", "2025-10-15"), "2024Q2": ("2024-07-01", "2024-10-15")}
ITEMS = (("revenue", "Satış Gelirleri"), ("ni_parent", "Ana Ortaklık Payları"), ("op_profit", "FAALİYET KARI (ZARARI)"))


def classify_one(raw: dict, fp: dict, period: str, factor: float) -> tuple[str, float | None]:
    v_ta, k_ta = vendor(raw, "bs", "TOPLAM VARLIKLAR", period), fp.get("total_assets")
    if not v_ta or not k_ta or v_ta <= 0 or k_ta <= 0:
        return "unknown", None
    scale = 10.0 ** round(math.log10(v_ta / k_ta))
    for item, label in ITEMS:
        v, k = vendor(raw, "inc", label, period), fp.get(item)
        if v and k:
            r = v / (k * scale)
            if abs(r / factor - 1) < TOL:
                return "reexpressed", r
            if abs(r - 1) < TOL:
                return "not_reexpressed", r
            return "unknown", r
    return "unknown", None


def main() -> None:
    cpi = pit_panel.cpi_index(pd.read_parquet(RESEARCH / "macro_monthly.parquet")["cpi_mom"])
    c = lambda p: cpi.get(pit_panel.period_end(p).to_period("M"), np.nan)  # noqa: E731
    t = targets()
    tickers = sorted(t["stock_code"].unique())
    rows = []
    for n, tk in enumerate(tickers, 1):
        raw_path = RESEARCH / "raw" / f"{tk}.pkl"
        if not raw_path.exists():
            continue
        raw = pickle.loads(raw_path.read_bytes())
        res = None
        for period, (lo, hi) in WINDOWS.items():
            d = t[(t["stock_code"] == tk) & (t["published_at"] >= lo) & (t["published_at"] < hi)]
            pages = []
            for idx in d["disclosure_index"]:
                try:
                    p = parse(kap_text(int(idx)))
                except Exception as exc:  # noqa: BLE001
                    print(f"HATA {tk} {idx}: {exc}", flush=True)
                    continue
                if p and p["period"] == period:
                    pages.append(p)
            if not pages:
                continue
            pages.sort(key=lambda p: {True: 0, None: 1, False: 2}[p["consolidated"]])
            nxt = f"{int(period[:4]) + 1}{period[4:]}"
            cls, ratio = classify_one(raw, pages[0], period, c(nxt) / c(period))
            res = {"ticker": tk, "period": period, "ratio": ratio, "factor": c(nxt) / c(period),
                   "cls": cls, "consolidated": pages[0]["consolidated"]}
            if cls != "unknown":
                break
        if res:
            rows.append(res)
        if n % 25 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
            pd.DataFrame(rows).to_parquet(OUT, index=False)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)
    print(df["cls"].value_counts().to_dict(), f"-> {OUT}")


if __name__ == "__main__":
    main()
