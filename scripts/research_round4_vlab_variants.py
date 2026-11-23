"""Round 4 vlab batch1: value_sn construction repairs (pre-registered).

Each variant rebuilds the 4-leg value composite exactly like R0
(scripts/backtest_factor_model.py::add_composites: per-month winsorize_z of each
leg on the liquidity-filtered universe, equal-weight mean of available legs,
then fb.sector_neutralize) and changes ONE thing. Frozen, zero free parameters
except the a-priori 0.15 momentum weight in vlab_val_mom15.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import factor_backtest as fb
from research_round3_features import _attach_pit_quarterly_values
from research_round4_vlab import VariantSpec, register_variant

BATCH = "batch1"
Q_COLS = ["ttm_revenue", "ttm_gross_profit", "ttm_op_profit", "fin_debt", "cash"]


def _quarterly_inputs(prep: pd.DataFrame, ctx: dict) -> pd.DataFrame:
    """PIT quarterly values matched on (ticker, stmt_period) the panel already selected."""
    return _attach_pit_quarterly_values(prep, ctx["quarterly"], Q_COLS)


def _ev(prep: pd.DataFrame, q: pd.DataFrame) -> pd.Series:
    """Same EV definition as core/pit_panel.value_ratios (ey leg): mcap + fin_debt - cash, > 0."""
    ev = prep["mcap"].astype(float) + q["fin_debt"] - q["cash"]
    return ev.where(ev > 0)


def _leg_z(prep: pd.DataFrame, raw_leg: pd.Series) -> pd.Series:
    """Per-month winsorize_z, identical to fb.prepare for a +1-signed factor."""
    s = pd.Series(raw_leg.to_numpy(dtype=float), index=prep.index)
    return s.groupby(prep["date"]).transform(fb.winsorize_z)


def _composite(prep: pd.DataFrame, legs: dict[str, pd.Series]) -> pd.Series:
    """Equal-weight mean of leg z-scores then sector-neutralize (R0 recipe)."""
    tmp = prep[["date", "sector"]].copy()
    tmp["vz"] = pd.concat(legs, axis=1).mean(axis=1)
    return fb.sector_neutralize(tmp, "vz")


def _r0_legs(prep: pd.DataFrame) -> dict[str, pd.Series]:
    return {k: prep[f"{k}_z"] for k in ("bm", "ep", "sp", "ey")}


def score_rev_ev(raw, prep, ctx):
    q = _quarterly_inputs(prep, ctx)
    legs = _r0_legs(prep)
    legs["sp"] = _leg_z(prep, q["ttm_revenue"] / _ev(prep, q))
    return _composite(prep, legs)


def score_gp_ev(raw, prep, ctx):
    q = _quarterly_inputs(prep, ctx)
    legs = _r0_legs(prep)
    legs["sp"] = _leg_z(prep, q["ttm_gross_profit"] / _ev(prep, q))
    return _composite(prep, legs)


def score_op_mcap(raw, prep, ctx):
    q = _quarterly_inputs(prep, ctx)
    legs = _r0_legs(prep)
    legs["ep"] = _leg_z(prep, q["ttm_op_profit"] / prep["mcap"].astype(float))
    return _composite(prep, legs)


def score_ep_floor0(raw, prep, ctx):
    legs = _r0_legs(prep)
    legs["ep"] = _leg_z(prep, prep["ep"].astype(float).clip(lower=0.0))
    return _composite(prep, legs)


def score_val_mom15(raw, prep, ctx):
    tmp = prep[["date", "sector"]].copy()
    tmp["m"] = prep["mom_12_1_z"]
    mom_sn = fb.sector_neutralize(tmp, "m")
    return 0.85 * prep["value_sn_z"] + 0.15 * mom_sn.fillna(0.0)


for _name, _fn, _desc, _params in (
    ("vlab_rev_ev", score_rev_ev, "R0 4-leg value with S/P replaced by Rev/EV (EV as in ey leg)", {}),
    ("vlab_gp_ev", score_gp_ev, "R0 4-leg value with S/P replaced by GrossProfit/EV", {}),
    ("vlab_op_mcap", score_op_mcap, "R0 4-leg value with E/P replaced by TTM operating profit / mcap", {}),
    ("vlab_ep_floor0", score_ep_floor0, "R0 4-leg value with E/P floored at 0 before winsorize_z", {"floor": 0.0}),
    ("vlab_val_mom15", score_val_mom15, "0.85*value_sn_z + 0.15*sector-neutral mom_12_1_z (NaN->0)", {"w_mom": 0.15}),
):
    register_variant(VariantSpec(name=_name, batch=BATCH, description=_desc, score_fn=_fn, frozen_params=_params))
