from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import portfolio_backtest as pb  # noqa: E402
from research_round4_risk import (  # noqa: E402
    build_batch2_targets,
    build_pit_vol6m,
    cap_weights,
    evaluate_gauntlet,
    holm_adjust,
    simulate_weighted,
    smooth_cohorts,
    solve_max_diversification,
)


def _synthetic_market(n_days: int = 120):
    days = pd.bdate_range("2020-01-02", periods=n_days)
    rng = np.random.default_rng(42)
    tickers = ["AAA", "BBB", "CCC", "DDD"]
    rets = rng.normal(0.0005, 0.02, size=(n_days, len(tickers)))
    close = pd.DataFrame(100.0 * np.cumprod(1.0 + rets, axis=0), index=days, columns=tickers)
    opn = close * (1.0 + rng.normal(0.0, 0.002, size=close.shape))
    adv = pd.DataFrame(5e6, index=days, columns=tickers)
    sigma = pd.DataFrame(0.02, index=days, columns=tickers)
    rf_daily = pd.Series(0.0004, index=days)
    mkt = pb.Market(close=close, open=opn, adv=adv, sigma=sigma, rf_daily=rf_daily)
    months = [
        days[15].to_period("M").to_timestamp("M"),
        days[37].to_period("M").to_timestamp("M"),
        days[60].to_period("M").to_timestamp("M"),
        days[83].to_period("M").to_timestamp("M"),
    ]
    d0_of = {m: days[days.searchsorted(m, side="right") - 1] for m in months}
    liq = {m: np.array([1e6, 3e6, 5e6, 8e6]) for m in months}
    cap = {m: 1e6 for m in months}
    return mkt, months, d0_of, liq, cap


def test_simulate_weighted_parity_with_pb_simulate() -> None:
    mkt, months, d0_of, liq, cap = _synthetic_market()
    ew_lists = {
        months[0]: ["AAA", "BBB", "CCC"],
        months[1]: ["BBB", "CCC", "DDD"],
        months[2]: ["AAA", "CCC"],
        months[3]: ["AAA", "BBB", "DDD"],
    }
    ew_weights = {m: {tk: 1.0 / len(tks) for tk in tks} for m, tks in ew_lists.items()}

    p_ref = pb.simulate(ew_lists, months, d0_of, mkt, liq, cap)
    p_w = simulate_weighted(ew_weights, months, d0_of, mkt, liq, cap)

    pd.testing.assert_frame_equal(p_ref, p_w, check_exact=False, atol=1e-12, rtol=1e-12)


def test_cap_weights_enforces_name_and_sector_caps() -> None:
    w0 = np.array([0.40, 0.30, 0.15, 0.05, 0.05, 0.03, 0.02])
    sectors = np.array(["S1", "S1", "S1", "S2", "S3", "S4", "S5"])
    wc = cap_weights(w0, sectors, max_name=0.20, max_sec=0.35)
    assert np.isclose(wc.sum(), 1.0, atol=1e-10)
    assert wc.max() <= 0.20 + 1e-9
    for s in np.unique(sectors):
        assert wc[sectors == s].sum() <= 0.35 + 1e-9


def test_pit_vol6m_has_no_lookahead() -> None:
    days = pd.bdate_range("2020-01-02", periods=150)
    rng = np.random.default_rng(7)
    close = pd.DataFrame({"AAA": 100.0 * np.cumprod(1 + rng.normal(0, 0.02, 150))}, index=days)
    v_orig = build_pit_vol6m(close, window=126, min_periods=60)

    close_mod = close.copy()
    close_mod.iloc[130:] *= 10.0  # future shock after day 129
    v_mod = build_pit_vol6m(close_mod, window=126, min_periods=60)

    assert np.isclose(v_orig.iloc[129]["AAA"], v_mod.iloc[129]["AAA"], atol=1e-12)


def test_smooth_cohorts_filters_missing_prices() -> None:
    days = pd.bdate_range("2020-01-02", periods=60)
    close = pd.DataFrame({"AAA": 10.0, "BBB": 20.0, "CCC": 30.0}, index=days)
    m0, m1 = days[20], days[40]
    close.loc[m1, "AAA"] = np.nan  # AAA delisted/untradable on d0(m1)
    raw = {m0: {"AAA": 0.5, "BBB": 0.5}, m1: {"BBB": 0.5, "CCC": 0.5}}
    d0 = {m0: m0, m1: m1}
    sm = smooth_cohorts(raw, [m0, m1], d0, close, k=3)
    assert "AAA" not in sm[m1]
    assert np.isclose(sum(sm[m1].values()), 1.0)
    assert np.isclose(sm[m1]["BBB"], 2.0 / 3.0)
    assert np.isclose(sm[m1]["CCC"], 1.0 / 3.0)


def test_holm_adjust_and_gauntlet_verdict() -> None:
    adj = holm_adjust({"a": 0.008, "b": 0.02, "c": 0.04, "d": 0.20, "e": 0.50})
    assert np.isclose(adj["a"], 0.04)
    assert np.isclose(adj["b"], 0.08)
    assert np.isclose(adj["c"], 0.12)

    def _mock_entry(d_full, t_full, d_blocks, dd_full, dd_hold, to):
        return {
            "full": {"paired_diff_vs_R0": {"mean_ann_pct": d_full, "t": t_full, "months": 161}, "max_dd_usd_pct": dd_full, "turnover_pct": to},
            "holdout": {"max_dd_usd_pct": dd_hold},
            "2013-16": {"paired_diff_vs_R0": {"mean_ann_pct": d_blocks[0], "t": 1.0}},
            "2017-20": {"paired_diff_vs_R0": {"mean_ann_pct": d_blocks[1], "t": 1.0}},
            "2021-23": {"paired_diff_vs_R0": {"mean_ann_pct": d_blocks[2], "t": 1.0}},
            "2024+": {"paired_diff_vs_R0": {"mean_ann_pct": d_blocks[3], "t": 1.0}},
        }

    primary = {
        "portfolio": {
            "R0": {"full": {"max_dd_usd_pct": -55.0, "turnover_pct": 20.0}, "holdout": {"max_dd_usd_pct": -35.0}},
            "v_pass": _mock_entry(3.0, 3.0, [1.0, 2.0, 3.0, 4.0], -56.0, -35.5, 25.0),
            "v_fail_block": _mock_entry(3.0, 3.0, [1.0, -0.1, 3.0, 4.0], -56.0, -35.5, 25.0),
        }
    }
    kap = {
        "portfolio": {
            "v_pass": {"full": {"paired_diff_vs_R0": {"mean_ann_pct": 2.0, "t": 1.5}}},
            "v_fail_block": {"full": {"paired_diff_vs_R0": {"mean_ann_pct": 2.0, "t": 1.5}}},
        }
    }
    res = evaluate_gauntlet(primary, kap, ["v_pass", "v_fail_block"])
    assert res["v_pass"]["verdict"] == "PASS"
    assert res["v_fail_block"]["verdict"] == "FAIL"


def test_solve_max_diversification_constraints() -> None:
    days = pd.bdate_range("2020-01-02", periods=100)
    rng = np.random.default_rng(123)
    tickers = [f"T{i:02d}" for i in range(30)]
    sectors = np.array(["S1"] * 6 + ["S2"] * 6 + ["S3"] * 5 + ["S4"] * 5 + ["S5"] * 4 + ["S6"] * 4)
    rets = pd.DataFrame(rng.normal(0.0, 0.02, size=(100, 30)), index=days, columns=tickers)
    w = solve_max_diversification(rets, tickers, sectors, max_name=0.05, max_sec=0.20, min_periods=60)
    assert len(w) == 30
    assert np.isclose(w.sum(), 1.0, atol=1e-9)
    assert w.max() <= 0.05 + 1e-8
    assert w.min() >= -1e-12
    for s in np.unique(sectors):
        assert w[sectors == s].sum() <= 0.20 + 1e-8


def test_batch2_sn_invvol_preserves_sector_shares() -> None:
    days = pd.bdate_range("2020-01-02", periods=100)
    rng = np.random.default_rng(99)
    n_univ = 150
    tickers = [f"T{i:03d}" for i in range(n_univ)]
    sectors = np.array([f"S{(i % 6) + 1}" for i in range(n_univ)])
    close = pd.DataFrame(
        100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.02, size=(100, n_univ)), axis=0),
        index=days,
        columns=tickers,
    )
    dt = days[-1]
    df = pd.DataFrame({
        "date": dt,
        "ticker": tickers,
        "sector": sectors,
        "value_sn_z": np.linspace(3.0, -1.0, n_univ),
    })
    tmap = build_batch2_targets(df, [dt], {dt: dt}, close)
    w_r0 = tmap["R0"][dt]
    w_sn = tmap["risk_sn_invvol"][dt]
    top_df = df.iloc[:30]
    for sec, grp in top_df.groupby("sector"):
        s_r0 = sum(w_r0[tk] for tk in grp["ticker"])
        s_sn = sum(w_sn[tk] for tk in grp["ticker"])
        assert np.isclose(s_r0, s_sn, atol=1e-10)

