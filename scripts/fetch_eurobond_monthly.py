#!/usr/bin/env python3
"""Turkiye USD Eurobond ay sonu getirileri (borsapy / Ziraat arsivi) ve ABD Hazine
getirileri (yfinance ^FVX, ^TNX, ^TYX) -> data/research/eurobond_monthly.parquet.

Her ay sonu icin o gun (ya da onceki 5 is gunu icinde ilk dolu gun) tum USD tahviller.
docs/research/sovereign_spread_preregistration.md

    python scripts/fetch_eurobond_monthly.py
"""
from __future__ import annotations

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
    from borsapy._providers.ziraat_eurobond import get_eurobond_provider
    import yfinance as yf

    p = get_eurobond_provider()
    months = pd.date_range("2008-01-31", pd.Timestamp.today().normalize() - pd.offsets.MonthEnd(1), freq="ME")
    rows = []
    for n, m in enumerate(months, 1):
        try:
            rows += month_end_bonds(p, m)
        except Exception as ex:  # noqa: BLE001
            print(f"  {m.date()} hata: {str(ex)[:60]}", flush=True)
        if n % 24 == 0:
            print(f"  {n}/{len(months)}", flush=True)
    eb = pd.DataFrame(rows)
    eb.to_parquet(RESEARCH / "eurobond_monthly.parquet", index=False)

    ust = yf.download(["^FVX", "^TNX", "^TYX"], start="2007-12-01", auto_adjust=False, progress=False)["Close"]
    ust.index = pd.to_datetime(ust.index).tz_localize(None).normalize()
    ust.to_parquet(RESEARCH / "ust_daily.parquet")
    print(f"eurobond satir {len(eb)}, ay {eb['month'].nunique() if len(eb) else 0}, "
          f"ilk ay {eb['month'].min() if len(eb) else None}; UST {len(ust)} gun")


if __name__ == "__main__":
    sys.exit(main())
