"""Unit tests for scripts/research_valuation_round1.py
(docs/research/valuation_round1_preregistration.md)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from core import pit_panel  # noqa: E402
import research_valuation_round1 as vr1  # noqa: E402


def test_blom_normal_score_symmetry_and_missing():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, np.nan])
    u = vr1.blom_normal_score(s)
    assert u.isna().sum() == 1
    valid = u.dropna().to_numpy()
    assert len(valid) == 5
    # Symmetric around 0 and strictly increasing
    assert np.allclose(valid.mean(), 0.0, atol=1e-12)
    assert np.allclose(valid[2], 0.0, atol=1e-12)
    assert np.allclose(valid[0], -valid[4], atol=1e-12)
    assert np.all(np.diff(valid) > 0)

    # Fewer than 3 observations -> all NaN
    assert vr1.blom_normal_score(pd.Series([1.0, 2.0, np.nan])).isna().all()


def test_eb_sector_standardize_equalizes_dispersion_and_handles_singleton_sector():
    rng = np.random.default_rng(123)
    # Sector A: wide dispersion (sd ~ 3), Sector B: tight dispersion (sd ~ 0.3), Sector C: singleton
    v_a = rng.normal(loc=2.0, scale=3.0, size=25)
    v_b = rng.normal(loc=-1.0, scale=0.3, size=25)
    v_c = np.array([5.0])
    v = pd.Series(np.concatenate([v_a, v_b, v_c]))
    sec = pd.Series(["A"] * 25 + ["B"] * 25 + ["C"])

    z = vr1.eb_sector_standardize(v, sec, nu0=5.0)
    assert z.notna().all()
    # EB standardization shifts both big sectors near mean 0 and brings their SDs close to 1
    assert abs(z[sec == "A"].mean()) < 0.25
    assert abs(z[sec == "B"].mean()) < 0.25
    ratio_raw = v[sec == "A"].std() / v[sec == "B"].std()
    ratio_eb = z[sec == "A"].std() / z[sec == "B"].std()
    assert ratio_raw > 7.0
    assert 1.0 < ratio_eb < ratio_raw / 3.0
    # Singleton sector is finite (uses pooled within-sector variance)
    assert np.isfinite(z.iloc[-1])


def test_compute_s1_month_reliability_shrinkage():
    rng = np.random.default_rng(7)
    n = 40
    g = pd.DataFrame({
        "date": pd.Timestamp("2020-06-30"),
        "ticker": [f"T{i:02d}" for i in range(n)],
        "sector": [f"S{i % 4}" for i in range(n)],
        "bm": rng.lognormal(0.0, 0.5, size=n),
        "ep": rng.normal(0.10, 0.08, size=n),
        "sp": rng.lognormal(0.2, 0.6, size=n),
        "ey": rng.normal(0.12, 0.06, size=n),
    })
    # Introduce missing leg on first two rows
    g.loc[0, ["sp", "ey"]] = np.nan
    s1 = vr1.compute_s1_month(g)
    assert s1.notna().all()
    assert abs(s1.mean()) < 0.15


def test_m2_and_fv1_signals_on_synthetic_panel():
    # Build 8 quarters (2019Q1..2020Q4) + 2 IAS29 quarters (2023Q4, 2024Q1) across 30 tickers
    periods_nom = ["2019Q1", "2019Q2", "2019Q3", "2019Q4", "2020Q1", "2020Q2", "2020Q3", "2020Q4"]
    periods_ias = ["2023Q1", "2023Q2", "2023Q3", "2023Q4", "2024Q1"]
    all_periods = periods_nom + periods_ias

    m_idx = pd.period_range("2018-01", "2024-12", freq="M")
    macro = pd.DataFrame({
        "cpi_mom": 2.0,
        "cpi_yoy": 35.0,
        "policy": 25.0,
    }, index=m_idx.to_timestamp("M"))

    eb = pd.DataFrame({
        "month": pd.date_range("2018-01-31", "2024-12-31", freq="ME"),
        "date": pd.date_range("2018-01-31", "2024-12-31", freq="ME"),
        "isin": "US900123AL40",
        "maturity": pd.Timestamp("2034-02-14"),
        "yield": 7.5,
    })

    rng = np.random.default_rng(99)
    q_rows = []
    for i in range(30):
        tk = f"TK{i:02d}"
        for p in all_periods:
            pe = pit_panel.period_end(p)
            q_rev = float(100 + 5 * i)
            q_op = float(15 + 1.5 * i)
            q_rows.append({
                "ticker": tk,
                "period": p,
                "period_end": pe,
                "available_at": pit_panel.available_at(p),
                "equity_parent": float(200 + 10 * i),
                "equity": float(200 + 10 * i),
                "fin_debt": float(50 + 2 * (30 - i)),
                "cash": float(20 + i),
                "q_revenue": q_rev,
                "ttm_revenue": 4 * q_rev,
                "q_op_profit": q_op,
                "ttm_op_profit": 4 * q_op,
            })
    quarterly = pd.DataFrame(q_rows)

    # Build two decision months: 2020-12-31 (nominal 2020Q3) and 2024-04-30 (mixed 2023Q3 & 2023Q4)
    p_rows = []
    for dt, per_fn in (
        (pd.Timestamp("2020-12-31"), lambda idx: "2020Q3"),
        (pd.Timestamp("2024-04-30"), lambda idx: "2023Q4" if idx % 2 == 0 else "2023Q3"),
    ):
        for i in range(30):
            mcap = float(300 + 8 * i + rng.uniform(-20, 20))
            p_rows.append({
                "date": dt,
                "ticker": f"TK{i:02d}",
                "sector": f"SEC{i % 5}",
                "mcap": mcap,
                "tlvol60": float(1e7 * (i + 1)),
                "bm": (200 + 10 * i) / mcap,
                "ep": (40 + 4 * i) / mcap,
                "sp": (400 + 20 * i) / mcap,
                "ey": (60 + 6 * i) / (mcap + 30),
                "value_sn_z": float(i - 15) / 10.0,
                "stmt_period": per_fn(i),
                "fwd_ret_1m": 0.01 * (i - 15),
            })
    panel = pd.DataFrame(p_rows)

    scored = vr1.build_all_signals(panel, quarterly, macro, eb)
    for col in vr1.ALL_METHODS:
        assert col in scored.columns
        assert scored[col].notna().all()


def test_evaluate_pass_rule_all_conditions():
    # Passes when disc D > 0 (t >= 1.0), hold D > 0 (t >= 2.0), hold DD within 2.0 pp of R0
    res_pass = vr1.evaluate_pass_rule(
        {"mean_ann_pct": 1.25, "t": 1.05},
        {"mean_ann_pct": 2.10, "t": 2.05},
        cand_hold_dd_usd_pct=-36.8,
        r0_hold_dd_usd_pct=-35.4,
    )
    assert res_pass["verdict"] == "PASS"

    # Fails if discovery t < 1.0
    assert vr1.evaluate_pass_rule(
        {"mean_ann_pct": 1.25, "t": 0.95},
        {"mean_ann_pct": 2.10, "t": 2.50},
        cand_hold_dd_usd_pct=-34.0,
        r0_hold_dd_usd_pct=-35.4,
    )["verdict"] == "FAIL"

    # Fails if holdout t < 2.0
    assert vr1.evaluate_pass_rule(
        {"mean_ann_pct": 1.25, "t": 1.50},
        {"mean_ann_pct": 2.10, "t": 1.99},
        cand_hold_dd_usd_pct=-34.0,
        r0_hold_dd_usd_pct=-35.4,
    )["verdict"] == "FAIL"

    # Fails if holdout USD max DD is worse than R0 by > 2.0 pp (-37.5 < -35.4 - 2.0)
    res_dd_fail = vr1.evaluate_pass_rule(
        {"mean_ann_pct": 1.25, "t": 1.50},
        {"mean_ann_pct": 2.10, "t": 2.50},
        cand_hold_dd_usd_pct=-37.5,
        r0_hold_dd_usd_pct=-35.4,
    )
    assert not res_dd_fail["hold_dd_usd_ok"]
    assert res_dd_fail["verdict"] == "FAIL"
