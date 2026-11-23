#!/usr/bin/env python3
"""Round 4 Value Construction Lab (vlab) confirmatory gauntlet harness.

Evaluates pre-registered value_sn construction variants on the read-only FP PIT
panel (/home/eren/bist_project/data/research/fp/) under the fixed Round 4
FULL-PERIOD ROBUSTNESS GAUNTLET:

  GAUNTLET PASS iff ALL:
    (1) full 2013-04..latest paired D vs R0 > 0 with NW t >= 2.0 (lag75);
    (2) D > 0 in EACH of 4 blocks 2013-16, 2017-20, 2021-23, 2024+ (lag75);
    (3) USD maxDD not worse than R0 by > 2pp in full and 2021+ (lag75);
    (4) also holds on kapdates panel (full D > 0, NW t >= 1.0);
    (5) Holm-adjusted p < 0.05 within the prereg batch;
    (6) one-way turnover <= 1.5x R0 (lag75 full).

  Report DSR at updated N_sel. Same universe, liquidity cut, 1M TL costs,
  next-close fills as R0.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy.stats import norm, t as student_t

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from core import research_stats as rs  # noqa: E402
from research_portfolio_backtest import (  # noqa: E402
    CAPITAL_REF,
    SPLIT,
    TOP,
    attach_benchmarks,
    stats,
)
from research_quant_review import variant_matrix  # noqa: E402
from research_round3 import (  # noqa: E402
    align_score_to_panel,
    ledger_n_sel,
    load_daily_from_dir,
    load_prepared_panel,
    resolve_data_dirs,
    strip_forward_columns,
)
from research_value_ablation import IAS29_START, nw_stat  # noqa: E402

AS_OF = "2026-11-24"
DEFAULT_BOARD_DIR = Path("/home/eren/bist_wt/r4-board")
LEDGER_PATH = ROOT / "data" / "research" / "trial_ledger.json"

GAUNTLET_RULE_VERBATIM = (
    "GAUNTLET PASS iff ALL: (1) full 2013-04..latest paired D vs R0 > 0 with NW t >= 2.0; "
    "(2) D > 0 in EACH of 4 blocks 2013-16, 2017-20, 2021-23, 2024+; "
    "(3) USD maxDD not worse than R0 by > 2pp in full and 2021+; "
    "(4) also holds on kapdates panel (D>0, t>=1.0); "
    "(5) Holm-adjusted p < 0.05 within your prereg batch; "
    "(6) one-way turnover <= 1.5x R0. "
    "Report DSR at updated N_sel. Same universe, liquidity cut, 1M TL costs, next-close fills as R0."
)

ScoreFn = Callable[[pd.DataFrame, pd.DataFrame, dict], pd.Series]


@dataclass(frozen=True)
class VariantSpec:
    name: str
    batch: str
    description: str
    score_fn: ScoreFn
    top_pct: float = TOP
    rebalance_months: tuple[int, ...] | None = None
    frozen_params: dict = field(default_factory=dict)


VARIANT_REGISTRY: dict[str, VariantSpec] = {}


def register_variant(spec: VariantSpec) -> VariantSpec:
    VARIANT_REGISTRY[spec.name] = spec
    return spec


# ---------------------------------------------------------------------------
# 1. Windows & Statistical Helpers
# ---------------------------------------------------------------------------
BLOCK_WINDOWS: dict[str, Callable[[pd.DatetimeIndex], np.ndarray]] = {
    "b1_2013_16": lambda idx: idx.year <= 2016,
    "b2_2017_20": lambda idx: (idx.year >= 2017) & (idx.year <= 2020),
    "b3_2021_23": lambda idx: (idx.year >= 2021) & (idx.year <= 2023),
    "b4_2024_plus": lambda idx: idx.year >= 2024,
}

ALL_WINDOWS: dict[str, Callable[[pd.DatetimeIndex], np.ndarray]] = {
    "full": lambda idx: np.ones(len(idx), dtype=bool),
    **BLOCK_WINDOWS,
    "holdout_2021_plus": lambda idx: idx >= SPLIT,
    "ias29_2024_05_plus": lambda idx: idx >= IAS29_START,
}


def two_sided_p_from_t(t_val: float | None, df: int | None = None) -> tuple[float, float]:
    """Return (normal_two_sided_p, student_t_two_sided_p) from NW t."""
    if t_val is None or not np.isfinite(t_val):
        return 1.0, 1.0
    z = abs(float(t_val))
    p_norm = float(2.0 * (1.0 - norm.cdf(z)))
    if df is not None and df > 0:
        p_t = float(2.0 * (1.0 - student_t.cdf(z, df=df)))
    else:
        p_t = p_norm
    return p_norm, p_t


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni step-down adjusted p-values within a prereg batch."""
    if not p_values:
        return {}
    items = sorted(p_values.items(), key=lambda kv: (kv[1], kv[0]))
    m = len(items)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for rank, (name, p) in enumerate(items):
        val = min(1.0, (m - rank) * float(p))
        running_max = max(running_max, val)
        adjusted[name] = running_max
    return adjusted


# ---------------------------------------------------------------------------
# 2. Pre-registration & Ledger Verification Gates
# ---------------------------------------------------------------------------
def verify_batch_prereg(batch_name: str, variant_names: list[str], prereg_dir: Path) -> Path:
    """Require prereg/vlab_<batch>.md with every variant and verbatim gauntlet rule tokens."""
    path = prereg_dir / f"vlab_{batch_name}.md"
    if not path.exists():
        raise RuntimeError(
            f"Pre-registration missing for batch '{batch_name}': expected {path}. "
            "Write prereg/vlab_<batch>.md and commit ledger before running backtests."
        )
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 100:
        raise RuntimeError(f"Pre-registration file {path} is unexpectedly short.")
    required_tokens = ("2013-16", "2017-20", "2021-23", "2024+", "2.0", "2pp", "kapdates", "Holm", "1.5x")
    missing = [tok for tok in required_tokens if tok not in text]
    if missing:
        raise RuntimeError(f"Pre-registration file {path} missing gauntlet rule tokens: {missing}")
    missing_vars = [v for v in variant_names if v not in text]
    if missing_vars:
        raise RuntimeError(f"Pre-registration file {path} missing variant names: {missing_vars}")
    return path


def verify_variants_in_ledger(variant_names: list[str], ledger_path: Path = LEDGER_PATH) -> int:
    """Verify every variant in the batch has a registered stock_selection trial in trial_ledger.json."""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    studies = [s for s in ledger.get("studies", []) if s.get("family") == "stock_selection"]
    missing = []
    for name in variant_names:
        found = any(
            name in str(s.get("study", ""))
            or name in str(s.get("source", ""))
            or name in s.get("candidates", [])
            for s in studies
        )
        if not found:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"Variants not registered in {ledger_path}: {missing}. "
            "Append +1 trial per variant and commit before running any return backtest."
        )
    return ledger_n_sel(ledger_path)


def append_vlab_trials(
    specs: list[VariantSpec],
    ledger_path: Path = LEDGER_PATH,
    as_of: str = AS_OF,
) -> int:
    """Append +1 stock_selection trial for each VariantSpec to trial_ledger.json."""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    existing = {s.get("study") for s in ledger.get("studies", [])}
    for sp in specs:
        study_id = f"round4_vlab_{sp.name}"
        if study_id in existing:
            raise ValueError(f"Trial already exists in ledger: {study_id}")
        ledger["studies"].append({
            "study": study_id,
            "family": "stock_selection",
            "trials": 1,
            "source": f"{sp.name} (batch {sp.batch}): {sp.description}",
        })
    ledger["as_of"] = as_of
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ledger_n_sel(ledger_path)


# ---------------------------------------------------------------------------
# 3. Portfolio Selection & Switcher Diagnostics
# ---------------------------------------------------------------------------
def build_selections(
    df: pd.DataFrame,
    specs: dict[str, VariantSpec],
) -> tuple[dict[str, dict[pd.Timestamp, list[str] | None]], dict[str, dict[pd.Timestamp, set[str]]]]:
    """Build simulator target maps (with None on skipped rebalance months) and effective held sets."""
    months = sorted(df["date"].unique())
    first_month = months[0]
    sel: dict[str, dict[pd.Timestamp, list[str] | None]] = {"EW": {}, "R0": {}}
    eff_sets: dict[str, dict[pd.Timestamp, set[str]]] = {"R0": {}}
    for name in specs:
        sel[name] = {}
        eff_sets[name] = {}

    last_held: dict[str, set[str]] = {name: set() for name in specs}

    for t, g in df.groupby("date", sort=True):
        sel["EW"][t] = sorted(g["ticker"])
        h0 = g[g["R0"].notna()]
        r0 = h0["R0"].rank(ascending=False, pct=True)
        r0_list = sorted(h0.loc[r0 <= TOP, "ticker"])
        sel["R0"][t] = r0_list
        eff_sets["R0"][t] = set(r0_list)

        for name, sp in specs.items():
            do_rebal = (
                sp.rebalance_months is None
                or t == first_month
                or (t.month in sp.rebalance_months)
            )
            if not do_rebal:
                sel[name][t] = None
                eff_sets[name][t] = set(last_held[name])
            else:
                h = g[g[name].notna()]
                if h.empty:
                    sel[name][t] = []
                    last_held[name] = set()
                else:
                    r = h[name].rank(ascending=False, pct=True)
                    picks = sorted(h.loc[r <= sp.top_pct, "ticker"])
                    sel[name][t] = picks
                    last_held[name] = set(picks)
                eff_sets[name][t] = set(last_held[name])

    return sel, eff_sets


def portfolio_switcher_stats(
    df: pd.DataFrame,
    cand_name: str,
    eff_sets: dict[str, dict[pd.Timestamp, set[str]]],
    ret_col: str = "fwd_ret_1m",
) -> pd.DataFrame:
    """Monthly overlap, rank correlation, and entrant-minus-dropout spread using effective sets."""
    rows = []
    for dt, g in df.groupby("date", sort=True):
        sub = g.dropna(subset=[cand_name, "R0", ret_col])
        if len(sub) < 10:
            continue
        set_k = eff_sets[cand_name].get(dt, set())
        set_0 = eff_sets["R0"].get(dt, set())
        if not set_0:
            continue
        idx_t = sub.set_index("ticker")[ret_col]
        valid = set(idx_t.index)
        set_k_v = set_k & valid
        set_0_v = set_0 & valid
        entrants = set_k_v - set_0_v
        dropouts = set_0_v - set_k_v
        ret_in = float(idx_t.loc[list(entrants)].mean()) if entrants else np.nan
        ret_out = float(idx_t.loc[list(dropouts)].mean()) if dropouts else np.nan
        rows.append({
            "date": dt,
            "rank_corr": float(sub[cand_name].rank().corr(sub["R0"].rank())),
            "overlap": len(set_k_v & set_0_v) / max(1, len(set_0_v)),
            "n_switch": len(entrants),
            "switch_spread": (ret_in - ret_out) if (entrants and dropouts) else 0.0,
        })
    return pd.DataFrame(rows).set_index("date").sort_index() if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# 4. Panel Evaluation & Gauntlet Verdict
# ---------------------------------------------------------------------------
def evaluate_panel(
    scored: pd.DataFrame,
    specs: dict[str, VariantSpec],
    macro: pd.DataFrame,
    fx: pd.DataFrame,
    raw_dir: Path,
    frames_cache: dict[str, pd.DataFrame],
    n_sel: int,
    var_sr: float,
) -> dict:
    """Run exact costed portfolio backtest + diagnostics on one prepared scored panel."""
    df = scored.copy()
    if "R0" not in df.columns:
        df["R0"] = df["value_sn_z"]
    names = list(specs.keys())
    all_methods = ("R0", *names)

    # 1. Rank-IC
    ics = {m: fb.rank_ic(df, m, "fwd_ret_1m") for m in all_methods}
    ic_report: dict[str, dict] = {}
    for m in all_methods:
        ic_report[m] = {}
        for wname, wfn in ALL_WINDOWS.items():
            sub_ic = ics[m][wfn(ics[m].index)]
            entry = nw_stat(sub_ic, scale=1.0)
            if m != "R0":
                diff_ic = (ics[m] - ics["R0"]).dropna()
                entry["diff_vs_R0"] = nw_stat(diff_ic[wfn(diff_ic.index)], scale=1.0)
            ic_report[m][wname] = entry

    # 2. Selections & Switcher diagnostics
    sel, eff_sets = build_selections(df, specs)
    switcher_report: dict[str, dict] = {}
    for m in names:
        sw = portfolio_switcher_stats(df, m, eff_sets)
        switcher_report[m] = {}
        for wname, wfn in ALL_WINDOWS.items():
            sub = sw[wfn(sw.index)] if not sw.empty else sw
            if sub.empty:
                switcher_report[m][wname] = {
                    "mean_rank_corr": None,
                    "mean_overlap_pct": None,
                    "mean_switches_per_month": None,
                    "entrants_minus_dropouts": {"mean_ann_pct": None, "mean_raw": None, "t": None, "months": 0},
                }
            else:
                switcher_report[m][wname] = {
                    "mean_rank_corr": round(float(sub["rank_corr"].mean()), 4),
                    "mean_overlap_pct": round(100.0 * float(sub["overlap"].mean()), 2),
                    "mean_switches_per_month": round(float(sub["n_switch"].mean()), 2),
                    "entrants_minus_dropouts": nw_stat(sub["switch_spread"]),
                }

    # 3. Costed portfolio simulation (identical to R0 / research_round3.py)
    days = fx.index
    months = sorted(df["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    needed_tickers = sorted({
        tk
        for lst_map in sel.values()
        for lst in lst_map.values()
        if lst is not None
        for tk in lst
    })
    for tk in needed_tickers:
        if tk not in frames_cache:
            f = load_daily_from_dir(tk, raw_dir)
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
    r0_dd_full = float(stats(r0_p.reset_index())["max_dd_usd_pct"])
    r0_dd_2021p = float(stats(r0_p[r0_p.index >= SPLIT].reset_index())["max_dd_usd_pct"])
    r0_turn_full = float(stats(r0_p.reset_index())["turnover_pct"])

    portfolio_report: dict[str, dict] = {}
    for m, p in sims.items():
        portfolio_report[m] = {}
        for wname, wfn in ALL_WINDOWS.items():
            mask = wfn(p.index)
            sub = p[mask].reset_index()
            base_stats = stats(sub)
            vs_ew_net = nw_stat(p.loc[mask, "active_ew_net"])
            vs_ew_gross = nw_stat(p.loc[mask, "active"])
            sub_panel = df[wfn(df["date"])]
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
            if wname == "full":
                entry["dd_usd_diff_vs_R0_pp"] = round(float(base_stats["max_dd_usd_pct"]) - r0_dd_full, 2)
                entry["turnover_ratio_vs_R0"] = round(float(base_stats["turnover_pct"]) / r0_turn_full, 3) if r0_turn_full > 0 else None
            elif wname == "holdout_2021_plus":
                entry["dd_usd_diff_vs_R0_pp"] = round(float(base_stats["max_dd_usd_pct"]) - r0_dd_2021p, 2)
            if m != "R0":
                d_series = (p["active_ew_net"] - r0_p["active_ew_net"]).loc[mask]
                st = nw_stat(d_series)
                _, t_exact, _ = fb.newey_west_t(d_series, 6)
                st["t_exact"] = float(t_exact) if np.isfinite(t_exact) else None
                entry["paired_diff_vs_R0"] = st
            portfolio_report[m][wname] = entry

    # 4. Deflated Sharpe Ratio at updated N_sel
    dsr_report: dict[str, dict] = {}
    for m, p in sims.items():
        d = rs.deflated_sharpe(p["active_ew_net"].dropna(), n_sel, var_sr)
        dsr_report[m] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}
        dsr_report[m]["var_sr_cross_variant"] = round(var_sr, 5)

    return {
        "months_span": [str(r0_p.index[0].date()), str(r0_p.index[-1].date())],
        "n_full": int(len(r0_p)),
        "window_counts": {w: int(wfn(r0_p.index).sum()) for w, wfn in ALL_WINDOWS.items()},
        "trial_ledger_N_sel": n_sel,
        "portfolio_simulation": portfolio_report,
        "rank_ic": ic_report,
        "switcher_analysis": switcher_report,
        "dsr": dsr_report,
    }


def evaluate_gauntlet_batch(
    primary: dict,
    kap: dict,
    variant_names: list[str],
) -> dict[str, dict]:
    """Evaluate all 6 Round 4 gauntlet criteria + Holm-Bonferroni adjustment across the batch."""
    p_raw_norm: dict[str, float] = {}
    p_raw_tdist: dict[str, float] = {}
    for name in variant_names:
        d_full = primary["portfolio_simulation"][name]["full"]["paired_diff_vs_R0"]
        t_val = d_full.get("t_exact", d_full["t"])
        n_obs = d_full["months"]
        pn, pt = two_sided_p_from_t(t_val, df=max(1, n_obs - 1))
        p_raw_norm[name] = pn
        p_raw_tdist[name] = pt

    p_holm_norm = holm_adjust(p_raw_norm)
    p_holm_tdist = holm_adjust(p_raw_tdist)

    verdicts: dict[str, dict] = {}
    r0_full = primary["portfolio_simulation"]["R0"]["full"]
    r0_2021p = primary["portfolio_simulation"]["R0"]["holdout_2021_plus"]

    for name in variant_names:
        ps = primary["portfolio_simulation"][name]
        ks = kap["portfolio_simulation"][name]

        d_full = ps["full"]["paired_diff_vs_R0"]
        blocks = {b: ps[b]["paired_diff_vs_R0"] for b in BLOCK_WINDOWS}
        d_kap = ks["full"]["paired_diff_vs_R0"]

        dd_full = float(ps["full"]["max_dd_usd_pct"])
        dd_full_diff = round(dd_full - float(r0_full["max_dd_usd_pct"]), 2)
        dd_2021p = float(ps["holdout_2021_plus"]["max_dd_usd_pct"])
        dd_2021p_diff = round(dd_2021p - float(r0_2021p["max_dd_usd_pct"]), 2)

        turn_cand = float(ps["full"]["turnover_pct"])
        turn_r0 = float(r0_full["turnover_pct"])
        turn_ratio = round(turn_cand / turn_r0, 3) if turn_r0 > 0 else float("inf")

        c1 = bool(d_full["mean_ann_pct"] is not None and d_full["mean_ann_pct"] > 0.0
                  and d_full["t"] is not None and d_full["t"] >= 2.0)
        block_pos = {b: bool(v["mean_ann_pct"] is not None and v["mean_ann_pct"] > 0.0) for b, v in blocks.items()}
        c2 = all(block_pos.values())
        c3 = (dd_full_diff >= -2.0) and (dd_2021p_diff >= -2.0)
        c4 = bool(d_kap["mean_ann_pct"] is not None and d_kap["mean_ann_pct"] > 0.0
                  and d_kap["t"] is not None and d_kap["t"] >= 1.0)
        c5 = bool(p_holm_tdist[name] < 0.05)
        c6 = bool(turn_cand <= 1.5 * turn_r0)

        passed = c1 and c2 and c3 and c4 and c5 and c6
        verdicts[name] = {
            "verdict": "PASS" if passed else "FAIL",
            "c1_full_D_t": c1,
            "c2_all_4_blocks_pos": c2,
            "c3_usd_maxdd_ok": c3,
            "c4_kapdates_ok": c4,
            "c5_holm_ok": c5,
            "c6_turnover_ok": c6,
            "full_D_ann_pct": d_full["mean_ann_pct"],
            "full_t": d_full["t"],
            "blocks_D_ann_pct": {b: v["mean_ann_pct"] for b, v in blocks.items()},
            "blocks_t": {b: v["t"] for b, v in blocks.items()},
            "blocks_pos": block_pos,
            "dd_full_usd_pct": dd_full,
            "dd_full_diff_pp": dd_full_diff,
            "dd_2021p_usd_pct": dd_2021p,
            "dd_2021p_diff_pp": dd_2021p_diff,
            "kap_full_D_ann_pct": d_kap["mean_ann_pct"],
            "kap_full_t": d_kap["t"],
            "p_raw_tdist": round(p_raw_tdist[name], 6),
            "p_holm_tdist": round(p_holm_tdist[name], 6),
            "p_raw_norm": round(p_raw_norm[name], 6),
            "p_holm_norm": round(p_holm_norm[name], 6),
            "turnover_pct": turn_cand,
            "r0_turnover_pct": turn_r0,
            "turnover_ratio": turn_ratio,
        }
    return verdicts


# ---------------------------------------------------------------------------
# 5. Markdown Formatting
# ---------------------------------------------------------------------------
def _fmt(v, fmt: str = "+.2f", suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f"{v:{fmt}}{suffix}"


def _pf(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


def format_batch_markdown(
    batch_name: str,
    specs: dict[str, VariantSpec],
    primary: dict,
    kap: dict,
    verdicts: dict[str, dict],
    n_sel: int,
    var_sr: float,
    prereg_path: Path,
    json_path: Path,
    as_of: str = AS_OF,
) -> str:
    """Format /home/eren/bist_wt/r4-board/results/vlab_<batch>.md with full gauntlet table."""
    names = list(specs.keys())
    r0_p = primary["portfolio_simulation"]["R0"]
    r0_k = kap["portfolio_simulation"]["R0"]
    r0_dsr = primary["dsr"]["R0"]
    n_pass = sum(1 for v in verdicts.values() if v["verdict"] == "PASS")

    lines = [
        f"# Round 4 Value Construction Lab (`vlab`) — Batch `{batch_name}` Results",
        "",
        f"- **Date**: {as_of}",
        f"- **Batch**: `{batch_name}` ({len(names)} variants; **{n_pass}/{len(names)} PASS**)",
        f"- **Pre-registration**: `{prereg_path}`",
        f"- **JSON report**: `{json_path}`",
        f"- **Trial ledger `N_sel`**: {n_sel} (`V[SR]` monthly = {var_sr:.5f}, `SR0` = {r0_dsr['sr0']:.4f})",
        f"- **Primary panel**: `fp/factors_monthly.parquet` (`lag75`, {primary['n_full']} months: {primary['months_span'][0]} .. {primary['months_span'][1]})",
        f"- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` ({kap['n_full']} months: {kap['months_span'][0]} .. {kap['months_span'][1]})",
        f"- **Baseline `R0` (`value_sn` top-20% monthly)**: full active vs EW net = {_fmt(r0_p['full']['vs_ew_net']['mean_ann_pct'], '+.2f', '%/yr')} (NW t={_fmt(r0_p['full']['vs_ew_net']['t'])}), full MaxDD USD = {_fmt(r0_p['full']['max_dd_usd_pct'], '.1f', '%')}, 2021+ MaxDD USD = {_fmt(r0_p['holdout_2021_plus']['max_dd_usd_pct'], '.1f', '%')}, 1-way turnover = {_fmt(r0_p['full']['turnover_pct'], '.1f', '%')}, DSR = {_fmt(r0_dsr['dsr'], '.4f')}",
        "",
        f"> **Gauntlet rule**: {GAUNTLET_RULE_VERBATIM}",
        "",
        "## 1. Gauntlet Pass/Fail Table",
        "",
        "| Variant | (1) Full D %/yr (NW t) | (2) 4-Block D %/yr (13-16 / 17-20 / 21-23 / 24+) | (3) MaxDD USD Δpp (Full / 21+) | (4) kapdates D %/yr (t) | (5) Holm p | (6) Turn Ratio | DSR | Verdict |",
        "|---|---:|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for name in names:
        v = verdicts[name]
        b = v["blocks_D_ann_pct"]
        dsr = primary["dsr"][name]["dsr"]
        b_str = " / ".join(_fmt(b[k], "+.2f") for k in ("b1_2013_16", "b2_2017_20", "b3_2021_23", "b4_2024_plus"))
        lines.append(
            f"| `{name}` "
            f"| {_fmt(v['full_D_ann_pct'])} ({_fmt(v['full_t'])}) [{_pf(v['c1_full_D_t'])}] "
            f"| {b_str} [{_pf(v['c2_all_4_blocks_pos'])}] "
            f"| {_fmt(v['dd_full_diff_pp'])} / {_fmt(v['dd_2021p_diff_pp'])} [{_pf(v['c3_usd_maxdd_ok'])}] "
            f"| {_fmt(v['kap_full_D_ann_pct'])} ({_fmt(v['kap_full_t'])}) [{_pf(v['c4_kapdates_ok'])}] "
            f"| {v['p_holm_tdist']:.4f} [{_pf(v['c5_holm_ok'])}] "
            f"| {v['turnover_ratio']:.2f}x [{_pf(v['c6_turnover_ok'])}] "
            f"| {dsr:.4f} "
            f"| **{v['verdict']}** |"
        )

    lines.extend([
        "",
        "## 2. Detailed Performance by Variant & Block (Primary `lag75`)",
        "",
        "| Strategy | Window | Months | vs EW net %/yr (t) | Paired D %/yr (NW t) | CAGR USD % | MaxDD USD % | Turn % | Cost %/yr | Avg Names |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    wlabels = (
        ("full", "Full (2013-04+)"),
        ("b1_2013_16", "2013-16"),
        ("b2_2017_20", "2017-20"),
        ("b3_2021_23", "2021-23"),
        ("b4_2024_plus", "2024+"),
        ("holdout_2021_plus", "2021+"),
        ("ias29_2024_05_plus", "IAS29 (24-05+)"),
    )
    for m in ("R0", *names):
        pm = primary["portfolio_simulation"][m]
        for wkey, wlbl in wlabels:
            x = pm[wkey]
            d_str = "—" if m == "R0" else f"{_fmt(x['paired_diff_vs_R0']['mean_ann_pct'])} ({_fmt(x['paired_diff_vs_R0']['t'])})"
            lines.append(
                f"| `{m}` | {wlbl} | {x['months']} | "
                f"{_fmt(x['vs_ew_net']['mean_ann_pct'])} ({_fmt(x['vs_ew_net']['t'])}) | "
                f"{d_str} | {_fmt(x['cagr_usd_pct'], '+.2f', '%')} | "
                f"{_fmt(x['max_dd_usd_pct'], '.1f', '%')} | {_fmt(x['turnover_pct'], '.1f', '%')} | "
                f"{_fmt(x['cost_ann_pct'], '.2f', '%')} | {_fmt(x['avg_names'], '.1f')} |"
            )

    lines.extend([
        "",
        "## 3. Cross-Sectional Rank-IC, Switcher & DSR Diagnostics (`lag75` Full)",
        "",
        "| Strategy | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Portfolio Overlap | Switches/mo | Entrants - Dropouts %/yr (t) | Monthly SR | DSR (`N_sel`) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for m in ("R0", *names):
        icw = primary["rank_ic"][m]["full"]
        dsr = primary["dsr"][m]
        if m == "R0":
            lines.append(
                f"| `R0` | {_fmt(icw['mean_raw'], '+.4f')} ({_fmt(icw['t'])}) | — | 1.0000 | 100.0% | 0.00 | — | "
                f"{_fmt(dsr['sr_monthly'], '.4f')} | {_fmt(dsr['dsr'], '.4f')} |"
            )
        else:
            dicw = icw["diff_vs_R0"]
            sww = primary["switcher_analysis"][m]["full"]
            em = sww["entrants_minus_dropouts"]
            lines.append(
                f"| `{m}` | {_fmt(icw['mean_raw'], '+.4f')} ({_fmt(icw['t'])}) | "
                f"{_fmt(dicw['mean_raw'], '+.4f')} ({_fmt(dicw['t'])}) | "
                f"{_fmt(sww['mean_rank_corr'], '.4f')} | {_fmt(sww['mean_overlap_pct'], '.1f', '%')} | "
                f"{_fmt(sww['mean_switches_per_month'], '.2f')} | "
                f"{_fmt(em['mean_ann_pct'])} ({_fmt(em['t'])}) | "
                f"{_fmt(dsr['sr_monthly'], '.4f')} | {_fmt(dsr['dsr'], '.4f')} |"
            )

    lines.extend([
        "",
        "## 4. KAP-Date Panel Summary (`factors_monthly_kapdates.parquet`)",
        "",
        f"- **`R0` (`kapdates` full)**: active vs EW net = {_fmt(r0_k['full']['vs_ew_net']['mean_ann_pct'], '+.2f', '%/yr')} (NW t={_fmt(r0_k['full']['vs_ew_net']['t'])}), MaxDD USD = {_fmt(r0_k['full']['max_dd_usd_pct'], '.1f', '%')}, turnover = {_fmt(r0_k['full']['turnover_pct'], '.1f', '%')}",
        "",
        "| Variant | Full D %/yr (NW t) | 2013-16 D | 2017-20 D | 2021-23 D | 2024+ D | MaxDD USD Full / 21+ | Turn % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for name in names:
        ks = kap["portfolio_simulation"][name]
        dfk = ks["full"]["paired_diff_vs_R0"]
        lines.append(
            f"| `{name}` | {_fmt(dfk['mean_ann_pct'])} ({_fmt(dfk['t'])}) | "
            f"{_fmt(ks['b1_2013_16']['paired_diff_vs_R0']['mean_ann_pct'])} | "
            f"{_fmt(ks['b2_2017_20']['paired_diff_vs_R0']['mean_ann_pct'])} | "
            f"{_fmt(ks['b3_2021_23']['paired_diff_vs_R0']['mean_ann_pct'])} | "
            f"{_fmt(ks['b4_2024_plus']['paired_diff_vs_R0']['mean_ann_pct'])} | "
            f"{_fmt(ks['full']['max_dd_usd_pct'], '.1f', '%')} / {_fmt(ks['holdout_2021_plus']['max_dd_usd_pct'], '.1f', '%')} | "
            f"{_fmt(ks['full']['turnover_pct'], '.1f', '%')} |"
        )

    lines.extend([
        "",
        "## 5. Frozen Variant Specifications",
        "",
    ])
    for name, sp in specs.items():
        lines.append(
            f"- **`{name}`**: {sp.description} | `top_pct={sp.top_pct}`, `rebalance_months={sp.rebalance_months}`, "
            f"`frozen_params={json.dumps(sp.frozen_params, sort_keys=True)}`"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Runner
# ---------------------------------------------------------------------------
def run_batch(
    batch_name: str,
    variant_names: list[str],
    *,
    research_dir: Path | None = None,
    fp_dir: Path | None = None,
    prereg_dir: Path = DEFAULT_BOARD_DIR / "prereg",
    results_dir: Path = DEFAULT_BOARD_DIR / "results",
    reports_dir: Path = ROOT / "data" / "reports",
    ledger_path: Path = LEDGER_PATH,
    as_of: str = AS_OF,
    skip_gates: bool = False,
) -> dict:
    if not variant_names:
        raise ValueError("At least one variant is required.")
    if len(variant_names) > 5:
        raise ValueError(f"Round 4 discipline caps each prereg batch at 5 variants (got {len(variant_names)}).")
    unknown = [v for v in variant_names if v not in VARIANT_REGISTRY]
    if unknown:
        raise KeyError(f"Unregistered variants: {unknown}")

    if not skip_gates:
        prereg_path = verify_batch_prereg(batch_name, variant_names, prereg_dir)
        n_sel = verify_variants_in_ledger(variant_names, ledger_path)
    else:
        prereg_path = prereg_dir / f"vlab_{batch_name}.md"
        n_sel = ledger_n_sel(ledger_path)

    specs = {name: VARIANT_REGISTRY[name] for name in variant_names}
    res_dir, fp = resolve_data_dirs(research_dir, fp_dir)
    fx_path = res_dir / "fx.parquet"
    macro_path = res_dir / "macro_monthly.parquet"
    eb_path = res_dir / "eurobond_monthly.parquet"
    raw_dir = res_dir / "raw"

    quarterly = pd.read_parquet(fp / "quarterly.parquet")
    macro = pd.read_parquet(macro_path)
    eurobond = pd.read_parquet(eb_path) if eb_path.exists() else pd.DataFrame()
    fx = pd.read_parquet(fx_path)
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()

    raw_lag75, df_lag75 = load_prepared_panel(fp / "factors_monthly.parquet", fx_path)
    vm = variant_matrix(df_lag75).dropna()
    sr_vm = vm.mean() / vm.std(ddof=1)
    var_sr = float(sr_vm.var(ddof=1))

    raw_kap, df_kap = load_prepared_panel(fp / "factors_monthly_kapdates.parquet", fx_path)

    def attach_scores(raw_p: pd.DataFrame, prep_df: pd.DataFrame, panel_tag: str) -> pd.DataFrame:
        out = prep_df.copy()
        out["R0"] = out["value_sn_z"]
        raw_safe = strip_forward_columns(raw_p)
        prep_safe = strip_forward_columns(prep_df)
        ctx = {
            "quarterly": quarterly,
            "macro": macro,
            "eurobond": eurobond,
            "fx": fx,
            "research_dir": res_dir,
            "fp_dir": fp,
            "raw_dir": raw_dir,
            "panel_tag": panel_tag,
        }
        for name, sp in specs.items():
            s = sp.score_fn(raw_safe, prep_safe, ctx)
            out[name] = align_score_to_panel(s, out)
        return out

    scored_lag75 = attach_scores(raw_lag75, df_lag75, "lag75")
    scored_kap = attach_scores(raw_kap, df_kap, "kapdates")

    frames_cache: dict[str, pd.DataFrame] = {}
    primary = evaluate_panel(scored_lag75, specs, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr)
    kap = evaluate_panel(scored_kap, specs, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr)
    verdicts = evaluate_gauntlet_batch(primary, kap, variant_names)

    reports_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"research_round4_vlab_{batch_name}_{as_of}.json"
    payload = {
        "as_of": as_of,
        "batch": batch_name,
        "variants": variant_names,
        "gauntlet_rule": GAUNTLET_RULE_VERBATIM,
        "trial_ledger_N_sel": n_sel,
        "var_sr_monthly": round(var_sr, 5),
        "prereg_path": str(prereg_path),
        "primary_lag75": primary,
        "sensitivity_kapdates": kap,
        "verdicts": verdicts,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    md_text = format_batch_markdown(
        batch_name, specs, primary, kap, verdicts, n_sel=n_sel, var_sr=var_sr,
        prereg_path=prereg_path, json_path=json_path, as_of=as_of,
    )
    md_path = results_dir / f"vlab_{batch_name}.md"
    md_path.write_text(md_text, encoding="utf-8")
    return {"payload": payload, "json_path": str(json_path), "md_path": str(md_path)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Round 4 Value Construction Lab gauntlet runner.")
    ap.add_argument("--batch", required=True, help="Batch name (e.g. batch1).")
    ap.add_argument("--prereg-dir", type=Path, default=DEFAULT_BOARD_DIR / "prereg")
    ap.add_argument("--results-dir", type=Path, default=DEFAULT_BOARD_DIR / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "data" / "reports")
    ap.add_argument("--as-of", default=AS_OF)
    args = ap.parse_args()

    try:
        import research_round4_vlab_variants  # noqa: F401
    except ImportError:
        pass

    vnames = [k for k, sp in VARIANT_REGISTRY.items() if sp.batch == args.batch]
    if not vnames:
        raise SystemExit(f"No variants registered for batch '{args.batch}'.")
    out = run_batch(
        args.batch,
        vnames,
        prereg_dir=args.prereg_dir,
        results_dir=args.results_dir,
        reports_dir=args.reports_dir,
        as_of=args.as_of,
    )
    print(f"Wrote {out['md_path']} and {out['json_path']}")
    for name, v in out["payload"]["verdicts"].items():
        print(
            f"  {name:26s} | D={v['full_D_ann_pct']:+6.2f}% (t={v['full_t']:+5.2f}) "
            f"| 4blk={v['c2_all_4_blocks_pos']} | DD={v['c3_usd_maxdd_ok']} "
            f"| kap={v['kap_full_D_ann_pct']:+6.2f}% ({v['kap_full_t']:+5.2f}) "
            f"| p_holm={v['p_holm_tdist']:.4f} | turn={v['turnover_ratio']:.2f}x | {v['verdict']}"
        )


if __name__ == "__main__":
    main()
