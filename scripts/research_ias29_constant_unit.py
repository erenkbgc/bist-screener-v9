#!/usr/bin/env python3
"""TMS 29: TTM akislari ortak satin alma gucunde (C1) vs mevcut tanim (C0)
(docs/research/ias29_constant_unit_ttm_preregistration.md).

Iki panel (kapdates, lag75) ham onbellekten C0 ve C1 ile kurulur; pencereler ve
metrikler research_ias29_regime.py ile ayni. Karar: C1 ADJ'de acikca kotu degilse benimsenir.

    python scripts/research_ias29_constant_unit.py
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
from core import long_term_research as ltr  # noqa: E402
from core import pit_panel  # noqa: E402
from research_ias29_regime import RATIOS, month_regimes, row_regime, window_stats  # noqa: E402
from research_survivorship import BASELINES, RESEARCH, SPLIT, prepared  # noqa: E402
from sensitivity_survivorship_net_debt import rebuild_baseline  # noqa: E402

IC_WORSE = -0.01
CHECK_COLS = ["ep", "sp", "ey", "bm", "fwd_ret_1m"]


def paired(a: pd.Series, b: pd.Series) -> dict:
    d = (a - b).dropna()
    m, t, n = fb.newey_west_t(d, 6)
    return {"mean": float(m), "t": float(t), "months": n}


def check_unchanged(c0: pd.DataFrame, c1: pd.DataFrame) -> dict:
    """TMS 29 oncesi tablolu satirlar birebir ayni olmali."""
    k = ["date", "ticker"]
    m = c0.merge(c1, on=k, suffixes=("_0", "_1"))
    old = m[m["stmt_period_0"] < pit_panel.IAS29_FIRST_PERIOD]
    bad = {c: int(((old[f"{c}_0"] - old[f"{c}_1"]).abs() > 1e-12).sum()
                  + (old[f"{c}_0"].isna() != old[f"{c}_1"].isna()).sum()) for c in CHECK_COLS}
    new = m[m["stmt_period_0"] >= pit_panel.IAS29_FIRST_PERIOD]
    changed = {c: int(((new[f"{c}_0"] - new[f"{c}_1"]).abs() > 1e-12).sum()) for c in ("ep", "sp", "ey")}
    return {"rows": len(m), "pre_ias29_rows": len(old), "pre_ias29_mismatches": bad,
            "ias29_rows": len(new), "ias29_rows_changed": changed, "valid": sum(bad.values()) == 0}


def main() -> None:
    sectors = {r["ticker"]: r["sektor"] for r in
               json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))}
    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    cpi = pit_panel.cpi_index(macro["cpi_mom"])
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    raw = {"C0": rebuild_baseline(sectors), "C1": rebuild_baseline(sectors, cpi=cpi)}
    result = {"as_of": date.today().isoformat(), "primary": "kapdates", "panels": {}}
    for variant, (fname, _) in BASELINES.items():
        chk = check_unchanged(raw["C0"][variant], raw["C1"][variant])
        dfs = {c: prepared(raw[c][variant], market_m) for c in ("C0", "C1")}
        for d in dfs.values():
            d["regime"] = d["stmt_period"].map(row_regime)
        reg = month_regimes(dfs["C0"])
        months = {"discovery": reg.index[reg.index < SPLIT],
                  "NOM": reg.index[(reg.index >= SPLIT) & (reg == "N")],
                  "ADJ": reg.index[reg.isin(["T", "I"])], "I_only": reg.index[reg == "I"]}
        res = {"check": chk, "windows": {}, "paired_ADJ": {}}
        ports, ics = {}, {}
        for c, d in dfs.items():
            ports[c] = ltr.portfolio(d, "value_sn_z")
            ics[c] = {"value_sn": fb.rank_ic(d, "value_sn_z", "fwd_ret_1m"),
                      **{r: fb.rank_ic(d, f"{r}_z", "fwd_ret_1m") for r in RATIOS}}
            res["windows"][c] = {w: window_stats(ports[c], ics[c], m) for w, m in months.items()}
        adj = months["ADJ"]
        ic_d = paired(ics["C1"]["value_sn"][lambda s: s.index.isin(adj)], ics["C0"]["value_sn"])
        a1 = ports["C1"].set_index("date")["active_fwd_ret_1m"]
        a0 = ports["C0"].set_index("date")["active_fwd_ret_1m"]
        act_d = paired(a1[a1.index.isin(adj)], a0)
        res["paired_ADJ"] = {"ic_value_sn": {"mean": round(ic_d["mean"], 4), "t": round(ic_d["t"], 2), "months": ic_d["months"]},
                             "net_active": {"diff_ann_pct": round(1200 * act_d["mean"], 2), "t": round(act_d["t"], 2),
                                            "months": act_d["months"]}}
        worse = (ic_d["mean"] < IC_WORSE and ic_d["t"] < -2) or act_d["t"] < -2
        res["verdict"] = "INVALID" if not chk["valid"] else ("KEEP_C0" if worse else "ADOPT_C1")
        result["panels"][variant] = res

        print(f"\n== {variant} | kontrol: {json.dumps(chk)}")
        for c in ("C0", "C1"):
            for w, s in res["windows"][c].items():
                tq = s["top_quintile"]
                ic_txt = " ".join(f"{k[3:]} {v['mean']:+.3f} ({v['t']:+.2f})" for k, v in s.items() if k.startswith("ic_"))
                print(f"  {c} {w:9s} n={s['months']:3d} aktif {tq.get('active_ann_pct')} (t {tq.get('t')})  IC: {ic_txt}")
        print(f"  C1-C0 ADJ: {res['paired_ADJ']} -> {res['verdict']}")
    result["verdict"] = result["panels"]["kapdates"]["verdict"]
    out = ROOT / "data" / "reports" / f"research_ias29_constant_unit_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=float))
    print(f"\nKarar (kapdates): {result['verdict']}\nJSON: {out}")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
