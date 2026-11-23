#!/usr/bin/env python3
"""Round 3 "beat value_sn" confirmatory backtest harness.

Modeled on scripts/research_valuation_round2.py and scripts/research_valuation_round1.py.
Uses the read-only FP PIT panel (/home/eren/bist_project/data/research/fp/) and
enforces the verbatim FIXED PASS RULE, pre-registration gate, and trial ledger accounting.

FIXED PASS RULE (verbatim):
  candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut,
  1M TL costs, next-close fills. D = net active(cand) - net active(R0).
  PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0
  AND holdout USD maxDD not worse than R0 by >2pp.
  Report DSR at updated N_sel. Every tested candidate +1 N_sel.

Usage:
    /home/eren/bist_project/.venv/bin/python scripts/research_round3.py --candidate <name>
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import research_valuation_round1 as r1  # noqa: E402
from backtest_factor_model import FACTORS, add_composites  # noqa: E402
from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from core import research_stats as rs  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_portfolio_backtest import (  # noqa: E402
    CAPITAL_REF,
    SPLIT,
    TOP,
    attach_benchmarks,
    daily_frame,
    stats,
)
from research_quant_review import variant_matrix  # noqa: E402
from research_value_ablation import IAS29_START, nw_stat, switcher_and_overlap  # noqa: E402

AS_OF = "2026-11-24"
DEFAULT_MAIN_RESEARCH = Path("/home/eren/bist_project/data/research")
DEFAULT_BOARD_DIR = Path("/home/eren/bist_wt/r3-board")
LEDGER_PATH = ROOT / "data" / "research" / "trial_ledger.json"

FIXED_PASS_RULE_VERBATIM = (
    "candidate monthly top-20% vs R0 value_sn top-20%, same universe, liquidity cut, "
    "1M TL costs, next-close fills. D = net active(cand) - net active(R0). "
    "PASS iff D>0 discovery 2013-2020 NW t>=1.0 AND D>0 holdout 2021+ NW t>=2.0 "
    "AND holdout USD maxDD not worse than R0 by >2pp. Report DSR at updated N_sel. "
    "Every tested candidate +1 N_sel."
)

# Signature: fn(raw_panel_no_fwd, prepared_df_no_fwd, ctx) -> pd.Series
# Returned Series must be indexed either by MultiIndex (date, ticker) or prepared_df.index.
SignalFn = Callable[[pd.DataFrame, pd.DataFrame, dict], pd.Series]


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    description: str
    fn: SignalFn
    frozen_params: dict = field(default_factory=dict)
    is_combination: bool = False


# Populated as pre-registered candidates are pulled from agent/r3-features.
CANDIDATE_REGISTRY: dict[str, CandidateSpec] = {}


def register_candidate(spec: CandidateSpec) -> CandidateSpec:
    CANDIDATE_REGISTRY[spec.name] = spec
    return spec


# ---------------------------------------------------------------------------
# 1. Data Resolution & PIT Safeguards
# ---------------------------------------------------------------------------
def resolve_data_dirs(
    research_dir: Path | None = None,
    fp_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Locate research auxiliary data (fx, macro, raw/*.pkl) and FP PIT panel directory."""
    if research_dir is None:
        env_dir = os.environ.get("BIST_RESEARCH_DIR")
        if env_dir:
            research_dir = Path(env_dir)
        elif (ROOT / "data" / "research" / "fx.parquet").exists():
            research_dir = ROOT / "data" / "research"
        else:
            research_dir = DEFAULT_MAIN_RESEARCH

    if fp_dir is None:
        env_fp = os.environ.get("BIST_FP_DIR")
        if env_fp:
            fp_dir = Path(env_fp)
        elif (research_dir / "fp" / "factors_monthly.parquet").exists():
            fp_dir = research_dir / "fp"
        else:
            fp_dir = DEFAULT_MAIN_RESEARCH / "fp"

    return research_dir, fp_dir


def load_daily_from_dir(ticker: str, raw_dir: Path) -> pd.DataFrame | None:
    f = raw_dir / f"{ticker}.pkl"
    if not f.exists():
        return None
    d = pickle.loads(f.read_bytes())
    return daily_frame(d.get("px_adj"), d.get("px_raw"))


def load_prepared_panel(panel_path: Path, fx_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw panel and prepare monthly panel identically to R0 (value_sn_z non-null)."""
    raw = pd.read_parquet(panel_path)
    raw["date"] = month_end(raw["date"])
    market_m = pit_panel.monthly_market(pd.read_parquet(fx_path))
    raw_with_usd = pit_panel.add_usd_returns(raw, market_m)
    df = add_composites(fb.prepare(raw_with_usd, FACTORS, liq_drop_pct=0.3))
    df = df[df["value_sn_z"].notna()].copy()
    return raw, df


def strip_forward_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove all forward-return target columns before handing a DataFrame to signal builders."""
    drop_cols = [c for c in df.columns if c.startswith("fwd_ret")]
    return df.drop(columns=drop_cols, errors="ignore").copy()


# ---------------------------------------------------------------------------
# 2. Pre-registration & Trial Ledger Gates
# ---------------------------------------------------------------------------
def ledger_n_sel(ledger_path: Path = LEDGER_PATH) -> int:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    return sum(int(s["trials"]) for s in ledger["studies"] if s["family"] == "stock_selection")


def verify_prereg(candidate_name: str, prereg_dir: Path) -> Path:
    """Verify prereg/<name>.md exists and contains the fixed pass rule before holdout runs."""
    path = prereg_dir / f"{candidate_name}.md"
    if not path.exists():
        raise RuntimeError(
            f"Pre-registration missing for '{candidate_name}': expected {path}. "
            "Write prereg/<name>.md and commit before touching holdout 2021+."
        )
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 50:
        raise RuntimeError(f"Pre-registration file {path} is too short/empty.")
    required_tokens = ("2013-2020", "2021+", "1.0", "2.0", "2pp")
    missing = [tok for tok in required_tokens if tok not in text]
    if missing:
        raise RuntimeError(
            f"Pre-registration file {path} is missing verbatim pass rule tokens: {missing}"
        )
    return path


def verify_ledger_registered(candidate_name: str, ledger_path: Path = LEDGER_PATH) -> int:
    """Verify candidate_name is recorded in trial_ledger.json and return current N_sel."""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    found = False
    for study in ledger.get("studies", []):
        if study.get("family") != "stock_selection":
            continue
        src = str(study.get("source", ""))
        st_name = str(study.get("study", ""))
        cands = study.get("candidates", [])
        if candidate_name in src or candidate_name in st_name or candidate_name in cands:
            found = True
            break
    if not found:
        raise RuntimeError(
            f"Candidate '{candidate_name}' not found in {ledger_path}. "
            "Append +1 trial to trial_ledger.json and commit before running holdout."
        )
    return ledger_n_sel(ledger_path)


def write_prereg_file(
    candidate_name: str,
    *,
    formula: str,
    frozen_params: dict,
    rationale: str,
    source_branch: str = "agent/r3-features",
    is_combination: bool = False,
    prereg_dir: Path = DEFAULT_BOARD_DIR / "prereg",
    as_of: str = AS_OF,
    n_sel_after: int | None = None,
) -> Path:
    """Write prereg/<name>.md with formula, frozen params, and verbatim FIXED PASS RULE."""
    prereg_dir.mkdir(parents=True, exist_ok=True)
    path = prereg_dir / f"{candidate_name}.md"
    if path.exists():
        raise FileExistsError(f"Pre-registration file already exists: {path}")
    lines = [
        f"# Round 3 Pre-registration: `{candidate_name}`",
        "",
        f"- **Date**: {as_of}",
        f"- **Source branch**: `{source_branch}`",
        f"- **Trial type**: {'Combination candidate (separate +1 N_sel trial)' if is_combination else 'Standalone candidate (+1 N_sel trial)'}",
    ]
    if n_sel_after is not None:
        lines.append(f"- **Trial ledger `N_sel` after registration**: {n_sel_after}")
    lines.extend([
        "",
        "## Motivation & Hypothesis",
        "",
        rationale.strip(),
        "",
        "## Formula",
        "",
        "```text",
        formula.strip(),
        "```",
        "",
        "## Frozen Parameters",
        "",
        "```json",
        json.dumps(frozen_params, indent=2, sort_keys=True),
        "```",
        "",
        "## Evaluation Panel & Execution",
        "",
        "- Primary panel: `/home/eren/bist_project/data/research/fp/factors_monthly.parquet` (lag-75 PIT).",
        "- Robustness panel: `/home/eren/bist_project/data/research/fp/factors_monthly_kapdates.parquet` (cannot flip FAIL to PASS).",
        "- Holdout 2021+ has NOT been inspected prior to this pre-registration.",
        "",
        "## FIXED PASS RULE (verbatim)",
        "",
        FIXED_PASS_RULE_VERBATIM,
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def append_trial_ledger(
    candidate_name: str,
    description: str,
    ledger_path: Path = LEDGER_PATH,
    as_of: str = AS_OF,
) -> int:
    """Append a single +1 stock_selection trial for candidate_name to trial_ledger.json."""
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for study in ledger.get("studies", []):
        if study.get("study") == f"round3_{candidate_name}":
            raise ValueError(f"Trial already exists in ledger for round3_{candidate_name}")
    ledger["as_of"] = as_of
    ledger["studies"].append({
        "study": f"round3_{candidate_name}",
        "family": "stock_selection",
        "trials": 1,
        "source": f"{candidate_name}: {description}",
    })
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return ledger_n_sel(ledger_path)


# ---------------------------------------------------------------------------
# 3. Combination & Alignment Helpers
# ---------------------------------------------------------------------------
def align_score_to_panel(score: pd.Series, df: pd.DataFrame) -> np.ndarray:
    """Align a score Series indexed by (date, ticker) or df.index onto df rows."""
    if isinstance(score.index, pd.MultiIndex) and score.index.nlevels == 2:
        idx = score.index
        dates = month_end(pd.Series(idx.get_level_values(0))).to_numpy()
        tickers = idx.get_level_values(1).astype(str).to_numpy()
        s_norm = pd.Series(score.to_numpy(dtype=float), index=pd.MultiIndex.from_arrays([dates, tickers]))
        if s_norm.index.has_duplicates:
            raise ValueError("Candidate score series has duplicate (date, ticker) keys.")
        key = pd.MultiIndex.from_arrays([df["date"], df["ticker"].astype(str)])
        return s_norm.reindex(key).to_numpy(dtype=float)
    if len(score) == len(df) and score.index.equals(df.index):
        return score.to_numpy(dtype=float)
    return score.reindex(df.index).to_numpy(dtype=float)


def rank_average_combo(
    df: pd.DataFrame,
    col_a: str,
    col_b: str,
    weight_a: float = 0.5,
    require_both: bool = False,
) -> pd.Series:
    """Monthly cross-sectional percentile-rank weighted average of two score columns.

    Higher score -> higher percentile rank in (0, 1].
    If require_both=False and col_b is NaN for a row, falls back to rank(col_a).
    """
    if not (0.0 <= weight_a <= 1.0):
        raise ValueError(f"weight_a must be in [0, 1], got {weight_a}")
    weight_b = 1.0 - weight_a
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for _, g in df.groupby("date", sort=False):
        ra = g[col_a].rank(ascending=True, pct=True)
        rb = g[col_b].rank(ascending=True, pct=True)
        if require_both:
            both = ra.notna() & rb.notna()
            comb = pd.Series(np.nan, index=g.index, dtype=float)
            comb.loc[both] = weight_a * ra.loc[both] + weight_b * rb.loc[both]
        else:
            comb = weight_a * ra + weight_b * rb
            only_a = ra.notna() & rb.isna()
            only_b = ra.isna() & rb.notna()
            comb.loc[only_a] = ra.loc[only_a]
            comb.loc[only_b] = rb.loc[only_b]
        out.loc[g.index] = comb
    return out


def z_average_combo(
    df: pd.DataFrame,
    col_a: str,
    col_b: str,
    weight_a: float = 0.5,
    sector_neutral: bool = False,
    min_n: int = 5,
    require_both: bool = False,
) -> pd.Series:
    """Monthly cross-sectional winsorized z-score weighted average of two score columns."""
    if not (0.0 <= weight_a <= 1.0):
        raise ValueError(f"weight_a must be in [0, 1], got {weight_a}")
    weight_b = 1.0 - weight_a
    za = df.groupby("date", group_keys=False)[col_a].apply(lambda s: fb.winsorize_z(s, lo=0.01, hi=0.99))
    zb = df.groupby("date", group_keys=False)[col_b].apply(lambda s: fb.winsorize_z(s, lo=0.01, hi=0.99))
    if require_both:
        comb = pd.Series(np.nan, index=df.index, dtype=float)
        both = za.notna() & zb.notna()
        comb.loc[both] = weight_a * za.loc[both] + weight_b * zb.loc[both]
    else:
        comb = weight_a * za + weight_b * zb
        only_a = za.notna() & zb.isna()
        only_b = za.isna() & zb.notna()
        comb.loc[only_a] = za.loc[only_a]
        comb.loc[only_b] = zb.loc[only_b]
    if sector_neutral:
        tmp = df[["date", "sector"]].copy()
        tmp["_comb"] = comb
        return fb.sector_neutralize(tmp, "_comb", min_n=min_n)
    return comb


# ---------------------------------------------------------------------------
# 4. Core Panel Evaluation (FIXED PASS RULE)
# ---------------------------------------------------------------------------
def evaluate_pass_rule(
    disc_d: dict,
    hold_d: dict,
    cand_hold_dd_usd_pct: float,
    r0_hold_dd_usd_pct: float,
) -> dict:
    """Delegate directly to research_valuation_round1.evaluate_pass_rule for exact parity."""
    return r1.evaluate_pass_rule(disc_d, hold_d, cand_hold_dd_usd_pct, r0_hold_dd_usd_pct)


def evaluate_scored_panel(
    scored: pd.DataFrame,
    candidate_names: list[str],
    macro: pd.DataFrame,
    fx: pd.DataFrame,
    raw_dir: Path,
    frames_cache: dict[str, pd.DataFrame],
    n_sel: int,
    var_sr: float,
) -> dict:
    """Evaluate R0 and candidate_names on a prepared panel that already contains score columns.

    Exact same simulation engine, universe, liquidity cut, 1M TL real capital,
    base costs, next-close fills, NW t (6 lags), and DSR methodology as
    scripts/research_portfolio_backtest.py and scripts/research_valuation_round1.py.
    """
    df = scored.copy()
    if "R0" not in df.columns:
        df["R0"] = df["value_sn_z"]
    all_methods = ("R0", *candidate_names)

    windows = {
        "discovery": lambda idx: idx < SPLIT,
        "holdout": lambda idx: idx >= SPLIT,
        "ias29_2024_05_plus": lambda idx: idx >= IAS29_START,
        "full": lambda idx: idx >= pd.Timestamp.min,
    }
    ic_windows = ("discovery", "holdout", "ias29_2024_05_plus", "full")

    # 1. Cross-sectional Spearman Rank-IC and paired delta-IC vs R0
    ics = {m: fb.rank_ic(df, m, "fwd_ret_1m") for m in all_methods}
    ic_report: dict[str, dict] = {}
    for m in all_methods:
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
    for m in candidate_names:
        sw = switcher_and_overlap(df, m, "R0")
        switcher_report[m] = {}
        for wname in ic_windows:
            wfn = windows[wname]
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

    # 3. Costed portfolio simulation (1M TL real capital, base costs, next-close fills)
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
    r0_hold_dd_usd = float(stats(r0_p[r0_p.index >= SPLIT].reset_index())["max_dd_usd_pct"])

    portfolio_report: dict[str, dict] = {}
    for m, p in sims.items():
        portfolio_report[m] = {}
        for wname, wfn in windows.items():
            sub = p[wfn(p.index)].reset_index()
            base_stats = stats(sub)
            vs_ew_net = nw_stat(p.loc[wfn(p.index), "active_ew_net"])
            vs_ew_gross = nw_stat(p.loc[wfn(p.index), "active"])
            sub_panel = df[wfn(df["date"])]
            cov_pct = round(100.0 * float(sub_panel[m].notna().mean()), 2) if len(sub_panel) else 0.0
            n_months_sig = int(sub_panel.groupby("date")[m].apply(lambda s: s.notna().any()).sum()) if len(sub_panel) else 0

            entry = {
                "months": int(len(sub)),
                "months_with_signal": n_months_sig,
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
                # D = net active(cand) - net active(R0) = (port_cand - ew_net) - (port_R0 - ew_net)
                d_series = (p["active_ew_net"] - r0_p["active_ew_net"]).loc[wfn(p.index)]
                entry["paired_diff_vs_R0"] = nw_stat(d_series)
            portfolio_report[m][wname] = entry

    # 4. Deflated Sharpe Ratio at updated N_sel
    dsr_report: dict[str, dict] = {}
    for m, p in sims.items():
        d = rs.deflated_sharpe(p["active_ew_net"].dropna(), n_sel, var_sr)
        dsr_report[m] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}
        dsr_report[m]["var_sr_cross_variant"] = round(var_sr, 5)

    # 5. Verdicts under the verbatim FIXED PASS RULE
    verdicts: dict[str, dict] = {}
    for m in candidate_names:
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
        "trial_ledger_N_sel": n_sel,
        "portfolio_simulation": portfolio_report,
        "rank_ic": ic_report,
        "switcher_analysis": switcher_report,
        "dsr": dsr_report,
        "verdicts": verdicts,
    }


# ---------------------------------------------------------------------------
# 5. Markdown Result Formatter
# ---------------------------------------------------------------------------
def _fmt(v, fmt: str = "+.2f", suffix: str = "") -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "n/a"
    return f"{v:{fmt}}{suffix}"


def format_candidate_markdown(
    spec: CandidateSpec,
    primary: dict,
    kap: dict,
    n_sel: int,
    var_sr: float,
    prereg_path: Path,
    json_path: Path,
    as_of: str = AS_OF,
) -> str:
    """Format /home/eren/bist_wt/r3-board/results/<name>.md cleanly."""
    name = spec.name
    v_p = primary["verdicts"][name]
    v_k = kap["verdicts"][name]
    ps_c = primary["portfolio_simulation"][name]
    ps_r = primary["portfolio_simulation"]["R0"]
    dsr_c = primary["dsr"][name]
    dsr_r = primary["dsr"]["R0"]
    ic_c = primary["rank_ic"][name]
    sw_c = primary["switcher_analysis"][name]

    lines = [
        f"# Round 3 Backtest Result: `{name}`",
        "",
        f"- **Date**: {as_of}",
        f"- **Description**: {spec.description}",
        f"- **Combination trial**: {'Yes' if spec.is_combination else 'No'}",
        f"- **Frozen params**: `{json.dumps(spec.frozen_params, sort_keys=True)}`",
        f"- **Pre-registration**: `{prereg_path}`",
        f"- **JSON report**: `{json_path}`",
        f"- **Trial ledger `N_sel`**: {n_sel} (`V[SR]` monthly = {var_sr:.5f})",
        f"- **Primary panel**: `fp/factors_monthly.parquet` (lag-75 PIT, {primary['n_discovery']} disc / {primary['n_holdout']} holdout months)",
        f"- **Robustness panel**: `fp/factors_monthly_kapdates.parquet` ({kap['n_discovery']} disc / {kap['n_holdout']} holdout months)",
        "",
        f"## Verdict (Primary lag-75): **{v_p['verdict']}**",
        "",
        f"> **Fixed pass rule**: {FIXED_PASS_RULE_VERBATIM}",
        "",
        "| Check | Value | Threshold | Result |",
        "|---|---:|---:|:---:|",
        f"| Discovery D (2013-2020) | {_fmt(v_p['disc_D_ann_pct'], '+.2f', '%/yr')} | > 0 | {'PASS' if v_p['disc_D_pos'] else 'FAIL'} |",
        f"| Discovery NW t(D) | {_fmt(v_p['disc_t'], '+.2f')} | >= 1.00 | {'PASS' if v_p['disc_t_ge_1'] else 'FAIL'} |",
        f"| Holdout D (2021+) | {_fmt(v_p['hold_D_ann_pct'], '+.2f', '%/yr')} | > 0 | {'PASS' if v_p['hold_D_pos'] else 'FAIL'} |",
        f"| Holdout NW t(D) | {_fmt(v_p['hold_t'], '+.2f')} | >= 2.00 | {'PASS' if v_p['hold_t_ge_2'] else 'FAIL'} |",
        f"| Holdout USD MaxDD vs R0 | {_fmt(v_p['hold_max_dd_usd_pct'], '.1f', '%')} vs {_fmt(v_p['r0_hold_max_dd_usd_pct'], '.1f', '%')} ({_fmt(v_p['hold_dd_usd_diff_vs_R0_pp'], '+.2f', ' pp')}) | >= -2.00 pp | {'PASS' if v_p['hold_dd_usd_ok'] else 'FAIL'} |",
        "",
        "## Primary (lag-75) Performance by Window",
        "",
        "| Window | Months | Cand vs EW net %/yr (t) | R0 vs EW net %/yr (t) | Paired D %/yr (NW t) | Cand MaxDD USD | R0 MaxDD USD | Cand Turnover | R0 Turnover | Cand Cost %/yr | Cov % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for wkey, wlabel in (
        ("discovery", "Discovery (2013-2020)"),
        ("holdout", "Holdout (2021+)"),
        ("ias29_2024_05_plus", "IAS 29 (2024-05+)"),
        ("full", "Full"),
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
            f"{_fmt(c['cost_ann_pct'], '.2f', '%')} | {_fmt(c['coverage_pct'], '.1f', '%')} |"
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
        "## Diagnostics (Primary lag-75)",
        "",
        "| Window | Rank-IC (NW t) | dIC vs R0 (NW t) | Rank Corr vs R0 | Top-20% Overlap | Switches/mo | Entrants - Dropouts %/yr (t) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for wkey, wlabel in (("discovery", "Discovery"), ("holdout", "Holdout"), ("ias29_2024_05_plus", "IAS 29"), ("full", "Full")):
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
        "## KAP-date Panel Sensitivity (Robustness Only)",
        "",
        f"- **Discovery D**: {_fmt(v_k['disc_D_ann_pct'], '+.2f', '%/yr')} (NW t = {_fmt(v_k['disc_t'])})",
        f"- **Holdout D**: {_fmt(v_k['hold_D_ann_pct'], '+.2f', '%/yr')} (NW t = {_fmt(v_k['hold_t'])})",
        f"- **Holdout USD MaxDD**: {_fmt(v_k['hold_max_dd_usd_pct'], '.1f', '%')} vs R0 {_fmt(v_k['r0_hold_max_dd_usd_pct'], '.1f', '%')} ({_fmt(v_k['hold_dd_usd_diff_vs_R0_pp'], '+.2f', ' pp')})",
        f"- **KAP-date Verdict**: {v_k['verdict']} (cannot overturn primary lag-75 verdict)",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6. Runner
# ---------------------------------------------------------------------------
def run_candidates(
    candidate_names: list[str],
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
    """Run one or more registered candidates through the full lag-75 + KAP-date evaluation."""
    if not candidate_names:
        raise ValueError("At least one candidate name is required.")
    unknown = [c for c in candidate_names if c not in CANDIDATE_REGISTRY]
    if unknown:
        raise KeyError(f"Unregistered candidates: {unknown}. Registered: {sorted(CANDIDATE_REGISTRY)}")

    prereg_paths: dict[str, Path] = {}
    if not skip_gates:
        for name in candidate_names:
            prereg_paths[name] = verify_prereg(name, prereg_dir)
            verify_ledger_registered(name, ledger_path)
    else:
        for name in candidate_names:
            prereg_paths[name] = prereg_dir / f"{name}.md"

    n_sel = ledger_n_sel(ledger_path)
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
        for name in candidate_names:
            spec = CANDIDATE_REGISTRY[name]
            s = spec.fn(raw_safe, prep_safe, ctx)
            out[name] = align_score_to_panel(s, out)
        return out

    scored_lag75 = attach_scores(raw_lag75, df_lag75, "lag75")
    scored_kap = attach_scores(raw_kap, df_kap, "kapdates")

    frames_cache: dict[str, pd.DataFrame] = {}
    primary = evaluate_scored_panel(
        scored_lag75, candidate_names, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr
    )
    kap = evaluate_scored_panel(
        scored_kap, candidate_names, macro, fx, raw_dir, frames_cache, n_sel=n_sel, var_sr=var_sr
    )

    reports_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, dict] = {}
    for name in candidate_names:
        spec = CANDIDATE_REGISTRY[name]
        # Extract single-candidate slice for clean per-candidate JSON
        def _slice(panel_res: dict) -> dict:
            return {
                "n_discovery": panel_res["n_discovery"],
                "n_holdout": panel_res["n_holdout"],
                "n_ias29": panel_res["n_ias29"],
                "n_full": panel_res["n_full"],
                "trial_ledger_N_sel": panel_res["trial_ledger_N_sel"],
                "portfolio_simulation": {
                    "R0": panel_res["portfolio_simulation"]["R0"],
                    name: panel_res["portfolio_simulation"][name],
                },
                "rank_ic": {
                    "R0": panel_res["rank_ic"]["R0"],
                    name: panel_res["rank_ic"][name],
                },
                "switcher_analysis": {name: panel_res["switcher_analysis"][name]},
                "dsr": {
                    "R0": panel_res["dsr"]["R0"],
                    name: panel_res["dsr"][name],
                },
                "verdicts": {name: panel_res["verdicts"][name]},
            }

        cand_payload = {
            "as_of": as_of,
            "candidate": name,
            "description": spec.description,
            "is_combination": spec.is_combination,
            "frozen_params": spec.frozen_params,
            "fixed_pass_rule": FIXED_PASS_RULE_VERBATIM,
            "trial_ledger_N_sel": n_sel,
            "var_sr_monthly": round(var_sr, 5),
            "prereg_path": str(prereg_paths[name]),
            "primary_lag75": _slice(primary),
            "sensitivity_kapdates": _slice(kap),
        }
        json_path = reports_dir / f"research_round3_{name}_{as_of}.json"
        json_path.write_text(json.dumps(cand_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        md_text = format_candidate_markdown(
            spec, primary, kap, n_sel=n_sel, var_sr=var_sr,
            prereg_path=prereg_paths[name], json_path=json_path, as_of=as_of,
        )
        md_path = results_dir / f"{name}.md"
        md_path.write_text(md_text, encoding="utf-8")
        outputs[name] = {"payload": cand_payload, "json_path": str(json_path), "md_path": str(md_path)}

    return {
        "as_of": as_of,
        "trial_ledger_N_sel": n_sel,
        "var_sr_monthly": round(var_sr, 5),
        "candidates": candidate_names,
        "primary_lag75": primary,
        "sensitivity_kapdates": kap,
        "outputs": outputs,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Round 3 confirmatory backtest runner.")
    ap.add_argument("--candidate", action="append", dest="candidates", help="Registered candidate name (repeatable).")
    ap.add_argument("--list", action="store_true", help="List registered candidates and exit.")
    ap.add_argument("--prereg-dir", type=Path, default=DEFAULT_BOARD_DIR / "prereg")
    ap.add_argument("--results-dir", type=Path, default=DEFAULT_BOARD_DIR / "results")
    ap.add_argument("--reports-dir", type=Path, default=ROOT / "data" / "reports")
    ap.add_argument("--research-dir", type=Path, default=None)
    ap.add_argument("--fp-dir", type=Path, default=None)
    ap.add_argument("--as-of", default=AS_OF)
    args = ap.parse_args()

    if args.list:
        print("Registered candidates:", sorted(CANDIDATE_REGISTRY))
        return

    names = args.candidates or sorted(CANDIDATE_REGISTRY)
    if not names:
        raise SystemExit("No candidates registered or specified.")

    res = run_candidates(
        names,
        research_dir=args.research_dir,
        fp_dir=args.fp_dir,
        prereg_dir=args.prereg_dir,
        results_dir=args.results_dir,
        reports_dir=args.reports_dir,
        as_of=args.as_of,
    )

    print(f"\n=== ROUND 3 SUMMARY (N_sel={res['trial_ledger_N_sel']}, V[SR]={res['var_sr_monthly']:.5f}) ===")
    for name in names:
        vp = res["primary_lag75"]["verdicts"][name]
        vk = res["sensitivity_kapdates"]["verdicts"][name]
        dsr = res["primary_lag75"]["dsr"][name]["dsr"]
        print(
            f"{name:28s} | lag75: D_disc={vp['disc_D_ann_pct']:+6.2f}% (t={vp['disc_t']:+5.2f}) "
            f"| D_hold={vp['hold_D_ann_pct']:+6.2f}% (t={vp['hold_t']:+5.2f}) "
            f"| DD_diff={vp['hold_dd_usd_diff_vs_R0_pp']:+5.2f}pp | DSR={dsr:.4f} | {vp['verdict']} "
            f"(kap: {vk['verdict']})"
        )


if __name__ == "__main__":
    main()
