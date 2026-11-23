#!/usr/bin/env python3
"""Valuation Round 1 pre-registered multi-track backtest
(docs/research/valuation_round1_preregistration.md).

Confirmatory methods tested against baseline R0 (value_sn_z):
  1. S1_value_eb_ns          -- Empirical-Bayes Sector-Standardized Normal-Score Value
  2. M2_value_real_spread_sn -- Sovereign-Spread-Conditioned Real Economic Value
  3. FV1_reoi_ev_sn          -- Inflation-Consistent Residual Operating Income (V_ReOI / EV)

Fixed Pass Rule:
  Candidate monthly top-20% portfolio vs R0 value_sn top-20%, same universe,
  liquidity cut, 1M TL costs and next-close fills as scripts/research_portfolio_backtest.py.
  Paired D = net active(candidate) - net active(R0).
  PASS iff:
    - D > 0 in discovery 2013-2020 with NW t(D) >= 1.0
    - AND D > 0 in holdout 2021+ with NW t(D) >= 2.0
    - AND holdout USD max drawdown not worse than R0 by more than 2 pp.
  Also report DSR at the updated N_sel = 89.

    .venv/bin/python scripts/research_valuation_round1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from core import research_stats as rs  # noqa: E402
from core.sovereign_spread import MAX_YEARS, MIN_YEARS  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_portfolio_backtest import (  # noqa: E402
    CAPITAL_REF,
    RESEARCH,
    SPLIT,
    TOP,
    attach_benchmarks,
    load_daily,
    stats,
)
from research_quant_review import LEDGER_PATH, variant_matrix  # noqa: E402
from research_value_ablation import IAS29_START, nw_stat, switcher_and_overlap  # noqa: E402

AS_OF = "2026-11-22"
LEGS = ("bm", "ep", "sp", "ey")
CANDIDATES = (
    "S1_value_eb_ns",
    "M2_value_real_spread_sn",
    "FV1_reoi_ev_sn",
)
ALL_METHODS = ("R0", *CANDIDATES)
IAS29_FIRST_PERIOD = pit_panel.IAS29_FIRST_PERIOD  # "2023Q4"
TAU_CORP = 0.25
ERP_PRIOR = 0.05
REOI_HORIZON = 5
EB_PRIOR_DF = 5.0
CORR_SHRINK_ALPHA = 0.10


# ---------------------------------------------------------------------------
# 1. Method S1: Empirical-Bayes Sector-Standardized Normal-Score Value
# ---------------------------------------------------------------------------
def blom_normal_score(s: pd.Series) -> pd.Series:
    """Blom (1958) rank-based inverse normal transformation:
    u_i = Phi^{-1}((r_i - 0.375) / (N + 0.25)) for N >= 3 finite observations."""
    x = s.astype(float)
    valid = x.notna() & np.isfinite(x)
    n = int(valid.sum())
    out = pd.Series(np.nan, index=s.index, dtype=float)
    if n < 3:
        return out
    r = x[valid].rank(ascending=True, method="average")
    out.loc[valid] = norm.ppf((r.to_numpy(dtype=float) - 0.375) / (n + 0.25))
    return out


def eb_sector_standardize(v: pd.Series, sector: pd.Series, nu0: float = EB_PRIOR_DF) -> pd.Series:
    """Hierarchical Empirical-Bayes sector location & scale standardization operator E_{nu0}(v | s)."""
    x = v.astype(float)
    valid = x.notna() & np.isfinite(x) & sector.notna()
    n_total = int(valid.sum())
    out = pd.Series(np.nan, index=v.index, dtype=float)
    if n_total < 5:
        return out

    xv = x[valid]
    sv = sector[valid].astype(str)
    grand_mean = float(xv.mean())

    grp = xv.groupby(sv)
    n_s = grp.count().astype(float)
    mean_s = grp.mean().astype(float)
    var_s = grp.var(ddof=1).fillna(0.0).astype(float)

    k_sectors = len(n_s)
    df_s = np.maximum(n_s - 1.0, 0.0)
    df_w = float(df_s.sum())
    if df_w > 0:
        sigma2_w = float((df_s * var_s).sum() / df_w)
    else:
        sigma2_w = float(xv.var(ddof=1)) if n_total > 1 else 1.0
    sigma2_w = max(sigma2_w, 1e-12)

    if k_sectors > 1:
        msb = float((n_s * (mean_s - grand_mean) ** 2).sum() / (k_sectors - 1.0))
        n0 = float((n_total - float((n_s ** 2).sum()) / n_total) / (k_sectors - 1.0))
        tau2_b = max(0.0, (msb - sigma2_w) / n0) if n0 > 0 else 0.0
    else:
        tau2_b = 0.0

    w_s = (n_s * tau2_b) / (n_s * tau2_b + sigma2_w)
    mu_eb = grand_mean + w_s * (mean_s - grand_mean)
    sigma_eb = np.sqrt((df_s * var_s + nu0 * sigma2_w) / (df_s + nu0)).clip(lower=1e-6)

    mu_i = sv.map(mu_eb).to_numpy(dtype=float)
    sig_i = sv.map(sigma_eb).to_numpy(dtype=float)
    out.loc[valid] = (xv.to_numpy(dtype=float) - mu_i) / sig_i
    return out


def compute_s1_month(g: pd.DataFrame, legs: tuple[str, ...] = LEGS, nu0: float = EB_PRIOR_DF) -> pd.Series:
    """Compute S1_value_eb_ns for a single monthly cross-section g."""
    z_tilde = pd.DataFrame(index=g.index, dtype=float)
    for leg in legs:
        u = blom_normal_score(g[leg]) if leg in g.columns else pd.Series(np.nan, index=g.index, dtype=float)
        z_tilde[leg] = eb_sector_standardize(u, g["sector"], nu0=nu0)

    n_legs = len(legs)
    r_raw = z_tilde.corr(method="pearson").to_numpy(dtype=float)
    r_raw = np.where(np.isfinite(r_raw), r_raw, 0.0)
    np.fill_diagonal(r_raw, 1.0)
    r_hat = (1.0 - CORR_SHRINK_ALPHA) * r_raw + CORR_SHRINK_ALPHA * np.eye(n_legs)

    z_mat = z_tilde.to_numpy(dtype=float)
    comp = np.full(len(g), np.nan, dtype=float)
    for i in range(len(g)):
        row = z_mat[i]
        mask = np.isfinite(row)
        k = int(mask.sum())
        if k == 0:
            continue
        quad = float(r_hat[np.ix_(mask, mask)].sum())
        if quad <= 0:
            continue
        comp[i] = (float(row[mask].sum()) / np.sqrt(quad)) * np.sqrt(k / float(n_legs))

    c_series = pd.Series(comp, index=g.index, dtype=float)
    return eb_sector_standardize(c_series, g["sector"], nu0=nu0)


def add_s1_signal(df: pd.DataFrame) -> pd.DataFrame:
    """Add S1_value_eb_ns column across all monthly cross-sections."""
    out = df.copy()
    parts = []
    for _, g in out.groupby("date", sort=False):
        parts.append(compute_s1_month(g))
    out["S1_value_eb_ns"] = pd.concat(parts).reindex(out.index) if parts else np.nan
    return out


# ---------------------------------------------------------------------------
# 2. Method M2: Sovereign-Spread-Conditioned Real Economic Value
# ---------------------------------------------------------------------------
def build_eurobond_yield_series(eb: pd.DataFrame, months: list[pd.Timestamp]) -> pd.Series:
    """Strictly PIT month-end Turkey USD Eurobond median yield y^{USD}_{TR,t} (in decimal)
    across 3 <= remaining_maturity <= 30 years."""
    d = eb.copy()
    d["month"] = month_end(pd.to_datetime(d["month"]))
    d["date"] = pd.to_datetime(d["date"])
    d["maturity"] = pd.to_datetime(d["maturity"])
    d["yrs"] = (d["maturity"] - d["date"]).dt.days / 365.25
    d = d[d["yrs"].between(MIN_YEARS, MAX_YEARS) & d["yield"].notna() & np.isfinite(d["yield"])]
    med_by_month = (d.groupby("month")["yield"].median() / 100.0).sort_index()

    out = {}
    for t in months:
        sub = med_by_month.loc[:t]
        out[t] = float(sub.iloc[-1]) if len(sub) else np.nan
    return pd.Series(out, dtype=float)


def prepare_quarterly_for_valuation(q: pd.DataFrame, cpi: pd.Series) -> pd.DataFrame:
    """Augment quarterly table with eq_p, net_debt_p, and universal constant period-p-end
    purchasing-power TTM flows (ttm_rev_real_m2, ttm_op_real_m2)."""
    w = q.sort_values(["ticker", "period_end"]).reset_index(drop=True).copy()
    w["period_end"] = pd.to_datetime(w["period_end"])
    m_s = w["period_end"].dt.to_period("M")

    i_m0 = m_s.map(cpi).astype(float)
    i_m1 = (m_s - 1).map(cpi).astype(float)
    i_m2 = (m_s - 2).map(cpi).astype(float)
    i_bar = (i_m0 + i_m1 + i_m2) / 3.0

    consec = w.groupby("ticker")["period_end"].diff().dt.days.between(80, 100)
    ok4 = consec.groupby(w["ticker"]).rolling(3, min_periods=3).sum().reset_index(level=0, drop=True) == 3
    is_ias29 = (w["period"] >= IAS29_FIRST_PERIOD).to_numpy()

    for short_name, col in (("rev", "revenue"), ("op", "op_profit")):
        q_col = f"q_{col}"
        ttm_col = f"ttm_{col}"
        scaled_q = w[q_col].astype(float) / i_bar
        roll_real = scaled_q.groupby(w["ticker"]).rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
        ttm_nom_real = (roll_real * i_m0).where(ok4)
        w[f"ttm_{short_name}_real_m2"] = np.where(is_ias29, w[ttm_col].astype(float), ttm_nom_real)

    eq_parent = w["equity_parent"].astype(float) if "equity_parent" in w else pd.Series(np.nan, index=w.index)
    eq_total = w["equity"].astype(float) if "equity" in w else pd.Series(np.nan, index=w.index)
    w["eq_p"] = eq_parent.where(eq_parent.notna() & np.isfinite(eq_parent), eq_total)

    fd = w["fin_debt"].astype(float)
    cash = w["cash"].astype(float)
    w["net_debt_p"] = np.where(fd.notna() & np.isfinite(fd) & cash.notna() & np.isfinite(cash), fd - cash, np.nan)
    w["m_p"] = m_s
    return w


def add_m2_signal(df: pd.DataFrame, q_aug: pd.DataFrame, cpi: pd.Series, eb_yield: pd.Series) -> pd.DataFrame:
    """Add M2_value_real_spread_sn (§3.2) to the prepared monthly panel df."""
    out = df.copy()
    q_cols = ["ticker", "period", "period_end", "m_p", "eq_p", "net_debt_p", "ttm_rev_real_m2", "ttm_op_real_m2"]
    q_sub = q_aug[q_cols].drop_duplicates(subset=["ticker", "period"]).rename(columns={"period": "stmt_period"})
    merged = out.merge(q_sub, on=["ticker", "stmt_period"], how="left")

    m_star = pd.to_datetime(merged["date"]).dt.to_period("M") - 1
    m_p = merged["m_p"]
    has_mp = m_p.notna()

    # max(m_p, m*(t)) in Period("M")
    m_num = pd.Series(np.where(has_mp & (m_p > m_star), m_p, m_star), index=merged.index)
    i_num = m_num.map(cpi).astype(float)
    i_den = m_p.map(cpi).astype(float)
    pi_p_to_t = np.where(has_mp & (i_den > 0) & np.isfinite(i_num) & np.isfinite(i_den), i_num / i_den, np.nan)

    mcap = merged["mcap"].to_numpy(dtype=float)
    eq_p = merged["eq_p"].to_numpy(dtype=float)
    nd_p = merged["net_debt_p"].to_numpy(dtype=float)
    rev_real = merged["ttm_rev_real_m2"].to_numpy(dtype=float)
    op_real = merged["ttm_op_real_m2"].to_numpy(dtype=float)
    y_tr = merged["date"].map(eb_yield).to_numpy(dtype=float)

    ev_real = np.where(np.isfinite(mcap) & np.isfinite(pi_p_to_t) & np.isfinite(nd_p), mcap + pi_p_to_t * nd_p, np.nan)

    with np.errstate(divide="ignore", invalid="ignore"):
        bm_real = np.where(
            np.isfinite(pi_p_to_t) & np.isfinite(eq_p) & (eq_p > 0) & np.isfinite(mcap) & (mcap > 0),
            (pi_p_to_t * eq_p) / mcap,
            np.nan,
        )
        real_ep_sp = np.where(
            np.isfinite(pi_p_to_t) & np.isfinite(op_real) & np.isfinite(nd_p)
            & np.isfinite(y_tr) & np.isfinite(mcap) & (mcap > 0),
            pi_p_to_t * (op_real - y_tr * nd_p) / mcap,
            np.nan,
        )
        sev_real = np.where(
            np.isfinite(pi_p_to_t) & np.isfinite(rev_real) & np.isfinite(ev_real) & (ev_real > 0),
            (pi_p_to_t * rev_real) / ev_real,
            np.nan,
        )
        ey_real = np.where(
            np.isfinite(pi_p_to_t) & np.isfinite(op_real) & np.isfinite(ev_real) & (ev_real > 0),
            (pi_p_to_t * op_real) / ev_real,
            np.nan,
        )

    out["_m2_bm"] = bm_real
    out["_m2_ep"] = real_ep_sp
    out["_m2_sev"] = sev_real
    out["_m2_ey"] = ey_real

    m2_legs = ("_m2_bm", "_m2_ep", "_m2_sev", "_m2_ey")
    z_cols = [f"{c}_z" for c in m2_legs]
    for c, zc in zip(m2_legs, z_cols):
        out[zc] = out.groupby("date", group_keys=False)[c].apply(lambda s: fb.winsorize_z(s, lo=0.01, hi=0.99))

    out["_m2_raw_z"] = out[z_cols].mean(axis=1, skipna=True)
    out["M2_value_real_spread_sn"] = fb.sector_neutralize(out, "_m2_raw_z", min_n=5)
    out.drop(columns=[*m2_legs, *z_cols, "_m2_raw_z"], inplace=True)
    return out


# ---------------------------------------------------------------------------
# 3. Method FV1: Inflation-Consistent Residual Operating Income (V_ReOI / EV)
# ---------------------------------------------------------------------------
def add_fv1_signal(df: pd.DataFrame, q_aug: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    """Add FV1_reoi_ev_sn (§3.3) to the prepared monthly panel df."""
    out = df.copy()
    q_cols = ["ticker", "period", "eq_p", "fin_debt", "cash", "ttm_op_profit"]
    q_sub = q_aug[q_cols].drop_duplicates(subset=["ticker", "period"]).rename(columns={"period": "stmt_period"})
    merged = out.merge(q_sub, on=["ticker", "stmt_period"], how="left")

    mac = macro.copy()
    if not isinstance(mac.index, pd.PeriodIndex):
        mac.index = pd.to_datetime(mac.index).to_period("M")
    policy_s = mac["policy"].astype(float)
    cpi_yoy_s = mac["cpi_yoy"].astype(float)

    m_t = pd.to_datetime(merged["date"]).dt.to_period("M")
    m_star = m_t - 1

    policy_t = m_t.map(policy_s).to_numpy(dtype=float)
    pi_lag1 = m_star.map(cpi_yoy_s).to_numpy(dtype=float) / 100.0

    rw_nom = policy_t / 100.0 + ERP_PRIOR
    with np.errstate(divide="ignore", invalid="ignore"):
        rw_real = np.maximum(0.05, (1.0 + rw_nom) / (1.0 + pi_lag1) - 1.0)

    stmt_p = merged["stmt_period"].fillna("").astype(str)
    is_ias29 = (stmt_p >= IAS29_FIRST_PERIOD).to_numpy()
    rw = np.where(is_ias29, rw_real, rw_nom)

    eq = merged["eq_p"].to_numpy(dtype=float)
    fd = merged["fin_debt"].to_numpy(dtype=float)
    cash = merged["cash"].to_numpy(dtype=float)
    op = merged["ttm_op_profit"].to_numpy(dtype=float)
    mcap = merged["mcap"].to_numpy(dtype=float)

    noa = eq + fd - cash
    ev = mcap + fd - cash
    nopat = (1.0 - TAU_CORP) * op

    valid = (
        np.isfinite(eq)
        & np.isfinite(fd)
        & np.isfinite(cash)
        & np.isfinite(op)
        & np.isfinite(mcap)
        & (mcap > 0)
        & np.isfinite(ev)
        & (ev > 0)
        & np.isfinite(rw)
        & (rw > 0)
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        disc_T = (1.0 + rw) ** (-REOI_HORIZON)
        ann = (1.0 - disc_T) / rw
        reoi = nopat - rw * noa
        v_reoi = noa + ann * reoi
        pv_mult = disc_T + (1.0 - TAU_CORP) * ann
        reoi_ev_tilde = np.where(valid & (pv_mult > 0), (v_reoi / ev) / pv_mult, np.nan)

    out["_fv1_tilde"] = reoi_ev_tilde
    out["_fv1_regime"] = is_ias29.astype(int)

    z_parts = []
    for _, g in out.groupby("date", sort=False):
        s_tilde = g["_fv1_tilde"]
        reg = g["_fv1_regime"]
        n0 = int(s_tilde[reg == 0].notna().sum())
        n1 = int(s_tilde[reg == 1].notna().sum())
        if n0 >= 5 and n1 >= 5:
            z_g = pd.Series(np.nan, index=g.index, dtype=float)
            z_g.loc[reg == 0] = fb.winsorize_z(s_tilde[reg == 0], lo=0.01, hi=0.99)
            z_g.loc[reg == 1] = fb.winsorize_z(s_tilde[reg == 1], lo=0.01, hi=0.99)
        else:
            z_g = fb.winsorize_z(s_tilde, lo=0.01, hi=0.99)
        z_parts.append(z_g)

    out["_fv1_z"] = pd.concat(z_parts).reindex(out.index) if z_parts else np.nan
    out["FV1_reoi_ev_sn"] = fb.sector_neutralize(out, "_fv1_z", min_n=5)
    out.drop(columns=["_fv1_tilde", "_fv1_regime", "_fv1_z"], inplace=True)
    return out


def build_all_signals(
    df: pd.DataFrame,
    quarterly: pd.DataFrame,
    macro: pd.DataFrame,
    eurobond: pd.DataFrame,
) -> pd.DataFrame:
    """Attach R0, S1_value_eb_ns, M2_value_real_spread_sn, and FV1_reoi_ev_sn to df."""
    out = df.copy()
    out["R0"] = out["value_sn_z"]
    cpi = pit_panel.cpi_index(macro["cpi_mom"])
    months = sorted(out["date"].unique())
    eb_yield = build_eurobond_yield_series(eurobond, months)
    q_aug = prepare_quarterly_for_valuation(quarterly, cpi)

    out = add_s1_signal(out)
    out = add_m2_signal(out, q_aug, cpi, eb_yield)
    out = add_fv1_signal(out, q_aug, macro)
    return out


# ---------------------------------------------------------------------------
# 4. Panel Loader, Portfolio Simulation & Pass-Rule Evaluation
# ---------------------------------------------------------------------------
def load_prepared_panel(panel_path: Path) -> pd.DataFrame:
    """Load and prepare a monthly factor panel identically to research_long_term.load()
    restricted to rows where R0 (value_sn_z) is non-null."""
    raw = pd.read_parquet(panel_path)
    raw["date"] = month_end(raw["date"])
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    raw = pit_panel.add_usd_returns(raw, market_m)
    df = add_composites(fb.prepare(raw, FACTORS, liq_drop_pct=0.3))
    return df[df["value_sn_z"].notna()].copy()


def evaluate_pass_rule(
    disc_d: dict,
    hold_d: dict,
    cand_hold_dd_usd_pct: float,
    r0_hold_dd_usd_pct: float,
) -> dict:
    """FIXED PASS RULE (cannot be changed by any agent):
    PASS iff:
      1. D > 0 in discovery 2013-2020 with NW t(D) >= 1.0
      2. AND D > 0 in holdout 2021+ with NW t(D) >= 2.0
      3. AND holdout USD max drawdown not worse than R0 by more than 2 pp.
    """
    d_disc_val = disc_d.get("mean_ann_pct")
    t_disc_val = disc_d.get("t")
    d_hold_val = hold_d.get("mean_ann_pct")
    t_hold_val = hold_d.get("t")

    disc_d_pos = bool(d_disc_val is not None and d_disc_val > 0.0)
    disc_t_ge_1 = bool(t_disc_val is not None and t_disc_val >= 1.0)
    hold_d_pos = bool(d_hold_val is not None and d_hold_val > 0.0)
    hold_t_ge_2 = bool(t_hold_val is not None and t_hold_val >= 2.0)
    dd_diff_pp = round(float(cand_hold_dd_usd_pct) - float(r0_hold_dd_usd_pct), 2)
    hold_dd_usd_ok = bool(float(cand_hold_dd_usd_pct) >= float(r0_hold_dd_usd_pct) - 2.0 - 1e-9)

    passed = disc_d_pos and disc_t_ge_1 and hold_d_pos and hold_t_ge_2 and hold_dd_usd_ok
    return {
        "disc_D_ann_pct": d_disc_val,
        "disc_t": t_disc_val,
        "disc_D_pos": disc_d_pos,
        "disc_t_ge_1": disc_t_ge_1,
        "hold_D_ann_pct": d_hold_val,
        "hold_t": t_hold_val,
        "hold_D_pos": hold_d_pos,
        "hold_t_ge_2": hold_t_ge_2,
        "hold_max_dd_usd_pct": round(float(cand_hold_dd_usd_pct), 1),
        "r0_hold_max_dd_usd_pct": round(float(r0_hold_dd_usd_pct), 1),
        "hold_dd_usd_diff_vs_R0_pp": dd_diff_pp,
        "hold_dd_usd_ok": hold_dd_usd_ok,
        "verdict": "PASS" if passed else "FAIL",
    }


def run_panel_evaluation(
    df: pd.DataFrame,
    quarterly: pd.DataFrame,
    macro: pd.DataFrame,
    eurobond: pd.DataFrame,
    fx: pd.DataFrame,
    frames_cache: dict[str, pd.DataFrame],
    n_sel: int,
    var_sr: float,
) -> dict:
    """Evaluate R0, S1, M2, and FV1 on a prepared panel (lag75 or kapdates)."""
    scored = build_all_signals(df, quarterly, macro, eurobond)

    windows = {
        "discovery": lambda idx: idx < SPLIT,
        "holdout": lambda idx: idx >= SPLIT,
        "ias29_2024_05_plus": lambda idx: idx >= IAS29_START,
        "full": lambda idx: idx >= pd.Timestamp.min,
    }
    ic_windows = ("discovery", "holdout", "ias29_2024_05_plus")

    # 1. Cross-sectional Spearman Rank-IC and paired delta-IC vs R0
    ics = {m: fb.rank_ic(scored, m, "fwd_ret_1m") for m in ALL_METHODS}
    ic_report: dict[str, dict] = {}
    for m in ALL_METHODS:
        ic_report[m] = {}
        for wname in ic_windows:
            wfn = windows[wname]
            sub_ic = ics[m][wfn(ics[m].index)]
            entry = nw_stat(sub_ic, scale=1.0)
            if m != "R0":
                diff_ic = (ics[m] - ics["R0"]).dropna()
                entry["diff_vs_R0"] = nw_stat(diff_ic[wfn(diff_ic.index)], scale=1.0)
            ic_report[m][wname] = entry

    # 2. Switcher analysis vs R0
    switcher_report: dict[str, dict] = {}
    for m in CANDIDATES:
        sw = switcher_and_overlap(scored, m, "R0")
        switcher_report[m] = {}
        for wname in ic_windows:
            wfn = windows[wname]
            sub = sw[wfn(sw.index)]
            switcher_report[m][wname] = {
                "mean_rank_corr": round(float(sub["rank_corr"].mean()), 4),
                "mean_top20_overlap_pct": round(100.0 * float(sub["overlap"].mean()), 2),
                "mean_switches_per_month": round(float(sub["n_switch"].mean()), 2),
                "entrants_minus_dropouts": nw_stat(sub["switch_spread"]),
            }

    # 3. Costed portfolio simulation (1M TL real capital, base costs, next-close fills)
    days = fx.index
    months = sorted(scored["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    sel: dict[str, dict[pd.Timestamp, list[str]]] = {m: {} for m in ALL_METHODS}
    sel["EW"] = {}
    for t, g in scored.groupby("date"):
        sel["EW"][t] = sorted(g["ticker"])
        for m in ALL_METHODS:
            h = g[g[m].notna()]
            r = h[m].rank(ascending=False, pct=True)
            sel[m][t] = sorted(h.loc[r <= TOP, "ticker"])

    needed_tickers = sorted({tk for lst_map in sel.values() for lst in lst_map.values() for tk in lst})
    for tk in needed_tickers:
        if tk not in frames_cache:
            f = load_daily(tk)
            if f is not None:
                frames_cache[tk] = f
    frames = {tk: frames_cache[tk] for tk in needed_tickers if tk in frames_cache}

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
    universe_liq = {t: np.sort(g["tlvol60"].to_numpy()) for t, g in scored.groupby("date")}
    bench = scored.groupby("date")[["fwd_ret_1m", "fwd_ret_1m_usd"]].mean()

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

    costs = pb.Costs()
    ew_sim = pb.simulate(sel["EW"], months, d0_of, mkt, universe_liq, cap, costs=costs).set_index("date")
    sims: dict[str, pd.DataFrame] = {}
    for m in ALL_METHODS:
        p = attach_benchmarks(pb.simulate(sel[m], months, d0_of, mkt, universe_liq, cap, costs=costs), ctx)
        p = p.set_index("date")
        p["ew_net"] = ew_sim["port"].reindex(p.index)
        p["active_ew_net"] = p["port"] - p["ew_net"]
        sims[m] = p

    r0_p = sims["R0"]
    r0_hold_dd_usd = float(stats(r0_p[r0_p.index >= SPLIT].reset_index())["max_dd_usd_pct"])

    portfolio_report: dict[str, dict] = {}
    for m, p in sims.items():
        portfolio_report[m] = {}
        for wname, wfn in windows.items():
            sub = p[wfn(p.index)].reset_index()
            base_stats = stats(sub)
            vs_ew_net = nw_stat(p.loc[wfn(p.index), "active_ew_net"])
            vs_ew_gross = nw_stat(p.loc[wfn(p.index), "active"])
            sub_panel = scored[wfn(scored["date"])]
            cov_pct = round(100.0 * float(sub_panel[m].notna().mean()), 2) if len(sub_panel) else 0.0

            entry = {
                "months": int(len(sub)),
                "vs_ew_net": vs_ew_net,
                "vs_ew_gross": vs_ew_gross,
                "cagr_tl_pct": base_stats.get("cagr_tl_pct"),
                "cagr_usd_pct": base_stats.get("cagr_usd_pct"),
                "cagr_real_pct": base_stats.get("cagr_real_pct"),
                "max_dd_tl_pct": base_stats.get("max_dd_tl_pct"),
                "max_dd_usd_pct": base_stats.get("max_dd_usd_pct"),
                "turnover_pct": base_stats.get("turnover_pct"),
                "cost_ann_pct": base_stats.get("cost_ann_pct"),
                "avg_names": base_stats.get("avg_names"),
                "coverage_pct": cov_pct,
            }
            if wname == "holdout":
                entry["holdout_dd_usd_diff_vs_R0_pp"] = round(
                    float(base_stats.get("max_dd_usd_pct", 0.0)) - r0_hold_dd_usd, 2
                )
            if m != "R0":
                d_series = (p["port"] - r0_p["port"]).loc[wfn(p.index)]
                entry["paired_diff_vs_R0"] = nw_stat(d_series)
            portfolio_report[m][wname] = entry

    # 4. Deflated Sharpe Ratio at updated N_sel = 89
    dsr_report: dict[str, dict] = {}
    for m, p in sims.items():
        d = rs.deflated_sharpe(p["active_ew_net"].dropna(), n_sel, var_sr)
        dsr_report[m] = {
            k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()
        }
        dsr_report[m]["var_sr_cross_variant"] = round(var_sr, 5)

    # 5. Verdicts under the verbatim FIXED PASS RULE
    verdicts: dict[str, dict] = {}
    for m in CANDIDATES:
        verdicts[m] = evaluate_pass_rule(
            portfolio_report[m]["discovery"]["paired_diff_vs_R0"],
            portfolio_report[m]["holdout"]["paired_diff_vs_R0"],
            portfolio_report[m]["holdout"]["max_dd_usd_pct"],
            r0_hold_dd_usd,
        )

    return {
        "n_discovery": int((r0_p.index < SPLIT).sum()),
        "n_holdout": int((r0_p.index >= SPLIT).sum()),
        "n_ias29": int((r0_p.index >= IAS29_START).sum()),
        "n_full": int(len(r0_p)),
        "portfolio_simulation": portfolio_report,
        "rank_ic": ic_report,
        "switcher_analysis": switcher_report,
        "dsr_at_N_sel_89": dsr_report,
        "verdicts": verdicts,
    }


def main() -> None:
    ledger = json.loads(LEDGER_PATH.read_text())
    n_sel = sum(s["trials"] for s in ledger["studies"] if s["family"] == "stock_selection")

    quarterly = pd.read_parquet(RESEARCH / "quarterly.parquet")
    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    eurobond = pd.read_parquet(RESEARCH / "eurobond_monthly.parquet")
    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()

    print("Loading primary lag75 panel...", flush=True)
    df_lag75 = load_prepared_panel(RESEARCH / "factors_monthly.parquet")
    vm = variant_matrix(df_lag75).dropna()
    sr_vm = vm.mean() / vm.std(ddof=1)
    var_sr = float(sr_vm.var(ddof=1))

    frames_cache: dict[str, pd.DataFrame] = {}
    print(f"Evaluating primary_lag75 (N_sel={n_sel}, V[SR]={var_sr:.5f})...", flush=True)
    primary_lag75 = run_panel_evaluation(
        df_lag75, quarterly, macro, eurobond, fx, frames_cache, n_sel=n_sel, var_sr=var_sr
    )

    print("Loading sensitivity kapdates panel...", flush=True)
    df_kap = load_prepared_panel(RESEARCH / "factors_monthly_kapdates.parquet")
    print("Evaluating sensitivity_kapdates...", flush=True)
    sensitivity_kapdates = run_panel_evaluation(
        df_kap, quarterly, macro, eurobond, fx, frames_cache, n_sel=n_sel, var_sr=var_sr
    )

    months = sorted(df_lag75["date"].unique())
    result = {
        "as_of": AS_OF,
        "months": [str(months[0].date()), str(months[-1].date())],
        "n_discovery": primary_lag75["n_discovery"],
        "n_holdout": primary_lag75["n_holdout"],
        "n_ias29": primary_lag75["n_ias29"],
        "trial_ledger_N_sel": n_sel,
        "var_sr_monthly": round(var_sr, 5),
        "primary_lag75": primary_lag75,
        "sensitivity_kapdates": sensitivity_kapdates,
    }

    out_path = ROOT / "data" / "reports" / f"research_valuation_round1_{AS_OF}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n=== PRIMARY (lag75) SUMMARY ===")
    for m in ALL_METHODS:
        ps = primary_lag75["portfolio_simulation"][m]
        dsr_m = primary_lag75["dsr_at_N_sel_89"][m]
        d_str = ""
        if m != "R0":
            dd_d = ps["discovery"]["paired_diff_vs_R0"]
            dd_h = ps["holdout"]["paired_diff_vs_R0"]
            v = primary_lag75["verdicts"][m]["verdict"]
            d_str = (
                f" | D_disc={dd_d['mean_ann_pct']:+6.2f}% (t={dd_d['t']:+5.2f})"
                f" | D_hold={dd_h['mean_ann_pct']:+6.2f}% (t={dd_h['t']:+5.2f})"
                f" | Verdict={v}"
            )
        print(
            f"{m:24s}: Disc vs EW_net={ps['discovery']['vs_ew_net']['mean_ann_pct']:+6.2f}% "
            f"(t={ps['discovery']['vs_ew_net']['t']:5.2f}), "
            f"Hold vs EW_net={ps['holdout']['vs_ew_net']['mean_ann_pct']:+6.2f}% "
            f"(t={ps['holdout']['vs_ew_net']['t']:5.2f}), "
            f"Hold maxDD_USD={ps['holdout']['max_dd_usd_pct']:5.1f}%, "
            f"DSR={dsr_m['dsr']:.4f}{d_str}"
        )
    print(f"\nJSON written to: {out_path}")


if __name__ == "__main__":
    main()
