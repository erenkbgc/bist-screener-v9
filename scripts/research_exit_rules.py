#!/usr/bin/env python3
"""On-kayitli rotasyon ve cikis kurallari testi (docs/research/exit_rules_preregistration.md).

    python scripts/build_fx_panel.py
    python scripts/research_long_term.py     # quarterly_ext.parquet onbellegi
    python scripts/research_exit_rules.py
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

from core import exit_rules as xr  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from research_entry_timing import load_daily  # noqa: E402
from research_long_term import load  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
HLZ_T, HOLDOUT_T = 3.0, 2.0
CONFIRMATORY = ["R1", "R2", "X1", "X2", "X3", "X4"]


def build_inputs():
    df = load()  # value_sn_z, ep, f7, fwd_ret_1m(_usd) -- long_term on-kaydi ile ayni evren
    df = df[df["value_sn_z"].notna()].copy()
    df["rank_pct"] = df.groupby("date")["value_sn_z"].rank(ascending=False, pct=True)
    fxm = pd.read_parquet(RESEARCH / "fx.parquet")
    fxm["date"] = pd.to_datetime(fxm["date"]).dt.normalize()
    xu = fxm.set_index("date")["xu100"]
    usd_m = fxm.set_index("date")["usdtry"].resample("ME").last()
    fx_ret = (usd_m.shift(-1) / usd_m - 1)

    months = sorted(df["date"].unique())
    universe, d0_of = {}, {}
    for t in months:
        g = df[df["date"] == t].set_index("ticker")
        g["bench"] = g["fwd_ret_1m"].mean()
        g["bench_usd"] = g["fwd_ret_1m_usd"].mean()
        g["fx_ret"] = fx_ret.get(t, np.nan)
        universe[t] = g
        d0_of[t] = xu.index[xu.index.searchsorted(t, side="right") - 1]

    tickers = sorted(df.loc[df["rank_pct"] <= 0.6, "ticker"].unique())
    closes, atrs = {}, {}
    for tk in tickers:
        px = load_daily(tk)
        if px is None:
            continue
        closes[tk] = px["Close"]
        atrs[tk] = px["atr20"]
    close = pd.DataFrame(closes).reindex(xu.index)
    atr = pd.DataFrame(atrs).reindex(xu.index)
    # bench/fx olmayan son ay(lar) simulasyondan cikar
    months = [t for t in months if np.isfinite(universe[t]["bench"].iloc[0])
              and np.isfinite(universe[t]["fx_ret"].iloc[0])]
    return months, universe, close, atr, xu, d0_of


def stats(p: pd.DataFrame) -> dict:
    if p.empty:
        return {"months": 0}
    m, t, n = fb.newey_west_t(p["active"], 6)
    mu, tu, _ = fb.newey_west_t(p["active_usd"], 6)
    cum = (1 + p["total_usd"]).cumprod()
    return {"months": n, "active_ann_pct": round(1200 * m, 2), "t": round(t, 2),
            "active_usd_ann_pct": round(1200 * mu, 2), "t_usd": round(tu, 2),
            "turnover_pct": round(100 * p["turnover"].mean(), 1),
            "stops_per_year": round(12 * p["n_stops"].mean(), 1),
            "avg_names": round(p["n"].mean(), 1),
            "usd_max_dd_pct": round(100 * float((cum / cum.cummax() - 1).min()), 1),
            "usd_vol_ann_pct": round(100 * float(p["total_usd"].std() * np.sqrt(12)), 1)}


def diff(base: pd.DataFrame, alt: pd.DataFrame) -> dict:
    d = (alt.set_index("date")["active"] - base.set_index("date")["active"]).dropna()
    m, t, n = fb.newey_west_t(d, 6)
    return {"months": n, "diff_ann_pct": round(1200 * m, 2), "t": round(t, 2)}


def recovered_share(stops: list[dict], close: pd.DataFrame, xu: pd.Series) -> float | None:
    hits = []
    for s in stops:
        i = close.index.get_loc(s["date"])
        if i + 63 >= len(close.index):
            continue
        p = close[s["ticker"]].iloc[[i, i + 63]].to_numpy()
        x = xu.iloc[[i, i + 63]].to_numpy()
        if np.isfinite(p).all():
            hits.append(p[1] / p[0] > x[1] / x[0])
    return round(100 * float(np.mean(hits)), 1) if hits else None


def verdict(d: dict, h: dict, rule_s: dict, base_s: dict) -> str:
    dd_ok = rule_s["holdout"]["usd_max_dd_pct"] >= base_s["holdout"]["usd_max_dd_pct"] - 2.0
    if d["diff"]["diff_ann_pct"] > 0 and d["diff"]["t"] > HLZ_T and h["diff"]["diff_ann_pct"] > 0 \
            and h["diff"]["t"] > HOLDOUT_T and dd_ok:
        return "PASS"
    risk = all(
        x["diff"]["diff_ann_pct"] > -1.0
        and rule_s[w]["usd_max_dd_pct"] >= base_s[w]["usd_max_dd_pct"] + 5.0
        and rule_s[w]["usd_vol_ann_pct"] < base_s[w]["usd_vol_ann_pct"]
        for w, x in (("discovery", d), ("holdout", h)))
    if risk:
        return "RISK_REDUCTION_NO_RETURN_GAIN"
    if d["diff"]["t"] < -2 and h["diff"]["t"] < -2:
        return "HARMFUL"
    return "FAIL"


def main() -> None:
    months, universe, close, atr, xu, d0_of = build_inputs()
    sims, stop_events = {}, {}
    for name, rule in xr.RULES.items():
        p, st = xr.simulate(rule, months, universe, close, atr, xu, d0_of)
        sims[name], stop_events[name] = p, st
        print(f"  {name}: {len(p)} ay, {len(st)} stop", flush=True)

    def split(p):
        return {"discovery": p[p["date"] < SPLIT], "holdout": p[p["date"] >= SPLIT]}

    summary = {name: {w: stats(s) for w, s in split(p).items()} for name, p in sims.items()}
    result = {"as_of": date.today().isoformat(), "months": [str(months[0].date()), str(months[-1].date())],
              "summary": summary, "tests": {}}
    for name in CONFIRMATORY:
        BASE = xr.BASE_OF[name]
        sp_a, sp_b = split(sims[name]), split(sims[BASE])
        d = {"diff": diff(sp_b["discovery"], sp_a["discovery"])}
        h = {"diff": diff(sp_b["holdout"], sp_a["holdout"])}
        result["tests"][name] = {
            "base": BASE, "discovery": d, "holdout": h,
            "stopped_then_beat_xu100_3m_pct": recovered_share(stop_events[name], close, xu) if stop_events[name] else None,
            "verdict": verdict(d, h, summary[name], summary[BASE]),
        }

    out = ROOT / "data" / "reports" / f"research_exit_rules_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nAylar {result['months'][0]} .. {result['months'][1]}")
    print("Kural  donem      aktif%/yil (t)   USD aktif%   devir%  stop/yil  USD maxDD%  USD vol%")
    for name, s in summary.items():
        for w in ("discovery", "holdout"):
            x = s[w]
            print(f"{name:5s}  {w:9s}  {x['active_ann_pct']:6.2f} ({x['t']:5.2f})   {x['active_usd_ann_pct']:6.2f}   "
                  f"{x['turnover_pct']:5.1f}   {x['stops_per_year']:6.1f}   {x['usd_max_dd_pct']:7.1f}   {x['usd_vol_ann_pct']:6.1f}")
    print("\nTest  taban  kesif D%/yil (t)   holdout D%/yil (t)   stop sonrasi XU100'u gecen%   sonuc")
    for name, e in result["tests"].items():
        d, h = e["discovery"]["diff"], e["holdout"]["diff"]
        print(f"{name:5s} {e['base']:5s}  {d['diff_ann_pct']:6.2f} ({d['t']:5.2f})    {h['diff_ann_pct']:6.2f} ({h['t']:5.2f})    "
              f"{e['stopped_then_beat_xu100_3m_pct']}    {e['verdict']}")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
