#!/usr/bin/env python3
"""Arastirma makro ve piyasa serilerini son tarihe gunceller (data/research/, git'e girmez).

Guncellenen dosyalar:
  - macro_monthly.parquet       (yfinance global/BIST + TUIK TUFE + TCMB politika faizi)
  - ipi_tsanay2021.parquet      (EVDS TP.TSANAY2021.BCD, EVDS_API_KEY gerektirir)
  - eurobond_monthly.parquet    (Ziraat USD Eurobond ay sonu getirileri)
  - ust_daily.parquet           (yfinance ^FVX, ^TNX, ^TYX)
  - eem_daily.parquet           (yfinance EEM gunluk duzeltilmis kapanis)
  - fx.parquet                  (borsapy USDTRY ve XU100 gunluk)
  - tr_indices.parquet          (borsapy XU100_CFNNTLTL ve XUTUM_CFNNTLTL)
  - xu100_usdtry_yf_daily.parquet (yfinance XU100.IS ve USDTRY=X gunluk)

    python scripts/refresh_macro_data.py
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

IPI_SERIES = "TP.TSANAY2021.BCD"
EVDS3_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis/series={series}&startDate={start}&endDate={end}&type=json"


def refresh_macro_monthly() -> pd.DataFrame:
    import research_macro_drivers as md

    df = md.download()
    out = RESEARCH / "macro_monthly.parquet"
    df.to_parquet(out)
    print(f"[macro_monthly] {len(df)} satir, {df.index.min().date()} .. {df.index.max().date()}, "
          f"cpi_mom son={df['cpi_mom'].dropna().index.max().date()}, "
          f"policy_last={df['policy_last_decision'].iloc[-1]}")
    return df


def refresh_evds_ipi() -> pd.DataFrame | None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    key = os.environ.get("EVDS_API_KEY", "").strip()
    if not key:
        print("[evds_ipi] UYARI: EVDS_API_KEY tanimli degil, atlandi.")
        return None
    end_str = date.today().strftime("%d-%m-%Y")
    url = EVDS3_URL.format(series=IPI_SERIES, start="01-01-2004", end=end_str)
    r = requests.get(url, headers={"key": key}, timeout=30)
    r.raise_for_status()
    items = r.json().get("items") or []
    col = IPI_SERIES.replace(".", "_")
    rows = []
    for it in items:
        t = it.get("Tarih")
        v = it.get(col)
        if t and v is not None:
            dt = pd.to_datetime(t, format="%Y-%m")
            rows.append((dt, float(v)))
    df = pd.DataFrame(rows, columns=["Date", "Value"]).set_index("Date").sort_index()
    out = RESEARCH / "ipi_tsanay2021.parquet"
    df.to_parquet(out)
    print(f"[evds_ipi] {len(df)} ay, {df.index.min().date()} .. {df.index.max().date()}, "
          f"son={df['Value'].iloc[-1]:.2f}")
    return df


def refresh_eem_and_yf_fx() -> None:
    import yfinance as yf

    d = yf.download("EEM", start="2004-01-01", auto_adjust=True, progress=False)
    s = d["Close"].squeeze().dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    s.index.name = "Date"
    out_eem = RESEARCH / "eem_daily.parquet"
    s.rename("eem").to_frame().to_parquet(out_eem)
    print(f"[eem_daily] {len(s)} gun, {s.index.min().date()} .. {s.index.max().date()}")

    fx_yf = yf.download(["USDTRY=X", "XU100.IS"], start="2005-01-01", auto_adjust=False, progress=False)["Close"]
    fx_yf.index = pd.to_datetime(fx_yf.index).tz_localize(None).normalize()
    fx_yf.index.name = "Date"
    out_yf = RESEARCH / "xu100_usdtry_yf_daily.parquet"
    fx_yf.to_parquet(out_yf)
    print(f"[xu100_usdtry_yf_daily] {len(fx_yf)} gun, {fx_yf.index.min().date()} .. {fx_yf.index.max().date()}")


def main() -> None:
    import build_fx_panel
    import fetch_eurobond_monthly
    import research_total_return_benchmarks as trb

    RESEARCH.mkdir(parents=True, exist_ok=True)
    refresh_macro_monthly()
    refresh_evds_ipi()
    fetch_eurobond_monthly.main()
    refresh_eem_and_yf_fx()
    build_fx_panel.main()
    tr = trb.tr_indices(refresh=True)
    print(f"[tr_indices] {len(tr)} gun, {tr.index.min().date()} .. {tr.index.max().date()}")


if __name__ == "__main__":
    main()
