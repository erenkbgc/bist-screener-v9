#!/usr/bin/env python3
"""Ilk yayin rakamlariyla aylik faktor paneli (P3-1, docs/research/first_published_panel.md).

Ham Is Yatirim tablolarinda (data/research/raw/*.pkl) 2022Q4 ve sonrasi donemlerin
kalemleri, KAP ilk yayin rakamlariyla (scripts/build_first_published.py) degistirilir.
Birim: KAP toplam varliklari Is Yatirim'inkine 10'un kuvvetiyle olceklenir; olcekli oran
[0.6, 1.8] disindaysa (farkli para birimi) o donem Is Yatirim'da kalir. TMS 29 yeniden
ifadesi (x1.3-1.5) bu araliktadir. KAP'ta bulunmayan kalem Is Yatirim'da kalir.

Yazilan dosyalar (mevcut paneller DEGISMEZ):
  data/research/fp/factors_monthly.parquet, factors_monthly_kapdates.parquet, quarterly.parquet

    python scripts/rebuild_panels_first_published.py
"""
from __future__ import annotations

import json
import math
import pickle
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import pit_panel  # noqa: E402
from sensitivity_survivorship_net_debt import BASELINES  # noqa: E402

RESEARCH = ROOT / "data" / "research"
OUT = RESEARCH / "fp"
FIRST_PERIOD = "2022Q4"
ITEMS = ["total_assets", "equity_parent", "equity", "paid_in", "cash", "fin_debt",
         "revenue", "gross_profit", "op_profit", "ni_parent", "net_income"]
SCALE_BAND = (0.6, 1.8)


def replace_first_published(long: pd.DataFrame, fp: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """long: statements_long ciktisi (tum hisseler). fp: first_published.parquet."""
    fp = fp[fp["period"] >= FIRST_PERIOD]
    ta = long[long["item"] == "total_assets"].set_index(["ticker", "period"])["value"]
    keep, add = [], []
    stats = {"periods": len(fp), "replaced": 0, "currency_or_unit_skip": 0, "no_vendor_ta": 0}
    replaced_keys = set()
    for r in fp.itertuples(index=False):
        v_ta, k_ta = ta.get((r.ticker, r.period)), r.total_assets
        if v_ta is None or not k_ta or k_ta <= 0 or v_ta <= 0:
            stats["no_vendor_ta"] += 1
            continue
        scale = 10.0 ** round(math.log10(v_ta / k_ta))
        if not (SCALE_BAND[0] <= v_ta / (k_ta * scale) <= SCALE_BAND[1]):
            stats["currency_or_unit_skip"] += 1
            continue
        stats["replaced"] += 1
        for item in ITEMS:
            val = getattr(r, item)
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                replaced_keys.add((r.ticker, r.period, item))
                add.append({"ticker": r.ticker, "period": r.period, "item": item, "value": float(val) * scale})
    mask = [(t, p, i) not in replaced_keys for t, p, i in zip(long["ticker"], long["period"], long["item"])]
    keep = long[mask]
    stats["values_replaced"] = len(add)
    return pd.concat([keep, pd.DataFrame(add)], ignore_index=True), stats


def main() -> None:
    sectors = {r["ticker"]: r["sektor"] for r in
               json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))}
    cpi = pit_panel.cpi_index(pd.read_parquet(RESEARCH / "macro_monthly.parquet")["cpi_mom"])
    longs, pxs, evs = [], [], []
    for f in sorted((RESEARCH / "raw").glob("*.pkl")):
        tk = f.stem
        if tk not in sectors or sectors[tk] in pit_panel.FINANCIAL_SECTORS:
            continue
        raw = pickle.loads(f.read_bytes())
        longs.append(pit_panel.statements_long(tk, raw.get("bs"), raw.get("inc")))
        pxs.append(pit_panel.monthly_prices(tk, raw.get("px_raw"), raw.get("px_adj")))
        evs.append(pit_panel.split_events(tk, raw.get("splits")))
    long = pd.concat([x for x in longs if not x.empty], ignore_index=True)
    long, stats = replace_first_published(long, pd.read_parquet(RESEARCH / "first_published.parquet"))
    print(json.dumps(stats))
    q = pit_panel.quarterly_table(long, cpi=cpi)
    px = pd.concat([x for x in pxs if not x.empty], ignore_index=True)
    ev = pd.concat([x for x in evs if not x.empty], ignore_index=True)
    dates = pit_panel.kap_report_dates(pd.read_parquet(RESEARCH / "kap_archive.parquet"))
    OUT.mkdir(exist_ok=True)
    names = {"lag75": "factors_monthly.parquet", "kapdates": "factors_monthly_kapdates.parquet"}
    for variant, (_, report_dates) in BASELINES.items():
        qv = pit_panel.apply_report_dates(q, dates) if report_dates else q
        pit_panel.build_monthly_factors(qv, px, ev, sectors).to_parquet(OUT / names[variant], index=False)
    q.to_parquet(OUT / "quarterly.parquet", index=False)
    (OUT / "STATS.json").write_text(json.dumps(stats, indent=1))
    print("yazildi:", OUT)


if __name__ == "__main__":
    main()
