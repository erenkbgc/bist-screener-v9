"""Measurement, not a trial: R0 with a market hedge (external review item 3).

How much of R0 is market beta, and what is left after shorting BIST index
futures? No VIOP history is available in our sources (borsapy lists only live
contracts), so the short futures leg is synthetic:
    fut_t = xu100_TR_t - dep_t          (cost of carry; basis risk ignored)
xu100 TR exists from 2018-07; before that, price return + the mean monthly
dividend yield implied by 2018-07+ (TR minus price) is used.
    hedged_t = port_t - beta_t * fut_t - ROLL_COST
beta_t: fixed 1.0, and a 36-month rolling OLS beta using only earlier months.
ROLL_COST = 0.05%/month (rolls, commissions, bid-ask; assumption).

    python scripts/report_hedged_r0.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import research_round4_vlab as h  # noqa: E402
from research_value_ablation import nw_stat  # noqa: E402

ROLL_COST = 0.0005
BETA_WINDOW = 36
TR_PATH = h.resolve_data_dirs(None, None)[0] / "tr_indices.parquet"
OUT = ROOT / "data" / "reports" / "report_hedged_r0_2026-11-24.json"

h.register_variant(h.VariantSpec("r0_copy", "hedge_measure", "R0 copy for measurement", lambda r, p, c: p["value_sn_z"]))


def r0_frame() -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as td:
        h.run_batch("hedge_measure", ["r0_copy"], skip_gates=True, results_dir=Path(td),
                    reports_dir=Path(td), prereg_dir=Path(td))
    return h.LAST_SIMS[0]["R0"].copy()  # primary lag75 panel


def market_excess(p: pd.DataFrame) -> pd.Series:
    tr = pd.read_parquet(TR_PATH)["xu100_tr"].dropna()
    tr.index = pd.to_datetime(tr.index)
    months = list(p.index)
    tr_ret = pd.Series(np.nan, index=p.index)
    for i, t in enumerate(months[:-1]):
        a, b = tr.asof(t), tr.asof(months[i + 1])
        if t >= tr.index[0] and np.isfinite(a) and np.isfinite(b):
            tr_ret[t] = b / a - 1
    have = tr_ret.notna()
    div_m = float((tr_ret[have] - p.loc[have, "xu"]).mean())
    total = tr_ret.where(have, p["xu"] + div_m)
    return total - p["dep"], div_m


def rolling_beta(y: pd.Series, x: pd.Series, n: int) -> pd.Series:
    out = pd.Series(np.nan, index=y.index)
    for i in range(n, len(y)):
        yy, xx = y.iloc[i - n:i], x.iloc[i - n:i]
        out.iloc[i] = float(np.cov(yy, xx, ddof=1)[0, 1] / np.var(xx, ddof=1))
    return out


def summary(r: pd.Series, dep: pd.Series) -> dict:
    r = r.dropna(); dep = dep.reindex(r.index)
    nav = (1 + r).cumprod()
    ex = r - dep
    return {
        "months": int(len(r)),
        "cagr_pct": round(100 * float(nav.iloc[-1] ** (12 / len(r)) - 1), 2),
        "excess_over_deposit": nw_stat(ex),
        "sharpe_ann": round(float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)), 3),
        "vol_ann_pct": round(100 * float(r.std(ddof=1) * np.sqrt(12)), 2),
        "max_dd_tl_pct": round(100 * float((nav / nav.cummax() - 1).min()), 1),
    }


def main() -> None:
    p = r0_frame()
    mkt, div_m = market_excess(p)
    port_ex = p["port"] - p["dep"]
    ok = mkt.notna() & port_ex.notna()
    x, y = mkt[ok], port_ex[ok]
    beta_full = float(np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1))
    beta_roll = rolling_beta(y, x, BETA_WINDOW).reindex(p.index)
    series = {
        "unhedged": p["port"],
        "hedged_beta1": p["port"] - 1.0 * mkt - ROLL_COST,
        "hedged_rolling_beta": (p["port"] - beta_roll * mkt - ROLL_COST).where(beta_roll.notna()),
        "market_tr": mkt + p["dep"],
    }
    windows = {
        "full": lambda i: np.ones(len(i), bool), **h.BLOCK_WINDOWS,
    }
    report = {"assumptions": {"roll_cost_monthly": ROLL_COST, "beta_window_months": BETA_WINDOW,
                              "pre_2018_dividend_yield_monthly": round(div_m, 5),
                              "hedge_instrument": "synthetic xu100 TR futures (no VIOP history)"},
              "beta_full_sample": round(beta_full, 3), "results": {}}
    common = series["hedged_rolling_beta"].dropna().index
    for name, s in series.items():
        report["results"][name] = {}
        for w, fn in windows.items():
            idx = p.index[fn(p.index)]
            idx = idx.intersection(common)
            report["results"][name][w] = summary(s.reindex(idx), p["dep"])
    OUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"beta {beta_full:.3f}; window starts {common[0].date()} (rolling beta warm-up)")
    for name in series:
        f = report["results"][name]["full"]
        blocks = " / ".join(f"{report['results'][name][b]['excess_over_deposit']['mean_ann_pct']:+.1f}"
                            for b in h.BLOCK_WINDOWS)
        e = f["excess_over_deposit"]
        print(f"{name:20s} exDep {e['mean_ann_pct']:+.2f}%/yr t {e['t']:+.2f} | blocks {blocks} | "
              f"Sharpe {f['sharpe_ann']:+.2f} vol {f['vol_ann_pct']:.1f}% maxDD {f['max_dd_tl_pct']:.1f}%")


if __name__ == "__main__":
    main()
