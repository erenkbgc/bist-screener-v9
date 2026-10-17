#!/usr/bin/env python3
"""Arastirma paneli dosyalarini C1 (TMS 29 sabit birim TTM) ile yeniden kurar.

ias29_constant_unit_ttm_preregistration.md C1'i benimsedi; canli skor C1 kullaniyor.
Bu script kayitli panel dosyalarini ayni tanima getirir. Ag erisimi yok: ham onbellek
(data/research/raw/*.pkl) ve macro_monthly.parquet (TUFE).

Dosyalar ve anlamlari KORUNUR (build_pit_panel.py'den farkli olarak):
  quarterly.parquet                75/100 gun available_at (KAP tarihi uygulanmamis)
  factors_monthly.parquet          lag75 panel (research_long_term.load, portfoy backtest'i)
  factors_monthly_kapdates.parquet gercek KAP tarihli panel
  quarterly_ext.parquet            tum hisseler (finansallar dahil), tablo ozellikleri
Eski dosyalar data/research/c0/ altina bir kez yedeklenir. TMS 29 oncesi tablolu satirlar
eski dosyalarla birebir ayni degilse hicbir dosya yazilmaz.

    python scripts/rebuild_panels_c1.py
"""
from __future__ import annotations

import json
import pickle
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import pit_panel  # noqa: E402
from sensitivity_survivorship_net_debt import rebuild_baseline  # noqa: E402

RESEARCH = ROOT / "data" / "research"
BACKUP = RESEARCH / "c0"
FILES = {"lag75": "factors_monthly.parquet", "kapdates": "factors_monthly_kapdates.parquet"}
COLS = ["mcap", "tlvol60", "bm", "ep", "sp", "ey", "gpa", "roe", "sue", "fwd_ret_1m", "fwd_ret_6m"]


def pre_ias29_mismatches(old: pd.DataFrame, new: pd.DataFrame) -> dict:
    k = ["date", "ticker"]
    o = old.assign(date=pd.to_datetime(old["date"]))
    n = new.assign(date=pd.to_datetime(new["date"]))
    m = o.merge(n, on=k, how="outer", suffixes=("_o", "_n"), indicator=True)
    pre = m[(m["stmt_period_o"] < pit_panel.IAS29_FIRST_PERIOD) | (m["stmt_period_n"] < pit_panel.IAS29_FIRST_PERIOD)]
    out = {"rows_old": len(o), "rows_new": len(n), "rows_only_one_side": int((m["_merge"] != "both").sum())}
    both = pre[pre["_merge"] == "both"]
    for c in COLS:
        a, b = both[f"{c}_o"], both[f"{c}_n"]
        out[c] = int((((a - b).abs() > 1e-9 * b.abs().clip(lower=1)) | (a.isna() != b.isna())).sum())
    post = m[(m["_merge"] == "both") & (m["stmt_period_n"] >= pit_panel.IAS29_FIRST_PERIOD)]
    out["ias29_rows_ep_changed"] = int(((post["ep_o"] - post["ep_n"]).abs() > 1e-12).sum())
    return out


def main() -> None:
    sectors = {r["ticker"]: r["sektor"] for r in
               json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))}
    cpi = pit_panel.cpi_index(pd.read_parquet(RESEARCH / "macro_monthly.parquet")["cpi_mom"])
    rb = rebuild_baseline(sectors, cpi=cpi)
    longs = [pit_panel.statements_long(f.stem, (r := pickle.loads(f.read_bytes())).get("bs"), r.get("inc"))
             for f in sorted((RESEARCH / "raw").glob("*.pkl"))]
    q_ext = pit_panel.quarterly_table(pd.concat([x for x in longs if not x.empty], ignore_index=True), cpi=cpi)

    report = {v: pre_ias29_mismatches(pd.read_parquet(RESEARCH / f), rb[v]) for v, f in FILES.items()}
    print(json.dumps(report, indent=1))
    bad = {v: r for v, r in report.items() if r["rows_only_one_side"] or any(r[c] for c in COLS)}
    if bad:
        raise SystemExit(f"TMS 29 oncesi satirlar degisti, dosya yazilmadi: {bad}")

    BACKUP.mkdir(exist_ok=True)
    for f in [*FILES.values(), "quarterly.parquet", "quarterly_ext.parquet"]:
        if not (BACKUP / f).exists():
            shutil.copy2(RESEARCH / f, BACKUP / f)
    for v, f in FILES.items():
        rb[v].to_parquet(RESEARCH / f, index=False)
    rb["_q"].to_parquet(RESEARCH / "quarterly.parquet", index=False)
    q_ext.to_parquet(RESEARCH / "quarterly_ext.parquet", index=False)
    (RESEARCH / "PANEL_DEFINITION.txt").write_text("C1 (ias29_constant_unit_ttm_preregistration.md); C0 yedegi: c0/\n")
    print("C1 panel dosyalari yazildi; C0 yedegi:", BACKUP)


if __name__ == "__main__":
    main()
