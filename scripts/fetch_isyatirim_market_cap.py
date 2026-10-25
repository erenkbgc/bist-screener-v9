#!/usr/bin/env python3
"""Is Yatirim HisseTekil: gunluk duzeltilmemis kapanis, sermaye, piyasa degeri, halka acik PD.

docs/research/market_cap_source.md. borsapy'nin "duzeltilmemis" fiyati bedelli sermaye
artirimlarinda geriye donuk duzeltilmis (187 bedellinin 159'u); panelin fiyat x pay
piyasa degeri bu yuzden bedelli oncesi donemde dusuk kaliyordu. HisseTekil alanlari:
  HG_KAPANIS  duzeltilmemis kapanis     SERMAYE  odenmis sermaye (islem gununde degisir)
  PD          piyasa degeri (TL)        HAO_PD   halka acik piyasa degeri (TL)
Tek cagri tum gecmisi (2012'den) donduruyor.

    python scripts/fetch_isyatirim_market_cap.py          # eksikleri ceker
    python scripts/fetch_isyatirim_market_cap.py --refresh

Cikti: data/research/isy_daily/<T>.parquet ve data/research/market_cap_monthly.parquet
(ticker, date = ay sonu, ayin son islem gunu degerleri).
"""
from __future__ import annotations

import argparse
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"
DAILY = RESEARCH / "isy_daily"
URL = "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTekil"
FIELDS = {"HG_KAPANIS": "close_unadj", "SERMAYE": "capital", "PD": "mcap", "HAO_PD": "ff_mcap"}


def fetch(ticker: str) -> pd.DataFrame:
    for attempt in range(4):
        try:
            r = requests.get(URL, params={"hisse": ticker, "startdate": "01-01-2012",
                                          "enddate": date.today().strftime("%d-%m-%Y")},
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            if r.status_code == 200:
                v = r.json().get("value") or []
                df = pd.DataFrame(v)
                if df.empty:
                    return df
                out = pd.DataFrame({"date": pd.to_datetime(df["HGDG_TARIH"], format="%d-%m-%Y")})
                for src, dst in FIELDS.items():
                    out[dst] = pd.to_numeric(df.get(src), errors="coerce")
                return out.sort_values("date").reset_index(drop=True)
        except (requests.RequestException, ValueError):
            pass
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"{ticker}: HisseTekil cevap vermedi")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    DAILY.mkdir(parents=True, exist_ok=True)
    tickers = sorted({f.stem for d in ("raw", "raw_delisted") for f in (RESEARCH / d).glob("*.pkl")})
    empty, failed = [], []
    for n, tk in enumerate(tickers, 1):
        path = DAILY / f"{tk}.parquet"
        if path.exists() and not args.refresh:
            continue
        try:
            df = fetch(tk)
        except RuntimeError as exc:
            failed.append(tk)
            print(exc, flush=True)
            continue
        if df.empty:
            empty.append(tk)
        df.to_parquet(path, index=False)
        time.sleep(1.0)
        if n % 50 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
    frames = []
    for f in sorted(DAILY.glob("*.parquet")):
        d = pd.read_parquet(f)
        if d.empty:
            continue
        d = d.dropna(subset=["mcap"])
        m = d.groupby(d["date"].dt.to_period("M")).last().reset_index(drop=True)
        m["date"] = m["date"].dt.to_period("M").dt.to_timestamp("M")
        frames.append(m.assign(ticker=f.stem))
    monthly = pd.concat(frames, ignore_index=True)
    monthly.to_parquet(RESEARCH / "market_cap_monthly.parquet", index=False)
    print(f"{len(tickers)} hisse, bos {len(empty)} {empty[:10]}, basarisiz {failed}; "
          f"aylik satir {len(monthly)}")


if __name__ == "__main__":
    main()
