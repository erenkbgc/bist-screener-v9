#!/usr/bin/env python3
"""Nokta-zamanli arastirma panelini kurar (data/research/, git'e girmez).

    python scripts/build_pit_panel.py                 # tum finansal-disi evren
    python scripts/build_pit_panel.py --tickers THYAO,ASELS,BIMAS
    python scripts/build_pit_panel.py --refresh       # ham onbellegi yenile

Ham borsapy cevaplari ticker basina data/research/raw/<T>.pkl olarak saklanir;
yarida kesilen kosu kaldigi yerden devam eder.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import pit_panel  # noqa: E402

OUT = ROOT / "data" / "research"
RAW = OUT / "raw"


RAW_VERSION = 2  # v1: borsapy'nin kartezyen-sismis tablolari (bkz. pit_panel.merge_statement_batches)


def fetch_raw(ticker: str, refresh: bool) -> dict | None:
    path = RAW / f"{ticker}.pkl"
    raw = pickle.loads(path.read_bytes()) if path.exists() and not refresh else None
    if raw is not None and raw.get("version") == RAW_VERSION:
        return raw
    import borsapy as bp
    t = bp.Ticker(ticker)

    def safe(fn, **kw):
        try:
            return fn(**kw)
        except Exception:
            return None
    if raw is None:
        raw = {
            "px_raw": safe(t.history, period="max", adjust=False),
            "px_adj": safe(t.history, period="max", adjust=True),
            "splits": safe(lambda: t.splits),
        }
    # v1 onbellekte fiyat/bolunme saglam; yalniz tablolar yeniden cekilir
    raw["bs"] = safe(pit_panel.fetch_statement, ticker=ticker, statement_type="balance_sheet", last_n=60)
    raw["inc"] = safe(pit_panel.fetch_statement, ticker=ticker, statement_type="income_stmt", last_n=60)
    raw["version"] = RAW_VERSION
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(raw))
    return raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    sector_rows = json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))
    sectors = {r["ticker"]: r["sektor"] for r in sector_rows}
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = sorted(t for t, s in sectors.items() if s not in pit_panel.FINANCIAL_SECTORS)

    longs, pxs, evs = [], [], []
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_raw, t, args.refresh): t for t in tickers}
        for n, fut in enumerate(as_completed(futs), 1):
            tk = futs[fut]
            try:
                raw = fut.result()
            except Exception as exc:  # noqa: BLE001
                failed.append((tk, str(exc)[:80]))
                continue
            longs.append(pit_panel.statements_long(tk, raw.get("bs"), raw.get("inc")))
            pxs.append(pit_panel.monthly_prices(tk, raw.get("px_raw"), raw.get("px_adj")))
            evs.append(pit_panel.split_events(tk, raw.get("splits")))
            if n % 50 == 0:
                print(f"  {n}/{len(tickers)}", flush=True)

    long = pd.concat([x for x in longs if not x.empty], ignore_index=True)
    q = pit_panel.quarterly_table(long)
    archive = OUT / "kap_archive.parquet"
    if archive.exists():  # gercek KAP yayin tarihleri (kap_report_dates_preregistration.md, varyant B)
        q = pit_panel.apply_report_dates(q, pit_panel.kap_report_dates(pd.read_parquet(archive)))
        print(f"KAP yayin tarihi eslesen ceyrek: %{100 * (q['available_source'] == 'kap').mean():.1f}")
    else:
        print("UYARI: data/research/kap_archive.parquet yok; varsayilan 75/100 gun gecikmesi kullaniliyor.")
    px = pd.concat([x for x in pxs if not x.empty], ignore_index=True)
    ev = pd.concat([x for x in evs if not x.empty], ignore_index=True) if any(not x.empty for x in evs) else pd.DataFrame()
    factors = pit_panel.build_monthly_factors(q, px, ev, sectors)

    OUT.mkdir(parents=True, exist_ok=True)
    q.to_parquet(OUT / "quarterly.parquet", index=False)
    px.to_parquet(OUT / "monthly_prices.parquet", index=False)
    if not ev.empty:
        ev.to_parquet(OUT / "share_events.parquet", index=False)
    factors.to_parquet(OUT / "factors_monthly.parquet", index=False)
    print(f"Hisse: {len(tickers)} (basarisiz {len(failed)}), ceyrek satiri {len(q)}, "
          f"faktor satiri {len(factors)}, {factors['date'].min().date() if len(factors) else '-'} .. "
          f"{factors['date'].max().date() if len(factors) else '-'}")
    if failed:
        print("Basarisiz:", failed[:10])


if __name__ == "__main__":
    main()
