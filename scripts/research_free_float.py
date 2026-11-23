#!/usr/bin/env python3
"""Pre-registered free-float market value filter test (P4-1).

Spec: docs/research/free_float_preregistration.md
Panel: data/research/fp/factors_monthly.parquet (point-in-time baseline)
Free-float source: data/research/market_cap_monthly.parquet (HAO_PD -> ff_mcap)

    .venv/bin/python scripts/research_free_float.py
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

from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_portfolio_backtest import (  # noqa: E402
    CAPITAL_REF,
    CAPITALS,
    SPLIT,
    TOP,
    attach_benchmarks,
    d3_verdict,
    diff,
    load_daily,
    split,
    stats,
)

RESEARCH = ROOT / "data" / "research"
FP_DIR = RESEARCH / "fp"
FF_DROP_PCT = 0.10


def load_fp_panel(factors_path: Path, mcap_path: Path = RESEARCH / "market_cap_monthly.parquet") -> pd.DataFrame:
    """Load point-in-time panel with liquid filter, value_sn_z, and monthly ff_mcap."""
    raw = pd.read_parquet(factors_path)
    raw["date"] = month_end(raw["date"])
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    raw = pit_panel.add_usd_returns(raw, market_m)
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    df = df[df["value_sn_z"].notna()].copy()

    mc = pd.read_parquet(mcap_path, columns=["date", "ticker", "mcap", "ff_mcap"])
    mc["date"] = month_end(mc["date"])
    mc = mc.drop_duplicates(subset=["date", "ticker"], keep="last")
    df = df.merge(
        mc.rename(columns={"mcap": "isy_mcap"}),
        on=["date", "ticker"],
        how="left",
        validate="many_to_one",
    )
    return df


def flag_ff1(df: pd.DataFrame, drop_pct: float = FF_DROP_PCT) -> pd.Series:
    """True = excluded by FF1: observed ff_mcap > 0 and strictly below month-t quantile.

    Missing ff_mcap is never excluded (consistent with project missing-data rules).
    """
    pos = df["ff_mcap"].where(df["ff_mcap"] > 0)
    cut = pos.groupby(df["date"]).transform(lambda s: s.quantile(drop_pct))
    return (pos < cut).fillna(False)


def selections_ff(df: pd.DataFrame, flag: pd.Series, top: float = TOP) -> dict[str, dict[pd.Timestamp, list[str]]]:
    """Monthly target ticker lists for P0, FF1, and EW universe."""
    out: dict[str, dict[pd.Timestamp, list[str]]] = {"P0": {}, "FF1": {}, "EW": {}}
    for t, g in df.groupby("date"):
        variants = {
            "P0": g,
            "FF1": g[~flag.loc[g.index]],
        }
        for name, h in variants.items():
            r = h["value_sn_z"].rank(ascending=False, pct=True)
            out[name][t] = sorted(h.loc[r <= top, "ticker"])
        out["EW"][t] = sorted(g["ticker"])
    return out


def build_market(df: pd.DataFrame, sel: dict[str, dict[pd.Timestamp, list[str]]]):
    """Build Market and context identical to research_portfolio_backtest.build()."""
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    days = fx.index
    months = sorted(df["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    tickers = sorted({tk for v in sel.values() for lst in v.values() for tk in lst})
    frames = {tk: load_daily(tk) for tk in tickers}
    frames = {tk: f for tk, f in frames.items() if f is not None}
    mat = {
        k: pd.DataFrame({tk: f[c] for tk, f in frames.items()}).reindex(days)
        for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))
    }
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()

    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], days)
    cpi_idx = (1 + macro["cpi_mom"].fillna(0) / 100).cumprod()
    ref = cpi_idx[CAPITAL_REF.to_period("M")]
    cpi_rel = {t: float(cpi_idx[t.to_period("M")] / ref) for t in months}

    universe_liq = {t: np.sort(g["tlvol60"].to_numpy()) for t, g in df.groupby("date")}
    bench = df.groupby("date")[["fwd_ret_1m", "fwd_ret_1m_usd"]].mean()

    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"], rf_daily=rf_daily)
    ctx = {
        "months": months,
        "d0_of": d0_of,
        "fx": fx,
        "rf_daily": rf_daily,
        "cpi_idx": cpi_idx,
        "bench": bench,
        "cpi_rel": cpi_rel,
        "universe_liq": universe_liq,
    }
    return mkt, ctx


def diff_col(base: pd.DataFrame, alt: pd.DataFrame, col: str = "active") -> dict:
    d = (alt.set_index("date")[col] - base.set_index("date")[col]).dropna()
    m, t, n = fb.newey_west_t(d, 6)
    return {"months": int(n), "diff_ann_pct": round(1200 * m, 2), "t": round(t, 2)}


def descriptive_stats(df: pd.DataFrame, flag: pd.Series, sel: dict[str, dict[pd.Timestamp, list[str]]]) -> dict:
    """Descriptive coverage, exclusion shares, overlap, and standalone rank ICs."""
    d = df.copy()
    d["flag"] = flag
    d["has_ff"] = d["ff_mcap"].notna() & (d["ff_mcap"] > 0)
    d["log_ff_mcap"] = np.log(d["ff_mcap"].where(d["ff_mcap"] > 0))
    d["ff_ratio"] = (d["ff_mcap"] / d["isy_mcap"]).where((d["ff_mcap"] > 0) & (d["isy_mcap"] > 0))

    windows = {
        "all": pd.Series(True, index=d.index),
        "discovery": d["date"] < SPLIT,
        "holdout": d["date"] >= SPLIT,
    }
    cov = {}
    for w, m in windows.items():
        sub = d[m]
        months_w = sorted(sub["date"].unique())
        p0_flagged, overlap_p0, jaccard = [], [], []
        for t in months_w:
            g = sub[sub["date"] == t].set_index("ticker")
            p0 = set(sel["P0"].get(t, []))
            ff1 = set(sel["FF1"].get(t, []))
            if p0:
                p0_flagged.append(float(g.loc[list(p0), "flag"].mean()))
                overlap_p0.append(len(p0 & ff1) / len(p0))
                jaccard.append(len(p0 & ff1) / len(p0 | ff1))
        cov[w] = {
            "rows": int(len(sub)),
            "months": len(months_w),
            "ff_known_pct": round(100 * float(sub["has_ff"].mean()), 1),
            "univ_flagged_pct": round(100 * float(sub["flag"].mean()), 1),
            "p0_top20_flagged_pct": round(100 * float(np.mean(p0_flagged)), 1) if p0_flagged else None,
            "p0_ff1_overlap_pct": round(100 * float(np.mean(overlap_p0)), 1) if overlap_p0 else None,
            "p0_ff1_jaccard_pct": round(100 * float(np.mean(jaccard)), 1) if jaccard else None,
            "median_ff_mcap_m_tl": round(float(sub["ff_mcap"].median() / 1e6), 1),
            "p10_ff_mcap_m_tl": round(float(sub["ff_mcap"].quantile(0.10) / 1e6), 1),
        }

    ic_out = {}
    for col in ("log_ff_mcap", "ff_ratio"):
        ic = fb.rank_ic(d, col, "fwd_ret_1m")
        ic_out[col] = {}
        for w, mask in (("discovery", ic.index < SPLIT), ("holdout", ic.index >= SPLIT)):
            mean, t_val, n = fb.newey_west_t(ic[mask], 6)
            ic_out[col][w] = {"mean_ic": round(float(mean), 4), "t": round(float(t_val), 2), "months": int(n)}

    return {"coverage": cov, "standalone_rank_ic": ic_out}


def run_panel(factors_path: Path, run_grid: bool = True) -> dict:
    df = load_fp_panel(factors_path)
    flag = flag_ff1(df)
    sel = selections_ff(df, flag)
    mkt, ctx = build_market(df, sel)
    months = ctx["months"]

    def sim(variant: str, capital: float, costs: pb.Costs, fill: str = "close") -> pd.DataFrame:
        cap = {t: capital * ctx["cpi_rel"][t] for t in months}
        p = pb.simulate(sel[variant], months, ctx["d0_of"], mkt, ctx["universe_liq"], cap, costs=costs, fill=fill)
        out = attach_benchmarks(p, ctx)
        out.attrs["delist_events"] = p.attrs["delist_events"]
        return out

    base_c = pb.Costs(mult=1.0)
    p0_main = sim("P0", 1e6, base_c)
    ff1_main = sim("FF1", 1e6, base_c)
    ew_main = sim("EW", 1e6, base_c)

    p0_sp, ff1_sp, ew_sp = split(p0_main), split(ff1_main), split(ew_main)
    p0_s = {w: stats(s) for w, s in p0_sp.items()}
    ff1_s = {w: stats(s) for w, s in ff1_sp.items()}
    dd = {w: diff(p0_sp[w], ff1_sp[w]) for w in ("discovery", "holdout")}
    dd_usd = {w: diff_col(p0_sp[w], ff1_sp[w], "active_usd") for w in ("discovery", "holdout")}
    verdict = d3_verdict(dd, ff1_s, p0_s)

    # Active vs costed EW universe (B2)
    b2 = {}
    for name, sp in (("P0", p0_sp), ("FF1", ff1_sp)):
        b2[name] = {}
        for w in ("discovery", "holdout"):
            a = (sp[w].set_index("date")["port"] - ew_sp[w].set_index("date")["port"]).dropna()
            m, t_val, n = fb.newey_west_t(a, 6)
            b2[name][w] = {"active_b2_ann_pct": round(1200 * m, 2), "t": round(t_val, 2), "months": int(n)}

    criteria = {
        "disc_diff_gt_minus_1": dd["discovery"]["diff_ann_pct"] > -1.0,
        "hold_diff_gt_minus_1": dd["holdout"]["diff_ann_pct"] > -1.0,
        "disc_t_gt_minus_2": dd["discovery"]["t"] > -2.0,
        "hold_t_gt_minus_2": dd["holdout"]["t"] > -2.0,
        "hold_usd_mdd_within_2pp": ff1_s["holdout"]["max_dd_usd_pct"] >= p0_s["holdout"]["max_dd_usd_pct"] - 2.0,
        "hold_usd_mdd_diff_pp": round(ff1_s["holdout"]["max_dd_usd_pct"] - p0_s["holdout"]["max_dd_usd_pct"], 2),
    }

    sensitivities = {}
    if run_grid:
        specs = [
            ("100k_base", 1e5, pb.Costs(mult=1.0), "close"),
            ("1M_stress2x", 1e6, pb.Costs(mult=2.0), "close"),
            ("1M_stress3x", 1e6, pb.Costs(mult=3.0), "close"),
            ("1M_open", 1e6, pb.Costs(mult=1.0), "open"),
            ("10M_base", 1e7, pb.Costs(mult=1.0), "close"),
            ("10M_stress2x", 1e7, pb.Costs(mult=2.0), "close"),
            ("100M_base", 1e8, pb.Costs(mult=1.0), "close"),
            ("100M_stress2x", 1e8, pb.Costs(mult=2.0), "close"),
        ]
        for label, cap_val, c_obj, fill in specs:
            p0_x = split(sim("P0", cap_val, c_obj, fill=fill))
            ff_x = split(sim("FF1", cap_val, c_obj, fill=fill))
            s0 = {w: stats(p0_x[w]) for w in ("discovery", "holdout")}
            s1 = {w: stats(ff_x[w]) for w in ("discovery", "holdout")}
            d_x = {w: diff(p0_x[w], ff_x[w]) for w in ("discovery", "holdout")}
            sensitivities[label] = {
                "P0": {w: {"active_univ_ann_pct": s0[w]["active_univ_ann_pct"], "t": s0[w]["active_univ_t"],
                           "max_dd_usd_pct": s0[w]["max_dd_usd_pct"], "cost_ann_pct": s0[w]["cost_ann_pct"],
                           "fills_over_10pct_adv_pct": s0[w]["fills_over_10pct_adv_pct"]}
                       for w in ("discovery", "holdout")},
                "FF1": {w: {"active_univ_ann_pct": s1[w]["active_univ_ann_pct"], "t": s1[w]["active_univ_t"],
                            "max_dd_usd_pct": s1[w]["max_dd_usd_pct"], "cost_ann_pct": s1[w]["cost_ann_pct"],
                            "fills_over_10pct_adv_pct": s1[w]["fills_over_10pct_adv_pct"]}
                        for w in ("discovery", "holdout")},
                "diff": d_x,
                "verdict": d3_verdict(d_x, s1, s0),
            }

    return {
        "panel": str(factors_path.relative_to(ROOT)),
        "months": [str(months[0].date()), str(months[-1].date())],
        "descriptive": descriptive_stats(df, flag, sel),
        "main_1M_base_close": {
            "P0": p0_s,
            "FF1": ff1_s,
            "diff": dd,
            "diff_usd": dd_usd,
            "vs_costed_ew_B2": b2,
            "criteria": criteria,
            "verdict": verdict,
        },
        "sensitivities": sensitivities,
    }


def main() -> None:
    main_res = run_panel(FP_DIR / "factors_monthly.parquet", run_grid=True)
    kap_res = run_panel(FP_DIR / "factors_monthly_kapdates.parquet", run_grid=False)

    result = {
        "as_of": date.today().isoformat(),
        "rule": "FF1: exclude bottom 10% of positive observed ff_mcap (HAO_PD) within monthly liquid universe; NaN kept",
        "trial_ledger_N_sel": 87,
        "verdict": main_res["main_1M_base_close"]["verdict"],
        "primary_lag75": main_res,
        "sensitivity_kapdates": kap_res,
    }

    out = ROOT / "data" / "reports" / f"research_free_float_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    m = main_res["main_1M_base_close"]
    print(f"Panel: {main_res['panel']}  Months: {main_res['months'][0]} .. {main_res['months'][1]}")
    for w in ("discovery", "holdout"):
        p0, ff1, d = m["P0"][w], m["FF1"][w], m["diff"][w]
        print(
            f"{w:9s} | P0 {p0['active_univ_ann_pct']:+6.2f}% (t {p0['active_univ_t']:5.2f}, USD DD {p0['max_dd_usd_pct']:5.1f}%, cost {p0['cost_ann_pct']:.2f}%) | "
            f"FF1 {ff1['active_univ_ann_pct']:+6.2f}% (t {ff1['active_univ_t']:5.2f}, USD DD {ff1['max_dd_usd_pct']:5.1f}%, cost {ff1['cost_ann_pct']:.2f}%) | "
            f"D {d['diff_ann_pct']:+6.2f}% (t {d['t']:5.2f})"
        )
    print(f"Criteria: {json.dumps(m['criteria'])}")
    print(f"VERDICT (primary, 1M TL base costs): {m['verdict']}")
    km = kap_res["main_1M_base_close"]
    print(
        f"KAP-dates sensitivity: disc D {km['diff']['discovery']['diff_ann_pct']:+.2f}% (t {km['diff']['discovery']['t']:.2f}), "
        f"hold D {km['diff']['holdout']['diff_ann_pct']:+.2f}% (t {km['diff']['holdout']['t']:.2f}), "
        f"hold USD DD P0 {km['P0']['holdout']['max_dd_usd_pct']:.1f}% vs FF1 {km['FF1']['holdout']['max_dd_usd_pct']:.1f}% -> {km['verdict']}"
    )
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
