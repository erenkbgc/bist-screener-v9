"""quality_value_lowvol yardimci fonksiyon testleri."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_quality_value_lowvol as qvl  # noqa: E402


def _synthetic_panel(n_months: int = 16, n_stocks: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows = []
    dates = pd.date_range("2020-06-30", periods=n_months, freq="ME")
    sectors = ["Sanayi", "Teknoloji", "Gıda", "Kimya"]
    for d in dates:
        for i in range(n_stocks):
            val = float(rng.normal())
            roe = float(rng.normal())
            roa = 0.6 * roe + 0.4 * float(rng.normal())
            opa = 0.7 * roe + 0.3 * float(rng.normal())
            gpa = 0.5 * roe + 0.5 * float(rng.normal())
            vol_z = float(rng.normal())
            f7 = int(rng.integers(1, 8))
            ret = 0.015 * val + 0.012 * roe + 0.008 * vol_z + 0.02 * float(rng.normal())
            rows.append({
                "date": d,
                "ticker": f"S{i:02d}",
                "sector": sectors[i % len(sectors)],
                "value_sn_z": val,
                "roe": np.nan if (i == 0 and d == dates[0]) else roe,
                "roa": roa,
                "opa": opa,
                "gpa": gpa,
                "f7": f7,
                "vol60_z": vol_z,
                "fwd_ret_1m": ret,
                "fwd_ret_6m_xs": 4.0 * ret - 0.15,
            })
    return pd.DataFrame(rows)


def test_enrich_quality_and_risk_factors_strict_nan():
    raw = _synthetic_panel(n_months=4, n_stocks=30)
    df = qvl.enrich_quality_and_risk_factors(raw, q_ext=None, min_peers=5)
    assert {"roe_sn_z", "roa_sn_z", "opa_sn_z", "gpa_sn_z", "f7_z", "qual_sn_z", "qual_sn_z_skipna"}.issubset(
        df.columns
    )
    # Row 0 has roe = NaN -> strict qual_sn_z must be NaN while qual_sn_z_skipna is finite
    assert np.isnan(df.loc[0, "qual_sn_z"])
    assert np.isfinite(df.loc[0, "qual_sn_z_skipna"])


def test_conditional_double_sort_and_portfolio_selections():
    df = qvl.enrich_quality_and_risk_factors(_synthetic_panel(n_months=16, n_stocks=40), q_ext=None, min_peers=5)
    ds = qvl.conditional_double_sort(df, "roe_sn_z", top_val_quintiles=(4,), min_names=25)
    assert "full" in ds and "holdout" in ds
    assert ds["full"]["high_minus_low"]["ann_pct"] > 0
    assert "trap_6m_pct" in ds["full"]

    sel, traps = qvl.build_portfolio_selections(df)
    assert {
        "P0_value_top20",
        "QV1_roe_filter",
        "QV2_f7_filter",
        "QV3_qual_in_top30",
        "LV1_lowvol_filter",
        "LV2_lowvol_in_top25",
        "QLV_combined_filter",
    }.issubset(sel.keys())
    for d in sel["P0_value_top20"]:
        assert len(sel["QV1_roe_filter"][d]) <= len(sel["P0_value_top20"][d])
        assert len(sel["LV1_lowvol_filter"][d]) <= len(sel["P0_value_top20"][d])
    assert len(traps["P0_value_top20"]) > 0


def test_classify_outcome_distinguishes_alpha_risk_and_rejected():
    p0_disc = {"vol_ann_pct": 30.0, "active_ew_max_dd_pct": -18.0, "vs_ew_net": {"t": 2.5}, "cagr_usd_pct": 10.0}
    p0_hold = {"vol_ann_pct": 32.0, "active_ew_max_dd_pct": -16.0, "vs_ew_net": {"t": 2.5}, "cagr_usd_pct": 4.0}

    # 1. ALPHA_ENHANCEMENT
    assert (
        qvl.classify_outcome(
            {"ann_pct": 2.5, "t": 2.3},
            {"ann_pct": 2.1, "t": 2.2},
            {"vol_ann_pct": 30.0, "active_ew_max_dd_pct": -17.0, "vs_ew_net": {"t": 2.8}, "cagr_usd_pct": 12.0},
            {"vol_ann_pct": 31.0, "active_ew_max_dd_pct": -15.0, "vs_ew_net": {"t": 3.0}, "cagr_usd_pct": 5.5},
            p0_disc,
            p0_hold,
        )
        == "ALPHA_ENHANCEMENT"
    )

    # 2. RISK_CONTROL_ONLY (lower vol/drawdown and higher active t in both periods, D > -1.0%/yr)
    assert (
        qvl.classify_outcome(
            {"ann_pct": -0.3, "t": -0.4},
            {"ann_pct": 0.6, "t": 0.8},
            {"vol_ann_pct": 27.5, "active_ew_max_dd_pct": -14.0, "vs_ew_net": {"t": 2.7}, "cagr_usd_pct": 9.8},
            {"vol_ann_pct": 29.0, "active_ew_max_dd_pct": -13.0, "vs_ew_net": {"t": 2.8}, "cagr_usd_pct": 4.2},
            p0_disc,
            p0_hold,
        )
        == "RISK_CONTROL_ONLY"
    )

    # 3. REJECTED
    assert (
        qvl.classify_outcome(
            {"ann_pct": -2.5, "t": -1.8},
            {"ann_pct": -1.4, "t": -1.2},
            {"vol_ann_pct": 31.0, "active_ew_max_dd_pct": -19.0, "vs_ew_net": {"t": 2.1}, "cagr_usd_pct": 8.0},
            {"vol_ann_pct": 33.0, "active_ew_max_dd_pct": -18.0, "vs_ew_net": {"t": 2.0}, "cagr_usd_pct": 2.5},
            p0_disc,
            p0_hold,
        )
        == "REJECTED"
    )
