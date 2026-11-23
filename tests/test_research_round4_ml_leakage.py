"""Leakage, causality, and gauntlet unit tests for Round 4 ML walk-forward model."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import research_round4_ml as r4ml  # noqa: E402


def _make_synthetic_panel(n_months: int = 48, n_stocks: int = 40, seed: int = 7) -> pd.DataFrame:
    """Create a synthetic monthly PIT panel spanning 2013-04 .. 2017-03."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2013-04-30", periods=n_months, freq="ME")
    base_sectors = ["Imalat", "Holding", "Enerji", "Gida"]
    rows = []
    for mi, dt in enumerate(dates):
        for si in range(n_stocks):
            # Introduce a brand-new sector ONLY starting in 2016-06 (mi >= 38)
            if mi >= 38 and si < 4:
                sec = "FutureSavunma"
            else:
                sec = base_sectors[si % len(base_sectors)]
            bm_z = float(rng.normal())
            ep_z = float(rng.normal())
            sp_z = float(rng.normal())
            ey_z = float(rng.normal())
            size_z = float(rng.normal())
            mom_z = float(rng.normal())
            vol_z = float(rng.normal())
            tlvol60 = float(np.exp(12.0 + 0.05 * mi + rng.normal()))
            # Mild signal + noise
            fwd_ret = 0.02 * bm_z + 0.01 * mom_z + float(rng.normal(0, 0.08))
            rows.append({
                "date": dt,
                "ticker": f"T{si:03d}",
                "sector": sec,
                "tlvol60": tlvol60,
                "bm_z": bm_z if (si % 19 != 0) else np.nan,  # test native NaN handling
                "ep_z": ep_z,
                "sp_z": sp_z,
                "ey_z": ey_z,
                "size_z": size_z,
                "mom_12_1_z": mom_z,
                "vol60_z": vol_z,
                "value_sn_z": 0.25 * (bm_z + ep_z + sp_z + ey_z),
                "fwd_ret_1m": np.nan if mi == n_months - 1 else fwd_ret,
            })
    return pd.DataFrame(rows)


FAST_HGB = {
    **r4ml.HGB_FROZEN_PARAMS,
    "max_iter": 15,
    "min_samples_leaf": 10,
}


def test_training_rows_strictly_before_rebalance_date():
    df = _make_synthetic_panel()
    preds, audits = r4ml.fit_predict_walk_forward_ml(df, hgb_params=FAST_HGB)

    assert len(audits) == df[df["date"] >= r4ml.FIRST_PRED_DATE]["date"].nunique()
    for a in audits:
        rebal = pd.Timestamp(a.rebalance_date)
        max_tr = pd.Timestamp(a.max_train_date)
        assert max_tr < rebal, f"max_train_date {max_tr} not < rebalance_date {rebal}"
        assert (max_tr.to_period("M") + 1) <= rebal.to_period("M")

    # Pre-2016 rows must have NaN predictions; 2016+ rows must be finite
    assert preds[df["date"] < r4ml.FIRST_PRED_DATE].isna().all()
    assert preds[df["date"] >= r4ml.FIRST_PRED_DATE].notna().all()


def test_causality_invariance_future_perturbation_zero_effect():
    """Scrambling ALL future rows (date > t_cut) and fwd_ret_1m at date == t_cut
    must leave predictions for all dates <= t_cut bit-for-bit identical."""
    df_orig = _make_synthetic_panel()
    t_cut = pd.Timestamp("2016-04-30")

    df_perturbed = df_orig.copy()
    rng = np.random.default_rng(999)
    # Scramble fwd_ret_1m on and after t_cut
    mask_ge = df_perturbed["date"] >= t_cut
    df_perturbed.loc[mask_ge, "fwd_ret_1m"] = rng.normal(5.0, 2.0, size=int(mask_ge.sum()))
    # Scramble ALL features strictly after t_cut
    mask_gt = df_perturbed["date"] > t_cut
    for col in ("bm_z", "ep_z", "sp_z", "ey_z", "size_z", "mom_12_1_z", "vol60_z"):
        df_perturbed.loc[mask_gt, col] = rng.normal(-10.0, 5.0, size=int(mask_gt.sum()))
    df_perturbed.loc[mask_gt, "tlvol60"] = rng.uniform(1e9, 1e12, size=int(mask_gt.sum()))
    df_perturbed.loc[mask_gt, "sector"] = "InjectedFutureSector"

    p_orig, _ = r4ml.fit_predict_walk_forward_ml(df_orig, hgb_params=FAST_HGB)
    p_pert, _ = r4ml.fit_predict_walk_forward_ml(df_perturbed, hgb_params=FAST_HGB)

    mask_le = (df_orig["date"] >= r4ml.FIRST_PRED_DATE) & (df_orig["date"] <= t_cut)
    np.testing.assert_array_equal(
        p_orig.loc[mask_le].to_numpy(),
        p_pert.loc[mask_le].to_numpy(),
    )


def test_sector_dummies_strictly_pit_no_future_sector_columns():
    """A sector first appearing at 2016-06-30 must NOT appear in train_sectors at 2016-06-30,
    and MUST appear starting at 2016-07-31."""
    df = _make_synthetic_panel()
    _, audits = r4ml.fit_predict_walk_forward_ml(df, hgb_params=FAST_HGB)
    by_date = {a.rebalance_date: a for a in audits}

    # Before 2016-06-30: 4 sectors, none unseen
    assert by_date["2016-05-31"].n_sector_dummies == 4
    assert by_date["2016-05-31"].unseen_test_sectors == []

    # At 2016-06-30 (first appearance): still only 4 train sectors; FutureSavunma flagged as unseen
    assert by_date["2016-06-30"].n_sector_dummies == 4
    assert by_date["2016-06-30"].unseen_test_sectors == ["FutureSavunma"]

    # At 2016-07-31 (now in train_df with date < t): 5 train sectors, none unseen
    assert by_date["2016-07-31"].n_sector_dummies == 5
    assert by_date["2016-07-31"].unseen_test_sectors == []


def test_liquidity_z_is_strictly_single_month():
    df1 = _make_synthetic_panel(n_months=6, n_stocks=30)
    df2 = df1.copy()
    last_dt = df2["date"].max()
    df2.loc[df2["date"] == last_dt, "tlvol60"] *= 1e6

    out1 = r4ml.add_pit_liquidity_feature(df1)
    out2 = r4ml.add_pit_liquidity_feature(df2)

    earlier = df1["date"] < last_dt
    np.testing.assert_array_equal(
        out1.loc[earlier, "log_tlvol60_z"].to_numpy(),
        out2.loc[earlier, "log_tlvol60_z"].to_numpy(),
    )


def test_blend50_exact_rank_average_and_pre2016_nan():
    df = _make_synthetic_panel()
    preds, _ = r4ml.fit_predict_walk_forward_ml(df, hgb_params=FAST_HGB)
    df["ml_hgb"] = preds
    blend = r4ml.compute_blend50_score(df, "ml_hgb", "value_sn_z")

    assert blend[df["date"] < r4ml.FIRST_PRED_DATE].isna().all()
    sample_dt = pd.Timestamp("2016-03-31")
    g = df[df["date"] == sample_dt]
    expected = 0.5 * g["ml_hgb"].rank(ascending=True, pct=True) + 0.5 * g["value_sn_z"].rank(ascending=True, pct=True)
    np.testing.assert_allclose(blend.loc[g.index].to_numpy(), expected.to_numpy(), rtol=0, atol=1e-12)


def test_holm_bonferroni_and_gauntlet_verdicts():
    adj = r4ml.holm_bonferroni({"a": 0.01, "b": 0.04})
    assert adj["a"] == pytest.approx(0.02)
    assert adj["b"] == pytest.approx(0.04)

    adj_mono = r4ml.holm_bonferroni({"a": 0.03, "b": 0.04})
    assert adj_mono["a"] == pytest.approx(0.06)
    assert adj_mono["b"] == pytest.approx(0.06)

    def _mock_eval(full_d, full_t, block_ds, dd_full, dd_21, turn_ratio):
        p_two, p_one = r4ml.nw_pvalues(full_t, 128)
        return {
            "portfolio_simulation": {
                "cand": {
                    "full": {
                        "paired_diff_vs_R0": {
                            "mean_ann_pct": full_d,
                            "t": full_t,
                            "months": 128,
                            "p_two_sided": p_two,
                            "p_one_sided": p_one,
                        },
                        "full_dd_usd_diff_vs_R0_pp": dd_full,
                        "turnover_ratio_vs_R0": turn_ratio,
                    },
                    "post_2021": {"post_2021_dd_usd_diff_vs_R0_pp": dd_21},
                    "block_2016": {"paired_diff_vs_R0": {"mean_ann_pct": block_ds[0], "t": 1.0, "months": 12}},
                    "block_2017_2020": {"paired_diff_vs_R0": {"mean_ann_pct": block_ds[1], "t": 1.0, "months": 48}},
                    "block_2021_2023": {"paired_diff_vs_R0": {"mean_ann_pct": block_ds[2], "t": 1.0, "months": 36}},
                    "block_2024_plus": {"paired_diff_vs_R0": {"mean_ann_pct": block_ds[3], "t": 1.0, "months": 32}},
                }
            }
        }

    # All 6 pass
    p_ok = _mock_eval(3.5, 2.6, [1.0, 2.0, 3.0, 1.5], -0.5, -1.0, 1.2)
    k_ok = _mock_eval(2.0, 1.5, [1.0, 1.0, 1.0, 1.0], 0.0, 0.0, 1.2)
    v = r4ml.evaluate_gauntlet_verdicts(p_ok, k_ok, ["cand"])["cand"]
    assert v["verdict"] == "PASS"

    # Fail criterion 2 (one block negative)
    p_b = _mock_eval(3.5, 2.6, [1.0, 2.0, -0.1, 1.5], -0.5, -1.0, 1.2)
    assert r4ml.evaluate_gauntlet_verdicts(p_b, k_ok, ["cand"])["cand"]["verdict"] == "FAIL"

    # Fail criterion 3 (2021+ DD worse by > 2pp)
    p_dd = _mock_eval(3.5, 2.6, [1.0, 2.0, 3.0, 1.5], -0.5, -2.1, 1.2)
    assert r4ml.evaluate_gauntlet_verdicts(p_dd, k_ok, ["cand"])["cand"]["verdict"] == "FAIL"

    # Fail criterion 6 (turnover > 1.5x R0)
    p_to = _mock_eval(3.5, 2.6, [1.0, 2.0, 3.0, 1.5], -0.5, -1.0, 1.51)
    assert r4ml.evaluate_gauntlet_verdicts(p_to, k_ok, ["cand"])["cand"]["verdict"] == "FAIL"
