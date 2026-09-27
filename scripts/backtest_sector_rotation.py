#!/usr/bin/env python3
"""BIST sektor rotasyonu backtest'i (sektor endeksleri, 2012 -> bugun).

    python scripts/backtest_sector_rotation.py            # aylik + ceyreklik
    python scripts/backtest_sector_rotation.py --cost-bps 30

Tasarim (ileriye bakis yok):
  - Haftalik (Cuma) kapanis. Sinyal t haftasi kapanisina kadar olan veriyle
    uretilir, getiri t -> bir sonraki dengeleme tarihinden alinir.
  - RRG serisi yalnizca gecmise bakan rolling pencerelerle hesaplanir
    (core/sector_rotation.py::rrg_series).
  - Maliyet: tek yon devir basina --cost-bps (varsayilan 20 bps).
Sinirlar:
  - Fiyat endeksi (temettu haric): yuksek temettulu sektorler (banka) aleyhine.
  - Endeksler dogrudan alinamaz; her sektor icin BYF yok -> uygulanabilirlik
    hisse sepetiyle replikasyona baglidir (ek maliyet/izleme hatasi).
  - Coklu test: N strateji x 2 frekans denendi; t-istatistigi Bonferroni
    esigiyle birlikte raporlanir. Gecmis getiri gelecegi garanti etmez.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.sector_rotation import (  # noqa: E402
    FRESH_WEEKS, SECTOR_INDEX_MAP, _weekly, quadrant, rrg_series,
)

BENCH = "XU100"
TOP_K = 3
WEEKS_PER_YEAR = 52


def load_weekly(codes: list[str]) -> pd.DataFrame:
    import borsapy as bp
    cols = {}
    for code in codes + [BENCH]:
        try:
            h = bp.Index(code).history(period="max")
        except Exception as exc:
            print(f"[{code}] alinamadi: {exc}", file=sys.stderr)
            continue
        s = h["Close"].astype(float)
        s.index = pd.to_datetime(s.index).tz_localize(None)
        cols[code] = _weekly(s)
    return pd.DataFrame(cols).dropna(how="all")


def rrg_panels(px: pd.DataFrame, codes: list[str]) -> dict[str, pd.DataFrame]:
    return {c: rrg_series(px[c].dropna(), px[BENCH].dropna()) for c in codes}


def rebalance_dates(idx: pd.DatetimeIndex, freq: str) -> list[pd.Timestamp]:
    s = pd.Series(idx, index=idx)
    key = idx.to_period("M" if freq == "monthly" else "Q")
    return list(s.groupby(key).last())


def _ret(px: pd.DataFrame, t: pd.Timestamp, weeks: int, skip: int = 0) -> pd.Series:
    i = px.index.get_loc(t)
    if i - weeks < 0:
        return pd.Series(dtype=float)
    end = px.iloc[i - skip]
    start = px.iloc[i - weeks]
    return (end / start - 1).dropna()


def select(strategy: str, t: pd.Timestamp, px: pd.DataFrame, codes: list[str],
           rrg: dict[str, pd.DataFrame]) -> list[str]:
    sub = px[codes]
    if strategy == "MOM_12_1":
        r = _ret(sub, t, 52, skip=4)
        return list(r.nlargest(TOP_K).index)
    if strategy == "MOM_6M":
        r = _ret(sub, t, 26)
        return list(r.nlargest(TOP_K).index)
    if strategy == "MEDIAN_13W":
        r = _ret(sub, t, 13).sort_values()
        if len(r) < TOP_K:
            return []
        mid = len(r) // 2
        lo = max(0, mid - TOP_K // 2)
        return list(r.index[lo:lo + TOP_K])
    if strategy == "REVERSAL_13W":
        r = _ret(sub, t, 13)
        return list(r.nsmallest(TOP_K).index)
    if strategy.startswith("RRG_"):
        picks = []
        for c in codes:
            s = rrg[c]
            s = s[s.index <= t]
            if len(s) < FRESH_WEEKS + 2:
                continue
            quads = [quadrant(a, b) for a, b in zip(s["r"].iloc[-(FRESH_WEEKS + 2):], s["m"].iloc[-(FRESH_WEEKS + 2):])]
            cur = quads[-1]
            if strategy == "RRG_IMPROVING" and cur == "Improving":
                picks.append(c)
            elif strategy == "RRG_LEADING" and cur == "Leading":
                picks.append(c)
            elif strategy == "RRG_FUTURE_STAR" and cur == "Improving" and "Lagging" in quads[:-1]:
                picks.append(c)
        return picks
    if strategy == "EW_SECTORS":
        return [c for c in codes if not math.isnan(px.at[t, c])]
    raise ValueError(strategy)


def run_strategy(strategy: str, px: pd.DataFrame, codes: list[str], rrg: dict, freq: str,
                 start: pd.Timestamp, cost_bps: float) -> pd.DataFrame:
    dates = [d for d in rebalance_dates(px.index, freq) if d >= start]
    rows = []
    prev_w: dict[str, float] = {}
    for t0, t1 in zip(dates[:-1], dates[1:]):
        picks = select(strategy, t0, px, codes, rrg)
        # Bos secimde (orn. hic Improving sektor yok) XU100'de kalinir.
        w = {c: 1.0 / len(picks) for c in picks} if picks else {BENCH: 1.0}
        period = (px.loc[t1] / px.loc[t0] - 1)
        gross = sum(wt * period.get(c, 0.0) for c, wt in w.items() if not math.isnan(period.get(c, np.nan)))
        turnover = sum(abs(w.get(c, 0) - prev_w.get(c, 0)) for c in set(w) | set(prev_w)) / 2
        net = gross - 2 * turnover * cost_bps / 1e4  # al + sat
        rows.append({"start": t0, "end": t1, "ret": net, "bench": period[BENCH],
                     "turnover": turnover, "n_holdings": len(w), "holdings": ",".join(sorted(w))})
        prev_w = w
    return pd.DataFrame(rows)


def metrics(df: pd.DataFrame, periods_per_year: float) -> dict:
    if df.empty:
        return {}
    eq = (1 + df["ret"]).cumprod()
    beq = (1 + df["bench"]).cumprod()
    years = len(df) / periods_per_year
    cagr = eq.iloc[-1] ** (1 / years) - 1
    bcagr = beq.iloc[-1] ** (1 / years) - 1
    active = df["ret"] - df["bench"]
    ir = active.mean() / active.std() * math.sqrt(periods_per_year) if active.std() > 0 else float("nan")
    t_stat = active.mean() / (active.std() / math.sqrt(len(active))) if active.std() > 0 else float("nan")
    dd = (eq / eq.cummax() - 1).min()
    return {
        "periods": len(df), "cagr_pct": round(100 * cagr, 2), "xu100_cagr_pct": round(100 * bcagr, 2),
        "active_cagr_pct": round(100 * (cagr - bcagr), 2),
        "vol_pct": round(100 * df["ret"].std() * math.sqrt(periods_per_year), 2),
        "max_dd_pct": round(100 * dd, 2), "info_ratio": round(ir, 3), "t_stat_active": round(t_stat, 2),
        "hit_rate_pct": round(100 * (active > 0).mean(), 1),
        "avg_turnover_pct": round(100 * df["turnover"].mean(), 1),
        "avg_holdings": round(df["n_holdings"].mean(), 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cost-bps", type=float, default=20.0)
    ap.add_argument("--split", default="2020-01-01", help="Alt donem ayrim tarihi")
    args = ap.parse_args()

    codes = sorted(set(SECTOR_INDEX_MAP.values()))
    px = load_weekly(codes)
    codes = [c for c in codes if c in px.columns]
    rrg = rrg_panels(px, codes)
    start = px.index[0] + pd.Timedelta(weeks=60)  # 52h lookback + RRG isinmasi
    print(f"Veri: {len(codes)} sektor, {px.index[0].date()} .. {px.index[-1].date()}, "
          f"backtest baslangici {start.date()}, maliyet {args.cost_bps} bps/yon\n")

    strategies = ["EW_SECTORS", "MOM_12_1", "MOM_6M", "MEDIAN_13W", "REVERSAL_13W",
                  "RRG_IMPROVING", "RRG_LEADING", "RRG_FUTURE_STAR"]
    n_tests = (len(strategies) - 1) * 2
    from statistics import NormalDist
    bonf_t = NormalDist().inv_cdf(1 - 0.05 / (2 * n_tests))
    results = []
    for freq, ppy in (("monthly", 12), ("quarterly", 4)):
        ew = run_strategy("EW_SECTORS", px, codes, rrg, freq, start, args.cost_bps).set_index("end")["ret"]
        for st in strategies:
            df = run_strategy(st, px, codes, rrg, freq, start, args.cost_bps)
            full = metrics(df, ppy)
            # Asil kiyas: esit agirlikli sektor sepeti (XU100 banka agirlikli
            # oldugu icin EW bile XU100'u yenebiliyor; secim becerisi EW'ye gore olculur).
            act_ew = df.set_index("end")["ret"] - ew
            if st != "EW_SECTORS" and act_ew.std() > 0:
                full["active_vs_ew_ann_pct"] = round(100 * act_ew.mean() * ppy, 2)
                full["t_stat_vs_ew"] = round(act_ew.mean() / (act_ew.std() / math.sqrt(len(act_ew))), 2)
            split = pd.Timestamp(args.split)
            early = metrics(df[df["end"] < split], ppy)
            late = metrics(df[df["start"] >= split], ppy)
            results.append({"strategy": st, "freq": freq, **full,
                            "active_cagr_early_pct": early.get("active_cagr_pct"),
                            "active_cagr_late_pct": late.get("active_cagr_pct"),
                            "last_holdings": df["holdings"].iloc[-1] if not df.empty else None})

    res = pd.DataFrame(results)
    cols = ["strategy", "freq", "cagr_pct", "active_cagr_pct", "t_stat_active",
            "active_vs_ew_ann_pct", "t_stat_vs_ew", "max_dd_pct", "avg_turnover_pct",
            "active_cagr_early_pct", "active_cagr_late_pct"]
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(res[cols].to_string(index=False))
    print(f"\nCoklu test: {n_tests} strateji-frekans kombinasyonu; Bonferroni |t| esigi ~{bonf_t:.2f} (alfa=0.05).")
    sig = res[(res["strategy"] != "EW_SECTORS") & (res["t_stat_vs_ew"].abs() >= bonf_t)]
    print("EW'ye gore esigi gecen: " + (", ".join(f"{r.strategy}/{r.freq} (t={r.t_stat_vs_ew})" for r in sig.itertuples()) or "yok"))

    out = ROOT / "data" / "reports" / f"backtest_sector_rotation_{date.today().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"cost_bps": args.cost_bps, "bonferroni_t": bonf_t,
                               "data_start": str(px.index[0].date()), "data_end": str(px.index[-1].date()),
                               "results": results}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
