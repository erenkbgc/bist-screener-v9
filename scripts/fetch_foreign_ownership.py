#!/usr/bin/env python3
"""Aylik hisse bazinda yabanci payi (docs/research/foreign_ownership_preregistration.md).

Kaynak: Is Yatirim GetYabanciOranlarXHR (sirket karti sayfasinin kullandigi uc nokta).
Ardisik ay sonu ciftleri icin tek cagri tum piyasayi dondurur. Ay sonu = ayin son
islem gunu; bos donerse 5 gune kadar geriye gidilir. Veri ~2013-06'dan baslar.

    python scripts/fetch_foreign_ownership.py      # data/research/foreign_monthly.parquet
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "research" / "foreign_monthly.parquet"
URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/StockInfo/CompanyInfoAjax.aspx/GetYabanciOranlarXHR"
HEADERS = {"User-Agent": "Mozilla/5.0",
           "Referer": "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx?hisse=THYAO"}
START = date(2013, 5, 31)


def _call(a: date, b: date) -> list[dict]:
    body = {"baslangicTarih": a.strftime("%d-%m-%Y"), "bitisTarihi": b.strftime("%d-%m-%Y"),
            "sektor": None, "endeks": None, "hisse": None}
    for attempt in range(3):
        try:
            r = httpx.post(URL, json=body, headers=HEADERS, timeout=120)
            r.raise_for_status()
            return r.json().get("d") or []
        except (httpx.HTTPError, ValueError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"fetch failed {a} {b}")


def month_ends(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        nxt = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
        last = nxt - timedelta(days=1)
        while last.weekday() > 4:
            last -= timedelta(days=1)
        out.append(last)
        d = nxt
    return out


def main() -> None:
    today = date.today()
    ends = [m for m in month_ends(START, today) if m < today]
    rows, prev = [], None
    for m in ends:
        if prev is None:
            prev = m
            continue
        got, used = [], m
        for back in range(6):
            used = m - timedelta(days=back)
            if used.weekday() > 4:
                continue
            got = _call(prev, used)
            if got:
                break
        for x in got:
            rows.append({"month": pd.Timestamp(m), "date_used": pd.Timestamp(used), "ticker": x["HISSE_KODU"],
                         "foreign_pct": x["YAB_ORAN_END"]})
        print(f"{m} (veri {used}): {len(got)} hisse", flush=True)
        prev = used if got else prev
        time.sleep(0.5)
    df = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"{len(df)} satir, {df['month'].nunique()} ay -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
