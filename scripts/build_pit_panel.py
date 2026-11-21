#!/usr/bin/env python3
"""Nokta-zamanli arastirma panelini kurar (data/research/, git'e girmez).

    python scripts/build_pit_panel.py                 # tum finansal-disi evren
    python scripts/build_pit_panel.py --tickers THYAO,ASELS,BIMAS
    python scripts/build_pit_panel.py --update        # fiyat/bolunme + son 8 ceyrek guncelle
    python scripts/build_pit_panel.py --refresh       # tum ham onbellegi sifirdan yenile

Ham borsapy cevaplari ticker basina data/research/raw/<T>.pkl olarak saklanir;
yarida kesilen kosu kaldigi yerden devam eder.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import pit_panel  # noqa: E402

OUT = ROOT / "data" / "research"
RAW = OUT / "raw"


RAW_VERSION = 2  # v1: borsapy'nin kartezyen-sismis tablolari (bkz. pit_panel.merge_statement_batches)
UPDATE_QUARTERS = 8  # son 2 batch (8 ceyrek): yeni ceyrek + TMS 29 yeniden ifade edilen onceki yil donemleri


def last_ended_quarter(as_of: date | None = None) -> tuple[int, int]:
    """as_of itibariyla takvim olarak bitmis en son ceyrek (yil, ay).

    borsapy._providers.isyatirim._get_periods Kasim ayinda Q2'de kaldigi icin
    Q3 yayinlarini atliyor; burada takvim olarak bitmis son ceyrekten baslanir.
    """
    d = as_of or date.today()
    for m, day in ((12, 31), (9, 30), (6, 30), (3, 31)):
        if (d.month, d.day) >= (m, day):
            return d.year, m
    return d.year - 1, 12


def quarter_periods(count: int, as_of: date | None = None) -> list[tuple[int, int]]:
    """Takvim olarak bitmis en son ceyrekten geriye dogru `count` adet (yil, ay) cifti."""
    year, period = last_ended_quarter(as_of)
    out: list[tuple[int, int]] = []
    for _ in range(count):
        out.append((year, period))
        period -= 3
        if period <= 0:
            period = 12
            year -= 1
    return out


def fetch_statement_upto_latest(
    ticker: str,
    statement_type: str,
    last_n: int,
    as_of: date | None = None,
    retries: int = 2,
) -> pd.DataFrame | None:
    """Is Yatirim sanayi sablonu, takvim olarak bitmis son ceyrekten geriye last_n donem.

    Is Yatirim API'si her cagrida 4 donem bekler; last_n 4'un kati secilmelidir.
    """
    from borsapy._providers.isyatirim import get_isyatirim_provider

    prov = get_isyatirim_provider()
    step = prov._MAX_PERIODS_PER_CALL
    n = max(step, ((last_n + step - 1) // step) * step)
    periods = quarter_periods(n, as_of=as_of)
    batches: list[pd.DataFrame] = []
    for i in range(0, len(periods), step):
        chunk = periods[i:i + step]
        for attempt in range(retries + 1):
            try:
                df = prov._fetch_financial_table(
                    symbol=ticker,
                    financial_group=prov.FINANCIAL_GROUP_INDUSTRIAL,
                    periods=chunk,
                    quarterly=True,
                    statement_type=statement_type,
                )
                if df is not None and not df.empty:
                    batches.append(df)
                break
            except Exception:  # noqa: BLE001
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
    merged = pit_panel.merge_statement_batches(batches)
    if merged.empty:
        return None
    return merged[sorted(merged.columns, key=prov._period_sort_key, reverse=True)]


def merge_updated_statement(old: pd.DataFrame | None, fresh: pd.DataFrame | None) -> pd.DataFrame | None:
    """Yeni cekilen son ceyrekleri mevcut gecmis tablo sutunlariyla birlestirir."""
    if fresh is None or fresh.empty:
        return old
    if old is None or old.empty:
        return fresh
    keep_cols = [c for c in old.columns if c not in fresh.columns]
    if not keep_cols:
        return fresh
    merged = pit_panel.merge_statement_batches([fresh, old[keep_cols]])
    if merged.empty:
        return old
    from borsapy._providers.isyatirim import get_isyatirim_provider
    prov = get_isyatirim_provider()
    return merged[sorted(merged.columns, key=prov._period_sort_key, reverse=True)]


def fetch_raw(ticker: str, refresh: bool, update: bool = False, as_of: date | None = None) -> dict | None:
    path = RAW / f"{ticker}.pkl"
    raw = pickle.loads(path.read_bytes()) if path.exists() and not refresh else None
    if raw is not None and raw.get("version") == RAW_VERSION and not update:
        return raw
    import borsapy as bp
    t = bp.Ticker(ticker)

    def safe(fn, retries: int = 2, **kw):
        for attempt in range(retries + 1):
            try:
                res = fn(**kw)
                if res is not None:
                    return res
            except Exception:  # noqa: BLE001
                pass
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
        return None

    if raw is None or update:
        px_raw = safe(t.history, period="max", adjust=False)
        px_adj = safe(t.history, period="max", adjust=True)
        splits = safe(lambda: t.splits)
        if raw is None:
            raw = {"px_raw": px_raw, "px_adj": px_adj, "splits": splits}
        else:
            if px_raw is not None and not px_raw.empty:
                raw["px_raw"] = px_raw
            if px_adj is not None and not px_adj.empty:
                raw["px_adj"] = px_adj
            if splits is not None:
                raw["splits"] = splits

    if update and raw.get("bs") is not None and raw.get("inc") is not None:
        fresh_bs = fetch_statement_upto_latest(ticker, "balance_sheet", UPDATE_QUARTERS, as_of=as_of)
        fresh_inc = fetch_statement_upto_latest(ticker, "income_stmt", UPDATE_QUARTERS, as_of=as_of)
        raw["bs"] = merge_updated_statement(raw.get("bs"), fresh_bs)
        raw["inc"] = merge_updated_statement(raw.get("inc"), fresh_inc)
    else:
        # v1 onbellekte fiyat/bolunme saglam; yalniz tablolar yeniden cekilir
        raw["bs"] = fetch_statement_upto_latest(ticker, "balance_sheet", 60, as_of=as_of)
        raw["inc"] = fetch_statement_upto_latest(ticker, "income_stmt", 60, as_of=as_of)
    raw["version"] = RAW_VERSION
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(raw))
    return raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--update", action="store_true", help="Fiyat/bolunme ve son 8 ceyregi guncelle")
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
        futs = {ex.submit(fetch_raw, t, args.refresh, args.update): t for t in tickers}
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
    # TMS 29 akislari ortak satin alma gucunde (C1); macro_monthly yoksa C0
    macro_path = OUT / "macro_monthly.parquet"
    cpi = pit_panel.cpi_index(pd.read_parquet(macro_path)["cpi_mom"]) if macro_path.exists() else None
    if cpi is None:
        print("UYARI: macro_monthly.parquet yok; TTM C0 (TMS 29 birim duzeltmesi yok).")
    q = pit_panel.quarterly_table(long, cpi=cpi)
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
