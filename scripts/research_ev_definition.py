#!/usr/bin/env python3
"""ey'nin firma degeri tanimi testi (docs/research/ev_definition_preregistration.md).

EV_k = mcap + fin_debt - cash - a_k * st_fin_inv + b_k * minority
  E0  (0, 0) canli tanim     E1  (1, 1) birincil aday
  E1a (1, 0) tani            E1b (0, 1) tani

Yeni kalemler (kisa vadeli "Finansal Yatırımlar", "Azınlık Payları") ham onbellekten
(data/research/raw/*.pkl) okunur ve hisse-ayina (ticker, stmt_period) ile baglanir.
Once E0'in kayitli panel ey / ey_z / value_sn_z ile birebir ayni oldugu dogrulanir.

    python scripts/research_ev_definition.py
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

from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from research_long_term import load  # noqa: E402
from research_portfolio_backtest import (  # noqa: E402
    CAPITAL_REF,
    RESEARCH,
    SPLIT,
    TOP,
    attach_benchmarks,
    load_daily,
    stats,
)
from research_value_ablation import nw_stat, switcher_and_overlap  # noqa: E402

VARIANTS = {"E0": (0, 0), "E1": (1, 1), "E1a": (1, 0), "E1b": (0, 1)}
BASE, CANDIDATE = "E0", "E1"
IAS29_START = pd.Timestamp("2024-05-01")
HLZ_T, HOLDOUT_T = 3.0, 2.0
NEW_ITEMS = {"st_fin_inv": ("Finansal Yatırımlar",), "minority": ("Azınlık Payları",)}


def new_items() -> pd.DataFrame:
    """(ticker, period, st_fin_inv, minority): ilk eslesen satir (kisa vade), toplama yok."""
    rows = []
    for f in sorted((RESEARCH / "raw").glob("*.pkl")):
        bs = pickle.loads(f.read_bytes()).get("bs")
        if bs is None or bs.empty:
            continue
        cols = {}
        for item, labels in NEW_ITEMS.items():
            s = pit_panel._pick(bs, labels, sum_dupes=False)
            if s is not None:
                cols[item] = s
        if cols:
            rows.append(pd.DataFrame(cols).rename_axis("period").reset_index().assign(ticker=f.stem))
    out = pd.concat(rows, ignore_index=True)
    out["period"] = out["period"].astype(str)
    return out


def ey_variant(d: pd.DataFrame, a: int, b: int) -> pd.Series:
    """value_ratios ile ayni kural: borc veya nakit bilinmiyorsa NaN, EV <= 0 ise NaN."""
    ev = d["mcap"] + d["fin_debt"] - d["cash"] - a * d["st_fin_inv"] + b * d["minority"]
    op = d["ttm_op_profit"]
    return (op / ev).where(op.notna() & np.isfinite(ev) & (ev > 0))


def attach(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    q = pd.read_parquet(RESEARCH / "quarterly.parquet")[["ticker", "period", "ttm_op_profit", "fin_debt", "cash"]]
    q["period"] = q["period"].astype(str)
    q = q.merge(new_items(), on=["ticker", "period"], how="left")
    coverage = {
        "quarters": len(q),
        "st_fin_inv_nonzero_pct": round(100 * float((q["st_fin_inv"].fillna(0) != 0).mean()), 2),
        "minority_nonzero_pct": round(100 * float((q["minority"].fillna(0) != 0).mean()), 2),
        "st_fin_inv_missing_pct": round(100 * float(q["st_fin_inv"].isna().mean()), 2),
        "minority_missing_pct": round(100 * float(q["minority"].isna().mean()), 2),
    }
    q[["st_fin_inv", "minority"]] = q[["st_fin_inv", "minority"]].fillna(0.0)
    d = df.merge(q.rename(columns={"period": "stmt_period"}), on=["ticker", "stmt_period"],
                 how="left", validate="many_to_one")
    assert len(d) == len(df)
    return d, coverage


def sanity_gate(d: pd.DataFrame) -> dict:
    """E0 yeniden hesabi kayitli ey, ey_z ve value_sn_z ile ayni olmali."""
    out = {}
    for col, new in (("ey", "ey_E0"), ("ey_z", "ey_E0_z"), ("value_sn_z", "value_sn_E0")):
        a, b = d[col], d[new]
        nan_mismatch = int((a.isna() != b.isna()).sum())
        rel = ((a - b).abs() / b.abs().clip(lower=1e-12))[a.notna() & b.notna()]
        out[col] = {"nan_mismatch": nan_mismatch, "max_rel_diff": float(rel.max()) if len(rel) else 0.0}
    out["passed"] = all(v["nan_mismatch"] == 0 and v["max_rel_diff"] < 1e-9 for v in out.values())
    return out


def build_scores(d: pd.DataFrame) -> pd.DataFrame:
    for name, (a, b) in VARIANTS.items():
        d[f"ey_{name}"] = ey_variant(d, a, b)
        d[f"ey_{name}_z"] = d.groupby("date")[f"ey_{name}"].transform(fb.winsorize_z)
        d[f"ey_{name}_sn"] = fb.sector_neutralize(d, f"ey_{name}_z")
        raw = d[["bm_z", "ep_z", "sp_z", f"ey_{name}_z"]].mean(axis=1)
        d[f"_raw_{name}"] = raw
        d[f"value_sn_{name}"] = fb.sector_neutralize(d, f"_raw_{name}")
        d.drop(columns=[f"_raw_{name}"], inplace=True)
    return d


def classify(disc_d: dict, hold_d: dict, sw_disc: dict, sw_hold: dict,
             hold_dic: dict, hold_vs_ew: dict) -> str:
    """On-kayitli karar kurallari (ev_definition_preregistration.md)."""
    def ok(x, key="mean_ann_pct"):
        return x.get(key) is not None and x.get("t") is not None
    if (ok(disc_d) and ok(hold_d) and disc_d["mean_ann_pct"] > 0 and disc_d["t"] > HLZ_T
            and hold_d["mean_ann_pct"] > 0 and hold_d["t"] > HOLDOUT_T
            and (sw_disc["mean_ann_pct"] or 0) > 0 and (sw_hold["mean_ann_pct"] or 0) > 0):
        return "SUPERIOR"
    non_inf = all(ok(x) and x["mean_ann_pct"] > -0.50 and x["t"] > -1.0 for x in (disc_d, hold_d))
    ic_ok = hold_dic.get("t") is not None and hold_dic["t"] > -1.0
    ew_ok = (hold_vs_ew.get("mean_ann_pct") or 0) > 0
    return "ADOPT_CORRECTION" if (non_inf and ic_ok and ew_ok) else "KEEP_E0"


def main() -> None:
    d, coverage = attach(load())
    d = build_scores(d)
    gate = sanity_gate(d)
    print("sanity gate:", json.dumps(gate))
    if not gate["passed"]:
        raise SystemExit("E0 yeniden hesabi kayitli panelle ayni degil; sonuc uretilmedi.")
    d = d[d["value_sn_E0"].notna()].copy()

    windows = {
        "discovery": lambda idx: idx < SPLIT,
        "holdout": lambda idx: idx >= SPLIT,
        "ias29_2024_05_plus": lambda idx: idx >= IAS29_START,
    }

    # 1. Rank-IC: tekil ey_k (sektor-notr) ve value_sn_k; E0'a gore eslestirilmis fark
    ic_report: dict[str, dict] = {}
    ics = {}
    for name in VARIANTS:
        for kind, col in (("ey_sn", f"ey_{name}_sn"), ("value_sn", f"value_sn_{name}")):
            ics[(name, kind)] = fb.rank_ic(d, col, "fwd_ret_1m")
    for name in VARIANTS:
        ic_report[name] = {}
        for kind in ("ey_sn", "value_sn"):
            ic_report[name][kind] = {}
            for wname, wfn in windows.items():
                s = ics[(name, kind)]
                entry = nw_stat(s[wfn(s.index)], scale=1.0)
                if name != BASE:
                    diff = (s - ics[(BASE, kind)]).dropna()
                    entry["diff_vs_E0"] = nw_stat(diff[wfn(diff.index)], scale=1.0)
                ic_report[name][kind][wname] = entry

    # 2. Ust %20 ortusme ve giren - cikan getirisi
    switcher_report: dict[str, dict] = {}
    for name in VARIANTS:
        if name == BASE:
            continue
        sw = switcher_and_overlap(d, f"value_sn_{name}", f"value_sn_{BASE}")
        switcher_report[name] = {}
        for wname, wfn in windows.items():
            sub = sw[wfn(sw.index)]
            switcher_report[name][wname] = {
                "mean_rank_corr": round(float(sub["rank_corr"].mean()), 4),
                "mean_top20_overlap_pct": round(100 * float(sub["overlap"].mean()), 2),
                "mean_switches_per_month": round(float(sub["n_switch"].mean()), 2),
                "entrants_minus_dropouts": nw_stat(sub["switch_spread"]),
            }

    # 3. Maliyetli portfoy simulasyonu (research_value_ablation.py ile ayni kurulum)
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    days = fx.index
    months = sorted(d["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    sel: dict[str, dict[pd.Timestamp, list[str]]] = {v: {} for v in VARIANTS}
    sel["EW"] = {}
    for t, g in d.groupby("date"):
        sel["EW"][t] = sorted(g["ticker"])
        for v in VARIANTS:
            h = g[g[f"value_sn_{v}"].notna()]
            r = h[f"value_sn_{v}"].rank(ascending=False, pct=True)
            sel[v][t] = sorted(h.loc[r <= TOP, "ticker"])

    tickers = sorted({tk for lst_map in sel.values() for lst in lst_map.values() for tk in lst})
    frames = {tk: load_daily(tk) for tk in tickers}
    frames = {tk: f for tk, f in frames.items() if f is not None}
    mat = {k: pd.DataFrame({tk: f[c] for tk, f in frames.items()}).reindex(days)
           for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))}
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()

    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], days)
    cpi_idx = (1 + macro["cpi_mom"].fillna(0) / 100).cumprod()
    ref = cpi_idx[CAPITAL_REF.to_period("M")]
    cpi_rel = {t: float(cpi_idx[t.to_period("M")] / ref) for t in months}
    cap = {t: 1e6 * cpi_rel[t] for t in months}
    universe_liq = {t: np.sort(g["tlvol60"].to_numpy()) for t, g in d.groupby("date")}
    bench = d.groupby("date")[["fwd_ret_1m", "fwd_ret_1m_usd"]].mean()
    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"], rf_daily=rf_daily)
    ctx = {"months": months, "d0_of": d0_of, "fx": fx, "rf_daily": rf_daily, "cpi_idx": cpi_idx,
           "bench": bench, "cpi_rel": cpi_rel, "universe_liq": universe_liq}

    costs = pb.Costs()
    ew_sim = pb.simulate(sel["EW"], months, d0_of, mkt, universe_liq, cap, costs=costs).set_index("date")
    sims: dict[str, pd.DataFrame] = {}
    for v in VARIANTS:
        p = attach_benchmarks(pb.simulate(sel[v], months, d0_of, mkt, universe_liq, cap, costs=costs), ctx)
        p = p.set_index("date")
        p["ew_net"] = ew_sim["port"].reindex(p.index)
        p["active_ew_net"] = p["port"] - p["ew_net"]
        sims[v] = p

    portfolio_report: dict[str, dict] = {}
    for v, p in sims.items():
        portfolio_report[v] = {}
        for wname, wfn in windows.items():
            sub = p[wfn(p.index)].reset_index()
            s = stats(sub)
            entry = {
                "vs_ew_net": nw_stat(p.loc[wfn(p.index), "active_ew_net"]),
                "cagr_tl_pct": s.get("cagr_tl_pct"), "cagr_usd_pct": s.get("cagr_usd_pct"),
                "max_dd_tl_pct": s.get("max_dd_tl_pct"), "max_dd_usd_pct": s.get("max_dd_usd_pct"),
                "turnover_pct": s.get("turnover_pct"), "cost_ann_pct": s.get("cost_ann_pct"),
            }
            if v != BASE:
                entry["diff_vs_E0"] = nw_stat((p["port"] - sims[BASE]["port"]).loc[wfn(p.index)])
            portfolio_report[v][wname] = entry

    pr = portfolio_report[CANDIDATE]
    verdict = classify(pr["discovery"]["diff_vs_E0"], pr["holdout"]["diff_vs_E0"],
                       switcher_report[CANDIDATE]["discovery"]["entrants_minus_dropouts"],
                       switcher_report[CANDIDATE]["holdout"]["entrants_minus_dropouts"],
                       ic_report[CANDIDATE]["value_sn"]["holdout"]["diff_vs_E0"],
                       pr["holdout"]["vs_ew_net"])

    result = {
        "as_of": date.today().isoformat(),
        "months": [str(months[0].date()), str(months[-1].date())],
        "coverage": coverage,
        "sanity_gate": gate,
        "rank_ic": ic_report,
        "switcher_analysis": switcher_report,
        "portfolio_simulation": portfolio_report,
        "verdict_E1": verdict,
        "note": "E1a ve E1b yalnizca tani; karar E1 uzerinden.",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    out = ROOT / "data" / "reports" / f"research_ev_definition_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
