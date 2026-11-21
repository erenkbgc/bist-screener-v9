"""Unit tests for P4-1 free-float filter selection and D3 decision logic."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import research_free_float as rff  # noqa: E402
from research_portfolio_backtest import d3_verdict  # noqa: E402


def test_flag_ff1_excludes_bottom_decile_and_keeps_missing():
    dt = pd.Timestamp("2024-01-31")
    # 10 stocks with positive ff_mcap (10..100) + 2 stocks with NaN
    df = pd.DataFrame({
        "date": [dt] * 12,
        "ticker": [f"T{i}" for i in range(12)],
        "ff_mcap": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, np.nan, np.nan],
        "value_sn_z": np.linspace(2.0, -1.0, 12),
    })
    fl = rff.flag_ff1(df, drop_pct=0.10)
    # 10th percentile of [10..100] is 19.0 -> only T0 (10.0) is strictly below 19.0
    assert fl.tolist() == [True] + [False] * 11
    # Missing ff_mcap rows (T10, T11) are never excluded
    assert not fl.iloc[10] and not fl.iloc[11]


def test_flag_ff1_is_per_month_and_ignores_nonpositive():
    d1, d2 = pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")
    df = pd.DataFrame({
        "date": [d1] * 5 + [d2] * 5,
        "ticker": [f"A{i}" for i in range(5)] + [f"B{i}" for i in range(5)],
        # In d1, A0 has 0 (nonpositive -> treated as missing, not excluded); pos=[10,20,30,40], q10=13 -> A1 excluded
        # In d2, pos=[100,200,300,400,500], q10=140 -> B0 excluded
        "ff_mcap": [0.0, 10.0, 20.0, 30.0, 40.0, 100.0, 200.0, 300.0, 400.0, 500.0],
        "value_sn_z": [1.0] * 10,
    })
    fl = rff.flag_ff1(df, drop_pct=0.10)
    assert fl.tolist() == [False, True, False, False, False, True, False, False, False, False]


def test_selections_ff_reranks_after_exclusion():
    dt = pd.Timestamp("2024-01-31")
    # 10 stocks; T0 has highest value_sn_z but lowest ff_mcap -> excluded in FF1
    df = pd.DataFrame({
        "date": [dt] * 10,
        "ticker": [f"T{i}" for i in range(10)],
        "ff_mcap": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0],
        "value_sn_z": [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
    })
    fl = rff.flag_ff1(df, drop_pct=0.10)
    sel = rff.selections_ff(df, fl, top=0.20)
    # P0: top 20% of 10 -> rank <= 0.2 -> T0, T1
    assert sel["P0"][dt] == ["T0", "T1"]
    # FF1: 9 remaining (T1..T9); rank pct = 1/9=0.111 (T1), 2/9=0.222 (T2) -> only T1 has pct <= 0.2
    assert sel["FF1"][dt] == ["T1"]
    assert len(sel["EW"][dt]) == 10


def test_d3_verdict_boundaries():
    base = {"holdout": {"max_dd_usd_pct": -35.4}}
    alt_ok = {"holdout": {"max_dd_usd_pct": -37.4}}
    alt_bad_dd = {"holdout": {"max_dd_usd_pct": -37.5}}
    dd_ok = {"discovery": {"diff_ann_pct": -0.99, "t": -1.99}, "holdout": {"diff_ann_pct": 0.10, "t": 0.20}}
    dd_bad_ret = {"discovery": {"diff_ann_pct": -1.00, "t": -0.50}, "holdout": {"diff_ann_pct": 0.50, "t": 0.50}}
    dd_bad_t = {"discovery": {"diff_ann_pct": -0.80, "t": -2.01}, "holdout": {"diff_ann_pct": 0.50, "t": 0.50}}

    assert d3_verdict(dd_ok, alt_ok, base) == "PASS"
    assert d3_verdict(dd_ok, alt_bad_dd, base) == "FAIL"
    assert d3_verdict(dd_bad_ret, alt_ok, base) == "FAIL"
    assert d3_verdict(dd_bad_t, alt_ok, base) == "FAIL"
