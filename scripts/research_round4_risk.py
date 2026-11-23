#!/usr/bin/env python3
"""Round 4 Portfolio & Risk Engineering backtest & Full-Period Robustness Gauntlet.

Evaluates portfolio construction / risk-engineering variants on the unchanged R0
(value_sn_z top-20%) signal using the read-only FP PIT panels and exact
core/portfolio_backtest.py 1M TL cost & next-close fill mechanics.

Usage:
    /home/eren/bist_project/.venv/bin/python scripts/research_round4_risk.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy import optimize as sp_opt
from scipy import stats as sp_stats
from sklearn.covariance import LedoitWolf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from core import research_stats as rs  # noqa: E402
from research_portfolio_backtest import CAPITAL_REF, SPLIT, TOP, attach_benchmarks, stats  # noqa: E402
from research_quant_review import variant_matrix  # noqa: E402
from research_round3 import (  # noqa: E402
    LEDGER_PATH,
    ledger_n_sel,
    load_daily_from_dir,
    load_prepared_panel,
    resolve_data_dirs,
)
from research_value_ablation import nw_stat  # noqa: E402

AS_OF = "2026-11-24"
BOARD_DIR = Path("/home/eren/bist_wt/r4-board")
BLOCKS = (
    ("2013-16", lambda idx: idx.year <= 2016),
    ("2017-20", lambda idx: (idx.year >= 2017) & (idx.year <= 2020)),
    ("2021-23", lambda idx: (idx.year >= 2021) & (idx.year <= 2023)),
    ("2024+", lambda idx: idx.year >= 2024),
)


# ---------------------------------------------------------------------------
# 1. Weighted Portfolio Simulator (exact parity with core.portfolio_backtest)
# ---------------------------------------------------------------------------
def simulate_weighted(
    targets: dict[pd.Timestamp, dict[str, float] | None],
    months: list[pd.Timestamp],
    d0_of: dict[pd.Timestamp, pd.Timestamp],
    mkt: pb.Market,
    universe_liq: dict[pd.Timestamp, np.ndarray],
    capital_tl: dict[pd.Timestamp, float],
    costs: pb.Costs = pb.Costs(),
    fill: str = "close",
    haircut: float = 0.0,
    limit_pct: float | None = None,
) -> pd.DataFrame:
    """Weighted portfolio simulator matching core/portfolio_backtest.py::simulate.

    When targets[t] assigns equal weight 1/N to each ticker in the list, output
    matches pb.simulate to machine precision.
    """
    days = mkt.close.index
    pos_of = {d: i for i, d in enumerate(days)}
    close = mkt.close.to_numpy(dtype=float)
    opn = mkt.open.to_numpy(dtype=float)
    adv = mkt.adv.to_numpy(dtype=float)
    sig = mkt.sigma.to_numpy(dtype=float)
    rf = mkt.rf_daily.reindex(days).fillna(0.0).to_numpy(dtype=float)
    col = {tk: j for j, tk in enumerate(mkt.close.columns)}

    fill_day = {}
    for t in months[:-1]:
        i0 = pos_of[d0_of[t]]
        if i0 + 1 < len(days):
            fill_day[i0 + 1] = t

    values: dict[str, float] = {}
    last_px: dict[str, float] = {}
    miss: dict[str, int] = {}
    cash = 1.0
    month_log: dict[pd.Timestamp, dict] = {}
    delist_events = 0

    def mark(i: int, px: np.ndarray, count_missing: bool) -> None:
        nonlocal cash, delist_events
        for tk in list(values):
            p = px[i, col[tk]]
            if np.isfinite(p):
                values[tk] *= p / last_px[tk]
                last_px[tk] = p
                if count_missing:
                    miss[tk] = 0
            elif count_missing:
                miss[tk] += 1
                if miss[tk] >= pb.DELIST_DAYS:
                    cash += values.pop(tk) * (1 - haircut)
                    last_px.pop(tk)
                    miss.pop(tk)
                    delist_events += 1

    def rebalance(i: int, t: pd.Timestamp, px: np.ndarray) -> None:
        nonlocal cash
        if t in targets and targets[t] is None:
            month_log[t] = {
                "commission": 0.0, "spread": 0.0, "impact": 0.0, "buy": 0.0,
                "fills": 0, "fills_over_10pct_adv": 0, "n_held": len(values),
            }
            return
        nav = cash + sum(values.values())
        cap = capital_tl[t]
        ref = i - 1  # d0: pre-trade known ADV/sigma
        raw_weights = targets.get(t) or {}
        stuck = {tk for tk in values if not np.isfinite(px[i, col[tk]])}
        locked = set()
        if limit_pct is not None and i > 0:
            for tk in set(values) | set(raw_weights):
                j = col.get(tk)
                if j is None:
                    continue
                c0, c1 = close[i - 1, j], close[i, j]
                if np.isfinite(c0) and np.isfinite(c1) and c0 > 0 and abs(c1 / c0 - 1) >= limit_pct:
                    locked.add(tk)
            stuck |= locked & set(values)

        tradable = nav - sum(values[tk] for tk in stuck)
        target_slots = {tk: float(w) for tk, w in raw_weights.items() if tk not in stuck and w > 0.0}
        total_slot_w = sum(target_slots.values())
        wanted = [tk for tk in target_slots if tk in col and np.isfinite(px[i, col[tk]]) and tk not in locked]
        tgt = (
            {tk: tradable * (target_slots[tk] / total_slot_w) for tk in wanted}
            if (wanted and total_slot_w > 0.0)
            else {}
        )

        log = {"commission": 0.0, "spread": 0.0, "impact": 0.0, "buy": 0.0, "fills": 0, "fills_over_10pct_adv": 0}
        for tk in set(values) - stuck | set(tgt):
            dv = tgt.get(tk, 0.0) - values.get(tk, 0.0)
            if abs(dv) < 1e-12:
                continue
            j = col[tk]
            q = abs(dv) / nav * cap
            a = adv[ref, j]
            lp = pb.liq_percentile(a, universe_liq.get(t, np.array([])))
            c_comm = costs.mult * costs.commission_bps / 1e4
            c_spr = costs.mult * costs.half_spread(lp)
            c_imp = costs.mult * costs.impact(sig[ref, j], q, a)
            log["commission"] += abs(dv) * c_comm / nav
            log["spread"] += abs(dv) * c_spr / nav
            log["impact"] += abs(dv) * c_imp / nav
            log["buy"] += max(dv, 0.0) / nav
            log["fills"] += 1
            if not np.isfinite(a) or q > pb.PARTICIPATION_FLAG * a:
                log["fills_over_10pct_adv"] += 1

        total_cost = (log["commission"] + log["spread"] + log["impact"]) * nav
        scale = (tradable - total_cost) / tradable if tradable > 0 else 1.0
        new_values = {tk: values[tk] for tk in stuck}
        for tk, v in tgt.items():
            new_values[tk] = v * scale
            last_px[tk] = px[i, col[tk]]
            miss[tk] = 0
        for tk in set(values) - set(new_values):
            last_px.pop(tk, None)
            miss.pop(tk, None)
        values.clear()
        values.update(new_values)
        cash = (tradable - sum(tgt.values())) * scale if tgt else tradable - total_cost
        log["n_held"] = len(wanted)
        month_log[t] = log

    start = pos_of[d0_of[months[0]]]
    nav_at: dict[pd.Timestamp, float] = {}
    d0_idx = {pos_of[d0_of[t]]: t for t in months}
    for i in range(start, len(days)):
        if i > start:
            cash *= 1 + rf[i]
            t = fill_day.get(i)
            if t is not None and fill == "open":
                mark(i, opn, count_missing=False)
                rebalance(i, t, opn)
                mark(i, close, count_missing=True)
            else:
                mark(i, close, count_missing=True)
                if t is not None:
                    rebalance(i, t, close)
        if i in d0_idx:
            nav_at[d0_idx[i]] = cash + sum(values.values())

    rows = []
    for k, t in enumerate(months[:-1]):
        t1 = months[k + 1]
        if t not in nav_at or t1 not in nav_at or t not in month_log:
            continue
        lg = month_log[t]
        rows.append({
            "date": t,
            "port": nav_at[t1] / nav_at[t] - 1,
            "cost": lg["commission"] + lg["spread"] + lg["impact"],
            "commission": lg["commission"],
            "spread": lg["spread"],
            "impact": lg["impact"],
            "turnover": lg["buy"],
            "fills": lg["fills"],
            "fills_over_10pct_adv": lg["fills_over_10pct_adv"],
            "n": lg["n_held"],
        })
    out = pd.DataFrame(rows)
    out.attrs["delist_events"] = delist_events
    return out


# ---------------------------------------------------------------------------
# 2. Weighting, Capping, PIT Volatility & Smoothing Builders
# ---------------------------------------------------------------------------
def cap_weights(
    w: np.ndarray,
    sectors: np.ndarray,
    max_name: float = 0.05,
    max_sec: float = 0.20,
    max_iter: int = 100,
) -> np.ndarray:
    """Iteratively project non-negative weights onto simplex with name & sector caps."""
    w = np.asarray(w, dtype=float).copy()
    s_sum = w.sum()
    if s_sum <= 0:
        return np.full(len(w), 1.0 / len(w))
    w /= s_sum
    uniq_secs = np.unique(sectors)
    # Feasibility guard: if caps are tighter than 1.0 total capacity, relax minimally only if infeasible.
    if len(w) * max_name < 1.0 - 1e-9 or len(uniq_secs) * max_sec < 1.0 - 1e-9:
        raise ValueError("Infeasible name/sector cap for universe size.")

    for _ in range(max_iter):
        over = w > max_name + 1e-12
        if over.any():
            excess = (w[over] - max_name).sum()
            w[over] = max_name
            under = ~over
            if under.any() and w[under].sum() > 0:
                w[under] += excess * (w[under] / w[under].sum())

        for sec in uniq_secs:
            mask = sectors == sec
            sw = w[mask].sum()
            if sw > max_sec + 1e-12:
                excess = sw - max_sec
                w[mask] *= max_sec / sw
                other = ~mask
                sec_totals = {os_: w[sectors == os_].sum() for os_ in uniq_secs}
                elig = (
                    other
                    & (w < max_name - 1e-12)
                    & np.array([sec_totals[os_] < max_sec - 1e-12 for os_ in sectors])
                )
                if elig.any() and w[elig].sum() > 0:
                    w[elig] += excess * (w[elig] / w[elig].sum())
                elif other.any() and w[other].sum() > 0:
                    w[other] += excess * (w[other] / w[other].sum())

        w /= w.sum()
        max_s = max(w[sectors == sec].sum() for sec in uniq_secs)
        if w.max() <= max_name + 1e-9 and max_s <= max_sec + 1e-9:
            break
    return w / w.sum()


def build_pit_vol6m(close_df: pd.DataFrame, window: int = 126, min_periods: int = 60) -> pd.DataFrame:
    """Trailing 6-month daily return volatility strictly up to each trading day (PIT)."""
    ret_d = close_df.pct_change(fill_method=None)
    return ret_d.rolling(window, min_periods=min_periods).std().ffill()


def smooth_cohorts(
    raw_targets: dict[pd.Timestamp, dict[str, float]],
    months: list[pd.Timestamp],
    d0_of: dict[pd.Timestamp, pd.Timestamp],
    close_df: pd.DataFrame,
    k: int = 3,
) -> dict[pd.Timestamp, dict[str, float]]:
    """Average the last k monthly target weight dicts, keeping names tradable on d0(t)."""
    smoothed: dict[pd.Timestamp, dict[str, float]] = {}
    history: list[dict[str, float]] = []
    for t in months:
        history.append(raw_targets[t])
        window = history[-k:]
        d0 = d0_of[t]
        row_px = close_df.loc[d0]
        acc: dict[str, float] = {}
        n_win = len(window)
        for w_map in window:
            for tk, w in w_map.items():
                if tk in row_px.index and np.isfinite(row_px[tk]):
                    acc[tk] = acc.get(tk, 0.0) + w / n_win
        tot = sum(acc.values())
        smoothed[t] = {tk: v / tot for tk, v in acc.items()} if tot > 0 else dict(raw_targets[t])
    return smoothed


def build_batch1_targets(
    df: pd.DataFrame,
    months: list[pd.Timestamp],
    d0_of: dict[pd.Timestamp, pd.Timestamp],
    close_df: pd.DataFrame,
) -> dict[str, dict[pd.Timestamp, dict[str, float]]]:
    """Build target weight dicts for R0 and the 5 Batch-1 risk variants."""
    vol6m = build_pit_vol6m(close_df, window=126, min_periods=60)
    targets: dict[str, dict[pd.Timestamp, dict[str, float]]] = {
        "R0": {},
        "risk_score_rank": {},
        "risk_score_exp_cap": {},
        "risk_invvol": {},
    }

    for t, g in df.groupby("date"):
        r = g["value_sn_z"].rank(ascending=False, pct=True)
        top = g[r <= TOP].copy()
        tickers = top["ticker"].tolist()
        n = len(tickers)

        # R0 equal weight
        targets["R0"][t] = {tk: 1.0 / n for tk in tickers}

        # 1. Rank-linear score weighting
        rk = top["value_sn_z"].rank(ascending=True, method="average").to_numpy(dtype=float)
        w_rk = rk / rk.sum()
        targets["risk_score_rank"][t] = dict(zip(tickers, map(float, w_rk)))

        # 2. Exponential score weighting + 5% name / 20% sector cap
        z = top["value_sn_z"].to_numpy(dtype=float)
        w_exp = np.exp(z - z.max())
        w_exp /= w_exp.sum()
        w_cap = cap_weights(w_exp, top["sector"].to_numpy(), max_name=0.05, max_sec=0.20)
        targets["risk_score_exp_cap"][t] = dict(zip(tickers, map(float, w_cap)))

        # 3. PIT 6-month inverse-volatility weighting
        d0 = d0_of[t]
        vols = np.array([vol6m.at[d0, tk] if tk in vol6m.columns else np.nan for tk in tickers], dtype=float)
        valid_v = vols[np.isfinite(vols) & (vols > 0)]
        med_v = float(np.median(valid_v)) if len(valid_v) else 0.025
        vols_clean = np.where(np.isfinite(vols) & (vols > 0), vols, med_v)
        w_iv = 1.0 / vols_clean
        w_iv /= w_iv.sum()
        targets["risk_invvol"][t] = dict(zip(tickers, map(float, w_iv)))

    # 4 & 5. 3-month staggered cohort smoothing on EW and Inverse-Vol
    targets["risk_smooth_k3"] = smooth_cohorts(targets["R0"], months, d0_of, close_df, k=3)
    targets["risk_invvol_smooth_k3"] = smooth_cohorts(targets["risk_invvol"], months, d0_of, close_df, k=3)
    return targets


def solve_max_diversification(
    ret_window: pd.DataFrame,
    tickers: list[str],
    sectors: np.ndarray,
    max_name: float = 0.05,
    max_sec: float = 0.20,
    min_periods: int = 60,
) -> np.ndarray:
    """PIT Maximum Diversification Portfolio using Ledoit-Wolf shrinkage covariance."""
    n = len(tickers)
    if n == 0:
        return np.array([], dtype=float)
    sub = ret_window.reindex(columns=tickers)
    valid_counts = sub.notna().sum(axis=0)
    ok_cols = [tk for tk in tickers if valid_counts[tk] >= min_periods]

    if len(ok_cols) >= 3:
        mat = sub[ok_cols].fillna(0.0).to_numpy(dtype=float)
        lw = LedoitWolf(assume_centered=False).fit(mat)
        cov_ok = np.asarray(lw.covariance_, dtype=float)
        std_ok = np.sqrt(np.maximum(np.diag(cov_ok), 1e-12))
        med_var = float(np.median(np.diag(cov_ok)))
    else:
        cov_ok = np.empty((0, 0), dtype=float)
        std_ok = np.empty(0, dtype=float)
        med_var = 0.000625  # (2.5% daily)^2 fallback

    cov = np.eye(n, dtype=float) * med_var
    ok_idx = {tk: i for i, tk in enumerate(ok_cols)}
    for i, tki in enumerate(tickers):
        if tki not in ok_idx:
            continue
        ii = ok_idx[tki]
        for j, tkj in enumerate(tickers):
            if tkj in ok_idx:
                cov[i, j] = cov_ok[ii, ok_idx[tkj]]
    cov = 0.5 * (cov + cov.T) + 1e-10 * np.eye(n)
    sig = np.sqrt(np.maximum(np.diag(cov), 1e-12))

    # Start from inverse-vol feasible point projected onto caps
    w0 = cap_weights(1.0 / sig, sectors, max_name=max_name, max_sec=max_sec)
    uniq_secs = np.unique(sectors)

    def neg_div_ratio(w: np.ndarray) -> float:
        port_var = float(w @ cov @ w)
        port_vol = np.sqrt(max(port_var, 1e-16))
        weighted_vol = float(w @ sig)
        return -weighted_vol / port_vol

    constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
    for sec in uniq_secs:
        mask = (sectors == sec).astype(float)
        constraints.append({"type": "ineq", "fun": lambda w, m=mask: float(max_sec - np.dot(m, w))})

    res = sp_opt.minimize(
        neg_div_ratio,
        w0,
        method="SLSQP",
        bounds=[(0.0, max_name)] * n,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 200},
    )
    w_opt = np.clip(res.x, 0.0, max_name) if res.success and np.all(np.isfinite(res.x)) else w0
    return cap_weights(w_opt, sectors, max_name=max_name, max_sec=max_sec)


def build_batch2_targets(
    df: pd.DataFrame,
    months: list[pd.Timestamp],
    d0_of: dict[pd.Timestamp, pd.Timestamp],
    close_df: pd.DataFrame,
) -> dict[str, dict[pd.Timestamp, dict[str, float]]]:
    """Build target weight dicts for R0 and the 3 Batch-2 risk variants."""
    vol6m = build_pit_vol6m(close_df, window=126, min_periods=60)
    ret_d = close_df.pct_change(fill_method=None)
    day_pos = {d: i for i, d in enumerate(close_df.index)}

    targets: dict[str, dict[pd.Timestamp, dict[str, float]]] = {
        "R0": {},
        "risk_sector_ew": {},
        "risk_sn_invvol": {},
        "risk_max_div": {},
    }

    for t, g in df.groupby("date"):
        r = g["value_sn_z"].rank(ascending=False, pct=True)
        top = g[r <= TOP].copy()
        tickers = top["ticker"].tolist()
        sectors = top["sector"].to_numpy()
        n = len(tickers)
        d0 = d0_of[t]

        # R0 equal weight
        targets["R0"][t] = {tk: 1.0 / n for tk in tickers}

        # 1. Sector-equalized weighting + 5% name / 20% sector cap
        sec_counts = top["sector"].value_counts()
        n_secs = len(sec_counts)
        w_sew_raw = np.array([1.0 / (n_secs * sec_counts[s]) for s in sectors], dtype=float)
        w_sew = cap_weights(w_sew_raw, sectors, max_name=0.05, max_sec=0.20)
        targets["risk_sector_ew"][t] = dict(zip(tickers, map(float, w_sew)))

        # 2. Sector-neutral inverse-volatility (preserves R0 sector weights n_s / N)
        vols = np.array([vol6m.at[d0, tk] if tk in vol6m.columns else np.nan for tk in tickers], dtype=float)
        valid_v = vols[np.isfinite(vols) & (vols > 0)]
        med_v = float(np.median(valid_v)) if len(valid_v) else 0.025
        vols_clean = np.where(np.isfinite(vols) & (vols > 0), vols, med_v)
        inv_v = 1.0 / vols_clean
        w_sn_iv = np.zeros(n, dtype=float)
        for sec in np.unique(sectors):
            m = sectors == sec
            sec_share = float(m.sum()) / n
            sub_iv = inv_v[m]
            w_sn_iv[m] = sec_share * (sub_iv / sub_iv.sum())
        targets["risk_sn_invvol"][t] = dict(zip(tickers, map(float, w_sn_iv)))

        # 3. PIT Maximum Diversification Portfolio (126d Ledoit-Wolf <= d0)
        i_d0 = day_pos[d0]
        i_start = max(0, i_d0 - 126 + 1)
        ret_win = ret_d.iloc[i_start : i_d0 + 1]
        w_md = solve_max_diversification(ret_win, tickers, sectors, max_name=0.05, max_sec=0.20, min_periods=60)
        targets["risk_max_div"][t] = dict(zip(tickers, map(float, w_md)))

    return targets


# ---------------------------------------------------------------------------
# 3. Holm Adjustment & Round 4 Gauntlet Evaluation
# ---------------------------------------------------------------------------
def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Step-down Holm-Bonferroni adjusted p-values for a batch of hypotheses."""
    names = list(p_values)
    m = len(names)
    if m == 0:
        return {}
    order = sorted(names, key=lambda k: p_values[k])
    adj: dict[str, float] = {}
    running_max = 0.0
    for rank, name in enumerate(order):
        val = min(1.0, (m - rank) * float(p_values[name]))
        running_max = max(running_max, val)
        adj[name] = running_max
    return adj


def two_sided_t_pvalue(t_stat: float, n_obs: int) -> float:
    """Two-sided Student-t p-value with df = n_obs - 1."""
    if not np.isfinite(t_stat) or n_obs <= 1:
        return 1.0
    return float(2.0 * sp_stats.t.sf(abs(t_stat), df=n_obs - 1))


def evaluate_panel(
    df: pd.DataFrame,
    macro: pd.DataFrame,
    fx: pd.DataFrame,
    raw_dir: Path,
    frames_cache: dict[str, pd.DataFrame],
    n_sel: int,
    var_sr: float,
    variants: list[str],
    target_builder: Callable = build_batch1_targets,
) -> dict:
    """Run all variants + R0 + EW on one PIT panel and compute full gauntlet metrics."""
    days = fx.index
    months = sorted(df["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    # Preload daily frames for all universe tickers that ever appear in top-20%
    top_tickers = sorted({
        tk for _, g in df.groupby("date")
        for tk in g.loc[g["value_sn_z"].rank(ascending=False, pct=True) <= TOP, "ticker"]
    })
    ew_tickers = sorted(df["ticker"].unique())
    all_needed = sorted(set(top_tickers) | set(ew_tickers))
    for tk in all_needed:
        if tk not in frames_cache:
            f = load_daily_from_dir(tk, raw_dir)
            if f is not None:
                frames_cache[tk] = f
    frames = {tk: frames_cache[tk] for tk in all_needed if tk in frames_cache}

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
    }

    # Build targets for R0 and batch variants
    target_map = target_builder(df, months, d0_of, mat["close"])
    ew_targets = {t: sorted(g["ticker"]) for t, g in df.groupby("date")}

    costs = pb.Costs()
    ew_sim = pb.simulate(ew_targets, months, d0_of, mkt, universe_liq, cap, costs=costs).set_index("date")

    all_methods = ("R0", *variants)
    sims: dict[str, pd.DataFrame] = {}
    for m in all_methods:
        p = attach_benchmarks(
            simulate_weighted(target_map[m], months, d0_of, mkt, universe_liq, cap, costs=costs),
            ctx,
        ).set_index("date")
        p["ew_net"] = ew_sim["port"].reindex(p.index)
        p["active_ew_net"] = p["port"] - p["ew_net"]
        sims[m] = p

    r0_p = sims["R0"]
    windows = {
        "full": lambda idx: idx >= pd.Timestamp.min,
        "discovery": lambda idx: idx < SPLIT,
        "holdout": lambda idx: idx >= SPLIT,
        **dict(BLOCKS),
    }

    report: dict[str, dict] = {}
    for m, p in sims.items():
        report[m] = {}
        for wname, wfn in windows.items():
            sub = p[wfn(p.index)].reset_index()
            st = stats(sub)
            st["vs_ew_net"] = nw_stat(p.loc[wfn(p.index), "active_ew_net"])
            if m != "R0":
                d_series = (p["active_ew_net"] - r0_p["active_ew_net"]).loc[wfn(p.index)]
                st["paired_diff_vs_R0"] = nw_stat(d_series)
            report[m][wname] = st

    # DSR at updated N_sel
    dsr_report: dict[str, dict] = {}
    for m, p in sims.items():
        d = rs.deflated_sharpe(p["active_ew_net"].dropna(), n_sel, var_sr)
        dsr_report[m] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}

    return {
        "n_full": int(len(r0_p)),
        "date_range": [str(r0_p.index.min().date()), str(r0_p.index.max().date())],
        "portfolio": report,
        "dsr": dsr_report,
    }


def evaluate_gauntlet(primary: dict, kap: dict, variants: list[str]) -> dict[str, dict]:
    """Apply all 6 Round 4 FULL-PERIOD ROBUSTNESS GAUNTLET rules."""
    p_map = primary["portfolio"]
    k_map = kap["portfolio"]
    r0_p = p_map["R0"]

    raw_pvals = {}
    for v in variants:
        d_full = p_map[v]["full"]["paired_diff_vs_R0"]
        raw_pvals[v] = two_sided_t_pvalue(d_full["t"], d_full["months"])
    holm_pvals = holm_adjust(raw_pvals)

    verdicts: dict[str, dict] = {}
    for v in variants:
        vp = p_map[v]
        vk = k_map[v]
        d_full = vp["full"]["paired_diff_vs_R0"]
        d_kap = vk["full"]["paired_diff_vs_R0"]

        c1_full = bool(
            np.isfinite(d_full["mean_ann_pct"])
            and d_full["mean_ann_pct"] > 0.0
            and d_full["t"] >= 2.0
        )
        blocks_d = {bname: vp[bname]["paired_diff_vs_R0"]["mean_ann_pct"] for bname, _ in BLOCKS}
        blocks_t = {bname: vp[bname]["paired_diff_vs_R0"]["t"] for bname, _ in BLOCKS}
        c2_blocks = all(np.isfinite(val) and val > 0.0 for val in blocks_d.values())

        dd_full = vp["full"]["max_dd_usd_pct"]
        r0_dd_full = r0_p["full"]["max_dd_usd_pct"]
        dd_hold = vp["holdout"]["max_dd_usd_pct"]
        r0_dd_hold = r0_p["holdout"]["max_dd_usd_pct"]
        c3_dd_full = bool(dd_full >= r0_dd_full - 2.0)
        c3_dd_hold = bool(dd_hold >= r0_dd_hold - 2.0)
        c3_dd = c3_dd_full and c3_dd_hold

        c4_kap = bool(
            np.isfinite(d_kap["mean_ann_pct"])
            and d_kap["mean_ann_pct"] > 0.0
            and d_kap["t"] >= 1.0
        )
        c5_holm = bool(c1_full and holm_pvals[v] < 0.05)

        to_ratio = vp["full"]["turnover_pct"] / r0_p["full"]["turnover_pct"]
        c6_turnover = bool(to_ratio <= 1.5)

        passed = c1_full and c2_blocks and c3_dd and c4_kap and c5_holm and c6_turnover
        verdicts[v] = {
            "verdict": "PASS" if passed else "FAIL",
            "c1_full_D_ann_pct": d_full["mean_ann_pct"],
            "c1_full_nw_t": d_full["t"],
            "c1_pass": c1_full,
            "c2_blocks_D_ann_pct": blocks_d,
            "c2_blocks_nw_t": blocks_t,
            "c2_pass": c2_blocks,
            "c3_dd_full_pct": dd_full,
            "c3_r0_dd_full_pct": r0_dd_full,
            "c3_dd_full_diff_pp": round(dd_full - r0_dd_full, 2),
            "c3_dd_2021p_pct": dd_hold,
            "c3_r0_dd_2021p_pct": r0_dd_hold,
            "c3_dd_2021p_diff_pp": round(dd_hold - r0_dd_hold, 2),
            "c3_pass": c3_dd,
            "c4_kap_D_ann_pct": d_kap["mean_ann_pct"],
            "c4_kap_nw_t": d_kap["t"],
            "c4_pass": c4_kap,
            "c5_raw_p": round(raw_pvals[v], 6),
            "c5_holm_p": round(holm_pvals[v], 6),
            "c5_pass": c5_holm,
            "c6_turnover_pct": vp["full"]["turnover_pct"],
            "c6_r0_turnover_pct": r0_p["full"]["turnover_pct"],
            "c6_turnover_ratio": round(to_ratio, 3),
            "c6_pass": c6_turnover,
        }
    return verdicts


# ---------------------------------------------------------------------------
# 4. Markdown Formatter & Main Runner
# ---------------------------------------------------------------------------
def _fmt(v, fmt: str = "+.2f", suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f"{v:{fmt}}{suffix}"


def format_results_markdown(
    variants: list[str],
    primary: dict,
    kap: dict,
    verdicts: dict[str, dict],
    n_sel: int,
    var_sr: float,
    json_path: Path,
    batch_num: int = 1,
) -> str:
    p_map = primary["portfolio"]
    r0 = p_map["R0"]["full"]
    lines = [
        f"# Round 4 Portfolio & Risk Engineering Results — Batch {batch_num}",
        "",
        f"- **Date**: {AS_OF}",
        f"- **Role**: Portfolio & Risk Engineer (`r4-risk`, branch `agent/r4-risk`)",
        f"- **Pre-registration**: `/home/eren/bist_wt/r4-board/prereg/risk_batch{batch_num}.md`",
        f"- **JSON report**: `{json_path}`",
        f"- **Trial ledger `N_sel`**: {n_sel} (`V[SR]` monthly = {var_sr:.5f})",
        f"- **Primary panel**: `fp/factors_monthly.parquet` (`lag75`, `{primary['n_full']}` months `{primary['date_range'][0]}..{primary['date_range'][1]}`)",
        f"- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` (`kapdates`, `{kap['n_full']}` months)",
        "",
        "## Full-Period Robustness Gauntlet Summary",
        "",
        "| Variant | Full D %/yr (NW t) | 2013-16 D | 2017-20 D | 2021-23 D | 2024+ D | USD MaxDD Full (vs R0) | USD MaxDD 2021+ (vs R0) | KAP Full D (t) | Raw p | Holm p | TO (xR0) | Verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for v in variants:
        vv = verdicts[v]
        bd = vv["c2_blocks_D_ann_pct"]
        lines.append(
            f"| `{v}` | {_fmt(vv['c1_full_D_ann_pct'])} ({_fmt(vv['c1_full_nw_t'])}) | "
            f"{_fmt(bd['2013-16'])} | {_fmt(bd['2017-20'])} | {_fmt(bd['2021-23'])} | {_fmt(bd['2024+'])} | "
            f"{_fmt(vv['c3_dd_full_pct'], '.1f', '%')} ({_fmt(vv['c3_dd_full_diff_pp'], '+.2f', 'pp')}) | "
            f"{_fmt(vv['c3_dd_2021p_pct'], '.1f', '%')} ({_fmt(vv['c3_dd_2021p_diff_pp'], '+.2f', 'pp')}) | "
            f"{_fmt(vv['c4_kap_D_ann_pct'])} ({_fmt(vv['c4_kap_nw_t'])}) | "
            f"{vv['c5_raw_p']:.4f} | {vv['c5_holm_p']:.4f} | "
            f"{vv['c6_turnover_pct']:.1f}% ({vv['c6_turnover_ratio']:.2f}x) | **{vv['verdict']}** |"
        )

    lines.extend([
        "",
        "## Full-Period Risk-Adjusted Performance & DSR (`N_sel = " + str(n_sel) + "`)",
        "",
        "| Strategy | vs EW net %/yr (t) | Sharpe | Sortino | CAGR TL | CAGR USD | CAGR Real | MaxDD TL | MaxDD USD | Turnover | Cost %/yr | Avg N | DSR |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for m in ("R0", *variants):
        st = p_map[m]["full"]
        dsr = primary["dsr"][m]
        lines.append(
            f"| `{m}` | {_fmt(st['vs_ew_net']['mean_ann_pct'])} ({_fmt(st['vs_ew_net']['t'])}) | "
            f"{_fmt(st['sharpe'], '.2f')} | {_fmt(st['sortino'], '.2f')} | "
            f"{_fmt(st['cagr_tl_pct'], '.1f', '%')} | {_fmt(st['cagr_usd_pct'], '.1f', '%')} | {_fmt(st['cagr_real_pct'], '.1f', '%')} | "
            f"{_fmt(st['max_dd_tl_pct'], '.1f', '%')} | {_fmt(st['max_dd_usd_pct'], '.1f', '%')} | "
            f"{_fmt(st['turnover_pct'], '.1f', '%')} | {_fmt(st['cost_ann_pct'], '.2f', '%')} | "
            f"{_fmt(st['avg_names'], '.1f')} | {dsr['dsr']:.4f} |"
        )

    lines.extend([
        "",
        "## Block-by-Block Paired D vs R0 (NW t) & Risk Metrics (Primary `lag75`)",
        "",
        "| Strategy | Window | Months | vs EW net %/yr (t) | Paired D %/yr (NW t) | Sharpe | Sortino | MaxDD USD | Turnover |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for m in ("R0", *variants):
        for wkey, wlabel in (("2013-16", "2013-16"), ("2017-20", "2017-20"), ("2021-23", "2021-23"), ("2024+", "2024+"), ("holdout", "2021+ (All)")):
            st = p_map[m][wkey]
            d_str = "-" if m == "R0" else f"{_fmt(st['paired_diff_vs_R0']['mean_ann_pct'])} ({_fmt(st['paired_diff_vs_R0']['t'])})"
            lines.append(
                f"| `{m}` | {wlabel} | {st['months']} | "
                f"{_fmt(st['vs_ew_net']['mean_ann_pct'])} ({_fmt(st['vs_ew_net']['t'])}) | "
                f"{d_str} | {_fmt(st['sharpe'], '.2f')} | {_fmt(st['sortino'], '.2f')} | "
                f"{_fmt(st['max_dd_usd_pct'], '.1f', '%')} | {_fmt(st['turnover_pct'], '.1f', '%')} |"
            )

    lines.extend([
        "",
        f"## DSR Details (`R0` vs Batch {batch_num})",
        "",
        "| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for m in ("R0", *variants):
        d = primary["dsr"][m]
        lines.append(
            f"| `{m}` | {d['T']} | {d['sr_monthly']:.4f} | {d['sr0']:.4f} | "
            f"{d['skew']:.3f} | {d['kurtosis']:.3f} | {d['dsr']:.4f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Round 4 Portfolio & Risk Engineering Gauntlet Runner.")
    ap.add_argument("--batch", type=int, choices=(1, 2), default=1)
    ap.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    ap.add_argument("--results-path", type=Path, default=None)
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "data" / "reports")
    args = ap.parse_args()

    if args.batch == 1:
        variants = [
            "risk_score_rank",
            "risk_score_exp_cap",
            "risk_invvol",
            "risk_smooth_k3",
            "risk_invvol_smooth_k3",
        ]
        target_builder = build_batch1_targets
    else:
        variants = [
            "risk_sector_ew",
            "risk_sn_invvol",
            "risk_max_div",
        ]
        target_builder = build_batch2_targets

    results_path = args.results_path or (BOARD_DIR / "results" / f"risk_batch{args.batch}.md")
    n_sel = ledger_n_sel(args.ledger)
    res_dir, fp_dir = resolve_data_dirs()
    fx_path = res_dir / "fx.parquet"
    macro_path = res_dir / "macro_monthly.parquet"
    raw_dir = res_dir / "raw"

    macro = pd.read_parquet(macro_path)
    fx = pd.read_parquet(fx_path)
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()

    _, df_lag75 = load_prepared_panel(fp_dir / "factors_monthly.parquet", fx_path)
    vm = variant_matrix(df_lag75).dropna()
    sr_vm = vm.mean() / vm.std(ddof=1)
    var_sr = float(sr_vm.var(ddof=1))

    _, df_kap = load_prepared_panel(fp_dir / "factors_monthly_kapdates.parquet", fx_path)

    frames_cache: dict[str, pd.DataFrame] = {}
    primary = evaluate_panel(
        df_lag75, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr,
        variants=variants, target_builder=target_builder,
    )
    kap = evaluate_panel(
        df_kap, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr,
        variants=variants, target_builder=target_builder,
    )
    verdicts = evaluate_gauntlet(primary, kap, variants)

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = args.reports_dir / f"research_round4_risk_batch{args.batch}_{AS_OF}.json"
    payload = {
        "as_of": AS_OF,
        "batch": args.batch,
        "trial_ledger_N_sel": n_sel,
        "var_sr_monthly": round(var_sr, 5),
        "variants": variants,
        "primary_lag75": primary,
        "sensitivity_kapdates": kap,
        "gauntlet_verdicts": verdicts,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    md_text = format_results_markdown(
        variants, primary, kap, verdicts, n_sel=n_sel, var_sr=var_sr,
        json_path=json_path, batch_num=args.batch,
    )
    results_path.write_text(md_text, encoding="utf-8")

    print(f"\n=== ROUND 4 RISK BATCH {args.batch} GAUNTLET (N_sel={n_sel}, V[SR]={var_sr:.5f}) ===")
    for v in variants:
        vv = verdicts[v]
        print(
            f"{v:24s} | full D={vv['c1_full_D_ann_pct']:+6.2f}% (t={vv['c1_full_nw_t']:+5.2f}) "
            f"| blocks={vv['c2_blocks_D_ann_pct']} "
            f"| DD_diff=({vv['c3_dd_full_diff_pp']:+.2f}, {vv['c3_dd_2021p_diff_pp']:+.2f})pp "
            f"| kap D={vv['c4_kap_D_ann_pct']:+6.2f}% (t={vv['c4_kap_nw_t']:+5.2f}) "
            f"| holm_p={vv['c5_holm_p']:.4f} | TO={vv['c6_turnover_ratio']:.2f}x | {vv['verdict']}"
        )
    print(f"Markdown: {results_path}\nJSON: {json_path}")


if __name__ == "__main__":
    main()
