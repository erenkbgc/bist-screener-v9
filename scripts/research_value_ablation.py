#!/usr/bin/env python3
"""value_sn bilesen ablation testi (docs/research/value_ablation_preregistration.md).

Karsilastirilan bilesimler:
  - V0 (Baz, 4 bacak): ("bm", "ep", "sp", "ey") -- canli value_sn
  - V1 (S/P haric, 3 bacak): ("bm", "ep", "ey")
  - V2 (Defter + Kar, 2 bacak): ("bm", "ep")

Olcumler:
  1. Kesitsel Rank-IC ve eslestirilmis dIC = IC(Vk) - IC(V0) (NW t, 6 gecikme).
  2. 4 tekil sektor-notr bacagin ortak Fama-MacBeth regresyonu (marjinal egim ve NW t).
  3. Ust %20 sepet ortusmesi, siralama korelasyonu ve degisen hisselerin (giren - cikan)
     ileri getirisi (switcher spread).
  4. Ayni maliyetli portfoy simulatoru (core/portfolio_backtest.py::simulate, 1M TL, baz
     maliyet, ertesi gun kapanisi, nakit politika faizi) ile EW net karsisinda aktif getiri
     ve eslestirilmis D = r_net(Vk) - r_net(V0).

    python scripts/research_value_ablation.py
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

LEGS = ("bm", "ep", "sp", "ey")
VARIANTS: dict[str, tuple[str, ...]] = {
    "V0_bm_ep_sp_ey": ("bm", "ep", "sp", "ey"),
    "V1_bm_ep_ey_no_sp": ("bm", "ep", "ey"),
    "V2_bm_ep": ("bm", "ep"),
}
IAS29_START = pd.Timestamp("2024-05-01")
HLZ_T = 3.0
HOLDOUT_T = 2.0


def build_variant_scores(df: pd.DataFrame,
                         variants: dict[str, tuple[str, ...]] = VARIANTS,
                         min_peers: int = 5) -> pd.DataFrame:
    """Her varyant icin ham ortalama z ve sektor-notr (min_peers=5) skor sutunlari ekler;
    ayrica tekil bacaklarin sektor-notr z-skorlarini (bm_sn_z, ...) uretir."""
    out = df.copy()
    for leg in LEGS:
        zcol = f"{leg}_z"
        if zcol in out.columns:
            out[f"{leg}_sn_z"] = fb.sector_neutralize(out, zcol, min_n=min_peers)
    for name, cols in variants.items():
        raw_col = f"_{name}_raw"
        out[raw_col] = out[[f"{c}_z" for c in cols]].mean(axis=1)
        out[name] = fb.sector_neutralize(out, raw_col, min_n=min_peers)
        out.drop(columns=[raw_col], inplace=True)
    return out


def nw_stat(s: pd.Series, lags: int = 6, scale: float = 1200.0) -> dict:
    m, t, n = fb.newey_west_t(s, lags)
    return {
        "mean_ann_pct": round(scale * m, 2) if np.isfinite(m) else None,
        "mean_raw": round(float(m), 4) if np.isfinite(m) else None,
        "t": round(float(t), 2) if np.isfinite(t) else None,
        "months": int(n),
    }


def switcher_and_overlap(df: pd.DataFrame, col_k: str, col_0: str,
                         ret_col: str = "fwd_ret_1m", top_pct: float = TOP) -> pd.DataFrame:
    """Her ay Vk ve V0 ust %20 sepetlerinin ortusme orani, Spearman siralama korelasyonu,
    girenlerin (Vk \\ V0) ve cikanlarin (V0 \\ Vk) esit agirlikli getirisi."""
    rows = []
    for dt, g in df.groupby("date"):
        sub = g.dropna(subset=[col_k, col_0, ret_col])
        if len(sub) < 10:
            continue
        rk = sub[col_k].rank(ascending=False, pct=True)
        r0 = sub[col_0].rank(ascending=False, pct=True)
        set_k = set(sub.loc[rk <= top_pct, "ticker"])
        set_0 = set(sub.loc[r0 <= top_pct, "ticker"])
        if not set_0:
            continue
        entrants = set_k - set_0
        dropouts = set_0 - set_k
        idx_t = sub.set_index("ticker")[ret_col]
        ret_in = float(idx_t.loc[list(entrants)].mean()) if entrants else np.nan
        ret_out = float(idx_t.loc[list(dropouts)].mean()) if dropouts else np.nan
        rows.append({
            "date": dt,
            "rank_corr": float(sub[col_k].rank().corr(sub[col_0].rank())),
            "overlap": len(set_k & set_0) / len(set_0),
            "n_switch": len(entrants),
            "ret_entrants": ret_in,
            "ret_dropouts": ret_out,
            "switch_spread": ret_in - ret_out if (entrants and dropouts) else 0.0,
        })
    return pd.DataFrame(rows).set_index("date").sort_index() if rows else pd.DataFrame()


def classify_variant(name: str, disc_d: dict, hold_d: dict,
                     sw_disc: dict, sw_hold: dict,
                     fm_sp_disc_t: float, fm_sp_hold_t: float,
                     hold_vs_ew_net: dict) -> str:
    """On-kayitli karar kurallari (value_ablation_preregistration.md)."""
    if (disc_d["mean_ann_pct"] is not None and hold_d["mean_ann_pct"] is not None
            and disc_d["mean_ann_pct"] > 0 and disc_d["t"] > HLZ_T
            and hold_d["mean_ann_pct"] > 0 and hold_d["t"] > HOLDOUT_T
            and (sw_disc["mean_ann_pct"] or 0) > 0 and (sw_hold["mean_ann_pct"] or 0) > 0):
        return "SUPERIOR"
    if "no_sp" in name:
        sp_redundant = (fm_sp_disc_t <= 2.0) and (fm_sp_hold_t <= 2.0)
        non_inf_disc = (disc_d["mean_ann_pct"] is not None
                        and disc_d["mean_ann_pct"] > -0.50 and disc_d["t"] > -1.0)
        non_inf_hold = (hold_d["mean_ann_pct"] is not None
                        and hold_d["mean_ann_pct"] > -0.50 and hold_d["t"] > -1.0)
        beats_ew = (hold_vs_ew_net.get("mean_ann_pct", 0) > 0
                    and hold_vs_ew_net.get("t", 0) > HOLDOUT_T)
        if sp_redundant and non_inf_disc and non_inf_hold and beats_ew:
            return "NON_INFERIOR_SIMPLIFICATION"
    return "KEEP_V0"


def main() -> None:
    df = build_variant_scores(load())
    df = df[df["V0_bm_ep_sp_ey"].notna()].copy()

    windows = {
        "discovery": lambda idx: idx < SPLIT,
        "holdout": lambda idx: idx >= SPLIT,
        "ias29_2024_05_plus": lambda idx: idx >= IAS29_START,
    }

    # 1. Tekil sektor-notr bacaklarin IC'si ve ortak 4-bacak Fama-MacBeth regresyonu
    sn_legs = [f"{leg}_sn_z" for leg in LEGS]
    leg_ics = {leg: fb.rank_ic(df, f"{leg}_sn_z", "fwd_ret_1m") for leg in LEGS}
    fm_joint = fb.fama_macbeth(df, sn_legs, "fwd_ret_1m")
    legs_report: dict[str, dict] = {}
    for wname, wfn in windows.items():
        legs_report[wname] = {
            "rank_ic": {leg: nw_stat(ic[wfn(ic.index)], scale=1.0) for leg, ic in leg_ics.items()},
            "fama_macbeth_joint_ann_pct": {
                leg: nw_stat(fm_joint.loc[wfn(fm_joint.index), f"{leg}_sn_z"])
                for leg in LEGS if f"{leg}_sn_z" in fm_joint.columns
            },
        }

    # 2. Varyant Rank-IC, dIC ve ust %20 switcher analizi
    ics = {v: fb.rank_ic(df, v, "fwd_ret_1m") for v in VARIANTS}
    ic_report: dict[str, dict] = {}
    switcher_report: dict[str, dict] = {}
    base_name = "V0_bm_ep_sp_ey"
    for v in VARIANTS:
        ic_report[v] = {}
        for wname, wfn in windows.items():
            sub_ic = ics[v][wfn(ics[v].index)]
            entry = nw_stat(sub_ic, scale=1.0)
            if v != base_name:
                diff_ic = (ics[v] - ics[base_name]).dropna()
                entry["diff_vs_V0"] = nw_stat(diff_ic[wfn(diff_ic.index)], scale=1.0)
            ic_report[v][wname] = entry
        if v != base_name:
            sw = switcher_and_overlap(df, v, base_name)
            switcher_report[v] = {}
            for wname, wfn in windows.items():
                sub = sw[wfn(sw.index)]
                switcher_report[v][wname] = {
                    "mean_rank_corr": round(float(sub["rank_corr"].mean()), 4),
                    "mean_top20_overlap_pct": round(100 * float(sub["overlap"].mean()), 2),
                    "mean_switches_per_month": round(float(sub["n_switch"].mean()), 2),
                    "entrants_minus_dropouts": nw_stat(sub["switch_spread"]),
                }

    # 3. Maliyetli portfoy simulasyonu (1M TL, base costs, next-day close, EW net benchmark)
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    days = fx.index
    months = sorted(df["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    sel: dict[str, dict[pd.Timestamp, list[str]]] = {v: {} for v in VARIANTS}
    sel["EW"] = {}
    for t, g in df.groupby("date"):
        sel["EW"][t] = sorted(g["ticker"])
        for v in VARIANTS:
            h = g[g[v].notna()]
            r = h[v].rank(ascending=False, pct=True)
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
    universe_liq = {t: np.sort(g["tlvol60"].to_numpy()) for t, g in df.groupby("date")}
    bench = df.groupby("date")[["fwd_ret_1m", "fwd_ret_1m_usd"]].mean()
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
    v0_p = sims[base_name]
    for v, p in sims.items():
        portfolio_report[v] = {}
        for wname, wfn in (("discovery", lambda idx: idx < SPLIT),
                           ("holdout", lambda idx: idx >= SPLIT),
                           ("ias29_2024_05_plus", lambda idx: idx >= IAS29_START)):
            sub = p[wfn(p.index)].reset_index()
            base_stats = stats(sub)
            vs_ew_net = nw_stat(p.loc[wfn(p.index), "active_ew_net"])
            entry = {
                "vs_ew_net": vs_ew_net,
                "vs_ew_gross_ann_pct": base_stats.get("active_univ_ann_pct"),
                "vs_ew_gross_t": base_stats.get("active_univ_t"),
                "cagr_tl_pct": base_stats.get("cagr_tl_pct"),
                "cagr_usd_pct": base_stats.get("cagr_usd_pct"),
                "max_dd_tl_pct": base_stats.get("max_dd_tl_pct"),
                "max_dd_usd_pct": base_stats.get("max_dd_usd_pct"),
                "turnover_pct": base_stats.get("turnover_pct"),
                "cost_ann_pct": base_stats.get("cost_ann_pct"),
            }
            if v != base_name:
                d_series = (p["port"] - v0_p["port"]).loc[wfn(p.index)]
                entry["diff_vs_V0"] = nw_stat(d_series)
            portfolio_report[v][wname] = entry

    verdicts: dict[str, str] = {}
    fm_sp_disc_t = float(legs_report["discovery"]["fama_macbeth_joint_ann_pct"]["sp"]["t"] or 0.0)
    fm_sp_hold_t = float(legs_report["holdout"]["fama_macbeth_joint_ann_pct"]["sp"]["t"] or 0.0)
    for v in VARIANTS:
        if v == base_name:
            continue
        verdicts[v] = classify_variant(
            v,
            portfolio_report[v]["discovery"]["diff_vs_V0"],
            portfolio_report[v]["holdout"]["diff_vs_V0"],
            switcher_report[v]["discovery"]["entrants_minus_dropouts"],
            switcher_report[v]["holdout"]["entrants_minus_dropouts"],
            fm_sp_disc_t,
            fm_sp_hold_t,
            portfolio_report[v]["holdout"]["vs_ew_net"],
        )

    result = {
        "as_of": date.today().isoformat(),
        "months": [str(months[0].date()), str(months[-1].date())],
        "n_discovery": int((v0_p.index < SPLIT).sum()),
        "n_holdout": int((v0_p.index >= SPLIT).sum()),
        "single_legs": legs_report,
        "variants_rank_ic": ic_report,
        "switcher_analysis": switcher_report,
        "portfolio_simulation": portfolio_report,
        "verdicts": verdicts,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    out = ROOT / "data" / "reports" / f"research_value_ablation_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
