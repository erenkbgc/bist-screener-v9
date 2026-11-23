#!/usr/bin/env python3
"""Aylik faktor panellerini duzeltilmis pay sayisi kuraliyla yeniden kurar.

docs/research/share_count_fix.md: pit_panel.shares_at artik bir bedelli/bedelsiz
islemin bilancodaki odenmis sermayeye yansiyip yansimadigina bakiyor (tescil
gecikmesi ve erken tescil). Yalnizca piyasa degeri ve ondan turetilen kolonlar
degisir; ceyreklik tablolar (quarterly*.parquet) ayni kalir. Ag erisimi yok.

Eski dosyalar data/research/pre_share_fix/ altina bir kez yedeklenir.

    python scripts/rebuild_panels_share_fix.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import pit_panel  # noqa: E402
from sensitivity_survivorship_net_debt import rebuild_baseline  # noqa: E402

RESEARCH = ROOT / "data" / "research"
BACKUP = RESEARCH / "pre_share_fix"
FILES = {"lag75": "factors_monthly.parquet", "kapdates": "factors_monthly_kapdates.parquet"}
UNCHANGED = ["bm", "ep", "sp", "ey", "gpa", "roe", "sue", "fwd_ret_1m", "fwd_ret_6m", "tlvol60"]


def diff(old: pd.DataFrame, new: pd.DataFrame) -> dict:
    k = ["date", "ticker"]
    m = old.assign(date=pd.to_datetime(old["date"])).merge(
        new.assign(date=pd.to_datetime(new["date"])), on=k, how="outer", suffixes=("_o", "_n"), indicator=True)
    both = m[m["_merge"] == "both"]
    lr = np.log(both["mcap_n"] / both["mcap_o"]).abs()
    out = {"rows_old": len(old), "rows_new": len(new), "rows_only_one_side": int((m["_merge"] != "both").sum()),
           "mcap_changed_rows": int((lr > 1e-9).sum()), "mcap_changed_tickers": int(both.loc[lr > 1e-9, "ticker"].nunique()),
           "mcap_off_gt_1_5x_rows": int((lr > np.log(1.5)).sum())}
    # Getiriler pay sayisina bagli degil: degismemeli.
    for c in ("fwd_ret_1m", "fwd_ret_6m", "tlvol60", "gpa", "sue"):
        a, b = both[f"{c}_o"], both[f"{c}_n"]
        out[f"{c}_changed"] = int((((a - b).abs() > 1e-9 * b.abs().clip(lower=1)) | (a.isna() != b.isna())).sum())
    return out


def main() -> None:
    sectors = {r["ticker"]: r["sektor"] for r in
               json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))}
    cpi = pit_panel.cpi_index(pd.read_parquet(RESEARCH / "macro_monthly.parquet")["cpi_mom"])
    rb = rebuild_baseline(sectors, cpi=cpi)
    report = {v: diff(pd.read_parquet(RESEARCH / f), rb[v]) for v, f in FILES.items()}
    print(json.dumps(report, indent=1))
    bad = {v: r for v, r in report.items()
           if r["rows_only_one_side"] or any(r[f"{c}_changed"] for c in ("fwd_ret_1m", "fwd_ret_6m", "tlvol60", "gpa", "sue"))}
    if bad:
        raise SystemExit(f"Pay sayisindan bagimsiz kolonlar degisti, dosya yazilmadi: {bad}")
    BACKUP.mkdir(exist_ok=True)
    for f in FILES.values():
        if not (BACKUP / f).exists():
            shutil.copy2(RESEARCH / f, BACKUP / f)
    for v, f in FILES.items():
        rb[v].to_parquet(RESEARCH / f, index=False)
    (RESEARCH / "PANEL_DEFINITION.txt").write_text(
        "C1 (ias29_constant_unit_ttm_preregistration.md) + pay sayisi duzeltmesi (share_count_fix.md); "
        "C0 yedegi: c0/, duzeltme oncesi: pre_share_fix/\n")
    print("Panel dosyalari yazildi; yedek:", BACKUP)


if __name__ == "__main__":
    main()
