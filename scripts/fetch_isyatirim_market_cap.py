#!/usr/bin/env python3
"""Is Yatirim HisseTekil: gunluk duzeltilmemis kapanis, sermaye, piyasa degeri, halka acik PD.

docs/research/market_cap_source.md. borsapy'nin "duzeltilmemis" fiyati bedelli sermaye
artirimlarinda geriye donuk duzeltilmis (187 bedellinin 159'u); panelin fiyat x pay
piyasa degeri bu yuzden bedelli oncesi donemde dusuk kaliyordu. HisseTekil alanlari:
  HG_KAPANIS  duzeltilmemis kapanis     SERMAYE  odenmis sermaye (islem gununde degisir)
  PD          piyasa degeri (TL)        HAO_PD   halka acik piyasa degeri (TL)
Tek cagri tum gecmisi (2012'den) donduruyor; bazi hisselerde tek bir bozuk islem gunu
(orn. INTEK/LRSHO/LYDHO Temmuz 2018, CITAS Agustos 2026) tum araligi bos dondurdugu
icin bos donen hisselerde yillik -> aylik -> ikili bolme (bisection) ile geri kalan
tum gunler kurtarilir.

    python scripts/fetch_isyatirim_market_cap.py              # eksikleri ceker
    python scripts/fetch_isyatirim_market_cap.py --retry-empty
    python scripts/fetch_isyatirim_market_cap.py --tickers INTEK LRSHO LYDHO CITAS
    python scripts/fetch_isyatirim_market_cap.py --update # mevcut hisselerin son tarihinden bugune ekler
    python scripts/fetch_isyatirim_market_cap.py --update # mevcut hisselerin son tarihinden bugune ekler
    python scripts/fetch_isyatirim_market_cap.py --refresh

Cikti: data/research/isy_daily/<T>.parquet ve data/research/market_cap_monthly.parquet
(ticker, date = ay sonu, ayin son islem gunu degerleri).
"""
from __future__ import annotations

import argparse
import calendar
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"
DAILY = RESEARCH / "isy_daily"
URL = "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTekil"
FIELDS = {"HG_KAPANIS": "close_unadj", "SERMAYE": "capital", "PD": "mcap", "HAO_PD": "ff_mcap"}
START_DATE = date(2012, 1, 1)


def _fetch_window(ticker: str, start: date, end: date) -> pd.DataFrame:
    for attempt in range(4):
        try:
            r = requests.get(
                URL,
                params={
                    "hisse": ticker,
                    "startdate": start.strftime("%d-%m-%Y"),
                    "enddate": end.strftime("%d-%m-%Y"),
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=60,
            )
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
    raise RuntimeError(f"{ticker}: HisseTekil cevap vermedi ({start}..{end})")


def _bisect_window(ticker: str, start: date, end: date, pause: float = 0.25) -> list[pd.DataFrame]:
    """Bos donen bir tarih araligini ikili bolerek tekil bozuk gunu atlar, diger gunleri kurtarir."""
    time.sleep(pause)
    df = _fetch_window(ticker, start, end)
    if not df.empty:
        return [df]
    if start >= end:
        return []
    mid = start + timedelta(days=(end - start).days // 2)
    return _bisect_window(ticker, start, mid, pause) + _bisect_window(ticker, mid + timedelta(days=1), end, pause)


def _fetch_year_months(ticker: str, yr: int, today: date, pause: float = 0.25) -> list[pd.DataFrame]:
    """Bir yilin aylarini tarar; aradaki/son bos aylari ikili bolerek bozuk tekil gunu atlar."""
    months: dict[int, pd.DataFrame] = {}
    max_m = today.month if yr == today.year else 12
    for m in range(1, max_m + 1):
        s = date(yr, m, 1)
        e = min(today, date(yr, m, calendar.monthrange(yr, m)[1]))
        time.sleep(pause)
        months[m] = _fetch_window(ticker, s, e)
    non_empty = [m for m, d in months.items() if not d.empty]
    if not non_empty:
        return []
    frames = [months[m] for m in non_empty]
    # Dolu aylarin arasinda veya ilk dolu aydan hemen once bos kalan aylari ikili bol
    lo = max(1, min(non_empty) - 1)
    hi = max(non_empty)
    for m in range(lo, hi + 1):
        if months[m].empty:
            s = date(yr, m, 1)
            e = min(today, date(yr, m, calendar.monthrange(yr, m)[1]))
            frames.extend(_bisect_window(ticker, s, e, pause))
    return frames


def fetch(ticker: str, bisect_on_empty: bool = True) -> pd.DataFrame:
    today = date.today()
    df = _fetch_window(ticker, START_DATE, today)
    if not df.empty or not bisect_on_empty:
        return df

    # Tek cagri bos dondu: yillik tarama (tekil bozuk gun tum sorguyu bosaltabiliyor)
    yearly: dict[int, pd.DataFrame] = {}
    for yr in range(START_DATE.year, today.year + 1):
        s = date(yr, 1, 1)
        e = min(today, date(yr, 12, 31))
        time.sleep(0.25)
        yearly[yr] = _fetch_window(ticker, s, e)
    non_empty_yrs = [yr for yr, d in yearly.items() if not d.empty]

    frames: list[pd.DataFrame] = [yearly[yr] for yr in non_empty_yrs]
    if not non_empty_yrs:
        # Yeni halka arz ve bozuk gun ayni yildaysa (orn. CITAS 2026) yalnizca son yili aylik dene
        frames.extend(_fetch_year_months(ticker, today.year, today))
    else:
        lo_yr = max(START_DATE.year, min(non_empty_yrs) - 1)
        hi_yr = max(non_empty_yrs)
        for yr in range(lo_yr, hi_yr + 1):
            if yearly[yr].empty:
                frames.extend(_fetch_year_months(ticker, yr, today))

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["date"])
    return out.sort_values("date").reset_index(drop=True)


def rebuild_monthly() -> pd.DataFrame:
    frames = []
    for f in sorted(DAILY.glob("*.parquet")):
        d = pd.read_parquet(f)
        if d.empty:
            continue
        d = d.dropna(subset=["mcap"])
        if d.empty:
            continue
        m = d.groupby(d["date"].dt.to_period("M")).last().reset_index(drop=True)
        m["date"] = m["date"].dt.to_period("M").dt.to_timestamp("M")
        frames.append(m.assign(ticker=f.stem))
    monthly = pd.concat(frames, ignore_index=True)
    monthly.to_parquet(RESEARCH / "market_cap_monthly.parquet", index=False)
    return monthly


def update_existing(ticker: str, end: date) -> str:
    """Mevcut gunluk dosyayi son tarihten (5 gun ortusmeli) `end` tarihine kadar uzatir."""
    path = DAILY / f"{ticker}.parquet"
    if not path.exists():
        return "missing"
    old = pd.read_parquet(path)
    if old.empty:
        return "empty"
    last_dt = pd.Timestamp(old["date"].max()).date()
    if last_dt >= end - timedelta(days=2):
        return "up_to_date"
    new = _fetch_window(ticker, last_dt - timedelta(days=5), end)
    if new.empty:
        return "no_new"
    merged = (pd.concat([old, new], ignore_index=True)
              .drop_duplicates(subset=["date"], keep="last")
              .sort_values("date").reset_index(drop=True))
    merged.to_parquet(path, index=False)
    return "updated"


def update_existing(ticker: str, end: date) -> str:
    """Mevcut gunluk dosyayi son tarihten (5 gun ortusmeli) `end` tarihine kadar uzatir."""
    path = DAILY / f"{ticker}.parquet"
    if not path.exists():
        return "missing"
    old = pd.read_parquet(path)
    if old.empty:
        return "empty"
    last_dt = pd.Timestamp(old["date"].max()).date()
    if last_dt >= end - timedelta(days=2):
        return "up_to_date"
    new = _fetch_window(ticker, last_dt - timedelta(days=5), end)
    if new.empty:
        return "no_new"
    merged = (pd.concat([old, new], ignore_index=True)
              .drop_duplicates(subset=["date"], keep="last")
              .sort_values("date").reset_index(drop=True))
    merged.to_parquet(path, index=False)
    return "updated"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--retry-empty", action="store_true", help="yalnizca 0 satirli mevcut dosyalari yeniden dener")
    ap.add_argument("--tickers", nargs="+", help="yalnizca belirtilen hisseleri ceker")
    ap.add_argument("--update", action="store_true", help="mevcut gunluk dosyalari son tarihten bugune uzatir")
    ap.add_argument("--end", default=date.today().isoformat(), help="--update bitis tarihi YYYY-MM-DD")
    args = ap.parse_args()
    DAILY.mkdir(parents=True, exist_ok=True)
    if args.tickers:
        tickers = sorted(set(args.tickers))
    else:
        tickers = sorted({
            f.stem
            for d in ("raw", "raw_delisted", "raw_fin")
            if (RESEARCH / d).exists()
            for f in (RESEARCH / d).glob("*.pkl")
        })
    empty, failed, fetched = [], [], 0
    if args.update:
        end = date.fromisoformat(args.end)
        counts: dict[str, int] = {}
        for n, tk in enumerate(tickers, 1):
            try:
                st = update_existing(tk, end)
            except RuntimeError as exc:
                st = "failed"
                print(exc, flush=True)
            counts[st] = counts.get(st, 0) + 1
            time.sleep(0.3)
            if n % 50 == 0:
                print(f"{n}/{len(tickers)} {counts}", flush=True)
        monthly = rebuild_monthly()
        print(f"--update: {counts}; aylik satir {len(monthly)} ({monthly['ticker'].nunique()} hisse)")
        return
    for n, tk in enumerate(tickers, 1):
        path = DAILY / f"{tk}.parquet"
        if path.exists() and not args.refresh and not args.tickers:
            if not args.retry_empty:
                continue
            if len(pd.read_parquet(path)) > 0:
                continue
        try:
            df = fetch(tk)
        except RuntimeError as exc:
            failed.append(tk)
            print(exc, flush=True)
            continue
        fetched += 1
        if df.empty:
            empty.append(tk)
        df.to_parquet(path, index=False)
        time.sleep(0.6)
        if fetched % 25 == 0:
            print(f"cekilen {fetched} ({n}/{len(tickers)})", flush=True)
    monthly = rebuild_monthly()
    print(f"{len(tickers)} hisse (cekilen {fetched}), bos {len(empty)} {empty[:15]}, basarisiz {failed}; "
          f"aylik satir {len(monthly)} ({monthly['ticker'].nunique()} hisse)")


if __name__ == "__main__":
    main()
