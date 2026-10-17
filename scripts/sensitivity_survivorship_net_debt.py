#!/usr/bin/env python3
"""Survivorship duzeltmesi, guncel net borc kuraliyla (duyarlilik, yeni hipotez degil).

PR #66 (research_survivorship.py) cikmis hisselerde eksik Finansal Borclar / Nakit
kalemini 0 saydi; taban panel dosyalari da net borc duzeltmesinden (PR #60) once
kurulmustu. Canli kural ve guncel core/pit_panel ise eksik kalemde EBIT/EV'yi NaN
birakir. Bu script ayni testi guncel kuralla tekrarlar:

1. Taban panel ham onbellekten (data/research/raw/*.pkl, ag erisimi yok) guncel
   pit_panel koduyla yeniden kurulur: lag75 (75/100 gun) ve kapdates (gercek KAP
   yayin tarihleri). Kayitli dosyalarla fark raporlanir.
2. Cikmis hisse satirlari fill_missing_debt=False ile kurulur.
3. Fiyat, rapor tarihi, likidite kesimi, kompozit, S1..S5 cikis varsayimlari ve
   karar kurali research_survivorship.py ile aynidir (ayni fonksiyonlar).

Yorum kurali (kosudan once yazildi, 2026-10-17):
- On-kayitli sonuc degismez: kapdates SURVIVORSHIP_FRAGILE (PR #66).
- Bu kosu yalnizca o kararin eksik borc varsayimina duyarli olup olmadigini
  gosterir. Karar ayni kalirsa "varsayimdan bagimsiz"; degisirse "varsayima
  duyarli" diye raporlanir. Iki durumda da canli kural degismez; kural degisikligi
  yeni on-kayit ister.

    python scripts/sensitivity_survivorship_net_debt.py
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

from core import pit_panel  # noqa: E402
from research_survivorship import (BASELINES, RESEARCH, delisted_panel, load_kap,  # noqa: E402
                                   print_variant, run_variant)

COMPARE_COLS = ["mcap", "tlvol60", "ep", "bm", "sp", "ey", "fwd_ret_1m"]


def rebuild_baseline(sectors: dict[str, str], cpi: pd.Series | None = None) -> dict[str, pd.DataFrame]:
    """Bugunku panel, ham onbellekten guncel pit_panel koduyla (build_pit_panel ile ayni adimlar)."""
    longs, pxs, evs = [], [], []
    for f in sorted((RESEARCH / "raw").glob("*.pkl")):
        tk = f.stem
        if tk not in sectors or sectors[tk] in pit_panel.FINANCIAL_SECTORS:
            continue
        raw = pickle.loads(f.read_bytes())
        longs.append(pit_panel.statements_long(tk, raw.get("bs"), raw.get("inc")))
        pxs.append(pit_panel.monthly_prices(tk, raw.get("px_raw"), raw.get("px_adj")))
        evs.append(pit_panel.split_events(tk, raw.get("splits")))
    q = pit_panel.quarterly_table(pd.concat([x for x in longs if not x.empty], ignore_index=True), cpi=cpi)
    px = pd.concat([x for x in pxs if not x.empty], ignore_index=True)
    ev = pd.concat([x for x in evs if not x.empty], ignore_index=True)
    dates = pit_panel.kap_report_dates(pd.read_parquet(RESEARCH / "kap_archive.parquet"))
    out = {}
    for variant, (_, report_dates) in BASELINES.items():
        qv = pit_panel.apply_report_dates(q, dates) if report_dates else q
        out[variant] = pit_panel.build_monthly_factors(qv, px, ev, sectors)
    out["_q"], out["_px"], out["_ev"] = q, px, ev
    out["_missing_debt_quarters"] = int((q["fin_debt"].isna() | q["cash"].isna()).sum())
    out["_quarters"] = len(q)
    return out


def compare(stored: pd.DataFrame, rebuilt: pd.DataFrame) -> dict:
    """Kayitli taban dosyasi ile yeniden kurulan panelin farki."""
    key = ["date", "ticker"]
    s = stored.assign(date=pd.to_datetime(stored["date"]))
    r = rebuilt.assign(date=pd.to_datetime(rebuilt["date"]))
    m = s.merge(r, on=key, how="outer", suffixes=("_s", "_r"), indicator=True)
    both = m[m["_merge"] == "both"]
    cols = {}
    for c in COMPARE_COLS:
        a, b = both[f"{c}_s"], both[f"{c}_r"]
        nan_diff = int((a.isna() != b.isna()).sum())
        rel = ((a - b).abs() / b.abs().clip(lower=1e-12))[a.notna() & b.notna()]
        cols[c] = {"nan_mismatch": nan_diff, "rows_rel_diff_gt_1e6": int((rel > 1e-6).sum()),
                   "max_rel_diff": float(rel.max()) if len(rel) else 0.0}
    return {"rows_stored": len(s), "rows_rebuilt": len(r),
            "only_stored": int((m["_merge"] == "left_only").sum()),
            "only_rebuilt": int((m["_merge"] == "right_only").sum()), "columns": cols}


def headline(v: dict) -> dict:
    s1 = v["specs"]["S1"]
    return {"verdict": v["verdict"],
            "baseline_discovery": v["baseline"]["discovery"]["tl"], "baseline_holdout": v["baseline"]["holdout"]["tl"],
            "S1_discovery": s1["discovery"]["tl"], "S1_holdout": s1["holdout"]["tl"],
            "S1_holdout_usd": s1["holdout"]["usd"]}


def main() -> None:
    sectors = {r["ticker"]: r["sektor"] for r in
               json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))}
    kap = load_kap()
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    rebuilt = rebuild_baseline(sectors)
    pr66 = sorted((ROOT / "data" / "reports").glob("research_survivorship_*.json"))
    result = {"as_of": date.today().isoformat(), "primary": "kapdates",
              "baseline_missing_debt_quarters": rebuilt["_missing_debt_quarters"],
              "baseline_quarters": rebuilt["_quarters"], "variants": {}}
    for variant, (fname, report_dates) in BASELINES.items():
        base_raw = rebuilt[variant]
        del_old, _ = delisted_panel(kap, report_dates, fill_missing_debt=True)
        del_raw, info = delisted_panel(kap, report_dates, fill_missing_debt=False)
        overlap = set(base_raw["ticker"]) & set(info)
        if overlap:
            raise SystemExit(f"Cikmis kod bugunku panelde de var: {sorted(overlap)}")
        old_ey = del_old.set_index(["date", "ticker"])["ey"]
        ey_nan = (del_raw["ey"].isna()
                  & old_ey.reindex(pd.MultiIndex.from_frame(del_raw[["date", "ticker"]])).notna().to_numpy())
        v = run_variant(base_raw, del_raw, info, market_m)
        v["baseline_vs_stored"] = compare(pd.read_parquet(RESEARCH / fname), base_raw)
        v["delisted_rows"] = len(del_raw)
        v["delisted_rows_ey_now_nan"] = int(ey_nan.sum())
        v["delisted_tickers_ey_now_nan"] = sorted(del_raw.loc[ey_nan, "ticker"].unique().tolist())
        result["variants"][variant] = v
        print_variant(f"{variant} (guncel kural)", v, info)
        print(f"Cikmis hisse satiri: {len(del_raw)}, EBIT/EV artik NaN: {int(ey_nan.sum())} "
              f"({v['delisted_tickers_ey_now_nan']})")
        print(f"Taban vs kayitli dosya: {json.dumps(v['baseline_vs_stored'])}")

    if pr66:  # PR #66 sonucu (en eski rapor: on-kayitli kosu)
        old = json.loads(pr66[0].read_text(encoding="utf-8"))
        result["pr66_file"] = pr66[0].name
        result["comparison"] = {k: {"pr66": headline(old["variants"][k]), "current_rule": headline(result["variants"][k])}
                                for k in BASELINES}
    result["verdict_current_rule"] = result["variants"]["kapdates"]["verdict"]
    result["verdict_pr66"] = "SURVIVORSHIP_FRAGILE"
    result["interpretation"] = ("verdict independent of missing-debt assumption"
                                if result["verdict_current_rule"] == result["verdict_pr66"]
                                else "verdict sensitive to missing-debt assumption")
    print(f"\nKarar (guncel kural): {result['verdict_current_rule']} | PR #66: {result['verdict_pr66']} "
          f"-> {result['interpretation']}")

    out = ROOT / "data" / "reports" / f"sensitivity_survivorship_net_debt_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"JSON: {out}")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
