#!/usr/bin/env python3
"""On-kayitli trend takip zamanlama katmanlari testi
(docs/research/trend_timing_preregistration.md): T1 Donchian 20/10 + ATR, T2 Supertrend 10/3,
T3 EMA geri cekilme + ATR; R0 secimi uzerinde, taban B0 = ay boyu tut.

    python scripts/research_trend_timing.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import portfolio_backtest as pb  # noqa: E402
from core import trend_timing as tt  # noqa: E402
from research_entry_timing import load_daily  # noqa: E402
from research_exit_rules import build_inputs, diff, stats  # noqa: E402
from research_exit_rules import verdict as exit_verdict  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SPLIT = pd.Timestamp("2021-01-01")


def positions(tickers: list[str], days: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    cols: dict[str, dict[str, pd.Series]] = {k: {} for k in tt.SYSTEMS}
    for tk in tickers:
        px = load_daily(tk)
        if px is None or len(px) < 60:
            continue
        h, lo, c = (px[k].to_numpy(dtype=float) for k in ("High", "Low", "Close"))
        for name, fn in tt.SYSTEMS.items():
            cols[name][tk] = pd.Series(tt.execute(fn(h, lo, c), c), index=px.index)
    return {k: pd.DataFrame(v).reindex(days).ffill().fillna(0).astype("int8") for k, v in cols.items()}


def main() -> None:
    months, universe, close, atr, xu, d0_of = build_inputs()
    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf = pb.policy_rf_daily(macro["policy"], xu.index)
    pos = positions(list(close.columns), xu.index)

    sims = {"B0": tt.simulate_overlay(months, universe, close, None, rf, xu, d0_of)}
    for name in tt.SYSTEMS:
        sims[name] = tt.simulate_overlay(months, universe, close, pos[name], rf, xu, d0_of)
        sims[f"{name}_xu100"] = tt.simulate_overlay(months, universe, close, pos[name], rf, xu, d0_of, park="xu100")

    def split(p):
        return {"discovery": p[p["date"] < SPLIT], "holdout": p[p["date"] >= SPLIT]}

    summary = {}
    for name, p in sims.items():
        summary[name] = {}
        for w, s in split(p).items():
            summary[name][w] = {**stats(s), "invested_pct": round(100 * float(s["invested"].mean()), 1)}
    result = {"as_of": date.today().isoformat(), "months": [str(months[0].date()), str(months[-1].date())],
              "summary": summary, "tests": {}}
    for name in list(tt.SYSTEMS) + [f"{k}_xu100" for k in tt.SYSTEMS]:
        a, b = split(sims[name]), split(sims["B0"])
        d = {"diff": diff(b["discovery"], a["discovery"])}
        h = {"diff": diff(b["holdout"], a["holdout"])}
        result["tests"][name] = {"discovery": d, "holdout": h,
                                 "verdict": exit_verdict(d, h, summary[name], summary["B0"])
                                 if name in tt.SYSTEMS else "INFO_ONLY"}

    out = ROOT / "data" / "reports" / f"research_trend_timing_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"Aylar {result['months'][0]} .. {result['months'][1]}")
    for name, s in summary.items():
        for w in ("discovery", "holdout"):
            x = s[w]
            print(f"{name:9s} {w:9s} aktif {x['active_ann_pct']:6.2f} ({x['t']:5.2f})  USD {x['active_usd_ann_pct']:6.2f}  "
                  f"maxDD {x['usd_max_dd_pct']:6.1f}  vol {x['usd_vol_ann_pct']:5.1f}  piyasada% {x['invested_pct']:5.1f}  "
                  f"degisim/yil {x['stops_per_year']:5.1f}")
    for name, e in result["tests"].items():
        print(f"{name:9s} D kesif {e['discovery']['diff']}  holdout {e['holdout']['diff']}  -> {e['verdict']}")
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
