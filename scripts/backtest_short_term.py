#!/usr/bin/env python3
"""Kisa vade secim kurali backtest'i (gunluk, 2013 -> bugun).

    python scripts/build_pit_panel.py      # ham gunluk seriler + aylik faktorler
    python scripts/backtest_short_term.py

Canli kural (run.py kisa vade blogu + core/scoring.py):
  - volume_ratio_20d = hacim_t / ort(hacim, son 20 gun, t dahil) >= 1.5
    (gun yonu KONTROL EDILMEZ)
  - sonra uzun vadeyle ayni deger-agirlikli final_score ile siralama
  - hedef = P + 2.5 ATR20, stop = (P - 0.5 ATR) - 1.5 ATR = P - 2 ATR, ufuk 20 gun
Test edilen gruplar (her gun, likiditenin en alt %30'u atilir):
  tum_likit (taban), hacim>=1.5, hacim>=1.5 & yukselis gunu, hacim>=1.5 & dusus
  gunu, hacim>=1.5 & deger ust ucte bir (canli siralamanin vekili: aylik PIT
  deger bileseni, sektor-notr).
Olculenler:
  - 20 gunluk fazla getiri: ayni gunun likit evren ortalamasina gore; gunluk grup
    ortalamalari serisi uzerinden Newey-West t (lag 20, ust uste binen pencereler).
  - Islem simulasyonu: giris t kapanisi, sonraki 20 gunde once dokunan hedef/stop
    (ayni gun ikisi -> stop, muhafazakar), yoksa 20. gun kapanisi; %0.5 gidis-donus.
Sinirlar: giris kapanista (canlida ertesi gun bant); yapisal tavan (swing tepesi,
Bollinger) yok; hayatta kalma yanliligi (bugunku liste); nominal TL.
Gecmis getiri gelecegi garanti etmez.
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import factor_backtest as fb  # noqa: E402

RAW = ROOT / "data" / "research" / "raw"
PANEL = ROOT / "data" / "research" / "factors_monthly.parquet"
H = 20
VR_MIN = 1.5
TARGET_ATR, STOP_ATR = 2.5, 2.0
COST = 0.005


def load_daily(tickers: list[str]) -> pd.DataFrame:
    out = []
    for t in tickers:
        p = RAW / f"{t}.pkl"
        if not p.exists():
            continue
        px = pickle.loads(p.read_bytes()).get("px_adj")
        if px is None or len(px) < 80:
            continue
        d = px[["Open", "High", "Low", "Close", "Volume"]].astype(float).copy()
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        d = d[~d.index.duplicated()]
        d["ticker"] = t
        out.append(d)
    return pd.concat(out).rename_axis("date").reset_index()


def add_signals(d: pd.DataFrame) -> pd.DataFrame:
    d = d.sort_values(["ticker", "date"]).copy()
    g = d.groupby("ticker", group_keys=False)
    d["vr"] = d["Volume"] / g["Volume"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    prev = g["Close"].shift(1)
    tr = np.maximum(d["High"] - d["Low"], np.maximum((d["High"] - prev).abs(), (d["Low"] - prev).abs()))
    d["atr20"] = tr.groupby(d["ticker"]).transform(lambda s: s.rolling(20, min_periods=20).mean())
    d["ret1"] = d["Close"] / prev - 1
    d["tlvol"] = (d["Close"] * d["Volume"]).groupby(d["ticker"]).transform(lambda s: s.rolling(60, min_periods=40).median())
    d["fwd20"] = g["Close"].shift(-H) / d["Close"] - 1
    return d


def simulate(d: pd.DataFrame) -> pd.Series:
    """ATR hedef/stop islem sonucu (net), her satir icin; veri yetmezse NaN."""
    res = np.full(len(d), np.nan)
    for _, idx in d.groupby("ticker").indices.items():
        c = d["Close"].values[idx]; hi = d["High"].values[idx]; lo = d["Low"].values[idx]
        atr = d["atr20"].values[idx]; take = d["_take"].values[idx]
        n = len(idx)
        for k in np.nonzero(take)[0]:
            if k + H >= n or not atr[k] > 0:
                continue
            entry = c[k]; tgt = entry + TARGET_ATR * atr[k]; stp = entry - STOP_ATR * atr[k]
            out = c[k + H] / entry - 1
            for j in range(k + 1, k + H + 1):
                if lo[j] <= stp:
                    out = stp / entry - 1
                    break
                if hi[j] >= tgt:
                    out = tgt / entry - 1
                    break
            res[idx[k]] = out - COST
    return pd.Series(res, index=d.index)


def value_scores() -> pd.DataFrame:
    raw = pd.read_parquet(PANEL)
    m = fb.prepare(raw, ["bm", "ep", "sp", "ey"], liq_drop_pct=0.0, min_names=10)
    m["value_z"] = m[["bm_z", "ep_z", "sp_z", "ey_z"]].mean(axis=1)
    m["value_sn"] = fb.sector_neutralize(m, "value_z")
    return m[["date", "ticker", "value_sn"]].dropna().sort_values("date")


def group_stats(d: pd.DataFrame, mask: pd.Series, split: pd.Timestamp) -> dict:
    sel = d[mask & d["excess20"].notna()]
    daily = sel.groupby("date")["excess20"].mean()
    m, t, n = fb.newey_west_t(daily, H)
    tr = sel["trade"].dropna()
    early = sel[(sel["date"] >= "2016-01-01") & (sel["date"] < split)]["excess20"]
    late = sel[sel["date"] >= split]["excess20"]
    return {"signals": int(len(sel)), "days": n, "excess20_pct": round(100 * m, 2), "t": round(t, 2),
            "trade_net_pct": round(100 * tr.mean(), 2) if len(tr) else None,
            "trade_win_pct": round(100 * (tr > 0).mean(), 1) if len(tr) else None,
            "excess20_2016_20": round(100 * early.mean(), 2) if len(early) else None,
            "excess20_2021_26": round(100 * late.mean(), 2) if len(late) else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liq-drop", type=float, default=0.3)
    ap.add_argument("--split", default="2021-01-01")
    args = ap.parse_args()
    split = pd.Timestamp(args.split)

    tickers = sorted(p.stem for p in RAW.glob("*.pkl"))
    d = add_signals(load_daily(tickers))
    d = d[d["date"] >= "2013-01-01"]
    d = d[d["tlvol"].notna() & d["fwd20"].notna() & d["vr"].notna()]
    cut = d.groupby("date")["tlvol"].transform(lambda s: s.quantile(args.liq_drop))
    d = d[d["tlvol"] >= cut].copy()
    d = d[d.groupby("date")["ticker"].transform("size") >= 30]
    d["excess20"] = d["fwd20"] - d.groupby("date")["fwd20"].transform("mean")

    v = value_scores().rename(columns={"date": "vdate"})
    v["vdate"] = v["vdate"].astype("datetime64[ns]")
    d["date"] = d["date"].astype("datetime64[ns]")
    d = pd.merge_asof(d.sort_values("date"), v.sort_values("vdate"),
                      left_on="date", right_on="vdate", by="ticker", direction="backward")
    # Deger skoru en fazla ~2 ay eski olabilir; daha eskiyse bos (satir ATILMAZ: taban evren degismesin).
    d.loc[(d["date"] - d["vdate"]).dt.days > 62, "value_sn"] = np.nan
    d = d.reset_index(drop=True)
    spike = d["vr"] >= VR_MIN
    d["_value_top"] = False
    sp = d[spike]
    top = sp.groupby("date")["value_sn"].transform(lambda s: s >= s.quantile(2 / 3))
    d.loc[top.index, "_value_top"] = top.fillna(False)

    groups = {
        "tum_likit (taban)": pd.Series(True, index=d.index),
        "hacim>=1.5 (canli kural)": spike,
        "hacim>=1.5 & yukselis gunu": spike & (d["ret1"] > 0),
        "hacim>=1.5 & dusus gunu": spike & (d["ret1"] < 0),
        "hacim>=1.5 & deger ust 1/3": spike & d["_value_top"],
    }
    # Islem simulasyonu taban icin cok sayida satir ister; taban orneklenir (her 5. gun).
    days = np.sort(d["date"].unique())
    sample_days = set(days[::5])
    d["_take"] = spike | d["date"].isin(sample_days)
    d["trade"] = simulate(d.sort_values(["ticker", "date"])).reindex(d.index)

    rows = [{"grup": name, **group_stats(d, mask, split)} for name, mask in groups.items()]
    res = pd.DataFrame(rows)
    print(f"Gunluk panel: {d['ticker'].nunique()} hisse, {d['date'].min().date()} .. {d['date'].max().date()}, "
          f"gunluk medyan {int(d.groupby('date').size().median())} likit hisse\n")
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(res.to_string(index=False))
    print(f"\nIslem: hedef +{TARGET_ATR} ATR, stop -{STOP_ATR} ATR, {H} gun, maliyet %{100 * COST} gidis-donus; "
          "taban islem sutunu her 5. gunun orneklemi.")

    out = ROOT / "data" / "reports" / f"backtest_short_term_{date.today().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"vr_min": VR_MIN, "horizon": H, "target_atr": TARGET_ATR, "stop_atr": STOP_ATR,
                               "cost": COST, "groups": rows}, ensure_ascii=False, indent=2,
                              default=lambda x: None if isinstance(x, float) and math.isnan(x) else str(x)),
                   encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
