#!/usr/bin/env python3
"""Turkiye USD Eurobond ay sonu getirileri (borsapy / Ziraat arsivi) ve ABD Hazine
getirileri (yfinance ^FVX, ^TNX, ^TYX) -> data/research/eurobond_monthly.parquet.

Her ay sonu icin o gun (ya da onceki 5 is gunu icinde ilk dolu gun) tum USD tahviller.
docs/research/sovereign_spread_preregistration.md

    python scripts/fetch_eurobond_monthly.py            # eksik yeni aylari ekler
    python scripts/fetch_eurobond_monthly.py --refresh  # tum 2008+ gecmisi yeniden ceker
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"


def month_end_bonds(p, month_end: pd.Timestamp) -> list[dict]:
    for k in range(6):
        d = (month_end - pd.offsets.BDay(k)) if k else month_end
        if d.weekday() >= 5:
            continue
        rows = [b for b in p._fetch_bonds_for_date_cached(d.strftime("%Y-%m-%d"))
                if b.get("currency") == "USD" and b.get("bid_yield")]
        if rows:
            return [{"month": month_end, "date": d, "isin": b["isin"], "maturity": pd.Timestamp(b["maturity"]),
                     "yield": float(b["bid_yield"])} for b in rows]
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="Tum gecmisi sifirdan cek")
    args = ap.parse_args()

    from borsapy._providers.ziraat_eurobond import get_eurobond_provider
    import yfinance as yf

    p = get_eurobond_provider()
    out_path = RESEARCH / "eurobond_monthly.parquet"
    existing = pd.read_parquet(out_path) if out_path.exists() and not args.refresh else pd.DataFrame()
    done_months = set(pd.to_datetime(existing["month"]).unique()) if not existing.empty else set()
    months = pd.date_range("2008-01-31", pd.Timestamp.today().normalize() - pd.offsets.MonthEnd(1), freq="ME")
    todo = [m for m in months if m not in done_months]
    rows = []
    for n, m in enumerate(todo, 1):
        try:
            rows += month_end_bonds(p, m)
        except Exception as ex:  # noqa: BLE001
            print(f"  {m.date()} hata: {str(ex)[:60]}", flush=True)
        if n % 24 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
    eb_new = pd.DataFrame(rows)
    eb = (pd.concat([existing, eb_new], ignore_index=True)
          .drop_duplicates(subset=["month", "isin"], keep="last")
          .sort_values(["month", "maturity", "isin"]).reset_index(drop=True))
    eb.to_parquet(out_path, index=False)

    ust = yf.download(["^FVX", "^TNX", "^TYX"], start="2007-12-01", auto_adjust=False, progress=False)["Close"]
    ust.index = pd.to_datetime(ust.index).tz_localize(None).normalize()
    ust.to_parquet(RESEARCH / "ust_daily.parquet")
    print(f"eurobond satir {len(eb)} (yeni {len(eb_new)}), ay {eb['month'].nunique() if len(eb) else 0}, "
          f"{eb['month'].min().date() if len(eb) else None} .. {eb['month'].max().date() if len(eb) else None}; "
          f"UST {len(ust)} gun (son {ust.index.max().date()})")


if __name__ == "__main__":
    sys.exit(main())
