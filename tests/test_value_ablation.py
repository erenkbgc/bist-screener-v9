"""value_ablation ve bist_factor_reconciliation yardimci fonksiyon testleri."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_bist_factor_reconciliation as rec  # noqa: E402
import research_value_ablation as va  # noqa: E402


def _synthetic_panel(n_months: int = 24, n_names: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows = []
    for d in pd.date_range("2020-01-31", periods=n_months, freq="ME"):
        bm = rng.normal(size=n_names)
        ep = rng.normal(size=n_names)
        ey = rng.normal(size=n_names)
        sp = rng.normal(size=n_names)  # saf gurultu
        ret = 0.02 * (bm + ep + ey) / 3 + 0.03 * rng.normal(size=n_names)
        for i in range(n_names):
            rows.append({
                "date": d,
                "ticker": f"T{i}",
                "sector": f"S{i % 4}",
                "mcap": float(100 * (i + 1)),
                "tlvol60": float(1e6 * (i + 1)),
                "bm_z": bm[i],
                "ep_z": ep[i],
                "ey_z": ey[i],
                "sp_z": sp[i],
                "vol60_z": bm[i],
                "fwd_ret_1m": ret[i],
            })
    return pd.DataFrame(rows)


def test_build_variant_scores_and_switcher_spread():
    df = va.build_variant_scores(_synthetic_panel())
    assert set(va.VARIANTS).issubset(df.columns)
    sw = va.switcher_and_overlap(df, "V1_bm_ep_ey_no_sp", "V0_bm_ep_sp_ey")
    assert not sw.empty
    assert (sw["overlap"] >= 0.0).all() and (sw["overlap"] <= 1.0).all()
    assert sw["overlap"].mean() > 0.5
    # sp saf gurultu oldugu icin V1 (sp haric) girenleri cikanlardan ortalama olarak daha iyi
    assert sw["switch_spread"].mean() > 0


def test_classify_variant_rules():
    # SUPERIOR: kesif t > 3, holdout t > 2, switcher pozitif
    assert va.classify_variant(
        "V1_bm_ep_ey_no_sp",
        {"mean_ann_pct": 1.5, "t": 3.2},
        {"mean_ann_pct": 1.2, "t": 2.4},
        {"mean_ann_pct": 2.0},
        {"mean_ann_pct": 1.8},
        0.5, 0.2,
        {"mean_ann_pct": 7.0, "t": 2.6},
    ) == "SUPERIOR"
    # NON_INFERIOR_SIMPLIFICATION: sp marjinal egimi anlamsiz, V1 - V0 farki 0 etrafinda, EW net'i geciyor
    assert va.classify_variant(
        "V1_bm_ep_ey_no_sp",
        {"mean_ann_pct": 0.1, "t": 0.3},
        {"mean_ann_pct": -0.1, "t": -0.2},
        {"mean_ann_pct": 0.2},
        {"mean_ann_pct": 0.1},
        0.8, -0.4,
        {"mean_ann_pct": 6.8, "t": 2.5},
    ) == "NON_INFERIOR_SIMPLIFICATION"
    # KEEP_V0: holdout'ta belirgin kayip
    assert va.classify_variant(
        "V2_bm_ep",
        {"mean_ann_pct": -1.5, "t": -2.1},
        {"mean_ann_pct": -1.2, "t": -1.8},
        {"mean_ann_pct": -1.0},
        {"mean_ann_pct": -0.8},
        2.5, 2.2,
        {"mean_ann_pct": 5.0, "t": 1.9},
    ) == "KEEP_V0"


def test_quintile_ew_vw_and_low_vol_decomposition():
    df = va.build_variant_scores(_synthetic_panel())
    df["value_sn_z"] = df["V0_bm_ep_sp_ey"]
    q = rec.quintile_ew_vw(df, "value_sn_z")
    assert not q.empty
    assert q["ew_q5_minus_q1"].mean() > 0 and q["vw_q5_minus_q1"].mean() > 0
    lv = rec.low_vol_decomposition(df)
    assert "full" in lv and "q5_minus_q1" in lv["full"]
