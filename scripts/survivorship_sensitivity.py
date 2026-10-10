#!/usr/bin/env python3
"""Hayatta kalma yanliligi duyarlilik analizi (level-up plani Faz 1).

Panel BUGUNKU listedeki hisselerden kurulu; borsadan cikmis hisselerin fiyat
gecmisi borsapy'de yok (TradingView "invalid symbol"). core/data_quality.py
icindeki 14 hisselik liste elle girilmis ve dogrulanmamis; test icin
kullanilmaz. Bu yuzden Shumway (1997) yaklasimi: eksik hisseleri "hayalet"
olarak modele ekleyip faktor kanitinin hangi cikis oraninda kayboldugunu olcer.

Model (aylik, esit agirlik):
  Gozlenen ust dilim getirisi r_top, evren r_uni. Yillik cikis orani h (evren),
  ust dilimde k*h (deger/sikinti hisseleri daha sik cikar). Cikan hisse o ay
  R getirisi verir (Shumway: performans kaynakli cikis ~ -30%; iflas -100%).
    top' = (1 - k*h/12) * r_top + (k*h/12) * R
    uni' = (1 - h/12) * r_uni + (h/12) * R
    aktif' = top' - uni' - devir maliyeti
  Rapor: her (sinyal, R, k) icin aktif getirinin NW t'si 3'un ve 0'in altina
  dustugu en kucuk yillik h (basabas orani).

Ayrica "cokmus" alt grup (ust dilim ve 5 yillik zirveden %70+ dusus) icin ayni
hesap, daha yuksek yogunlasma (k) ile.

    python scripts/survivorship_sensitivity.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from diagnose_crashed_picks import CRASH_PCT, drawdown_from_peak, month_end  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SIGNALS = ["value_z", "value_sn_z", "vol60_z", "sue_z", "model_proxy_z"]
DELIST_RETURNS = [-0.30, -1.00]
CONCENTRATION = [1.0, 2.0, 3.0]
CRASH_CONCENTRATION = [3.0, 5.0, 10.0]
H_GRID = np.round(np.arange(0.0, 0.4001, 0.0025), 4)  # yillik 0..40%
COST_BPS = 20.0
HLZ_T = 3.0


def active_series(q: pd.DataFrame, h: float, k: float, R: float) -> pd.Series:
    hm = h / 12.0
    top = (1 - min(k * hm, 1.0)) * q["top"] + min(k * hm, 1.0) * R
    uni = (1 - hm) * q["universe"] + hm * R
    return top - uni - 2 * q["turnover"] * COST_BPS / 1e4


def stats(series: pd.Series) -> tuple[float, float]:
    m, t, _ = fb.newey_west_t(series, 1)
    return 100 * 12 * m, t


def breakeven(q: pd.DataFrame, k: float, R: float) -> dict:
    base_m, base_t = stats(active_series(q, 0.0, k, R))
    out = {"active_net_ann_pct_h0": round(base_m, 2), "t_h0": round(base_t, 2),
           "h_t_below_3_pct": None, "h_t_below_2_pct": None, "h_mean_below_0_pct": None}
    for h in H_GRID:
        m, t = stats(active_series(q, h, k, R))
        if out["h_t_below_3_pct"] is None and t < HLZ_T:
            out["h_t_below_3_pct"] = round(100 * h, 2)
        if out["h_t_below_2_pct"] is None and t < 2.0:
            out["h_t_below_2_pct"] = round(100 * h, 2)
        if out["h_mean_below_0_pct"] is None and m < 0:
            out["h_mean_below_0_pct"] = round(100 * h, 2)
            break
    return out


def crashed_top_series(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Ust dilim ICINDEKI cokmus hisseler vs evren; devir maliyeti icin ust dilim devri kullanilmaz (0)."""
    rows = []
    for dt, g in df[["date", "ticker", col, "fwd_ret_1m", "crashed"]].dropna(subset=[col, "fwd_ret_1m"]).groupby("date"):
        if len(g) < 30:
            continue
        cut = g[col].quantile(0.8)
        sub = g[(g[col] >= cut) & (g["crashed"] == True)]  # noqa: E712
        if sub.empty:
            continue
        rows.append({"date": dt, "top": sub["fwd_ret_1m"].mean(), "universe": g["fwd_ret_1m"].mean(),
                     "turnover": 0.0, "n": len(sub)})
    return pd.DataFrame(rows)


def main() -> None:
    raw = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    raw["date"] = month_end(raw["date"])
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    prices = pd.read_parquet(RESEARCH / "monthly_prices.parquet")
    prices["date"] = month_end(prices["date"])
    df = df.merge(drawdown_from_peak(prices), on=["date", "ticker"], how="left")
    df["crashed"] = df["dd_5y_pct"] <= CRASH_PCT

    result = {"as_of": date.today().isoformat(), "cost_bps": COST_BPS, "hlz_t": HLZ_T,
              "data_start": str(df["date"].min().date()), "data_end": str(df["date"].max().date()),
              "signals": {}, "crashed_top_quintile": {}}
    for col in SIGNALS:
        q = fb.quintile_spread(df, col, "fwd_ret_1m")
        result["signals"][col.removesuffix("_z")] = {
            f"R{int(100 * R)}_k{k:g}": breakeven(q, k, R) for R in DELIST_RETURNS for k in CONCENTRATION
        }
    for col in ("value_z", "model_proxy_z"):
        q = crashed_top_series(df, col)
        entry = {"months": int(len(q)), "mean_names": round(float(q["n"].mean()), 1) if len(q) else 0}
        for R in DELIST_RETURNS:
            for k in CRASH_CONCENTRATION:
                entry[f"R{int(100 * R)}_k{k:g}"] = breakeven(q, k, R)
        result["crashed_top_quintile"][col.removesuffix("_z")] = entry

    result["notes"] = [
        "h = annual delisting hazard of the whole universe; top quintile hazard = k*h.",
        "Shumway (1997): performance delistings average about -30%; -100% is a full-loss bound.",
        "No verified BIST delisting statistics are in the repo; compare break-even h with an external count before relying on it.",
        "1-month forward returns; Newey-West t with 1 lag; equal weight; 20 bps one-way cost on top-quintile turnover.",
    ]
    out = ROOT / "data" / "reports" / f"survivorship_sensitivity_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"Panel {result['data_start']} .. {result['data_end']}")
    print("Basabas yillik evren cikis orani h (%): t<3 / t<2 / ortalama<0")
    for name, grid in list(result["signals"].items()) + list(result["crashed_top_quintile"].items()):
        for key, v in grid.items():
            if not isinstance(v, dict):
                continue
            print(f"  {name:12s} {key:10s} h0: {v['active_net_ann_pct_h0']:6.2f}%/yil t={v['t_h0']:5.2f} | "
                  f"{v['h_t_below_3_pct']} / {v['h_t_below_2_pct']} / {v['h_mean_below_0_pct']}")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
