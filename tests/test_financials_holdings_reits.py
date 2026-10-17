"""financials_holdings_reits yardimci fonksiyon testleri."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_financials_holdings_reits as fhr  # noqa: E402


def test_fin_statements_long_extracts_ufrs_and_insurance_labels():
    tbl = pd.DataFrame(
        {
            "2025Q2": [3.2e12, 3.7e11, 4.2e9, 6.3e10, 5.4e10, 5.3e10],
            "2025Q1": [3.0e12, 3.5e11, 4.2e9, 3.1e10, 2.7e10, 2.6e10],
        },
        index=[
            "AKTİF TOPLAMI",
            "XVI. ÖZKAYNAKLAR",
            "16.1 Ödenmiş Sermaye",
            "III. NET FAİZ GELİRİ/GİDERİ (I - II)",
            "XI. NET FAALİYET KARI/ZARARI (VIII-IX-X)",
            "XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)",
        ],
    )
    long_df = fhr.fin_statements_long("GARAN", tbl)
    items = set(long_df["item"])
    assert {"total_assets", "equity", "paid_in", "gross_profit", "op_profit", "net_income"}.issubset(items)


def test_cross_sectional_residual_orthogonal_to_regressor():
    rng = np.random.default_rng(7)
    rows = []
    for d in pd.date_range("2022-01-31", periods=6, freq="ME"):
        roe = rng.normal(size=20)
        eps = rng.normal(size=20)
        bm = 0.8 * roe + eps
        for i in range(20):
            rows.append({"date": d, "ticker": f"B{i}", "roe_z": roe[i], "bm_z": bm[i]})
    df = pd.DataFrame(rows)
    res = fhr.cross_sectional_residual(df, "bm_z", ["roe_z"], min_n=6)
    assert res.notna().all()
    # Artik roe_z ile yaklasik dik (ortogonal) olmali
    assert abs(df["roe_z"].corr(res)) < 0.15


def test_compute_holding_and_reit_scores_and_evaluate():
    rng = np.random.default_rng(11)
    rows = []
    for d in pd.date_range("2020-01-31", periods=18, freq="ME"):
        for i in range(15):
            bm = float(rng.normal())
            ep = float(rng.normal())
            roe = float(rng.normal())
            rows.append({
                "date": d,
                "ticker": f"H{i}",
                "sector": "Holding",
                "mcap": 1000.0 * (i + 1),
                "size": float(np.log(1000.0 * (i + 1))),
                "tlvol60": 1e7 * (i + 1),
                "bm": 0.5 + 0.1 * bm,
                "ep": 0.1 + 0.05 * ep,
                "sp": 0.8 + 0.2 * float(rng.normal()),
                "ey": 0.12 + 0.04 * float(rng.normal()),
                "roe": 0.15 + 0.05 * roe,
                "equity_parent": 600.0 * (i + 1),
                "intangibles": 20.0,
                "goodwill": 10.0,
                "cash": 100.0,
                "fin_investments": 200.0,
                "eq_investments": 150.0,
                "fin_debt": 120.0,
                "inv_property": 500.0 * (i + 1),
                "inventories": 100.0 * (i + 1),
                "total_assets": 1200.0 * (i + 1),
                "ttm_op_profit": 90.0 * (i + 1) * (1 + 0.2 * ep),
                "fwd_ret_1m": 0.02 * (bm + ep + roe) / 3 + 0.02 * float(rng.normal()),
            })
    df = pd.DataFrame(rows)
    h = fhr.compute_holding_scores(df)
    assert {"H0_value_sn", "H1_bm_ep_roe", "H2_backing_nav"}.issubset(h.columns)
    ev = fhr.evaluate_sector_models(h, ["H0_value_sn", "H1_bm_ep_roe", "H2_backing_nav"], "H0_value_sn", min_names=8)
    assert "H1_bm_ep_roe" in ev and "diff_vs_base" in ev["H1_bm_ep_roe"]["full"]

    g = fhr.compute_reit_scores(df)
    assert {"G0_value_sn", "G1_nav_ffo", "G2_letdin_sirmans_resid"}.issubset(g.columns)
