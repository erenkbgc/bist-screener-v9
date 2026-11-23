#!/usr/bin/env python3
"""Round 4 ML Researcher: strictly causal walk-forward HistGradientBoosting model.

Pre-registration:
  - /home/eren/bist_wt/r4-board/prereg/ml_batch1.md
  - docs/research/round4_ml_batch1_preregistration.md
  - data/research/trial_ledger.json (N_sel 98 -> 100)

Variants (2 trials):
  1. ml_hgb         : expanding-window HistGradientBoostingRegressor predicting
                      next-month cross-sectional percentile rank return.
  2. ml_hgb_blend50 : 50/50 cross-sectional percentile-rank average of ml_hgb
                      and R0 (value_sn_z).

Usage:
    /home/eren/bist_project/.venv/bin/python scripts/research_round4_ml.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from core import research_stats as rs  # noqa: E402
import research_round3 as r3  # noqa: E402
from research_portfolio_backtest import CAPITAL_REF, SPLIT, TOP, attach_benchmarks, stats  # noqa: E402
from research_quant_review import variant_matrix  # noqa: E402
from research_value_ablation import IAS29_START, nw_stat, switcher_and_overlap  # noqa: E402

AS_OF = "2026-11-24"
FIRST_PRED_DATE = pd.Timestamp("2016-01-31")
BOARD_DIR = Path("/home/eren/bist_wt/r4-board")
PREREG_PATH = BOARD_DIR / "prereg" / "ml_batch1.md"

NUMERIC_FEATURES: tuple[str, ...] = (
    "bm_z",
    "ep_z",
    "sp_z",
    "ey_z",
    "size_z",
    "log_tlvol60_z",
    "mom_12_1_z",
    "vol60_z",
)

HGB_FROZEN_PARAMS: dict[str, Any] = {
    "loss": "squared_error",
    "learning_rate": 0.05,
    "max_iter": 100,
    "max_leaf_nodes": 15,
    "max_depth": 4,
    "min_samples_leaf": 50,
    "l2_regularization": 1.0,
    "max_bins": 255,
    "early_stopping": False,
    "random_state": 42,
}

BLEND_WEIGHT_ML = 0.5
GAUNTLET_BLOCKS: tuple[tuple[str, str, pd.Timestamp, pd.Timestamp], ...] = (
    ("block_2016", "2016", pd.Timestamp("2016-01-01"), pd.Timestamp("2017-01-01")),
    ("block_2017_2020", "2017-20", pd.Timestamp("2017-01-01"), pd.Timestamp("2021-01-01")),
    ("block_2021_2023", "2021-23", pd.Timestamp("2021-01-01"), pd.Timestamp("2024-01-01")),
    ("block_2024_plus", "2024+", pd.Timestamp("2024-01-01"), pd.Timestamp("2100-01-01")),
)


@dataclass
class WalkForwardFoldAudit:
    rebalance_date: str
    min_train_date: str
    max_train_date: str
    n_train_months: int
    n_train_rows: int
    n_test_rows: int
    n_sector_dummies: int
    unseen_test_sectors: list[str]


def add_pit_liquidity_feature(df: pd.DataFrame) -> pd.DataFrame:
    """Compute within-month cross-sectional winsorized z-score of log(tlvol60).

    Strictly single-month cross-sectional operation: zero cross-date leakage.
    """
    out = df.copy()
    log_liq = pd.Series(np.nan, index=out.index, dtype=float)
    pos = out["tlvol60"].notna() & (out["tlvol60"] > 0)
    log_liq.loc[pos] = np.log(out.loc[pos, "tlvol60"].astype(float))
    out["log_tlvol60_z"] = (
        log_liq.groupby(out["date"], group_keys=False)
        .apply(lambda s: fb.winsorize_z(s, lo=0.01, hi=0.99))
    )
    return out


def build_fold_design_matrices(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    numeric_features: tuple[str, ...] = NUMERIC_FEATURES,
) -> tuple[np.ndarray, np.ndarray, list[str], list[str], list[str]]:
    """Build strictly PIT feature matrices (X_train, X_test) for a single walk-forward fold.

    Sector one-hot vocabulary is derived strictly from train_df (date < rebalance_date).
    Any sector present in test_df that has never appeared in train_df gets all-zero dummies.
    All forward-return columns are explicitly excluded.
    """
    for bad_col in numeric_features:
        if bad_col.startswith("fwd_ret"):
            raise ValueError(f"Forward-return column forbidden in features: {bad_col}")

    train_sectors = sorted(str(s) for s in train_df["sector"].dropna().unique())
    test_sectors = sorted(str(s) for s in test_df["sector"].dropna().unique())
    unseen_test_sectors = sorted(set(test_sectors) - set(train_sectors))

    feature_names = list(numeric_features) + [f"sec__{s}" for s in train_sectors]

    def _encode(frame: pd.DataFrame) -> np.ndarray:
        num = frame[list(numeric_features)].to_numpy(dtype=float)
        sec_vals = frame["sector"].astype(str).to_numpy()
        dummies = np.column_stack([(sec_vals == s).astype(float) for s in train_sectors]) if train_sectors else np.empty((len(frame), 0), dtype=float)
        return np.hstack([num, dummies])

    return _encode(train_df), _encode(test_df), feature_names, train_sectors, unseen_test_sectors


def compute_rank_target(train_df: pd.DataFrame, ret_col: str = "fwd_ret_1m") -> np.ndarray:
    """Compute within-month cross-sectional percentile rank of next-month return strictly inside train_df."""
    ranks = train_df.groupby("date", sort=False)[ret_col].rank(ascending=True, pct=True)
    return ranks.to_numpy(dtype=float)


def fit_predict_walk_forward_ml(
    prepared_df: pd.DataFrame,
    *,
    first_pred_date: pd.Timestamp = FIRST_PRED_DATE,
    hgb_params: dict[str, Any] | None = None,
    numeric_features: tuple[str, ...] = NUMERIC_FEATURES,
    ret_col: str = "fwd_ret_1m",
    collect_audit: bool = True,
) -> tuple[pd.Series, list[WalkForwardFoldAudit]]:
    """Expanding-window monthly walk-forward HistGradientBoosting rank-return predictor.

    For each rebalance month-end t >= first_pred_date:
      - Training rows are strictly `date < t` with finite `ret_col`.
      - Enforces hard runtime assertions that every training row satisfies:
          1) `train_date < t`
          2) `train_date.to_period('M') + 1 <= t.to_period('M')`
      - Strips all `fwd_ret*` columns from `test_df` before constructing `X_test`.
      - Fits frozen `HistGradientBoostingRegressor` and predicts cross-sectional score at `t`.
    """
    params = dict(HGB_FROZEN_PARAMS if hgb_params is None else hgb_params)
    work = add_pit_liquidity_feature(prepared_df)

    preds = pd.Series(np.nan, index=work.index, dtype=float, name="ml_hgb")
    audits: list[WalkForwardFoldAudit] = []

    all_dates = sorted(work["date"].unique())
    pred_dates = [t for t in all_dates if t >= first_pred_date]

    for t in pred_dates:
        train_mask = (work["date"] < t) & work[ret_col].notna()
        test_mask = work["date"] == t

        train_df = work.loc[train_mask]
        test_df_raw = work.loc[test_mask]
        if train_df.empty or test_df_raw.empty:
            continue

        # Hard leakage assertions on every fold
        if not bool((train_df["date"] < t).all()):
            raise AssertionError(f"Leakage detected: train_df has date >= rebalance_date {t}")
        target_end_periods = train_df["date"].dt.to_period("M") + 1
        rebal_period = t.to_period("M")
        if not bool((target_end_periods <= rebal_period).all()):
            raise AssertionError(f"Leakage detected: training target period exceeds rebalance period {rebal_period}")

        # Strip all forward columns from test slice before feature construction
        test_df_safe = r3.strip_forward_columns(test_df_raw)

        X_train, X_test, _, train_sectors, unseen_sectors = build_fold_design_matrices(
            train_df, test_df_safe, numeric_features=numeric_features
        )
        y_train = compute_rank_target(train_df, ret_col=ret_col)
        if not np.all(np.isfinite(y_train)):
            raise AssertionError(f"Non-finite training targets at fold {t}")

        model = HistGradientBoostingRegressor(**params)
        model.fit(X_train, y_train)
        preds.loc[test_mask] = model.predict(X_test)

        if collect_audit:
            audits.append(
                WalkForwardFoldAudit(
                    rebalance_date=str(pd.Timestamp(t).date()),
                    min_train_date=str(pd.Timestamp(train_df["date"].min()).date()),
                    max_train_date=str(pd.Timestamp(train_df["date"].max()).date()),
                    n_train_months=int(train_df["date"].nunique()),
                    n_train_rows=int(len(train_df)),
                    n_test_rows=int(len(test_df_safe)),
                    n_sector_dummies=len(train_sectors),
                    unseen_test_sectors=unseen_sectors,
                )
            )

    return preds, audits


def compute_blend50_score(df: pd.DataFrame, ml_col: str = "ml_hgb", base_col: str = "value_sn_z") -> pd.Series:
    """50/50 cross-sectional percentile-rank average of ml_col and base_col (require_both=True)."""
    return r3.rank_average_combo(df, ml_col, base_col, weight_a=BLEND_WEIGHT_ML, require_both=True)


def holm_bonferroni(raw_pvals: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni step-down adjusted p-values for a family of hypotheses."""
    items = sorted(raw_pvals.items(), key=lambda kv: (float("inf") if not np.isfinite(kv[1]) else kv[1], kv[0]))
    m = len(items)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for idx, (name, pval) in enumerate(items):
        if not np.isfinite(pval):
            adjusted[name] = float("nan")
            continue
        adj = min(1.0, max(running_max, (m - idx) * float(pval)))
        running_max = adj
        adjusted[name] = adj
    return adjusted


def nw_pvalues(t_stat: float | None, n_obs: int) -> tuple[float, float]:
    """Return (two_sided_p, one_sided_gt0_p) from Student-t with df = n_obs - 1."""
    if t_stat is None or not np.isfinite(t_stat) or n_obs <= 2:
        return float("nan"), float("nan")
    df = n_obs - 1
    p_two = float(2.0 * sp_stats.t.sf(abs(t_stat), df=df))
    p_one = float(sp_stats.t.sf(t_stat, df=df))
    return p_two, p_one


def evaluate_gauntlet_panel(
    scored_full: pd.DataFrame,
    candidate_names: list[str],
    macro: pd.DataFrame,
    fx: pd.DataFrame,
    raw_dir: Path,
    frames_cache: dict[str, pd.DataFrame],
    *,
    eval_start: pd.Timestamp = FIRST_PRED_DATE,
    n_sel: int = 100,
    var_sr: float = 0.02335,
) -> dict:
    """Evaluate R0 and candidate_names symmetrically from eval_start (2016-01) onward."""
    df = scored_full[scored_full["date"] >= eval_start].copy()
    if "R0" not in df.columns:
        df["R0"] = df["value_sn_z"]
    all_methods = ("R0", *candidate_names)

    windows: dict[str, Any] = {
        "full": lambda idx: idx >= eval_start,
        "post_2021": lambda idx: idx >= SPLIT,
        "ias29_2024_05_plus": lambda idx: idx >= IAS29_START,
    }
    for bkey, _, lo, hi in GAUNTLET_BLOCKS:
        windows[bkey] = (lambda lo_=lo, hi_=hi: (lambda idx: (idx >= lo_) & (idx < hi_)))()

    # 1. Cross-sectional Rank-IC and paired delta-IC vs R0
    ics = {m: fb.rank_ic(df, m, "fwd_ret_1m") for m in all_methods}
    ic_report: dict[str, dict] = {}
    for m in all_methods:
        ic_report[m] = {}
        for wname, wfn in windows.items():
            sub_ic = ics[m][wfn(ics[m].index)]
            entry = nw_stat(sub_ic, scale=1.0)
            if m != "R0":
                diff_ic = (ics[m] - ics["R0"]).dropna()
                entry["diff_vs_R0"] = nw_stat(diff_ic[wfn(diff_ic.index)], scale=1.0)
            ic_report[m][wname] = entry

    # 2. Switcher & overlap vs R0
    switcher_report: dict[str, dict] = {}
    for m in candidate_names:
        sw = switcher_and_overlap(df, m, "R0")
        switcher_report[m] = {}
        for wname, wfn in windows.items():
            sub = sw[wfn(sw.index)] if not sw.empty else sw
            if sub.empty:
                switcher_report[m][wname] = {
                    "mean_rank_corr": None,
                    "mean_top20_overlap_pct": None,
                    "mean_switches_per_month": None,
                    "entrants_minus_dropouts": {"mean_ann_pct": None, "mean_raw": None, "t": None, "months": 0},
                }
            else:
                switcher_report[m][wname] = {
                    "mean_rank_corr": round(float(sub["rank_corr"].mean()), 4),
                    "mean_top20_overlap_pct": round(100.0 * float(sub["overlap"].mean()), 2),
                    "mean_switches_per_month": round(float(sub["n_switch"].mean()), 2),
                    "entrants_minus_dropouts": nw_stat(sub["switch_spread"]),
                }

    # 3. Costed portfolio simulation (symmetric entry from eval_start, 1M TL real capital, base costs, next-close fills)
    days = fx.index
    months = sorted(df["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    sel: dict[str, dict[pd.Timestamp, list[str]]] = {m: {} for m in all_methods}
    sel["EW"] = {}
    for t, g in df.groupby("date"):
        sel["EW"][t] = sorted(g["ticker"])
        for m in all_methods:
            h = g[g[m].notna()]
            if h.empty:
                sel[m][t] = []
            else:
                r = h[m].rank(ascending=False, pct=True)
                sel[m][t] = sorted(h.loc[r <= TOP, "ticker"])

    needed_tickers = sorted({tk for lst_map in sel.values() for lst in lst_map.values() for tk in lst})
    for tk in needed_tickers:
        if tk not in frames_cache:
            f = r3.load_daily_from_dir(tk, raw_dir)
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

    costs = pb.Costs()
    ew_sim = pb.simulate(sel["EW"], months, d0_of, mkt, universe_liq, cap, costs=costs).set_index("date")
    sims: dict[str, pd.DataFrame] = {}
    for m in all_methods:
        p = attach_benchmarks(pb.simulate(sel[m], months, d0_of, mkt, universe_liq, cap, costs=costs), ctx)
        p = p.set_index("date")
        p["ew_net"] = ew_sim["port"].reindex(p.index)
        p["active_ew_net"] = p["port"] - p["ew_net"]
        sims[m] = p

    r0_p = sims["R0"]
    r0_full_dd_usd = float(stats(r0_p.reset_index())["max_dd_usd_pct"])
    r0_2021_dd_usd = float(stats(r0_p[r0_p.index >= SPLIT].reset_index())["max_dd_usd_pct"])
    r0_full_turnover = float(r0_p["turnover"].mean())
    r0_ss_turnover = float(r0_p.iloc[1:]["turnover"].mean()) if len(r0_p) > 1 else r0_full_turnover

    portfolio_report: dict[str, dict] = {}
    for m, p in sims.items():
        portfolio_report[m] = {}
        for wname, wfn in windows.items():
            sub_df = p[wfn(p.index)]
            base_stats = stats(sub_df.reset_index())
            vs_ew_net = nw_stat(sub_df["active_ew_net"])
            vs_ew_gross = nw_stat(sub_df["active"])
            sub_panel = df[wfn(df["date"])]
            cov_pct = round(100.0 * float(sub_panel[m].notna().mean()), 2) if len(sub_panel) else 0.0
            turn_mean = float(sub_df["turnover"].mean()) if len(sub_df) else float("nan")
            ss_turn = float(sub_df.iloc[1:]["turnover"].mean()) if (wname == "full" and len(sub_df) > 1) else turn_mean

            entry: dict[str, Any] = {
                "months": int(len(sub_df)),
                "vs_ew_net": vs_ew_net,
                "vs_ew_gross": vs_ew_gross,
                "cagr_tl_pct": base_stats.get("cagr_tl_pct"),
                "cagr_usd_pct": base_stats.get("cagr_usd_pct"),
                "cagr_real_pct": base_stats.get("cagr_real_pct"),
                "max_dd_tl_pct": base_stats.get("max_dd_tl_pct"),
                "max_dd_usd_pct": base_stats.get("max_dd_usd_pct"),
                "turnover_pct": round(100.0 * turn_mean, 2) if np.isfinite(turn_mean) else None,
                "steady_state_turnover_pct": round(100.0 * ss_turn, 2) if np.isfinite(ss_turn) else None,
                "cost_ann_pct": base_stats.get("cost_ann_pct"),
                "avg_names": base_stats.get("avg_names"),
                "coverage_pct": cov_pct,
            }
            if wname == "full":
                entry["full_dd_usd_diff_vs_R0_pp"] = round(float(base_stats["max_dd_usd_pct"]) - r0_full_dd_usd, 2)
                entry["turnover_ratio_vs_R0"] = round(turn_mean / r0_full_turnover, 4) if r0_full_turnover > 0 else None
                entry["steady_state_turnover_ratio_vs_R0"] = round(ss_turn / r0_ss_turnover, 4) if r0_ss_turnover > 0 else None
            if wname == "post_2021":
                entry["post_2021_dd_usd_diff_vs_R0_pp"] = round(float(base_stats["max_dd_usd_pct"]) - r0_2021_dd_usd, 2)
            if m != "R0":
                d_series = (p["active_ew_net"] - r0_p["active_ew_net"]).loc[wfn(p.index)]
                d_stat = nw_stat(d_series)
                p_two, p_one = nw_pvalues(d_stat["t"], d_stat["months"])
                d_stat["p_two_sided"] = round(p_two, 6) if np.isfinite(p_two) else None
                d_stat["p_one_sided"] = round(p_one, 6) if np.isfinite(p_one) else None
                entry["paired_diff_vs_R0"] = d_stat
            portfolio_report[m][wname] = entry

    # 4. Deflated Sharpe Ratio at updated N_sel
    dsr_report: dict[str, dict] = {}
    for m, p in sims.items():
        d = rs.deflated_sharpe(p["active_ew_net"].dropna(), n_sel, var_sr)
        dsr_report[m] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}
        dsr_report[m]["var_sr_cross_variant"] = round(var_sr, 5)

    return {
        "eval_start": str(eval_start.date()),
        "eval_end_return_month": str(r0_p.index.max().date()),
        "n_months_full": int(len(r0_p)),
        "trial_ledger_N_sel": n_sel,
        "portfolio_simulation": portfolio_report,
        "rank_ic": ic_report,
        "switcher_analysis": switcher_report,
        "dsr": dsr_report,
    }


def evaluate_gauntlet_verdicts(
    primary: dict,
    kap: dict,
    candidate_names: list[str],
) -> dict[str, dict]:
    """Apply the fixed Round 4 Full-Period Robustness Gauntlet across a prereg batch."""
    raw_p_two = {
        m: float(primary["portfolio_simulation"][m]["full"]["paired_diff_vs_R0"]["p_two_sided"])
        for m in candidate_names
    }
    raw_p_one = {
        m: float(primary["portfolio_simulation"][m]["full"]["paired_diff_vs_R0"]["p_one_sided"])
        for m in candidate_names
    }
    holm_two = holm_bonferroni(raw_p_two)
    holm_one = holm_bonferroni(raw_p_one)

    verdicts: dict[str, dict] = {}
    for m in candidate_names:
        ps = primary["portfolio_simulation"][m]
        ks = kap["portfolio_simulation"][m]
        full_d = ps["full"]["paired_diff_vs_R0"]
        kap_d = ks["full"]["paired_diff_vs_R0"]

        c1_full_pos_t2 = bool(
            full_d["mean_ann_pct"] is not None
            and full_d["t"] is not None
            and full_d["mean_ann_pct"] > 0.0
            and full_d["t"] >= 2.0
        )

        block_checks: dict[str, dict] = {}
        for bkey, blabel, _, _ in GAUNTLET_BLOCKS:
            bd = ps[bkey]["paired_diff_vs_R0"]
            block_checks[blabel] = {
                "months": bd["months"],
                "D_ann_pct": bd["mean_ann_pct"],
                "t": bd["t"],
                "pass": bool(bd["mean_ann_pct"] is not None and bd["mean_ann_pct"] > 0.0),
            }
        c2_all_blocks_pos = all(v["pass"] for v in block_checks.values())

        dd_full_diff = float(ps["full"]["full_dd_usd_diff_vs_R0_pp"])
        dd_2021_diff = float(ps["post_2021"]["post_2021_dd_usd_diff_vs_R0_pp"])
        c3_dd_ok = bool(dd_full_diff >= -2.0 and dd_2021_diff >= -2.0)

        c4_kap_ok = bool(
            kap_d["mean_ann_pct"] is not None
            and kap_d["t"] is not None
            and kap_d["mean_ann_pct"] > 0.0
            and kap_d["t"] >= 1.0
        )

        c5_holm_ok = bool(
            full_d["mean_ann_pct"] is not None
            and full_d["mean_ann_pct"] > 0.0
            and np.isfinite(holm_two[m])
            and holm_two[m] < 0.05
        )

        turn_ratio = float(ps["full"]["turnover_ratio_vs_R0"])
        c6_turnover_ok = bool(turn_ratio <= 1.5)

        passed = all((c1_full_pos_t2, c2_all_blocks_pos, c3_dd_ok, c4_kap_ok, c5_holm_ok, c6_turnover_ok))
        verdicts[m] = {
            "verdict": "PASS" if passed else "FAIL",
            "c1_full_D_pos_t_ge_2": c1_full_pos_t2,
            "c2_all_4_blocks_D_pos": c2_all_blocks_pos,
            "c3_usd_maxdd_within_2pp": c3_dd_ok,
            "c4_kapdates_D_pos_t_ge_1": c4_kap_ok,
            "c5_holm_p_lt_005": c5_holm_ok,
            "c6_turnover_le_15x_R0": c6_turnover_ok,
            "full_D_ann_pct": full_d["mean_ann_pct"],
            "full_t": full_d["t"],
            "raw_p_two_sided": round(raw_p_two[m], 6),
            "holm_p_two_sided": round(holm_two[m], 6),
            "raw_p_one_sided": round(raw_p_one[m], 6),
            "holm_p_one_sided": round(holm_one[m], 6),
            "blocks": block_checks,
            "full_dd_usd_diff_pp": dd_full_diff,
            "post_2021_dd_usd_diff_pp": dd_2021_diff,
            "kap_full_D_ann_pct": kap_d["mean_ann_pct"],
            "kap_full_t": kap_d["t"],
            "turnover_ratio_vs_R0": turn_ratio,
        }
    return verdicts


def _fmt(v: Any, fmt: str = "+.2f", suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f"{v:{fmt}}{suffix}"


def format_result_markdown(
    name: str,
    description: str,
    primary: dict,
    kap: dict,
    verdict: dict,
    audits: list[WalkForwardFoldAudit],
    json_path: Path,
    as_of: str = AS_OF,
) -> str:
    ps_c = primary["portfolio_simulation"][name]
    ps_r = primary["portfolio_simulation"]["R0"]
    ks_c = kap["portfolio_simulation"][name]
    ks_r = kap["portfolio_simulation"]["R0"]
    dsr_c = primary["dsr"][name]
    dsr_r = primary["dsr"]["R0"]
    ic_c = primary["rank_ic"][name]
    sw_c = primary["switcher_analysis"][name]
    n_sel = primary["trial_ledger_N_sel"]

    lines = [
        f"# Round 4 Gauntlet Result: `{name}`",
        "",
        f"- **Date**: {as_of}",
        f"- **Role / Batch**: `ml` / `ml_batch1` (`m = 2` variants: `ml_hgb`, `ml_hgb_blend50`)",
        f"- **Description**: {description}",
        f"- **Pre-registration**: `{PREREG_PATH}` (`docs/research/round4_ml_batch1_preregistration.md`)",
        f"- **JSON report**: `{json_path}`",
        f"- **Trial ledger `N_sel`**: {n_sel} (`V[SR]` monthly = {dsr_c['var_sr_cross_variant']:.5f})",
        f"- **Evaluation window**: `{primary['eval_start']}` .. `{primary['eval_end_return_month']}` ({primary['n_months_full']} realized return months; first train window `2013-04..2015-12`)",
        f"- **Leakage audit**: {len(audits)} walk-forward folds verified (`max_train_date < rebalance_date` on 100% of folds; `tests/test_research_round4_ml_leakage.py` PASS)",
        "",
        f"## Gauntlet Verdict: **{verdict['verdict']}**",
        "",
        "| # | Gauntlet Criterion (Blocks Start 2016) | Value | Threshold | Result |",
        "|---:|---|---:|---:|:---:|",
        f"| 1 | Full (2016-01+) paired `D` & NW `t` (6 lags) | {_fmt(verdict['full_D_ann_pct'], '+.2f', '%/yr')} (t = {_fmt(verdict['full_t'])}) | D > 0 & t >= 2.00 | {'PASS' if verdict['c1_full_D_pos_t_ge_2'] else 'FAIL'} |",
        "| 2 | All 4 blocks `D > 0` (`2016`, `2017-20`, `2021-23`, `2024+`) | "
        + ", ".join(f"{k}: {_fmt(v['D_ann_pct'], '+.2f', '%')}" for k, v in verdict["blocks"].items())
        + f" | All 4 > 0 | {'PASS' if verdict['c2_all_4_blocks_D_pos'] else 'FAIL'} |",
        f"| 3 | USD MaxDD vs R0 (Full / 2021+) | {_fmt(ps_c['full']['max_dd_usd_pct'], '.1f', '%')} vs {_fmt(ps_r['full']['max_dd_usd_pct'], '.1f', '%')} ({_fmt(verdict['full_dd_usd_diff_pp'], '+.2f', ' pp')}) / {_fmt(ps_c['post_2021']['max_dd_usd_pct'], '.1f', '%')} vs {_fmt(ps_r['post_2021']['max_dd_usd_pct'], '.1f', '%')} ({_fmt(verdict['post_2021_dd_usd_diff_pp'], '+.2f', ' pp')}) | Both >= -2.00 pp | {'PASS' if verdict['c3_usd_maxdd_within_2pp'] else 'FAIL'} |",
        f"| 4 | KAP-dates panel Full paired `D` & NW `t` | {_fmt(verdict['kap_full_D_ann_pct'], '+.2f', '%/yr')} (t = {_fmt(verdict['kap_full_t'])}) | D > 0 & t >= 1.00 | {'PASS' if verdict['c4_kapdates_D_pos_t_ge_1'] else 'FAIL'} |",
        f"| 5 | Holm-adjusted p-value (`m = 2`, two-sided / one-sided) | {verdict['holm_p_two_sided']:.4f} (raw {verdict['raw_p_two_sided']:.4f}) / 1-sided {verdict['holm_p_one_sided']:.4f} | D > 0 & Holm p < 0.05 | {'PASS' if verdict['c5_holm_p_lt_005'] else 'FAIL'} |",
        f"| 6 | One-way monthly turnover vs R0 (steady-state ratio) | {_fmt(ps_c['full']['turnover_pct'], '.2f', '%')} vs {_fmt(ps_r['full']['turnover_pct'], '.2f', '%')} ({verdict['turnover_ratio_vs_R0']:.2f}x; SS {ps_c['full']['steady_state_turnover_ratio_vs_R0']:.2f}x) | <= 1.50x R0 | {'PASS' if verdict['c6_turnover_le_15x_R0'] else 'FAIL'} |",
        "",
        "## Primary Panel (`lag75`) Performance by Block & Window",
        "",
        "| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turn | R0 Turn | Cost %/yr |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for wkey, wlabel in (
        ("block_2016", "Block 1: 2016"),
        ("block_2017_2020", "Block 2: 2017-20"),
        ("block_2021_2023", "Block 3: 2021-23"),
        ("block_2024_plus", "Block 4: 2024+"),
        ("post_2021", "2021+ Combined"),
        ("ias29_2024_05_plus", "IAS 29 (2024-05+)"),
        ("full", "Full (2016-01+)"),
    ):
        c = ps_c[wkey]
        r = ps_r[wkey]
        d = c["paired_diff_vs_R0"]
        lines.append(
            f"| {wlabel} | {c['months']} | "
            f"{_fmt(c['vs_ew_net']['mean_ann_pct'])} ({_fmt(c['vs_ew_net']['t'])}) | "
            f"{_fmt(r['vs_ew_net']['mean_ann_pct'])} ({_fmt(r['vs_ew_net']['t'])}) | "
            f"{_fmt(d['mean_ann_pct'])} ({_fmt(d['t'])}) | "
            f"{_fmt(c['max_dd_usd_pct'], '.1f', '%')} | {_fmt(r['max_dd_usd_pct'], '.1f', '%')} | "
            f"{_fmt(c['turnover_pct'], '.1f', '%')} | {_fmt(r['turnover_pct'], '.1f', '%')} | "
            f"{_fmt(c['cost_ann_pct'], '.2f', '%')} |"
        )

    lines.extend([
        "",
        f"## Deflated Sharpe Ratio (DSR at `N_sel = {n_sel}`)",
        "",
        "| Strategy | T | Monthly SR | SR0 | Skew | Kurtosis | DSR |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| `{name}` | {dsr_c['T']} | {_fmt(dsr_c['sr_monthly'], '.4f')} | {_fmt(dsr_c['sr0'], '.4f')} | {_fmt(dsr_c['skew'], '.3f')} | {_fmt(dsr_c['kurtosis'], '.3f')} | {_fmt(dsr_c['dsr'], '.4f')} |",
        f"| `R0` (`value_sn`) | {dsr_r['T']} | {_fmt(dsr_r['sr_monthly'], '.4f')} | {_fmt(dsr_r['sr0'], '.4f')} | {_fmt(dsr_r['skew'], '.3f')} | {_fmt(dsr_r['kurtosis'], '.3f')} | {_fmt(dsr_r['dsr'], '.4f')} |",
        "",
        "## Cross-Sectional Rank-IC & Switcher Diagnostics (Primary `lag75`)",
        "",
        "| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for wkey, wlabel in (
        ("block_2016", "2016"),
        ("block_2017_2020", "2017-20"),
        ("block_2021_2023", "2021-23"),
        ("block_2024_plus", "2024+"),
        ("full", "Full (2016-01+)"),
    ):
        icw = ic_c[wkey]
        dicw = icw["diff_vs_R0"]
        sww = sw_c[wkey]
        em = sww["entrants_minus_dropouts"]
        lines.append(
            f"| {wlabel} | {_fmt(icw['mean_raw'], '+.4f')} ({_fmt(icw['t'])}) | "
            f"{_fmt(dicw['mean_raw'], '+.4f')} ({_fmt(dicw['t'])}) | "
            f"{_fmt(sww['mean_rank_corr'], '.4f')} | {_fmt(sww['mean_top20_overlap_pct'], '.1f', '%')} | "
            f"{_fmt(sww['mean_switches_per_month'], '.2f')} | {_fmt(em['mean_ann_pct'])} ({_fmt(em['t'])}) |"
        )

    lines.extend([
        "",
        "## KAP-date Panel Performance (`factors_monthly_kapdates.parquet`)",
        "",
        "| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for wkey, wlabel in (
        ("block_2016", "2016"),
        ("block_2017_2020", "2017-20"),
        ("block_2021_2023", "2021-23"),
        ("block_2024_plus", "2024+"),
        ("full", "Full (2016-01+)"),
    ):
        c = ks_c[wkey]
        r = ks_r[wkey]
        d = c["paired_diff_vs_R0"]
        lines.append(
            f"| {wlabel} | {c['months']} | "
            f"{_fmt(c['vs_ew_net']['mean_ann_pct'])} ({_fmt(c['vs_ew_net']['t'])}) | "
            f"{_fmt(r['vs_ew_net']['mean_ann_pct'])} ({_fmt(r['vs_ew_net']['t'])}) | "
            f"{_fmt(d['mean_ann_pct'])} ({_fmt(d['t'])}) | "
            f"{_fmt(c['max_dd_usd_pct'], '.1f', '%')} | {_fmt(r['max_dd_usd_pct'], '.1f', '%')} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_all(
    *,
    write_board: bool = True,
    as_of: str = AS_OF,
) -> dict:
    # Verify pre-registration and trial ledger gates before running any backtest
    if not PREREG_PATH.exists():
        raise RuntimeError(f"Pre-registration missing: {PREREG_PATH}")
    n_sel = r3.ledger_n_sel()
    if n_sel < 100:
        raise RuntimeError(f"Expected N_sel >= 100 after ml_batch1 registration, got {n_sel}")
    for cname in ("ml_hgb", "ml_hgb_blend50"):
        r3.verify_ledger_registered(cname)

    res_dir, fp_dir = r3.resolve_data_dirs()
    fx_path = res_dir / "fx.parquet"
    macro_path = res_dir / "macro_monthly.parquet"
    raw_dir = res_dir / "raw"

    macro = pd.read_parquet(macro_path)
    fx = pd.read_parquet(fx_path)
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()

    _, df_lag75 = r3.load_prepared_panel(fp_dir / "factors_monthly.parquet", fx_path)
    _, df_kap = r3.load_prepared_panel(fp_dir / "factors_monthly_kapdates.parquet", fx_path)

    # Same cross-variant SR variance methodology as Round 3
    vm_full = variant_matrix(df_lag75).dropna()
    sr_vm = vm_full.mean() / vm_full.std(ddof=1)
    var_sr = float(sr_vm.var(ddof=1))

    print("Running walk-forward HistGradientBoosting on primary lag75 panel...", flush=True)
    ml_lag75, audits_lag75 = fit_predict_walk_forward_ml(df_lag75)
    scored_lag75 = df_lag75.copy()
    scored_lag75["R0"] = scored_lag75["value_sn_z"]
    scored_lag75["ml_hgb"] = ml_lag75
    scored_lag75["ml_hgb_blend50"] = compute_blend50_score(scored_lag75, "ml_hgb", "value_sn_z")

    print("Running walk-forward HistGradientBoosting on kapdates panel...", flush=True)
    ml_kap, audits_kap = fit_predict_walk_forward_ml(df_kap)
    scored_kap = df_kap.copy()
    scored_kap["R0"] = scored_kap["value_sn_z"]
    scored_kap["ml_hgb"] = ml_kap
    scored_kap["ml_hgb_blend50"] = compute_blend50_score(scored_kap, "ml_hgb", "value_sn_z")

    # Quick leakage audit summary check
    assert all(a.max_train_date < a.rebalance_date for a in audits_lag75), "lag75 fold date violation"
    assert all(a.max_train_date < a.rebalance_date for a in audits_kap), "kapdates fold date violation"
    assert scored_lag75.loc[scored_lag75["date"] < FIRST_PRED_DATE, "ml_hgb"].isna().all()
    assert scored_lag75.loc[scored_lag75["date"] < FIRST_PRED_DATE, "ml_hgb_blend50"].isna().all()

    candidates = ["ml_hgb", "ml_hgb_blend50"]
    frames_cache: dict[str, pd.DataFrame] = {}

    print("Simulating primary lag75 portfolios (2016-01+)...", flush=True)
    primary = evaluate_gauntlet_panel(
        scored_lag75, candidates, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr
    )
    print("Simulating kapdates portfolios (2016-01+)...", flush=True)
    kap = evaluate_gauntlet_panel(
        scored_kap, candidates, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr
    )

    verdicts = evaluate_gauntlet_verdicts(primary, kap, candidates)

    # Feature correlation diagnostic with ML predictions (purely descriptive, post-eval)
    post = scored_lag75[scored_lag75["date"] >= FIRST_PRED_DATE].copy()
    post = add_pit_liquidity_feature(post)
    feat_corrs = {}
    for col in (*NUMERIC_FEATURES, "value_sn_z"):
        c_by_m = post.groupby("date").apply(lambda g: g["ml_hgb"].rank().corr(g[col].rank()), include_groups=False)
        feat_corrs[col] = round(float(c_by_m.mean()), 4)

    report = {
        "as_of": as_of,
        "batch": "ml_batch1",
        "prereg_path": str(PREREG_PATH),
        "frozen_params": {
            "hgb": HGB_FROZEN_PARAMS,
            "numeric_features": list(NUMERIC_FEATURES),
            "first_pred_date": str(FIRST_PRED_DATE.date()),
            "blend_weight_ml": BLEND_WEIGHT_ML,
        },
        "trial_ledger_N_sel": n_sel,
        "var_sr_cross_variant": round(var_sr, 6),
        "leakage_audit_summary": {
            "lag75_folds": len(audits_lag75),
            "lag75_first_fold": audits_lag75[0].__dict__ if audits_lag75 else None,
            "lag75_last_fold": audits_lag75[-1].__dict__ if audits_lag75 else None,
            "kap_folds": len(audits_kap),
            "all_folds_strictly_causal": True,
        },
        "ml_pred_mean_rank_corr_with_features": feat_corrs,
        "primary_lag75": primary,
        "kapdates": kap,
        "gauntlet_verdicts": verdicts,
    }

    reports_dir = ROOT / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"research_round4_ml_{as_of}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    descriptions = {
        "ml_hgb": "Expanding-window walk-forward HistGradientBoostingRegressor predicting next-month cross-sectional rank return (PIT value/size/liquidity/momentum/volatility/sector features, 2016-01+)",
        "ml_hgb_blend50": "50/50 cross-sectional percentile-rank average of walk-forward ml_hgb and R0 value_sn_z (2016-01+)",
    }

    if write_board:
        results_dir = BOARD_DIR / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        for name in candidates:
            md = format_result_markdown(
                name, descriptions[name], primary, kap, verdicts[name], audits_lag75, json_path, as_of=as_of
            )
            (results_dir / f"{name}.md").write_text(md, encoding="utf-8")

    for name in candidates:
        v = verdicts[name]
        print(
            f"\n[{name}] VERDICT={v['verdict']} | "
            f"Full D={v['full_D_ann_pct']:+.2f}%/yr (NW t={v['full_t']:+.2f}, Holm p={v['holm_p_two_sided']:.4f}) | "
            f"Blocks={ {k: x['D_ann_pct'] for k, x in v['blocks'].items()} } | "
            f"DD diff={v['full_dd_usd_diff_pp']:+.2f}/{v['post_2021_dd_usd_diff_pp']:+.2f}pp | "
            f"KAP D={v['kap_full_D_ann_pct']:+.2f}%/yr (t={v['kap_full_t']:+.2f}) | "
            f"Turn={v['turnover_ratio_vs_R0']:.2f}x R0"
        )
    print(f"\nML score mean cross-sectional rank corr with features: {feat_corrs}")
    print(f"JSON written: {json_path}")
    return report


if __name__ == "__main__":
    run_all()
