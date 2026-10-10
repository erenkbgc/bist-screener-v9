#!/usr/bin/env python3
"""Gunluk USDTRY ve XU100 kapanisini data/research/fx.parquet'e yazar (git'e girmez).

    python scripts/build_fx_panel.py

Kaynak borsapy (bp.FX("USD"), bp.Index("XU100")). Faktor paneline USD ve
XU100'e gore fazla getiri kolonlari eklemek icin kullanilir
(core/pit_panel.py::add_usd_returns, backtest_factor_model.py --currency).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "research" / "fx.parquet"
START = "2011-01-01"


def _close(df: pd.DataFrame, name: str) -> pd.Series:
    s = df["Close"].astype(float)
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")].rename(name)


def main() -> None:
    import borsapy as bp

    fx = _close(bp.FX("USD").history(start=START), "usdtry")
    xu = _close(bp.Index("XU100").history(start=START), "xu100")
    # Kur hafta sonu da kote edilir; borsa gunlerine hizala, son bilinen kuru kullan.
    df = pd.concat([fx, xu], axis=1, sort=True)
    df["usdtry"] = df["usdtry"].ffill()
    df = df.dropna(subset=["xu100"]).reset_index(names="date")
    if df.empty:
        sys.exit("Kur/endeks verisi bos geldi.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"{len(df)} gun, {df['date'].min().date()} .. {df['date'].max().date()} -> {OUT}")


if __name__ == "__main__":
    main()
