#!/usr/bin/env python3
"""On-kayitli SMC giris (S1-S4) ve cikis (X5, X6) zamanlamasi testi
(docs/research/smc_timing_preregistration.md).

Giris: research_entry_timing cercevesi (secim, d0/d1, 126 gun cikis, I_mkt/I_cash).
Cikis: research_exit_rules cercevesi (R1 tamponu tabani, gunluk tetik, gelir XU100'de).

    python scripts/research_smc_timing.py
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

from core import entry_timing as et  # noqa: E402
from core import exit_rules as xr  # noqa: E402
from core import smc  # noqa: E402
from research_entry_timing import MAX_D0_GAP_DAYS, load_daily, selections, summarize  # noqa: E402
from research_entry_timing import verdict as entry_verdict  # noqa: E402
from research_exit_rules import build_inputs, diff, stats  # noqa: E402
from research_exit_rules import verdict as exit_verdict  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
DEADLINE = 21


def _ohlc(px: pd.DataFrame) -> pd.DataFrame:
    return px[["Open", "High", "Low", "Close"]].rename(columns=str.lower)


def _close(a: dict, i: int) -> et.Leg:
    return (i, float(a["Close"][i]), 1.0)


def _limit_fill(a: dict, d0: int, lim: float) -> list[et.Leg]:
    for i in range(d0 + 1, d0 + DEADLINE + 1):
        if a["Low"][i] <= lim:
            return [(i, float(min(a["Open"][i], lim)), 1.0)]
    return [_close(a, d0 + DEADLINE)]


def s1(a: dict, d0: int, st: dict, bull_internal: np.ndarray) -> list[et.Leg]:
    p0 = a["Close"][d0]
    obs = [b.top for b in st["order_blocks"] if b.bias == smc.BULLISH and b.top < p0]
    return _limit_fill(a, d0, max(obs)) if obs else [_close(a, d0 + 1)]


def s2(a: dict, d0: int, st: dict, bull_internal: np.ndarray) -> list[et.Leg]:
    top, bot = st["trailing_top"], st["trailing_bottom"]
    if smc.zone(a["Close"][d0], top, bot) not in ("premium", "premium_half"):
        return [_close(a, d0 + 1)]
    mid = (top + bot) / 2
    for i in range(d0 + 1, d0 + DEADLINE + 1):
        if a["Close"][i] <= mid:
            return [_close(a, i)]
    return [_close(a, d0 + DEADLINE)]


def s3(a: dict, d0: int, st: dict, bull_internal: np.ndarray) -> list[et.Leg]:
    if st["internal_bias"] != smc.BEARISH:
        return [_close(a, d0 + 1)]
    for i in range(d0 + 1, d0 + DEADLINE + 1):
        if bull_internal[i]:
            return [_close(a, i)]
    return [_close(a, d0 + DEADLINE)]


def s4(a: dict, d0: int, st: dict, bull_internal: np.ndarray) -> list[et.Leg]:
    p0 = a["Close"][d0]
    gaps = [g.top for g in st["fvgs"] if g.bias == smc.BULLISH and g.top < p0]
    return _limit_fill(a, d0, max(gaps)) if gaps else [_close(a, d0 + 1)]


ENTRY_RULES = {"S1": s1, "S2": s2, "S3": s3, "S4": s4}


def run_entry() -> pd.DataFrame:
    sel = selections()
    xu = pd.read_parquet(RESEARCH / "fx.parquet").set_index("date")["xu100"]
    xu.index = pd.to_datetime(xu.index).normalize()
    policy = pd.read_parquet(RESEARCH / "macro_monthly.parquet")["policy"]
    policy.index = policy.index.to_period("M").to_timestamp("M")
    policy = policy.ffill()

    out = []
    for tk, g in sel.groupby("ticker"):
        px = load_daily(tk)
        if px is None or len(px) < 200:
            continue
        a = {c: px[c].to_numpy() for c in px.columns}
        xu_al = xu.reindex(px.index, method="ffill").to_numpy()
        dates = px.index
        jobs = []
        for r in g.itertuples():
            d0 = int(dates.searchsorted(r.date, side="right")) - 1
            if d0 < 50 or d0 + et.EXIT_DAY >= len(dates) or (r.date - dates[d0]).days > MAX_D0_GAP_DAYS:
                continue
            if not np.isfinite(xu_al[d0 + 1:d0 + et.EXIT_DAY + 1]).all():
                continue
            jobs.append((r, d0))
        if not jobs:
            continue
        res = smc.analyze(_ohlc(px), states_at={d0 for _, d0 in jobs})
        ev = res.events
        bull_internal = np.zeros(len(px), dtype=bool)
        hit = ev[(ev["scope"] == "internal") & ev["kind"].isin([smc.BOS, smc.CHOCH]) & (ev["direction"] == smc.BULLISH)]
        bull_internal[hit["bar"].to_numpy(dtype=int)] = True
        for r, d0 in jobs:
            pol = float(policy.get(r.date, np.nan))
            st = res.states[d0]
            for name, fn in ENTRY_RULES.items():
                legs = fn(a, d0, st, bull_internal)
                imp = et.improvement(a, xu_al, d0, legs, pol if np.isfinite(pol) else 0.0)
                out.append({"date": r.date, "ticker": tk, "new_entrant": r.new_entrant, "rule": name, **imp,
                            "triggered_early": imp["first_idx"] < d0 + DEADLINE,
                            "better_than_immediate": imp["i_mkt"] > 0,
                            "condition_active": legs != [_close(a, d0 + 1)]})
    return pd.DataFrame(out)


def exit_events(tickers: list[str], scope: str) -> dict[str, set[pd.Timestamp]]:
    out = {}
    for tk in tickers:
        px = load_daily(tk)
        if px is None or len(px) < 60:
            continue
        ev = smc.analyze(_ohlc(px)).events
        hit = ev[(ev["scope"] == scope) & (ev["kind"] == smc.CHOCH) & (ev["direction"] == smc.BEARISH)]
        out[tk] = set(px.index[hit["bar"].to_numpy(dtype=int)])
    return out


def main() -> None:
    result = {"as_of": date.today().isoformat(), "split": str(SPLIT.date()), "entry": {}, "exit": {}}

    res = run_entry()
    result["entry_data"] = [str(res["date"].min().date()), str(res["date"].max().date())]
    for rule in ENTRY_RULES:
        r = res[res["rule"] == rule]
        entry = {}
        for sample, mask in (("new_entrants", r["new_entrant"]), ("all_members", pd.Series(True, index=r.index))):
            s = r[mask]
            entry[sample] = {"discovery": summarize(s[s["date"] < SPLIT]), "holdout": summarize(s[s["date"] >= SPLIT]),
                             "condition_active_pct": round(100 * float(s["condition_active"].mean()), 1)}
        entry["verdict"] = entry_verdict(entry["new_entrants"]["discovery"], entry["new_entrants"]["holdout"])
        result["entry"][rule] = entry
    print("entry done", flush=True)

    months, universe, close, atr, xu, d0_of = build_inputs()
    tickers = list(close.columns)
    sims = {"R1": xr.simulate(xr.RULES["R1"], months, universe, close, atr, xu, d0_of)[0]}
    for name, scope in (("X5", "swing"), ("X6", "internal")):
        ev = exit_events(tickers, scope)
        rule = xr.Rule(name, keep_pct=0.4, event_exit=True)
        sims[name], stops = xr.simulate(rule, months, universe, close, atr, xu, d0_of, events=ev)
        result["exit"][name] = {"scope": scope, "exits": len(stops)}
        print(f"  {name}: {len(stops)} cikis", flush=True)

    def split(p):
        return {"discovery": p[p["date"] < SPLIT], "holdout": p[p["date"] >= SPLIT]}

    summary = {name: {w: stats(s) for w, s in split(p).items()} for name, p in sims.items()}
    result["exit_summary"] = summary
    for name in ("X5", "X6"):
        a, b = split(sims[name]), split(sims["R1"])
        d = {"diff": diff(b["discovery"], a["discovery"])}
        h = {"diff": diff(b["holdout"], a["holdout"])}
        result["exit"][name].update({"discovery": d, "holdout": h,
                                     "verdict": exit_verdict(d, h, summary[name], summary["R1"])})

    out = ROOT / "data" / "reports" / f"research_smc_timing_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print("Kural ornek     kesif I_mkt% (t)  holdout I_mkt% (t)  holdout I_cash%  kosul%  bekleme  iyi%  sonuc")
    for rule, e in result["entry"].items():
        for sample in ("new_entrants", "all_members"):
            d, h = e[sample]["discovery"], e[sample]["holdout"]
            print(f"{rule:4s} {sample[:9]:9s} {d['i_mkt_mean_pct']:7.2f} ({d['i_mkt_t']:5.2f})   "
                  f"{h['i_mkt_mean_pct']:7.2f} ({h['i_mkt_t']:5.2f})   {h['i_cash_mean_pct']:7.2f}   "
                  f"{e[sample]['condition_active_pct']:5.1f}  {h['mean_wait_days']:5.1f}  {h['better_than_immediate_pct']:5.1f}  "
                  f"{e['verdict'] if sample == 'new_entrants' else ''}")
    for name in ("R1", "X5", "X6"):
        for w in ("discovery", "holdout"):
            x = summary[name][w]
            print(f"{name} {w:9s} aktif {x['active_ann_pct']:6.2f} ({x['t']:5.2f}) USD maxDD {x['usd_max_dd_pct']:6.1f} "
                  f"vol {x['usd_vol_ann_pct']:5.1f} cikis/yil {x['stops_per_year']:5.1f}")
    for name in ("X5", "X6"):
        e = result["exit"][name]
        print(f"{name} D kesif {e['discovery']['diff']} holdout {e['holdout']['diff']} -> {e['verdict']}")
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
