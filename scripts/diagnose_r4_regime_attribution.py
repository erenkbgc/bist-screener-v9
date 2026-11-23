#!/usr/bin/env python3
"""Round 4 Regime & Attribution Lab — Diagnostics Only (NO candidate trials).

Decomposes R0 (value_sn_z top-20% monthly) across the 4 Round-4 gauntlet blocks:
  B1: 2013-04 .. 2016-12
  B2: 2017-01 .. 2020-12
  B3: 2021-01 .. 2023-12
  B4: 2024-01 .. latest (2026-08)
plus Full, 2021+, and IAS29 (2024-05+).

Covers:
  1. Headline R0 performance (costed 1M TL, next-close fills, lag75 & kapdates) + macro context
  2. Component ablation (single legs, LOO composites, raw vs sector-neutral, joint FM, leg IC)
  3. Value_sn construction defects (missing legs, negative ep/ey, sector dispersion & n<5 fallback,
     tail monotonicity / top-5% blowups, CPI-unit age mismatch)
  4. Sector attribution & concentration (weights, HHI, Brinson allocation vs selection)
  5. Size, liquidity & style-factor loadings (size terciles, vol60, mom_12_1, str_1m, beta/FX)
  6. IAS 29 seam quarters (2023Q4-2024Q4) & reexpression_class / statement jump analysis
  7. Staleness attribution (lag75 vs kapdates, filing lag, statement age, fresh vs stale)
  8. Entrants vs Holdings vs Exits (price-driven vs filing-driven entrants, holding tenure, boundary churn)
  9. USD drawdown & worst active episodes

Strictly diagnostic: does not touch live code, prereg/, or trial_ledger.json.
"""
from __future__ import annotations

import json
import sys
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
from research_portfolio_backtest import CAPITAL_REF, SPLIT, TOP, attach_benchmarks, stats  # noqa: E402
from research_round3 import load_daily_from_dir, load_prepared_panel, resolve_data_dirs  # noqa: E402
from research_value_ablation import IAS29_START, LEGS, nw_stat, switcher_and_overlap  # noqa: E402

AS_OF = "2026-11-24"

BLOCKS: list[tuple[str, str, str]] = [
    ("B1_2013_16", "2013-04-01", "2016-12-31"),
    ("B2_2017_20", "2017-01-01", "2020-12-31"),
    ("B3_2021_23", "2021-01-01", "2023-12-31"),
    ("B4_2024_plus", "2024-01-01", "2099-12-31"),
]

ALL_WINDOWS: list[tuple[str, str, str]] = [
    *BLOCKS,
    ("Full", "2013-04-01", "2099-12-31"),
    ("Holdout_2021_plus", "2021-01-01", "2099-12-31"),
    ("IAS29_2024_05_plus", "2024-05-01", "2099-12-31"),
]


def wmask(idx: pd.DatetimeIndex | pd.Series, start: str, end: str) -> np.ndarray:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    return (idx >= s) & (idx <= e)


def assign_block(dt: pd.Timestamp) -> str:
    for bname, s, e in BLOCKS:
        if pd.Timestamp(s) <= dt <= pd.Timestamp(e):
            return bname
    return "OTHER"


def build_sim_env(df: pd.DataFrame, macro: pd.DataFrame, fx: pd.DataFrame, raw_dir: Path, frames_cache: dict):
    days = fx.index
    months = sorted(df["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    tickers = sorted(df["ticker"].unique())
    for tk in tickers:
        if tk not in frames_cache:
            f = load_daily_from_dir(tk, raw_dir)
            if f is not None:
                frames_cache[tk] = f
    frames = {tk: frames_cache[tk] for tk in tickers if tk in frames_cache}

    mat = {
        k: pd.DataFrame({tk: f[c] for tk, f in frames.items()}).reindex(days)
        for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))
    }
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()

    mac = macro.copy()
    if not isinstance(mac.index, pd.PeriodIndex):
        mac.index = pd.to_datetime(mac.index).to_period("M")
    rf_daily = pb.policy_rf_daily(mac["policy"], days)
    cpi_idx = (1.0 + mac["cpi_mom"].fillna(0.0) / 100.0).cumprod()
    ref = cpi_idx[CAPITAL_REF.to_period("M")]
    cpi_rel = {t: float(cpi_idx[t.to_period("M")] / ref) for t in months}
    cap = {t: 1e6 * cpi_rel[t] for t in months}
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
        "cap": cap,
    }
    return mkt, ctx


def simulate_scores(df: pd.DataFrame, score_cols: list[str], mkt: pb.Market, ctx: dict) -> dict[str, pd.DataFrame]:
    months, d0_of, universe_liq, cap = ctx["months"], ctx["d0_of"], ctx["universe_liq"], ctx["cap"]
    sel: dict[str, dict[pd.Timestamp, list[str]]] = {c: {} for c in score_cols}
    sel["EW"] = {}
    for t, g in df.groupby("date"):
        sel["EW"][t] = sorted(g["ticker"])
        for c in score_cols:
            h = g[g[c].notna()]
            if h.empty:
                sel[c][t] = []
            else:
                r = h[c].rank(ascending=False, pct=True)
                sel[c][t] = sorted(h.loc[r <= TOP, "ticker"])

    costs = pb.Costs()
    ew_sim = pb.simulate(sel["EW"], months, d0_of, mkt, universe_liq, cap, costs=costs).set_index("date")
    sims: dict[str, pd.DataFrame] = {}
    for c in score_cols:
        p = attach_benchmarks(pb.simulate(sel[c], months, d0_of, mkt, universe_liq, cap, costs=costs), ctx)
        p = p.set_index("date")
        p["ew_net"] = ew_sim["port"].reindex(p.index)
        p["active_ew_net"] = p["port"] - p["ew_net"]
        sims[c] = p
    sims["EW"] = ew_sim
    return sims


def summarize_sim_windows(sim: pd.DataFrame, ref_sim: pd.DataFrame | None = None) -> dict:
    out = {}
    for wname, s, e in ALL_WINDOWS:
        m = wmask(sim.index, s, e)
        sub = sim.loc[m]
        st = stats(sub.reset_index())
        entry = {
            "months": int(len(sub)),
            "vs_ew_net": nw_stat(sub["active_ew_net"]),
            "vs_ew_gross": nw_stat(sub["active"]),
            "active_usd": nw_stat(sub["active_usd"]),
            "cagr_tl_pct": st.get("cagr_tl_pct"),
            "cagr_usd_pct": st.get("cagr_usd_pct"),
            "cagr_real_pct": st.get("cagr_real_pct"),
            "max_dd_usd_pct": st.get("max_dd_usd_pct"),
            "max_dd_tl_pct": st.get("max_dd_tl_pct"),
            "turnover_pct": st.get("turnover_pct"),
            "cost_ann_pct": st.get("cost_ann_pct"),
            "avg_names": st.get("avg_names"),
        }
        if ref_sim is not None:
            common = sub.index.intersection(ref_sim.index)
            d = sim.loc[common, "active_ew_net"] - ref_sim.loc[common, "active_ew_net"]
            entry["D_vs_R0"] = nw_stat(d)
        out[wname] = entry
    return out


def add_diagnostic_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for leg in LEGS:
        out[f"{leg}_sn_z"] = fb.sector_neutralize(out, f"{leg}_z")
    # Leave-one-out composites (exact R0 construction: mean of remaining _z, then sector_neutralize)
    loo_specs = {
        "no_bm": ["ep", "sp", "ey"],
        "no_ep": ["bm", "sp", "ey"],
        "no_sp": ["bm", "ep", "ey"],
        "no_ey": ["bm", "ep", "sp"],
    }
    for name, cols in loo_specs.items():
        raw = out[[f"{c}_z" for c in cols]].mean(axis=1)
        out[f"_{name}_raw"] = raw
        out[name] = fb.sector_neutralize(out, f"_{name}_raw")
        out.drop(columns=[f"_{name}_raw"], inplace=True)

    # Diagnostic construction probes (NOT candidate trials — isolating specific defects):
    # 1. Raw value_z (no sector neutralization) already exists as value_z
    # 2. Within-sector z-score (mean AND std standardized within sector, min_n=5)
    g_sec = out.groupby(["date", "sector"])["value_z"]
    cnt = g_sec.transform("count")
    sec_mean = g_sec.transform("mean")
    sec_std = g_sec.transform("std")
    mkt_mean = out.groupby("date")["value_z"].transform("mean")
    mkt_std = out.groupby("date")["value_z"].transform("std")
    within_z = (out["value_z"] - sec_mean) / sec_std.replace(0, np.nan)
    mkt_z = (out["value_z"] - mkt_mean) / mkt_std.replace(0, np.nan)
    out["diag_within_sec_z"] = within_z.where((cnt >= 5) & sec_std.notna() & (sec_std > 0), mkt_z)

    # Mark R0 top-20% membership and ranks
    out["r0_pct_rank"] = out.groupby("date")["value_sn_z"].rank(ascending=False, pct=True)
    out["in_r0"] = out["r0_pct_rank"] <= TOP
    out["n_legs_valid"] = out[[f"{c}_z" for c in LEGS]].notna().sum(axis=1)
    out["sec_count"] = out.groupby(["date", "sector"])["ticker"].transform("count")
    out["small_sec_fallback"] = out["sec_count"] < 5
    out["stmt_period_end"] = out["stmt_period"].map(pit_panel.period_end)
    out["stmt_age_days"] = (out["date"] - out["stmt_period_end"]).dt.days
    out["block"] = out["date"].map(assign_block)
    return out


def compute_macro_blocks(macro: pd.DataFrame, fx: pd.DataFrame, df_dates: pd.DatetimeIndex) -> dict:
    mac = macro.copy()
    if not isinstance(mac.index, pd.PeriodIndex):
        mac.index = pd.to_datetime(mac.index).to_period("M")
    fx_m = fx[["usdtry", "xu100"]].resample("ME").last()
    fx_m["usdtry_ret"] = fx_m["usdtry"].pct_change()
    fx_m["xu100_ret"] = fx_m["xu100"].pct_change()
    fx_m["xu100_usd_ret"] = (1 + fx_m["xu100_ret"]) / (1 + fx_m["usdtry_ret"]) - 1

    out = {}
    for wname, s, e in ALL_WINDOWS:
        dts = df_dates[wmask(df_dates, s, e)]
        pers = pd.PeriodIndex(dts, freq="M")
        sub_m = mac.reindex(pers)
        sub_fx = fx_m.reindex(dts)
        cpi_yoy = float(sub_m["cpi_yoy"].mean()) if "cpi_yoy" in sub_m else np.nan
        pol = float(sub_m["policy"].mean()) if "policy" in sub_m else np.nan
        real_pol = pol - cpi_yoy
        # Cumulative FX & XU100 USD CAGR
        n = len(sub_fx.dropna(subset=["usdtry_ret"]))
        fx_cagr = float((1 + sub_fx["usdtry_ret"].dropna()).prod() ** (12 / n) - 1) * 100 if n > 0 else np.nan
        xu_usd_cagr = float((1 + sub_fx["xu100_usd_ret"].dropna()).prod() ** (12 / n) - 1) * 100 if n > 0 else np.nan
        out[wname] = {
            "months": int(len(dts)),
            "mean_cpi_yoy_pct": round(cpi_yoy, 1),
            "mean_policy_pct": round(pol, 1),
            "mean_real_policy_pct": round(real_pol, 1),
            "usdtry_ann_pct": round(fx_cagr, 1),
            "xu100_usd_cagr_pct": round(xu_usd_cagr, 1),
        }
    return out


def compute_quintile_and_tail_profile(df: pd.DataFrame) -> dict:
    """Gross fwd_ret_1m excess vs monthly EW across quintiles & top vigintiles (top 5%, 5-10%, 10-20%)."""
    valid = df.dropna(subset=["value_sn_z", "fwd_ret_1m"]).copy()
    valid["ew_ret"] = valid.groupby("date")["fwd_ret_1m"].transform("mean")
    valid["ex_ret"] = valid["fwd_ret_1m"] - valid["ew_ret"]

    # Assign buckets per month
    def _bucket(g: pd.DataFrame) -> pd.Series:
        r = g["value_sn_z"].rank(ascending=False, pct=True)
        out = pd.Series("Q2_20_40", index=g.index)
        out[r <= 0.05] = "T1_top5"
        out[(r > 0.05) & (r <= 0.10)] = "T2_5_10"
        out[(r > 0.10) & (r <= 0.20)] = "T3_10_20"
        out[(r > 0.20) & (r <= 0.40)] = "Q2_20_40"
        out[(r > 0.40) & (r <= 0.60)] = "Q3_40_60"
        out[(r > 0.60) & (r <= 0.80)] = "Q4_60_80"
        out[r > 0.80] = "Q5_bot20"
        return out

    valid["bucket"] = valid.groupby("date", group_keys=False).apply(_bucket)
    monthly = valid.groupby(["date", "bucket"])["ex_ret"].mean().unstack("bucket")

    out = {}
    for wname, s, e in ALL_WINDOWS:
        sub = monthly.loc[wmask(monthly.index, s, e)]
        out[wname] = {b: nw_stat(sub[b]) for b in ["T1_top5", "T2_5_10", "T3_10_20", "Q2_20_40", "Q3_40_60", "Q4_60_80", "Q5_bot20"] if b in sub}
        # Also Top 5% minus 5-20%
        if {"T1_top5", "T2_5_10", "T3_10_20"}.issubset(sub.columns):
            rest_top20 = (sub["T2_5_10"] + 2 * sub["T3_10_20"]) / 3.0
            out[wname]["T1_minus_T23"] = nw_stat(sub["T1_top5"] - rest_top20)
    return out


def compute_sector_attribution(df: pd.DataFrame) -> dict:
    """Brinson allocation vs selection attribution + concentration stats per block."""
    valid = df.dropna(subset=["value_sn_z", "fwd_ret_1m"]).copy()
    monthly_rows = []
    sec_month_rows = []

    for dt, g in valid.groupby("date"):
        n_all = len(g)
        r0 = g[g["in_r0"]]
        n_r0 = len(r0)
        if n_r0 == 0:
            continue
        r_ew = float(g["fwd_ret_1m"].mean())
        r_p = float(r0["fwd_ret_1m"].mean())

        alloc_total = 0.0
        sel_total = 0.0
        w_p_list = []
        w_b_list = []

        for sec, gs in g.groupby("sector"):
            w_b = len(gs) / n_all
            r_b_sec = float(gs["fwd_ret_1m"].mean())
            rs_p = gs[gs["in_r0"]]
            w_p = len(rs_p) / n_r0
            r_p_sec = float(rs_p["fwd_ret_1m"].mean()) if len(rs_p) > 0 else r_b_sec
            alloc = (w_p - w_b) * (r_b_sec - r_ew)
            sel = w_p * (r_p_sec - r_b_sec)
            alloc_total += alloc
            sel_total += sel
            w_p_list.append(w_p)
            w_b_list.append(w_b)
            sec_month_rows.append({
                "date": dt, "sector": sec, "w_p": w_p, "w_b": w_b,
                "active_w": w_p - w_b, "alloc": alloc, "sel": sel,
                "total_contrib": alloc + sel, "sec_count": len(gs),
                "small_sec": len(gs) < 5, "r_p_sec_ex": (r_p_sec - r_b_sec) if len(rs_p) > 0 else np.nan,
            })

        hhi_p = float(sum(w * w for w in w_p_list))
        hhi_b = float(sum(w * w for w in w_b_list))
        monthly_rows.append({
            "date": dt,
            "active_gross": r_p - r_ew,
            "alloc": alloc_total,
            "sel": sel_total,
            "hhi_p": hhi_p,
            "hhi_b": hhi_b,
            "eff_n_sec_p": 1.0 / hhi_p if hhi_p > 0 else np.nan,
            "eff_n_sec_b": 1.0 / hhi_b if hhi_b > 0 else np.nan,
            "max_sec_w_p": max(w_p_list),
            "small_sec_w_p": float(r0["small_sec_fallback"].mean()),
            "small_sec_w_b": float(g["small_sec_fallback"].mean()),
            "small_sec_r0_ex": float(r0.loc[r0["small_sec_fallback"], "fwd_ret_1m"].mean() - r_ew) if r0["small_sec_fallback"].any() else np.nan,
            "big_sec_r0_ex": float(r0.loc[~r0["small_sec_fallback"], "fwd_ret_1m"].mean() - r_ew) if (~r0["small_sec_fallback"]).any() else np.nan,
        })

    mdf = pd.DataFrame(monthly_rows).set_index("date").sort_index()
    sdf = pd.DataFrame(sec_month_rows)

    out = {"by_window": {}, "top_sectors_by_block": {}}
    for wname, s, e in ALL_WINDOWS:
        sub = mdf.loc[wmask(mdf.index, s, e)]
        out["by_window"][wname] = {
            "active_gross": nw_stat(sub["active_gross"]),
            "allocation": nw_stat(sub["alloc"]),
            "selection": nw_stat(sub["sel"]),
            "mean_hhi_p": round(float(sub["hhi_p"].mean()), 4),
            "mean_hhi_b": round(float(sub["hhi_b"].mean()), 4),
            "eff_n_sec_p": round(float(sub["eff_n_sec_p"].mean()), 1),
            "eff_n_sec_b": round(float(sub["eff_n_sec_b"].mean()), 1),
            "mean_max_sec_w_p_pct": round(100 * float(sub["max_sec_w_p"].mean()), 1),
            "small_sec_w_p_pct": round(100 * float(sub["small_sec_w_p"].mean()), 1),
            "small_sec_w_b_pct": round(100 * float(sub["small_sec_w_b"].mean()), 1),
            "small_sec_r0_ex": nw_stat(sub["small_sec_r0_ex"]),
            "big_sec_r0_ex": nw_stat(sub["big_sec_r0_ex"]),
        }

    for wname, s, e in [*BLOCKS, ("Full", "2013-04-01", "2099-12-31")]:
        sub_s = sdf[wmask(sdf["date"], s, e)]
        n_m = sub_s["date"].nunique()
        agg = sub_s.groupby("sector").agg(
            w_p_pct=("w_p", lambda x: 100 * x.sum() / n_m),
            w_b_pct=("w_b", lambda x: 100 * x.sum() / n_m),
            active_w_pct=("active_w", lambda x: 100 * x.sum() / n_m),
            alloc_ann_pct=("alloc", lambda x: 1200 * x.sum() / n_m),
            sel_ann_pct=("sel", lambda x: 1200 * x.sum() / n_m),
            total_ann_pct=("total_contrib", lambda x: 1200 * x.sum() / n_m),
            mean_count=("sec_count", "mean"),
        ).round(2)
        out["top_sectors_by_block"][wname] = {
            "most_overweight": agg.sort_values("active_w_pct", ascending=False).head(7).to_dict(orient="index"),
            "most_underweight": agg.sort_values("active_w_pct", ascending=True).head(5).to_dict(orient="index"),
            "top_contributors": agg.sort_values("total_ann_pct", ascending=False).head(6).to_dict(orient="index"),
            "worst_detractors": agg.sort_values("total_ann_pct", ascending=True).head(6).to_dict(orient="index"),
        }
    return out


def compute_size_and_style_attribution(df: pd.DataFrame) -> dict:
    """Size terciles Brinson attribution + style exposures (vol60, mom, str_1m, size, nsi) of R0 vs EW."""
    valid = df.dropna(subset=["value_sn_z", "fwd_ret_1m"]).copy()
    valid["size_terc"] = valid.groupby("date")["mcap"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["Small", "Mid", "Large"])
    )
    valid["liq_terc"] = valid.groupby("date")["tlvol60"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["LowLiq", "MidLiq", "HighLiq"])
    )

    m_rows = []
    style_cols = ["size_z", "vol60_z", "mom_12_1_z", "str_1m_z", "gpa_z", "roe_z", "nsi_rights_12m_z",
                  "bm_sn_z", "ep_sn_z", "sp_sn_z", "ey_sn_z"]
    for dt, g in valid.groupby("date"):
        r0 = g[g["in_r0"]]
        r_ew = float(g["fwd_ret_1m"].mean())
        row = {"date": dt}
        # Size Brinson
        alloc_sz, sel_sz = 0.0, 0.0
        for sz in ("Small", "Mid", "Large"):
            gs = g[g["size_terc"] == sz]
            rs_p = gs[gs["in_r0"]]
            wb = len(gs) / len(g)
            wp = len(rs_p) / len(r0)
            rb = float(gs["fwd_ret_1m"].mean())
            rp = float(rs_p["fwd_ret_1m"].mean()) if len(rs_p) else rb
            alloc_sz += (wp - wb) * (rb - r_ew)
            sel_sz += wp * (rp - rb)
            row[f"w_{sz}"] = wp
            row[f"ex_vs_terc_{sz}"] = (rp - rb) if len(rs_p) else np.nan
            row[f"ex_vs_ew_{sz}"] = (rp - r_ew) if len(rs_p) else np.nan
            row[f"contrib_{sz}"] = (wp - wb) * (rb - r_ew) + wp * (rp - rb)
        row["size_alloc"] = alloc_sz
        row["size_sel"] = sel_sz

        for lq in ("LowLiq", "MidLiq", "HighLiq"):
            gs = g[g["liq_terc"] == lq]
            rs_p = gs[gs["in_r0"]]
            row[f"w_{lq}"] = len(rs_p) / len(r0)
            row[f"ex_vs_terc_{lq}"] = float(rs_p["fwd_ret_1m"].mean() - gs["fwd_ret_1m"].mean()) if len(rs_p) else np.nan

        for sc in style_cols:
            if sc in g.columns:
                row[f"exp_{sc}"] = float(r0[sc].mean() - g[sc].mean())
        m_rows.append(row)

    mdf = pd.DataFrame(m_rows).set_index("date").sort_index()
    out = {}
    for wname, s, e in ALL_WINDOWS:
        sub = mdf.loc[wmask(mdf.index, s, e)]
        entry = {
            "size_alloc": nw_stat(sub["size_alloc"]),
            "size_sel": nw_stat(sub["size_sel"]),
            "size_terciles": {
                sz: {
                    "w_r0_pct": round(100 * float(sub[f"w_{sz}"].mean()), 1),
                    "ex_vs_own_terc": nw_stat(sub[f"ex_vs_terc_{sz}"]),
                    "contrib": nw_stat(sub[f"contrib_{sz}"]),
                }
                for sz in ("Small", "Mid", "Large")
            },
            "liq_terciles": {
                lq: {
                    "w_r0_pct": round(100 * float(sub[f"w_{lq}"].mean()), 1),
                    "ex_vs_own_terc": nw_stat(sub[f"ex_vs_terc_{lq}"]),
                }
                for lq in ("LowLiq", "MidLiq", "HighLiq")
            },
            "style_loadings_z": {
                sc: round(float(sub[f"exp_{sc}"].mean()), 3)
                for sc in style_cols if f"exp_{sc}" in sub
            },
        }
        out[wname] = entry
    return out


def compute_construction_defects(df: pd.DataFrame, quarterly: pd.DataFrame, macro: pd.DataFrame) -> dict:
    """Audit concrete defects of value_sn_z construction:
      1) Missing-leg & negative-ep/ey inclusion in R0 top-20%
      2) Sector std dispersion skew (why unscaled sector_neutralize overweights volatile sectors)
      3) CPI-unit / statement-age mismatch in cross-section
      4) Leg variance contribution & correlation matrix
    """
    valid = df.dropna(subset=["value_sn_z", "fwd_ret_1m"]).copy()
    valid["ew_ret"] = valid.groupby("date")["fwd_ret_1m"].transform("mean")
    valid["ex_ret"] = valid["fwd_ret_1m"] - valid["ew_ret"]

    # 1. Missing legs & loss-makers inside R0 top-20%
    def_rows = []
    for dt, g in valid.groupby("date"):
        r0 = g[g["in_r0"]]
        r_ew = float(g["fwd_ret_1m"].mean())
        row = {
            "date": dt,
            "r0_lt4_legs_pct": float((r0["n_legs_valid"] < 4).mean()),
            "univ_lt4_legs_pct": float((g["n_legs_valid"] < 4).mean()),
            "r0_ep_neg_pct": float((r0["ep"] < 0).mean()),
            "univ_ep_neg_pct": float((g["ep"] < 0).mean()),
            "r0_ey_neg_pct": float((r0["ey"] < 0).mean()),
            "univ_ey_neg_pct": float((g["ey"] < 0).mean()),
            "r0_bm_na_pct": float(r0["bm"].isna().mean()),
            "r0_ey_na_pct": float(r0["ey"].isna().mean()),
            "r0_ep_na_pct": float(r0["ep"].isna().mean()),
            "r0_sp_na_pct": float(r0["sp"].isna().mean()),
            # Returns of defective pockets inside R0
            "ret_r0_4legs": float(r0.loc[r0["n_legs_valid"] == 4, "ex_ret"].mean()) if (r0["n_legs_valid"] == 4).any() else np.nan,
            "ret_r0_lt4legs": float(r0.loc[r0["n_legs_valid"] < 4, "ex_ret"].mean()) if (r0["n_legs_valid"] < 4).any() else np.nan,
            "ret_r0_ep_pos": float(r0.loc[r0["ep"] > 0, "ex_ret"].mean()) if (r0["ep"] > 0).any() else np.nan,
            "ret_r0_ep_neg": float(r0.loc[r0["ep"] < 0, "ex_ret"].mean()) if (r0["ep"] < 0).any() else np.nan,
            "ret_r0_ey_pos": float(r0.loc[r0["ey"] > 0, "ex_ret"].mean()) if (r0["ey"] > 0).any() else np.nan,
            "ret_r0_ey_neg": float(r0.loc[r0["ey"] < 0, "ex_ret"].mean()) if (r0["ey"] < 0).any() else np.nan,
            "corr_age_vsn": float(g["stmt_age_days"].corr(g["value_sn_z"])) if g["stmt_age_days"].nunique() > 1 else np.nan,
            "age_std_days": float(g["stmt_age_days"].std()),
            "age_p90_m_p10": float(g["stmt_age_days"].quantile(0.9) - g["stmt_age_days"].quantile(0.1)),
            "age_r0_mean": float(r0["stmt_age_days"].mean()),
            "age_univ_mean": float(g["stmt_age_days"].mean()),
        }
        def_rows.append(row)
    ddf = pd.DataFrame(def_rows).set_index("date").sort_index()

    # 2. Sector dispersion vs R0 selection rate (for sectors with >=5 stocks)
    big_sec = valid[valid["sec_count"] >= 5]
    sec_disp = big_sec.groupby(["date", "sector"]).agg(
        sec_std=("value_z", "std"),
        r0_rate=("in_r0", "mean"),
        n=("ticker", "count"),
    ).reset_index()
    disp_corr = float(sec_disp["sec_std"].corr(sec_disp["r0_rate"]))
    sec_disp_summary = sec_disp.groupby("sector").agg(
        months=("date", "count"),
        mean_std=("sec_std", "mean"),
        mean_r0_rate_pct=("r0_rate", lambda x: 100 * x.mean()),
    ).query("months >= 24").sort_values("mean_std", ascending=False).round(2)

    # 3. Leg correlation & skewness in value_sn_z
    leg_corrs = {}
    for wname, s, e in ALL_WINDOWS:
        sub = valid[wmask(valid["date"], s, e)]
        c_vs_vsn = {leg: round(float(sub[f"{leg}_sn_z"].corr(sub["value_sn_z"])), 3) for leg in LEGS}
        skew_legs = {leg: round(float(sub[f"{leg}_z"].skew()), 2) for leg in LEGS}
        leg_corrs[wname] = {"corr_with_value_sn": c_vs_vsn, "z_skew": skew_legs}

    # 4. CPI-age inflation distortion magnitude: CPI(date) / CPI(stmt_period_end) - 1
    mac = macro.copy()
    if not isinstance(mac.index, pd.PeriodIndex):
        mac.index = pd.to_datetime(mac.index).to_period("M")
    cpi_idx = (1.0 + mac["cpi_mom"].fillna(0.0) / 100.0).cumprod()
    valid["cpi_date"] = valid["date"].dt.to_period("M").map(cpi_idx)
    valid["cpi_stmt"] = valid["stmt_period_end"].dt.to_period("M").map(cpi_idx)
    valid["cpi_drift_pct"] = 100.0 * (valid["cpi_date"] / valid["cpi_stmt"] - 1.0)
    cpi_drift_by_win = {}
    for wname, s, e in ALL_WINDOWS:
        sub = valid[wmask(valid["date"], s, e)]
        g_spread = sub.groupby("date")["cpi_drift_pct"].agg(
            mean="mean",
            p90_p10=lambda x: x.quantile(0.9) - x.quantile(0.1),
            std="std",
        )
        cpi_drift_by_win[wname] = {
            "mean_cpi_drift_pct": round(float(g_spread["mean"].mean()), 1),
            "mean_xsec_p90_p10_pct": round(float(g_spread["p90_p10"].mean()), 1),
            "mean_xsec_std_pct": round(float(g_spread["std"].mean()), 1),
        }

    by_win = {}
    for wname, s, e in ALL_WINDOWS:
        sub = ddf.loc[wmask(ddf.index, s, e)]
        by_win[wname] = {
            "r0_lt4_legs_pct": round(100 * float(sub["r0_lt4_legs_pct"].mean()), 1),
            "univ_lt4_legs_pct": round(100 * float(sub["univ_lt4_legs_pct"].mean()), 1),
            "r0_ep_neg_pct": round(100 * float(sub["r0_ep_neg_pct"].mean()), 1),
            "univ_ep_neg_pct": round(100 * float(sub["univ_ep_neg_pct"].mean()), 1),
            "r0_ey_neg_pct": round(100 * float(sub["r0_ey_neg_pct"].mean()), 1),
            "univ_ey_neg_pct": round(100 * float(sub["univ_ey_neg_pct"].mean()), 1),
            "r0_ey_na_pct": round(100 * float(sub["r0_ey_na_pct"].mean()), 1),
            "r0_bm_na_pct": round(100 * float(sub["r0_bm_na_pct"].mean()), 1),
            "ret_r0_4legs": nw_stat(sub["ret_r0_4legs"]),
            "ret_r0_lt4legs": nw_stat(sub["ret_r0_lt4legs"]),
            "ret_r0_ep_pos": nw_stat(sub["ret_r0_ep_pos"]),
            "ret_r0_ep_neg": nw_stat(sub["ret_r0_ep_neg"]),
            "ret_r0_ey_pos": nw_stat(sub["ret_r0_ey_pos"]),
            "ret_r0_ey_neg": nw_stat(sub["ret_r0_ey_neg"]),
            "age_r0_mean_days": round(float(sub["age_r0_mean"].mean()), 1),
            "age_univ_mean_days": round(float(sub["age_univ_mean"].mean()), 1),
            "age_p90_p10_days": round(float(sub["age_p90_m_p10"].mean()), 1),
            "corr_age_vsn": round(float(sub["corr_age_vsn"].mean()), 3),
        }

    return {
        "by_window": by_win,
        "sector_std_vs_r0_rate_corr": round(disp_corr, 3),
        "sector_dispersion_top10": sec_disp_summary.head(10).to_dict(orient="index"),
        "sector_dispersion_bot6": sec_disp_summary.tail(6).to_dict(orient="index"),
        "leg_corrs_and_skew": leg_corrs,
        "cpi_unit_drift": cpi_drift_by_win,
    }


def compute_ias29_seam_diagnostics(df_lag75: pd.DataFrame, df_kap: pd.DataFrame,
                                   quarterly: pd.DataFrame, reexpr: pd.DataFrame) -> dict:
    """Deep-dive into IAS 29 seam quarters (2023Q4-2024Q4) and post-seam (2025+)."""
    # 1. Quarterly jump from 2023Q3 -> 2023Q4 -> 2024Q1 -> 2024Q4 in quarterly.parquet
    q = quarterly.copy()
    q["eq"] = q["equity_parent"].fillna(q["equity"])
    q["ttm_ni"] = q["ttm_ni_parent"].fillna(q["ttm_net_income"])
    seam_periods = ["2023Q2", "2023Q3", "2023Q4", "2024Q1", "2024Q2", "2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q4"]
    q_sub = q[q["period"].isin(seam_periods)]

    # Pairwise QoQ median ratios across consecutive periods
    qoq_jumps = {}
    for p0, p1 in zip(seam_periods[:-1], seam_periods[1:]):
        a = q_sub[q_sub["period"] == p0].set_index("ticker")
        b = q_sub[q_sub["period"] == p1].set_index("ticker")
        common = a.index.intersection(b.index)
        if len(common) < 20:
            continue
        item_stats = {}
        for col in ["eq", "total_assets", "ttm_revenue", "ttm_op_profit", "ttm_ni", "q_op_profit", "q_ni_parent"]:
            va = a.loc[common, col]
            vb = b.loc[common, col]
            pos = (va > 0) & (vb > 0) & np.isfinite(va) & np.isfinite(vb)
            ratio = (vb[pos] / va[pos])
            # Sign flip rate (pos -> neg)
            flip_neg = ((va > 0) & (vb <= 0)).sum() / max(1, (va > 0).sum())
            item_stats[col] = {
                "n_pos_both": int(pos.sum()),
                "med_ratio": round(float(ratio.median()), 3) if len(ratio) else None,
                "p75_ratio": round(float(ratio.quantile(0.75)), 3) if len(ratio) else None,
                "p25_ratio": round(float(ratio.quantile(0.25)), 3) if len(ratio) else None,
                "pos_to_neg_pct": round(100 * float(flip_neg), 1),
                "nan_rate_p1_pct": round(100 * float(b[col].isna().mean()), 1),
            }
        qoq_jumps[f"{p0}->{p1}"] = item_stats

    # 2. Month-by-month 2023-07 .. 2026-08: fraction on IAS29 (>=2023Q4), R0 gross active, leg ICs
    def _monthly_seam(df: pd.DataFrame) -> list[dict]:
        sub = df[(df["date"] >= "2023-07-01") & df["fwd_ret_1m"].notna()].copy()
        sub["is_ias29_stmt"] = sub["stmt_period"] >= "2023Q4"
        rows = []
        for dt, g in sub.groupby("date"):
            r0 = g[g["in_r0"]]
            r_ew = float(g["fwd_ret_1m"].mean())
            r_p = float(r0["fwd_ret_1m"].mean())
            ic_vsn = float(g["value_sn_z"].rank().corr(g["fwd_ret_1m"].rank()))
            leg_ics = {leg: round(float(g[f"{leg}_sn_z"].rank().corr(g["fwd_ret_1m"].rank())), 3) for leg in LEGS}
            # Split R0 picks by IAS29 stmt vs pre-IAS29 stmt during mixed months
            ias_frac_univ = float(g["is_ias29_stmt"].mean())
            ias_frac_r0 = float(r0["is_ias29_stmt"].mean())
            rows.append({
                "date": str(dt.date()),
                "n_univ": int(len(g)),
                "ias29_univ_pct": round(100 * ias_frac_univ, 1),
                "ias29_r0_pct": round(100 * ias_frac_r0, 1),
                "r0_active_pct": round(100 * (r_p - r_ew), 2),
                "ic_vsn": round(ic_vsn, 3),
                **{f"ic_{k}": v for k, v in leg_ics.items()},
                "med_bm_univ": round(float(g["bm"].median()), 3),
                "med_ep_univ": round(float(g["ep"].median()), 3),
                "med_ey_univ": round(float(g["ey"].median()), 3),
            })
        return rows

    seam_lag75 = _monthly_seam(df_lag75)
    seam_kap = _monthly_seam(df_kap)

    # 3. Sub-period split of 2024+:
    #    - Seam transition: 2024-01 .. 2024-12 (or 2024-04 .. 2025-04 covering 2023Q4..2024Q4 filings)
    #    - Post-seam steady-state IAS29: 2025-05 .. 2026-08
    sub_2024_phases = {}
    for pname, ps, pe in [
        ("Pre_IAS29_2023", "2023-01-01", "2024-03-31"),
        ("Seam_2024_04_to_2025_04", "2024-04-01", "2025-04-30"),
        ("PostSeam_2025_05_plus", "2025-05-01", "2099-12-31"),
    ]:
        sub = df_lag75[wmask(df_lag75["date"], ps, pe)].dropna(subset=["fwd_ret_1m"])
        m_act = sub.groupby("date").apply(lambda g: float(g.loc[g["in_r0"], "fwd_ret_1m"].mean() - g["fwd_ret_1m"].mean()))
        leg_ic_map = {leg: nw_stat(fb.rank_ic(sub, f"{leg}_sn_z", "fwd_ret_1m"), scale=1.0) for leg in LEGS}
        sub_2024_phases[pname] = {
            "r0_gross_active": nw_stat(m_act),
            "vsn_ic": nw_stat(fb.rank_ic(sub, "value_sn_z", "fwd_ret_1m"), scale=1.0),
            "leg_ics": leg_ic_map,
        }

    # 4. Reexpression class breakdown in 2024+ (reexpressed vs not_reexpressed vs unknown)
    rc_map = dict(zip(reexpr["ticker"], reexpr["cls"]))
    d24 = df_lag75[(df_lag75["date"] >= "2024-01-01") & df_lag75["fwd_ret_1m"].notna()].copy()
    d24["reexpr_cls"] = d24["ticker"].map(rc_map).fillna("unclassified")
    d24["ew_ret"] = d24.groupby("date")["fwd_ret_1m"].transform("mean")
    d24["ex_ret"] = d24["fwd_ret_1m"] - d24["ew_ret"]

    reexpr_diag = {}
    for cls_name, g in d24.groupby("reexpr_cls"):
        m_all = g.groupby("date")["ex_ret"].mean()
        g_r0 = g[g["in_r0"]]
        m_r0 = g_r0.groupby("date")["ex_ret"].mean()
        reexpr_diag[cls_name] = {
            "n_tickers": int(g["ticker"].nunique()),
            "univ_share_pct": round(100 * len(g) / len(d24), 1),
            "r0_share_pct": round(100 * len(g_r0) / max(1, int(d24["in_r0"].sum())), 1),
            "r0_selection_rate_pct": round(100 * float(g["in_r0"].mean()), 1),
            "mean_vsn_z": round(float(g["value_sn_z"].mean()), 3),
            "mean_bm_sn_z": round(float(g["bm_sn_z"].mean()), 3),
            "mean_ep_sn_z": round(float(g["ep_sn_z"].mean()), 3),
            "mean_ey_sn_z": round(float(g["ey_sn_z"].mean()), 3),
            "univ_ex_ret": nw_stat(m_all),
            "r0_ex_ret": nw_stat(m_r0),
        }

    return {
        "qoq_statement_jumps": qoq_jumps,
        "monthly_seam_lag75": seam_lag75,
        "monthly_seam_kapdates": seam_kap,
        "phases_2023_2026": sub_2024_phases,
        "reexpression_class_2024_plus": reexpr_diag,
    }


def compute_staleness_attribution(df_lag75: pd.DataFrame, df_kap: pd.DataFrame,
                                  sim_lag75: pd.DataFrame, sim_kap: pd.DataFrame) -> dict:
    """Compare lag75 vs kapdates across blocks, and inspect fresh vs stale statement subsets."""
    # 1. Paired portfolio diff (kapdates - lag75) across blocks
    port_cmp = {}
    for wname, s, e in ALL_WINDOWS:
        c_idx = sim_lag75.index.intersection(sim_kap.index)
        c_idx = c_idx[wmask(c_idx, s, e)]
        d_kap_minus_l75 = sim_kap.loc[c_idx, "active_ew_net"] - sim_lag75.loc[c_idx, "active_ew_net"]
        port_cmp[wname] = {
            "lag75_vs_ew_net": nw_stat(sim_lag75.loc[c_idx, "active_ew_net"]),
            "kapdates_vs_ew_net": nw_stat(sim_kap.loc[c_idx, "active_ew_net"]),
            "kap_minus_lag75": nw_stat(d_kap_minus_l75),
        }

    # 2. Row-level merge of lag75 & kapdates on (date, ticker)
    cols = ["date", "ticker", "stmt_period", "stmt_age_days", "value_sn_z", "in_r0", "fwd_ret_1m"]
    m = df_lag75[cols].merge(df_kap[cols], on=["date", "ticker"], suffixes=("_l75", "_kap"))
    m = m.dropna(subset=["fwd_ret_1m_l75"])
    m["ew_ret"] = m.groupby("date")["fwd_ret_1m_l75"].transform("mean")
    m["ex_ret"] = m["fwd_ret_1m_l75"] - m["ew_ret"]
    m["kap_fresher"] = m["stmt_period_kap"] > m["stmt_period_l75"]
    m["l75_fresher_lookahead"] = m["stmt_period_l75"] > m["stmt_period_kap"]  # lag75 ahead of actual KAP!
    m["same_stmt"] = m["stmt_period_kap"] == m["stmt_period_l75"]

    rows = []
    for dt, g in m.groupby("date"):
        s_l75 = set(g.loc[g["in_r0_l75"], "ticker"])
        s_kap = set(g.loc[g["in_r0_kap"], "ticker"])
        if not s_l75:
            continue
        kap_only = g[g["in_r0_kap"] & ~g["in_r0_l75"]]
        l75_only = g[g["in_r0_l75"] & ~g["in_r0_kap"]]
        rows.append({
            "date": dt,
            "overlap_pct": 100.0 * len(s_l75 & s_kap) / len(s_l75),
            "kap_fresher_pct": 100.0 * float(g["kap_fresher"].mean()),
            "l75_ahead_pct": 100.0 * float(g["l75_fresher_lookahead"].mean()),
            "mean_age_l75": float(g["stmt_age_days_l75"].mean()),
            "mean_age_kap": float(g["stmt_age_days_kap"].mean()),
            "kap_only_minus_l75_only": float(kap_only["ex_ret"].mean() - l75_only["ex_ret"].mean()) if (len(kap_only) and len(l75_only)) else 0.0,
            "n_kap_only": len(kap_only),
        })
    sdf = pd.DataFrame(rows).set_index("date").sort_index()

    # 3. Within-panel staleness: fresh report (new stmt_period vs t-1) vs stale report in R0
    for tag, dpanel in (("lag75", df_lag75), ("kapdates", df_kap)):
        d = dpanel.sort_values(["ticker", "date"]).copy()
        d["prev_stmt"] = d.groupby("ticker")["stmt_period"].shift(1)
        d["is_new_stmt"] = (d["stmt_period"] != d["prev_stmt"]) & d["prev_stmt"].notna()
        d["ew_ret"] = d.groupby("date")["fwd_ret_1m"].transform("mean")
        d["ex_ret"] = d["fwd_ret_1m"] - d["ew_ret"]
        d["age_med"] = d.groupby("date")["stmt_age_days"].transform("median")
        d["is_older_half"] = d["stmt_age_days"] > d["age_med"]
        if tag == "lag75":
            d_l75_fresh = d
        else:
            d_kap_fresh = d

    panel_cmp = {}
    for wname, s, e in ALL_WINDOWS:
        sub = sdf.loc[wmask(sdf.index, s, e)]
        # Fresh vs Carried-over inside R0 on kapdates & lag75
        dl = d_l75_fresh[wmask(d_l75_fresh["date"], s, e) & d_l75_fresh["in_r0"]].dropna(subset=["ex_ret"])
        dk = d_kap_fresh[wmask(d_kap_fresh["date"], s, e) & d_kap_fresh["in_r0"]].dropna(subset=["ex_ret"])
        panel_cmp[wname] = {
            "top20_overlap_pct": round(float(sub["overlap_pct"].mean()), 1),
            "kap_fresher_rows_pct": round(float(sub["kap_fresher_pct"].mean()), 1),
            "l75_ahead_of_kap_rows_pct": round(float(sub["l75_ahead_pct"].mean()), 1),
            "mean_age_l75_days": round(float(sub["mean_age_l75"].mean()), 1),
            "mean_age_kap_days": round(float(sub["mean_age_kap"].mean()), 1),
            "kap_only_minus_l75_only": nw_stat(sub["kap_only_minus_l75_only"]),
            "l75_r0_new_stmt_ex": nw_stat(dl[dl["is_new_stmt"]].groupby("date")["ex_ret"].mean()),
            "l75_r0_old_stmt_ex": nw_stat(dl[~dl["is_new_stmt"]].groupby("date")["ex_ret"].mean()),
            "kap_r0_new_stmt_ex": nw_stat(dk[dk["is_new_stmt"]].groupby("date")["ex_ret"].mean()),
            "kap_r0_old_stmt_ex": nw_stat(dk[~dk["is_new_stmt"]].groupby("date")["ex_ret"].mean()),
        }

    # Check specific 2024 months where lag75 was ahead of actual KAP dates!
    l75_ahead_2024 = sdf.loc["2024-01-01":"2025-06-30", ["kap_fresher_pct", "l75_ahead_pct", "overlap_pct", "mean_age_l75", "mean_age_kap"]].round(1)

    return {
        "portfolio_comparison": port_cmp,
        "panel_staleness": panel_cmp,
        "l75_ahead_2024_monthly": {str(idx.date()): row.to_dict() for idx, row in l75_ahead_2024.iterrows()},
    }


def compute_entrants_holdings_exits(df: pd.DataFrame) -> dict:
    """Decompose R0 monthly portfolio into Entrants (Price-driven vs Filing-driven),
    Incumbent Holdings (by tenure: 1-2m, 3-6m, 7+m), and Exits/Dropouts, plus boundary churn."""
    d = df.sort_values(["ticker", "date"]).copy()
    d["ew_ret"] = d.groupby("date")["fwd_ret_1m"].transform("mean")
    d["ex_ret"] = d["fwd_ret_1m"] - d["ew_ret"]

    months = sorted(d["date"].unique())
    by_m = {dt: g.set_index("ticker") for dt, g in d.groupby("date")}

    tenure: dict[str, int] = {}
    prev_set: set[str] = set()
    prev_prev_set: set[str] = set()
    prev_stmt: dict[str, str] = {}

    rows = []
    for i, dt in enumerate(months):
        g = by_m[dt]
        cur_set = set(g.index[g["in_r0"]])
        if i == 0:
            prev_set = cur_set
            for tk in cur_set:
                tenure[tk] = 1
            prev_stmt = g["stmt_period"].to_dict()
            continue

        entrants = cur_set - prev_set
        holdings = cur_set & prev_set
        exits = (prev_set - cur_set) & set(g.index)  # still in liquid universe

        # Split entrants into filing-driven (stmt_period changed) vs price-driven (same stmt_period)
        ent_filing = {tk for tk in entrants if prev_stmt.get(tk) is not None and g.at[tk, "stmt_period"] != prev_stmt.get(tk)}
        ent_price = {tk for tk in entrants if prev_stmt.get(tk) is not None and g.at[tk, "stmt_period"] == prev_stmt.get(tk)}
        # Flicker re-entrants: were in R0 2 months ago, dropped at t-1, re-entered at t
        ent_flicker = entrants & prev_prev_set

        # Update tenure
        new_tenure = {}
        for tk in cur_set:
            new_tenure[tk] = tenure.get(tk, 0) + 1 if tk in holdings else 1
        tenure = new_tenure

        hold_short = {tk for tk in holdings if 2 <= tenure[tk] <= 3}
        hold_mid = {tk for tk in holdings if 4 <= tenure[tk] <= 6}
        hold_long = {tk for tk in holdings if tenure[tk] >= 7}

        # Exits split: rally exits (str_1m > 0 & same stmt) vs deterioration/other
        ex_filing = {tk for tk in exits if prev_stmt.get(tk) is not None and g.at[tk, "stmt_period"] != prev_stmt.get(tk)}
        ex_price = {tk for tk in exits if prev_stmt.get(tk) is not None and g.at[tk, "stmt_period"] == prev_stmt.get(tk)}

        def _mean_ex(tks: set[str]) -> float:
            if not tks:
                return np.nan
            s = g.loc[list(tks), "ex_ret"].dropna()
            return float(s.mean()) if len(s) else np.nan

        def _mean_col(tks: set[str], col: str) -> float:
            if not tks or col not in g.columns:
                return np.nan
            s = g.loc[list(tks), col].dropna()
            return float(s.mean()) if len(s) else np.nan

        n_cur = max(1, len(cur_set))
        rows.append({
            "date": dt,
            "n_r0": len(cur_set),
            "w_entrants": len(entrants) / n_cur,
            "w_ent_price": len(ent_price) / n_cur,
            "w_ent_filing": len(ent_filing) / n_cur,
            "w_ent_flicker": len(ent_flicker) / max(1, len(entrants)),
            "w_holdings": len(holdings) / n_cur,
            "w_hold_long": len(hold_long) / n_cur,
            "ex_r0": _mean_ex(cur_set),
            "ex_entrants": _mean_ex(entrants),
            "ex_ent_price": _mean_ex(ent_price),
            "ex_ent_filing": _mean_ex(ent_filing),
            "ex_holdings": _mean_ex(holdings),
            "ex_hold_short": _mean_ex(hold_short),
            "ex_hold_mid": _mean_ex(hold_mid),
            "ex_hold_long": _mean_ex(hold_long),
            "ex_exits": _mean_ex(exits),
            "ex_exits_price": _mean_ex(ex_price),
            "ex_exits_filing": _mean_ex(ex_filing),
            "ent_minus_exits": _mean_ex(entrants) - _mean_ex(exits) if (entrants and exits) else np.nan,
            "ent_price_str1m": _mean_col(ent_price, "str_1m"),
            "ent_price_mom12": _mean_col(ent_price, "mom_12_1"),
            "ent_filing_str1m": _mean_col(ent_filing, "str_1m"),
            "ent_rank_pct": _mean_col(entrants, "r0_pct_rank"),
            "hold_rank_pct": _mean_col(holdings, "r0_pct_rank"),
        })

        prev_prev_set = prev_set
        prev_set = cur_set
        prev_stmt = g["stmt_period"].to_dict()

    edf = pd.DataFrame(rows).set_index("date").sort_index()
    out = {}
    for wname, s, e in ALL_WINDOWS:
        sub = edf.loc[wmask(edf.index, s, e)]
        out[wname] = {
            "w_entrants_pct": round(100 * float(sub["w_entrants"].mean()), 1),
            "w_ent_price_pct": round(100 * float(sub["w_ent_price"].mean()), 1),
            "w_ent_filing_pct": round(100 * float(sub["w_ent_filing"].mean()), 1),
            "flicker_share_of_entrants_pct": round(100 * float(sub["w_ent_flicker"].mean()), 1),
            "w_hold_long_7m_plus_pct": round(100 * float(sub["w_hold_long"].mean()), 1),
            "ex_entrants": nw_stat(sub["ex_entrants"]),
            "ex_ent_price": nw_stat(sub["ex_ent_price"]),
            "ex_ent_filing": nw_stat(sub["ex_ent_filing"]),
            "ex_holdings": nw_stat(sub["ex_holdings"]),
            "ex_hold_2_3m": nw_stat(sub["ex_hold_short"]),
            "ex_hold_4_6m": nw_stat(sub["ex_hold_mid"]),
            "ex_hold_7m_plus": nw_stat(sub["ex_hold_long"]),
            "ex_exits": nw_stat(sub["ex_exits"]),
            "ex_exits_price": nw_stat(sub["ex_exits_price"]),
            "ex_exits_filing": nw_stat(sub["ex_exits_filing"]),
            "ent_minus_exits": nw_stat(sub["ent_minus_exits"]),
            "ent_price_mean_str1m_pct": round(100 * float(sub["ent_price_str1m"].mean()), 2),
            "ent_price_mean_mom12_pct": round(100 * float(sub["ent_price_mom12"].mean()), 1),
            "ent_filing_mean_str1m_pct": round(100 * float(sub["ent_filing_str1m"].mean()), 2),
        }
    return out


def compute_drawdowns_and_episodes(sim_r0: pd.DataFrame) -> dict:
    """Identify worst USD drawdown episodes and worst active-vs-EW drawdown episodes."""
    p = sim_r0.copy()
    p["nav_usd"] = (1 + p["port_usd"]).cumprod()
    p["dd_usd"] = p["nav_usd"] / p["nav_usd"].cummax() - 1
    p["nav_act"] = (1 + p["active_ew_net"]).cumprod()
    p["dd_act"] = p["nav_act"] / p["nav_act"].cummax() - 1

    # Annual breakdown of R0 vs EW net and USD return
    p["year"] = p.index.year
    annual = {}
    for yr, g in p.groupby("year"):
        annual[int(yr)] = {
            "months": int(len(g)),
            "r0_tl_pct": round(100 * float((1 + g["port"]).prod() - 1), 1),
            "r0_usd_pct": round(100 * float((1 + g["port_usd"]).prod() - 1), 1),
            "ew_net_tl_pct": round(100 * float((1 + g["ew_net"]).prod() - 1), 1),
            "active_ew_net_ann_pct": round(1200 * float(g["active_ew_net"].mean()), 1),
            "active_ew_net_cum_pct": round(100 * float((1 + g["active_ew_net"]).prod() - 1), 1),
            "hit_rate_pct": round(100 * float((g["active_ew_net"] > 0).mean()), 1),
            "worst_mo_active_pct": round(100 * float(g["active_ew_net"].min()), 2),
            "best_mo_active_pct": round(100 * float(g["active_ew_net"].max()), 2),
        }

    # Worst 10 active months
    worst_act = p.nsmallest(10, "active_ew_net")[["active_ew_net", "port", "ew_net", "port_usd", "fx_ret"]]
    worst_act_list = [
        {
            "date": str(dt.date()),
            "active_ew_net_pct": round(100 * float(r["active_ew_net"]), 2),
            "port_tl_pct": round(100 * float(r["port"]), 2),
            "port_usd_pct": round(100 * float(r["port_usd"]), 2),
            "fx_ret_pct": round(100 * float(r["fx_ret"]), 2),
        }
        for dt, r in worst_act.iterrows()
    ]

    # USD drawdown peaks/troughs in full and 2021+
    def _dd_info(sub: pd.DataFrame) -> dict:
        nav = (1 + sub["port_usd"]).cumprod()
        dd = nav / nav.cummax() - 1
        trough = dd.idxmin()
        peak = nav.loc[:trough].idxmax()
        return {
            "max_dd_usd_pct": round(100 * float(dd.min()), 2),
            "peak_date": str(peak.date()),
            "trough_date": str(trough.date()),
        }

    return {
        "annual": annual,
        "worst_10_active_months": worst_act_list,
        "dd_usd_full": _dd_info(p),
        "dd_usd_2021_plus": _dd_info(p[p.index >= SPLIT]),
        "dd_usd_2024_plus": _dd_info(p[p.index >= pd.Timestamp("2024-01-01")]),
    }


def main() -> None:
    res_dir, fp_dir = resolve_data_dirs()
    fx_path = res_dir / "fx.parquet"
    macro = pd.read_parquet(res_dir / "macro_monthly.parquet")
    fx = pd.read_parquet(fx_path)
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    quarterly = pd.read_parquet(fp_dir / "quarterly.parquet")
    reexpr = pd.read_parquet(res_dir / "reexpression_class.parquet")

    _, df_l75_raw = load_prepared_panel(fp_dir / "factors_monthly.parquet", fx_path)
    _, df_kap_raw = load_prepared_panel(fp_dir / "factors_monthly_kapdates.parquet", fx_path)
    df_l75 = add_diagnostic_scores(df_l75_raw)
    df_kap = add_diagnostic_scores(df_kap_raw)

    print(f"Loaded lag75: {len(df_l75)} rows, {df_l75['date'].min().date()}..{df_l75['date'].max().date()} ({df_l75['date'].nunique()} mo)")
    print(f"Loaded kapdates: {len(df_kap)} rows, {df_kap['date'].min().date()}..{df_kap['date'].max().date()} ({df_kap['date'].nunique()} mo)")

    # Portfolio simulations (exact R0 engine: 1M TL real capital, base costs, next-close fills)
    frames_cache: dict = {}
    mkt_l75, ctx_l75 = build_sim_env(df_l75, macro, fx, res_dir / "raw", frames_cache)
    score_cols = [
        "value_sn_z", "value_z", "diag_within_sec_z",
        "bm_sn_z", "ep_sn_z", "sp_sn_z", "ey_sn_z",
        "no_bm", "no_ep", "no_sp", "no_ey",
    ]
    sims_l75 = simulate_scores(df_l75, score_cols, mkt_l75, ctx_l75)

    mkt_kap, ctx_kap = build_sim_env(df_kap, macro, fx, res_dir / "raw", frames_cache)
    kap_score_cols = ["value_sn_z", "bm_sn_z", "ep_sn_z", "sp_sn_z", "ey_sn_z", "no_bm", "no_ep", "no_sp", "no_ey"]
    sims_kap = simulate_scores(df_kap, kap_score_cols, mkt_kap, ctx_kap)

    # 1. Headline + Component Ablation (Portfolio & IC & Joint FM)
    ablation_port_l75 = {
        c: summarize_sim_windows(sims_l75[c], ref_sim=(None if c == "value_sn_z" else sims_l75["value_sn_z"]))
        for c in score_cols
    }
    ablation_port_kap = {
        c: summarize_sim_windows(sims_kap[c], ref_sim=(None if c == "value_sn_z" else sims_kap["value_sn_z"]))
        for c in kap_score_cols
    }

    # Rank-IC & Joint 4-leg Fama-MacBeth per window
    ic_cols = ["value_sn_z", "value_z", "diag_within_sec_z", "bm_sn_z", "ep_sn_z", "sp_sn_z", "ey_sn_z",
               "no_bm", "no_ep", "no_sp", "no_ey"]
    ics = {c: fb.rank_ic(df_l75, c, "fwd_ret_1m") for c in ic_cols}
    ic_by_win = {}
    for c in ic_cols:
        ic_by_win[c] = {wname: nw_stat(ics[c][wmask(ics[c].index, s, e)], scale=1.0) for wname, s, e in ALL_WINDOWS}

    sn_legs = [f"{leg}_sn_z" for leg in LEGS]
    fm_joint = fb.fama_macbeth(df_l75, sn_legs, "fwd_ret_1m")
    fm_by_win = {}
    for wname, s, e in ALL_WINDOWS:
        sub = fm_joint.loc[wmask(fm_joint.index, s, e)]
        fm_by_win[wname] = {leg: nw_stat(sub[f"{leg}_sn_z"]) for leg in LEGS}

    # Switcher overlap for LOO vs R0
    loo_switchers = {}
    for c in ["value_z", "diag_within_sec_z", "no_bm", "no_ep", "no_sp", "no_ey"]:
        sw = switcher_and_overlap(df_l75, c, "value_sn_z")
        loo_switchers[c] = {}
        for wname, s, e in ALL_WINDOWS:
            sub = sw.loc[wmask(sw.index, s, e)]
            loo_switchers[c][wname] = {
                "overlap_pct": round(100 * float(sub["overlap"].mean()), 1),
                "ent_minus_drop": nw_stat(sub["switch_spread"]),
            }

    # 2..9 Other modules
    macro_blocks = compute_macro_blocks(macro, fx, sims_l75["value_sn_z"].index)
    tail_profile = compute_quintile_and_tail_profile(df_l75)
    sector_attr = compute_sector_attribution(df_l75)
    size_style = compute_size_and_style_attribution(df_l75)
    defects = compute_construction_defects(df_l75, quarterly, macro)
    ias29 = compute_ias29_seam_diagnostics(df_l75, df_kap, quarterly, reexpr)
    staleness = compute_staleness_attribution(df_l75, df_kap, sims_l75["value_sn_z"], sims_kap["value_sn_z"])
    entrants = compute_entrants_holdings_exits(df_l75)
    entrants_kap = compute_entrants_holdings_exits(df_kap)
    drawdowns = compute_drawdowns_and_episodes(sims_l75["value_sn_z"])

    report = {
        "as_of": AS_OF,
        "panel_lag75_months": [str(sims_l75["value_sn_z"].index.min().date()), str(sims_l75["value_sn_z"].index.max().date()), int(len(sims_l75["value_sn_z"]))],
        "panel_kap_months": [str(sims_kap["value_sn_z"].index.min().date()), str(sims_kap["value_sn_z"].index.max().date()), int(len(sims_kap["value_sn_z"]))],
        "macro_blocks": macro_blocks,
        "ablation_portfolio_lag75": ablation_port_l75,
        "ablation_portfolio_kapdates": ablation_port_kap,
        "rank_ic": ic_by_win,
        "fama_macbeth_joint": fm_by_win,
        "loo_switchers": loo_switchers,
        "quintile_tail_profile": tail_profile,
        "sector_attribution": sector_attr,
        "size_and_style": size_style,
        "construction_defects": defects,
        "ias29_seam": ias29,
        "staleness": staleness,
        "entrants_holdings_exits_lag75": entrants,
        "entrants_holdings_exits_kapdates": entrants_kap,
        "drawdowns_and_annual": drawdowns,
    }

    out_path = ROOT / "data" / "reports" / f"r4_regime_attribution_{AS_OF}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nSaved full diagnostic JSON: {out_path}")

    # Compact console summary for immediate inspection
    print("\n=== 1. R0 HEADLINE BY BLOCK (lag75 vs kapdates) ===")
    for wname, _, _ in ALL_WINDOWS:
        r = ablation_port_l75["value_sn_z"][wname]
        k = ablation_port_kap["value_sn_z"][wname]
        m = macro_blocks[wname]
        print(f"{wname:18s} ({r['months']:3d}m) | L75 vsEW {r['vs_ew_net']['mean_ann_pct']:+6.2f}% (t={r['vs_ew_net']['t']:+5.2f}) "
              f"DD_USD {r['max_dd_usd_pct']:6.1f}% TO {r['turnover_pct']:4.1f}% | "
              f"KAP vsEW {k['vs_ew_net']['mean_ann_pct']:+6.2f}% (t={k['vs_ew_net']['t']:+5.2f}) | "
              f"CPI {m['mean_cpi_yoy_pct']:4.1f}% Pol {m['mean_policy_pct']:4.1f}% RealPol {m['mean_real_policy_pct']:+5.1f}%")

    print("\n=== 2. COMPONENT ABLATION: PAIRED D vs R0 (lag75, %/yr (NW t)) ===")
    hdr = f"{'Variant':18s} | " + " | ".join(f"{b[0]:14s}" for b in BLOCKS) + " | Full"
    print(hdr)
    for c in score_cols:
        if c == "value_sn_z":
            continue
        vals = []
        for wname in [b[0] for b in BLOCKS] + ["Full"]:
            d = ablation_port_l75[c][wname]["D_vs_R0"]
            vals.append(f"{d['mean_ann_pct']:+6.2f}({d['t']:+5.2f})")
        print(f"{c:18s} | " + " | ".join(vals))

    print("\n=== 3. JOINT 4-LEG FAMA-MACBETH (ann %/yr (NW t)) ===")
    for wname in [b[0] for b in BLOCKS] + ["Full", "IAS29_2024_05_plus"]:
        parts = [f"{leg}:{fm_by_win[wname][leg]['mean_ann_pct']:+6.2f}({fm_by_win[wname][leg]['t']:+5.2f})" for leg in LEGS]
        print(f"{wname:18s} | " + " | ".join(parts))

    print("\n=== 4. QUINTILE & TOP-TAIL PROFILE (gross excess vs EW %/yr) ===")
    for wname in [b[0] for b in BLOCKS] + ["Full", "IAS29_2024_05_plus"]:
        tp = tail_profile[wname]
        parts = [f"{k}:{tp[k]['mean_ann_pct']:+6.2f}" for k in ["T1_top5", "T2_5_10", "T3_10_20", "Q2_20_40", "Q5_bot20", "T1_minus_T23"]]
        print(f"{wname:18s} | " + " | ".join(parts))

    print("\n=== 5. SECTOR ATTRIBUTION (gross active = alloc + sel, %/yr) ===")
    for wname in [b[0] for b in BLOCKS] + ["Full"]:
        sa = sector_attr["by_window"][wname]
        print(f"{wname:18s} | Act {sa['active_gross']['mean_ann_pct']:+6.2f} = Alloc {sa['allocation']['mean_ann_pct']:+6.2f}({sa['allocation']['t']:+5.2f}) "
              f"+ Sel {sa['selection']['mean_ann_pct']:+6.2f}({sa['selection']['t']:+5.2f}) | "
              f"EffSec {sa['eff_n_sec_p']:4.1f} vs {sa['eff_n_sec_b']:4.1f} | SmallSec(<5) wP {sa['small_sec_w_p_pct']:4.1f}% vs wB {sa['small_sec_w_b_pct']:4.1f}% "
              f"ex={sa['small_sec_r0_ex']['mean_ann_pct']:+6.2f}")

    print("\n=== 6. SIZE ATTRIBUTION & STYLE LOADINGS ===")
    for wname in [b[0] for b in BLOCKS] + ["Full"]:
        ss = size_style[wname]
        sz = ss["size_terciles"]
        st = ss["style_loadings_z"]
        print(f"{wname:18s} | Alloc {ss['size_alloc']['mean_ann_pct']:+5.2f} Sel {ss['size_sel']['mean_ann_pct']:+5.2f} | "
              f"w(S/M/L) {sz['Small']['w_r0_pct']:4.1f}/{sz['Mid']['w_r0_pct']:4.1f}/{sz['Large']['w_r0_pct']:4.1f}% | "
              f"ex(S/M/L) {sz['Small']['ex_vs_own_terc']['mean_ann_pct']:+6.2f}/{sz['Mid']['ex_vs_own_terc']['mean_ann_pct']:+6.2f}/{sz['Large']['ex_vs_own_terc']['mean_ann_pct']:+6.2f} | "
              f"vol60_z {st['vol60_z']:+.2f} mom {st['mom_12_1_z']:+.2f} str1m {st['str_1m_z']:+.2f}")

    print("\n=== 7. ENTRANTS vs HOLDINGS vs EXITS (lag75, excess vs EW %/yr) ===")
    for wname in [b[0] for b in BLOCKS] + ["Full"]:
        en = entrants[wname]
        print(f"{wname:18s} | wEnt {en['w_entrants_pct']:4.1f}% (Px {en['w_ent_price_pct']:4.1f} Fil {en['w_ent_filing_pct']:4.1f} Flick {en['flicker_share_of_entrants_pct']:4.1f}%) | "
              f"Ent {en['ex_entrants']['mean_ann_pct']:+6.2f} (Px {en['ex_ent_price']['mean_ann_pct']:+6.2f} Fil {en['ex_ent_filing']['mean_ann_pct']:+6.2f}) | "
              f"Hold {en['ex_holdings']['mean_ann_pct']:+6.2f} (7m+ {en['ex_hold_7m_plus']['mean_ann_pct']:+6.2f}) | "
              f"Exits {en['ex_exits']['mean_ann_pct']:+6.2f}")

    print("\n=== 8. CONSTRUCTION DEFECTS (missing legs, loss-makers, CPI-age) ===")
    for wname in [b[0] for b in BLOCKS] + ["Full"]:
        d = defects["by_window"][wname]
        c = defects["cpi_unit_drift"][wname]
        print(f"{wname:18s} | <4legs R0 {d['r0_lt4_legs_pct']:4.1f}% (ex {d['ret_r0_lt4legs']['mean_ann_pct']:+6.2f} vs 4L {d['ret_r0_4legs']['mean_ann_pct']:+6.2f}) | "
              f"ep<0 R0 {d['r0_ep_neg_pct']:4.1f}% (ex {d['ret_r0_ep_neg']['mean_ann_pct']:+6.2f} vs >0 {d['ret_r0_ep_pos']['mean_ann_pct']:+6.2f}) | "
              f"CPI-drift mean {c['mean_cpi_drift_pct']:4.1f}% p90-p10 {c['mean_xsec_p90_p10_pct']:4.1f}%")


if __name__ == "__main__":
    main()
