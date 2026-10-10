#!/usr/bin/env python3
"""On-kayitli alis zamanlamasi testi (docs/research/entry_timing_preregistration.md).

    python scripts/build_fx_panel.py          # once (XU100 gunluk)
    python scripts/research_entry_timing.py
"""
from __future__ import annotations

import json
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import entry_timing as et  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")
HLZ_T, HOLDOUT_T = 3.0, 2.0
MAX_D0_GAP_DAYS = 7


def selections() -> pd.DataFrame:
    raw = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    raw["date"] = month_end(raw["date"])
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    df["ret_quintile"] = df.groupby("date")["str_1m"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False))
    rows = []
    prev: set = set()
    for dt, g in df.groupby("date"):
        g = g[g["value_sn_z"].notna()]
        n_top = max(1, int(round(len(g) * 0.2)))
        top = g.nlargest(n_top, "value_sn_z")
        names = set(top["ticker"])
        for r in top.itertuples():
            rows.append({"date": dt, "ticker": r.ticker, "ret_quintile": r.ret_quintile,
                         "new_entrant": r.ticker not in prev})
        prev = names
    return pd.DataFrame(rows)


def load_daily(ticker: str) -> pd.DataFrame | None:
    f = RESEARCH / "raw" / f"{ticker}.pkl"
    if not f.exists():
        return None
    px = pickle.loads(f.read_bytes()).get("px_adj")
    if px is None or px.empty:
        return None
    px = px[["Open", "High", "Low", "Close"]].astype(float).copy()
    idx = pd.to_datetime(px.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    px.index = idx.normalize()
    px = px[~px.index.duplicated(keep="last")].dropna()
    px = px[(px["Close"] > 0) & (px["Low"] > 0)]
    return et.indicators(px)


def run() -> pd.DataFrame:
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
        for r in g.itertuples():
            d0 = int(dates.searchsorted(r.date, side="right")) - 1
            if d0 < 50 or d0 + et.EXIT_DAY >= len(dates):
                continue
            if (r.date - dates[d0]).days > MAX_D0_GAP_DAYS:
                continue
            if not np.isfinite(xu_al[d0 + 1:d0 + et.EXIT_DAY + 1]).all():
                continue
            pol = float(policy.get(r.date, np.nan))
            ctx = {"ret_quintile": r.ret_quintile}
            for name, fn in et.RULES.items():
                legs = fn(a, d0, ctx)
                res = et.improvement(a, xu_al, d0, legs, pol if np.isfinite(pol) else 0.0)
                deadline = {"E1": 22, "E4": 63, "E5": 21}.get(name, 21)
                out.append({"date": r.date, "ticker": tk, "new_entrant": r.new_entrant, "rule": name,
                            **res, "triggered_early": res["first_idx"] < d0 + deadline,
                            "better_than_immediate": res["i_mkt"] > 0})
    return pd.DataFrame(out)


def summarize(sub: pd.DataFrame) -> dict:
    if sub.empty:
        return {"months": 0}
    monthly = sub.groupby("date")[["i_mkt", "i_cash"]].mean()
    m, t, n = fb.newey_west_t(monthly["i_mkt"], 6)
    mc, tc, _ = fb.newey_west_t(monthly["i_cash"], 6)
    return {"months": n, "obs": int(len(sub)),
            "i_mkt_mean_pct": round(100 * m, 3), "i_mkt_t": round(t, 2),
            "i_cash_mean_pct": round(100 * mc, 3), "i_cash_t": round(tc, 2),
            "mean_wait_days": round(float(sub["wait_days"].mean()), 1),
            "median_wait_days": round(float(sub["wait_days"].median()), 1),
            "triggered_early_pct": round(100 * float(sub["triggered_early"].mean()), 1),
            "better_than_immediate_pct": round(100 * float(sub["better_than_immediate"].mean()), 1)}


def verdict(d: dict, h: dict) -> str:
    if d.get("i_mkt_mean_pct", 0) > 0 and d.get("i_mkt_t", 0) > HLZ_T and h.get("i_mkt_mean_pct", 0) > 0 \
            and h.get("i_mkt_t", 0) > HOLDOUT_T and h.get("i_cash_mean_pct", 0) > 0:
        return "PASS"
    if d.get("i_mkt_t", 0) < -2 and h.get("i_mkt_t", 0) < -2:
        return "WAITING_IS_COSTLY"
    return "FAIL"


def main() -> None:
    res = run()
    result = {"as_of": date.today().isoformat(), "split": str(SPLIT.date()),
              "data_start": str(res["date"].min().date()), "data_end": str(res["date"].max().date()),
              "rules": {}}
    for rule in et.RULES:
        r = res[res["rule"] == rule]
        entry = {}
        for sample, mask in (("new_entrants", r["new_entrant"]), ("all_members", pd.Series(True, index=r.index))):
            s = r[mask]
            entry[sample] = {"discovery": summarize(s[s["date"] < SPLIT]), "holdout": summarize(s[s["date"] >= SPLIT])}
        entry["verdict"] = verdict(entry["new_entrants"]["discovery"], entry["new_entrants"]["holdout"])
        result["rules"][rule] = entry

    out = ROOT / "data" / "reports" / f"research_entry_timing_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Secim aylari {result['data_start']} .. {result['data_end']}")
    print("Kural  ornek     kesif I_mkt% (t)  holdout I_mkt% (t)  holdout I_cash%  bekleme(gun)  erken%  iyi%   sonuc")
    for rule, e in result["rules"].items():
        for sample in ("new_entrants", "all_members"):
            d, h = e[sample]["discovery"], e[sample]["holdout"]
            tag = e["verdict"] if sample == "new_entrants" else ""
            print(f"{rule:5s} {sample[:9]:9s} {d['i_mkt_mean_pct']:7.2f} ({d['i_mkt_t']:5.2f})   "
                  f"{h['i_mkt_mean_pct']:7.2f} ({h['i_mkt_t']:5.2f})   {h['i_cash_mean_pct']:7.2f}        "
                  f"{h['mean_wait_days']:5.1f}       {h['triggered_early_pct']:5.1f}  {h['better_than_immediate_pct']:5.1f}  {tag}")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
