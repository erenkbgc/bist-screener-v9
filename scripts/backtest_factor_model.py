#!/usr/bin/env python3
"""Kesitsel faktor backtest'i (roadmap Adim 3).

    python scripts/build_pit_panel.py          # once panel (data/research/)
    python scripts/backtest_factor_model.py
    python scripts/backtest_factor_model.py --liq-drop 0.5 --cost-bps 30

Olculenler (aylik dengeleme, ay sonu kapanisi):
  - Rank-IC: faktor vs 1 ve 6 aylik ileri getiri; Newey-West t, ICIR (ort/std).
  - Fama-MacBeth: tek degiskenli ve cok degiskenli aylik kesitsel OLS.
  - Quintile: ust-alt yayilimi ve uygulanabilir tarafi -- ust dilim eksi evren
    ortalamasi, devir basina --cost-bps ile net (BIST'te aciga satis kisitli).
  - Mevcut skor vekili: weights.yaml'daki valuation/momentum/low_vol agirliklari
    (catalyst ve ownership icin gecmis veri yok, agirliklari yeniden olceklenir).
  - Alt donemler: --split oncesi/sonrasi (varsayilan 2016-2020 / 2021-2026).
Coklu test: esik Harvey-Liu-Zhu (2016) |t| > 3; Bonferroni esigi de raporlanir.
Sinirlar:
  - Hayatta kalma yanliligi: evren BUGUNKU fintables listesi; borsadan cikmis
    hisseler yok. Getiriler yukari yanli olabilir (IC'ye etkisi daha sinirli).
  - Sinyal ve islem ayni ay sonu kapanisinda; str_1m icin bid-ask sicramasi
    donus primini sisirebilir.
  - Nominal TL getiri; kesitsel olcumler enflasyondan buyuk olcude bagimsizdir,
    mutlak getiri seviyeleri degildir.
Gecmis getiri gelecegi garanti etmez.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path
from statistics import NormalDist

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402

PANEL = ROOT / "data" / "research" / "factors_monthly.parquet"
FX = ROOT / "data" / "research" / "fx.parquet"
FACTORS = list(fb.SIGNS)
VALUE = ["bm", "ep", "sp", "ey"]
# Cok degiskenli FM: birbiriyle en az ortusen temsilciler.
FM_MULTI = ["size", "bm", "ep", "gpa", "mom_12_1", "str_1m", "vol60", "nsi_rights_12m", "sue"]
HLZ_T = 3.0


def add_composites(df: pd.DataFrame) -> pd.DataFrame:
    w = yaml.safe_load((ROOT / "config" / "weights.yaml").read_text(encoding="utf-8"))["scoring_weights"]
    df = df.copy()
    df["value_z"] = df[[f + "_z" for f in VALUE]].mean(axis=1)
    # Canli valuation_z sektor-notr; ham bilesenle ayni kanitin tasinip tasinmadigini gosterir.
    df["value_sn_z"] = fb.sector_neutralize(df, "value_z")
    parts = {"value_z": w["valuation_z"], "mom_12_1_z": w["momentum_z"], "vol60_z": w["low_vol_z"]}
    tot = sum(parts.values())
    df["model_proxy_z"] = sum(df[c].fillna(0) * v / tot for c, v in parts.items())
    df.loc[df[list(parts)].isna().all(axis=1), "model_proxy_z"] = float("nan")
    return df


def period_mask(df: pd.DataFrame, which: str, split: pd.Timestamp) -> pd.Series:
    if which == "early":
        return (df["date"] >= pd.Timestamp("2016-01-01")) & (df["date"] < split)
    if which == "late":
        return df["date"] >= split
    return pd.Series(True, index=df.index)


def ic_stats(df: pd.DataFrame, col: str, ret: str, lags: int) -> dict:
    ic = fb.rank_ic(df, col, ret)
    m, t, n = fb.newey_west_t(ic, lags)
    # ICIR: IC ortalamasi / IC std (aylik, yilliklastirilmamis); ~0.5 ustu istikrarli kabul edilir
    icir = m / ic.std() if ic.std() > 0 else float("nan")
    return {"ic_mean": round(m, 4), "ic_t": round(t, 2), "icir": round(icir, 3),
            "ic_hit_pct": round(100 * (ic > 0).mean(), 1), "months": n}


def spread_stats(df: pd.DataFrame, col: str, cost_bps: float) -> dict:
    q = fb.quintile_spread(df, col, "fwd_ret_1m")
    if q.empty:
        return {}
    ls_m, ls_t, _ = fb.newey_west_t(q["spread"], 1)
    active = q["top"] - q["universe"] - 2 * q["turnover"] * cost_bps / 1e4
    a_m, a_t, _ = fb.newey_west_t(active, 1)
    return {"ls_ann_pct": round(100 * 12 * ls_m, 2), "ls_t": round(ls_t, 2),
            "top_active_net_ann_pct": round(100 * 12 * a_m, 2), "top_active_net_t": round(a_t, 2),
            "top_turnover_pct": round(100 * q["turnover"].mean(), 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liq-drop", type=float, default=0.3, help="Her ay atilan en az likit dilim")
    ap.add_argument("--cost-bps", type=float, default=20.0)
    ap.add_argument("--split", default="2021-01-01")
    ap.add_argument("--currency", choices=("tl", "usd", "xs"), default="tl",
                    help="Ileri getiri birimi: nominal TL, USD ya da XU100'e gore fazla getiri "
                         "(usd/xs icin once scripts/build_fx_panel.py)")
    args = ap.parse_args()

    if not PANEL.exists():
        sys.exit(f"{PANEL} yok; once scripts/build_pit_panel.py calistirin.")
    raw = pd.read_parquet(PANEL)
    if args.currency != "tl":
        if not FX.exists():
            sys.exit(f"{FX} yok; once scripts/build_fx_panel.py calistirin.")
        raw = pit_panel.add_usd_returns(raw, pit_panel.monthly_market(pd.read_parquet(FX)))
        for h in ("1m", "6m"):
            raw[f"fwd_ret_{h}"] = raw[f"fwd_ret_{h}_{args.currency}"]
    prepared = fb.prepare(raw, FACTORS, liq_drop_pct=args.liq_drop)
    if prepared.empty:
        sys.exit(f"Hicbir ay filtre sonrasi >=30 hisse icermiyor ({raw['ticker'].nunique()} hisse); "
                 "tam evren paneli gerekli.")
    df = add_composites(prepared)
    split = pd.Timestamp(args.split)
    per_month = df.groupby("date").size()
    print(f"Panel: {raw['ticker'].nunique()} hisse, {df['date'].min().date()} .. {df['date'].max().date()}, "
          f"{len(per_month)} ay, aylik evren medyan {int(per_month.median())} hisse "
          f"(likidite alt %{int(100 * args.liq_drop)} atildi)\n")

    signals = [f + "_z" for f in FACTORS] + ["value_z", "value_sn_z", "model_proxy_z"]
    rows = []
    for col in signals:
        r = {"signal": col.removesuffix("_z")}
        for which in ("full", "early", "late"):
            sub = df[period_mask(df, which, split)]
            ic1 = ic_stats(sub, col, "fwd_ret_1m", lags=1)
            pre = "" if which == "full" else which + "_"
            r[pre + "ic1"] = ic1["ic_mean"]
            r[pre + "ic1_t"] = ic1["ic_t"]
            if which == "full":
                r["months"] = ic1["months"]
                r["ic1_hit_pct"] = ic1["ic_hit_pct"]
                r["icir1"] = ic1["icir"]
                ic6 = ic_stats(sub, col, "fwd_ret_6m", lags=6)
                r["ic6"], r["ic6_t"] = ic6["ic_mean"], ic6["ic_t"]
                fm = fb.fama_macbeth(sub, [col], "fwd_ret_1m")
                m, t, _ = fb.newey_west_t(fm[col], 1) if not fm.empty else (float("nan"),) * 3
                r["fm_uni_bps"], r["fm_uni_t"] = round(1e4 * m, 1), round(t, 2)
                r.update(spread_stats(sub, col, args.cost_bps))
        rows.append(r)
    res = pd.DataFrame(rows)

    fm = fb.fama_macbeth(df, [f + "_z" for f in FM_MULTI], "fwd_ret_1m")
    multi = []
    for f in FM_MULTI:
        m, t, n = fb.newey_west_t(fm[f + "_z"], 1)
        multi.append({"factor": f, "slope_bps": round(1e4 * m, 1), "t": round(t, 2), "months": n})
    multi = pd.DataFrame(multi)

    n_tests = len(signals) * 2  # iki ufuk
    bonf_t = NormalDist().inv_cdf(1 - 0.05 / (2 * n_tests))
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print("Rank-IC / FM / quintile (tam donem; early=2016..split, late=split..):")
        print(res[["signal", "months", "ic1", "ic1_t", "icir1", "ic1_hit_pct", "ic6", "ic6_t", "fm_uni_bps", "fm_uni_t",
                   "ls_ann_pct", "ls_t", "top_active_net_ann_pct", "top_active_net_t", "top_turnover_pct",
                   "early_ic1", "early_ic1_t", "late_ic1", "late_ic1_t"]].to_string(index=False))
        print("\nCok degiskenli Fama-MacBeth (1 aylik getiri, egim = 1 std faktor basina aylik bps):")
        print(multi.to_string(index=False))

    def passes(r) -> bool:
        return abs(r.ic1_t) > HLZ_T and (r.early_ic1_t * r.late_ic1_t > 0)
    sig = [r.signal for r in res.itertuples() if passes(r)]
    print(f"\nEsik: HLZ |t|>{HLZ_T} (Bonferroni {n_tests} test icin ~{bonf_t:.2f}) VE iki alt donemde ayni isaret.")
    print("Gecen sinyaller: " + (", ".join(sig) or "yok"))

    suffix = "" if args.currency == "tl" else f"_{args.currency}"
    out = ROOT / "data" / "reports" / f"backtest_factor_model{suffix}_{date.today().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "liq_drop": args.liq_drop, "cost_bps": args.cost_bps, "split": args.split, "currency": args.currency,
        "hlz_t": HLZ_T, "bonferroni_t": bonf_t, "n_tickers": int(raw["ticker"].nunique()),
        "data_start": str(df["date"].min().date()), "data_end": str(df["date"].max().date()),
        "signals": res.to_dict("records"), "fama_macbeth_multi": multi.to_dict("records"),
        "passing": sig,
    }, ensure_ascii=False, indent=2, default=lambda x: None if isinstance(x, float) and math.isnan(x) else str(x)),
        encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
