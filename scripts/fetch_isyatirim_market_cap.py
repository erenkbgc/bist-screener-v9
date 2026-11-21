#!/usr/bin/env python3
"""Is Yatirim HisseTekil: gunluk duzeltilmemis kapanis, sermaye, piyasa degeri, halka acik PD.

docs/research/market_cap_source.md. borsapy'nin "duzeltilmemis" fiyati bedelli sermaye
artirimlarinda geriye donuk duzeltilmis (187 bedellinin 159'u); panelin fiyat x pay
piyasa degeri bu yuzden bedelli oncesi donemde dusuk kaliyordu. HisseTekil alanlari:
  HG_KAPANIS  duzeltilmemis kapanis     SERMAYE  odenmis sermaye (islem gununde degisir)
  PD          piyasa degeri (TL)        HAO_PD   halka acik piyasa degeri (TL)
Tek cagri tum gecmisi (2012'den) donduruyor.

    python scripts/fetch_isyatirim_market_cap.py          # eksikleri ceker
    python scripts/fetch_isyatirim_market_cap.py --update # mevcut hisselerin son tarihinden bugune ekler
    python scripts/fetch_isyatirim_market_cap.py --refresh

Cikti: data/research/isy_daily/<T>.parquet ve data/research/market_cap_monthly.parquet
(ticker, date = ay sonu, ayin son islem gunu degerleri).
"""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"
DAILY = RESEARCH / "isy_daily"
URL = "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTekil"
FIELDS = {"HG_KAPANIS": "close_unadj", "SERMAYE": "capital", "PD": "mcap", "HAO_PD": "ff_mcap"}


def fetch(ticker: str, start: str = "01-01-2012", end: str | None = None) -> pd.DataFrame:
    enddate = end or date.today().strftime("%d-%m-%Y")
    for attempt in range(4):
        try:
            r = requests.get(URL, params={"hisse": ticker, "startdate": start,
                                          "enddate": enddate},
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
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{ticker}: HisseTekil cevap vermedi")


def update_one(tk: str, refresh: bool, update: bool, end: date, sleep_s: float) -> tuple[str, str]:
    path = DAILY / f"{tk}.parquet"
    if path.exists() and not refresh and not update:
        return tk, "skip"
    if update and path.exists() and not refresh:
        old = pd.read_parquet(path)
        if old.empty:
            return tk, "empty"
        last_dt = pd.Timestamp(old["date"].max()).date()
        if last_dt >= end - timedelta(days=2):
            return tk, "up_to_date"
        start_str = (last_dt - timedelta(days=5)).strftime("%d-%m-%Y")
        df_new = fetch(tk, start=start_str, end=end.strftime("%d-%m-%Y"))
        if sleep_s > 0:
            time.sleep(sleep_s)
        if df_new.empty:
            return tk, "no_new"
        merged = (pd.concat([old, df_new], ignore_index=True)
                  .drop_duplicates(subset=["date"], keep="last")
                  .sort_values("date").reset_index(drop=True))
        merged.to_parquet(path, index=False)
        return tk, "updated"
    df = fetch(tk, end=end.strftime("%d-%m-%Y"))
    if sleep_s > 0:
        time.sleep(sleep_s)
    df.to_parquet(path, index=False)
    return tk, ("empty" if df.empty else "fetched")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--update", action="store_true", help="Mevcut gunluk dosyalari son tarihten bugune uzat")
    ap.add_argument("--end", default=date.today().isoformat(), help="Bitis tarihi YYYY-MM-DD")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args()
    DAILY.mkdir(parents=True, exist_ok=True)
    end = date.fromisoformat(args.end)
    tickers = sorted({f.stem for d in ("raw", "raw_delisted") for f in (RESEARCH / d).glob("*.pkl")})
    empty, failed, updated = [], [], 0
    if args.workers <= 1:
        for n, tk in enumerate(tickers, 1):
            try:
                _, st = update_one(tk, args.refresh, args.update, end, args.sleep)
                if st == "empty":
                    empty.append(tk)
                elif st in ("updated", "fetched"):
                    updated += 1
            except RuntimeError as exc:
                failed.append(tk)
                print(exc, flush=True)
            if n % 50 == 0:
                print(f"{n}/{len(tickers)} (guncellenen {updated}, hata {len(failed)})", flush=True)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(update_one, tk, args.refresh, args.update, end, args.sleep): tk for tk in tickers}
            for n, fut in enumerate(as_completed(futs), 1):
                tk = futs[fut]
                try:
                    _, st = fut.result()
                    if st == "empty":
                        empty.append(tk)
                    elif st in ("updated", "fetched"):
                        updated += 1
                except RuntimeError as exc:
                    failed.append(tk)
                    print(exc, flush=True)
                if n % 50 == 0:
                    print(f"{n}/{len(tickers)} (guncellenen {updated}, hata {len(failed)})", flush=True)
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
    print(f"{len(tickers)} hisse, guncellenen {updated}, bos {len(empty)} {empty[:10]}, basarisiz {failed}; "
          f"aylik satir {len(monthly)}, son ay {monthly['date'].max().date()}")


if __name__ == "__main__":
    main()
