"""Unit tests for scripts/research_round3.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import research_round3 as r3  # noqa: E402


def test_pass_rule_boundaries():
    # Exact threshold boundary: disc D>0 t=1.0, hold D>0 t=2.0, DD diff = -2.0 pp -> PASS
    res = r3.evaluate_pass_rule(
        {"mean_ann_pct": 0.50, "t": 1.00},
        {"mean_ann_pct": 1.50, "t": 2.00},
        cand_hold_dd_usd_pct=-37.4,
        r0_hold_dd_usd_pct=-35.4,
    )
    assert res["verdict"] == "PASS"
    assert res["hold_dd_usd_ok"]

    # Worse DD by 2.1 pp -> FAIL
    res_dd = r3.evaluate_pass_rule(
        {"mean_ann_pct": 2.0, "t": 2.0},
        {"mean_ann_pct": 3.0, "t": 3.0},
        cand_hold_dd_usd_pct=-37.5,
        r0_hold_dd_usd_pct=-35.4,
    )
    assert res_dd["verdict"] == "FAIL"
    assert not res_dd["hold_dd_usd_ok"]

    # Discovery t < 1.0 -> FAIL
    res_disc = r3.evaluate_pass_rule(
        {"mean_ann_pct": 1.0, "t": 0.99},
        {"mean_ann_pct": 3.0, "t": 3.0},
        cand_hold_dd_usd_pct=-35.0,
        r0_hold_dd_usd_pct=-35.4,
    )
    assert res_disc["verdict"] == "FAIL"

    # Holdout t < 2.0 -> FAIL
    res_hold = r3.evaluate_pass_rule(
        {"mean_ann_pct": 1.5, "t": 1.5},
        {"mean_ann_pct": 2.0, "t": 1.99},
        cand_hold_dd_usd_pct=-35.0,
        r0_hold_dd_usd_pct=-35.4,
    )
    assert res_hold["verdict"] == "FAIL"


def test_prereg_and_ledger_gates(tmp_path: Path):
    prereg_dir = tmp_path / "prereg"
    prereg_dir.mkdir()
    with pytest.raises(RuntimeError, match="Pre-registration missing"):
        r3.verify_prereg("C1_demo", prereg_dir)

    (prereg_dir / "C1_demo.md").write_text("short", encoding="utf-8")
    with pytest.raises(RuntimeError, match="too short"):
        r3.verify_prereg("C1_demo", prereg_dir)

    (prereg_dir / "C1_demo.md").write_text(
        f"# Pre-registration: C1_demo\n\nFormula: x\n\nPass rule: {r3.FIXED_PASS_RULE_VERBATIM}\n",
        encoding="utf-8",
    )
    assert r3.verify_prereg("C1_demo", prereg_dir) == prereg_dir / "C1_demo.md"

    ledger_path = tmp_path / "trial_ledger.json"
    ledger_path.write_text(json.dumps({
        "studies": [
            {"study": "prior", "family": "stock_selection", "trials": 92, "source": "prior"},
        ]
    }), encoding="utf-8")
    assert r3.ledger_n_sel(ledger_path) == 92
    with pytest.raises(RuntimeError, match="not found"):
        r3.verify_ledger_registered("C1_demo", ledger_path)

    ledger_path.write_text(json.dumps({
        "studies": [
            {"study": "prior", "family": "stock_selection", "trials": 92, "source": "prior"},
            {"study": "round3_C1_demo", "family": "stock_selection", "trials": 1, "source": "C1_demo"},
        ]
    }), encoding="utf-8")
    assert r3.verify_ledger_registered("C1_demo", ledger_path) == 93


def test_strip_forward_columns_removes_all_fwd_targets():
    df = pd.DataFrame({
        "date": [pd.Timestamp("2020-01-31")],
        "ticker": ["AAA"],
        "bm": [1.0],
        "fwd_ret_1m": [0.05],
        "fwd_ret_6m": [0.15],
        "fwd_ret_1m_usd": [0.02],
    })
    clean = r3.strip_forward_columns(df)
    assert list(clean.columns) == ["date", "ticker", "bm"]


def test_rank_average_and_z_average_combos():
    dt = pd.Timestamp("2020-06-30")
    df = pd.DataFrame({
        "date": [dt] * 5,
        "ticker": ["A", "B", "C", "D", "E"],
        "sector": ["S1"] * 5,
        "value_sn_z": [1.0, 2.0, 3.0, 4.0, 5.0],
        "cand_x": [5.0, 4.0, 3.0, 2.0, np.nan],
    })
    ra_fb = r3.rank_average_combo(df, "value_sn_z", "cand_x", weight_a=0.5, require_both=False)
    assert ra_fb.notna().all()
    # E has NaN cand_x, falls back to rank(value_sn_z) = 1.0
    assert ra_fb.iloc[4] == pytest.approx(1.0)
    # A: rank(value_sn_z)=0.2, rank(cand_x)=1.0 -> avg 0.6
    assert ra_fb.iloc[0] == pytest.approx(0.6)

    ra_req = r3.rank_average_combo(df, "value_sn_z", "cand_x", weight_a=0.5, require_both=True)
    assert np.isnan(ra_req.iloc[4])
    assert ra_req.iloc[0] == pytest.approx(0.6)

    za = r3.z_average_combo(df, "value_sn_z", "cand_x", weight_a=0.5, sector_neutral=True, min_n=5)
    assert za.notna().all()
    assert abs(float(za.mean())) < 1e-9


def test_align_score_to_panel_multiindex_and_duplicates():
    df = pd.DataFrame({
        "date": [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-01-31")],
        "ticker": ["AAA", "BBB"],
    })
    idx = pd.MultiIndex.from_tuples([
        (pd.Timestamp("2020-01-15"), "BBB"),  # normalized to month-end 2020-01-31
        (pd.Timestamp("2020-01-31"), "AAA"),
    ])
    s = pd.Series([2.5, 1.5], index=idx)
    aligned = r3.align_score_to_panel(s, df)
    assert np.allclose(aligned, [1.5, 2.5])

    dup_idx = pd.MultiIndex.from_tuples([
        (pd.Timestamp("2020-01-31"), "AAA"),
        (pd.Timestamp("2020-01-31"), "AAA"),
    ])
    with pytest.raises(ValueError, match="duplicate"):
        r3.align_score_to_panel(pd.Series([1.0, 2.0], index=dup_idx), df)


def test_evaluate_scored_panel_identity_candidate_gives_zero_diff(tmp_path: Path):
    """A candidate identical to R0 must produce D = 0, overlap = 100%, and FAIL."""
    import pickle

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    dates = pd.bdate_range("2019-06-03", "2022-06-30")
    rng = np.random.default_rng(42)
    tickers = [f"T{i:02d}" for i in range(35)]

    for i, tk in enumerate(tickers):
        rets = rng.normal(0.001 + 0.0001 * (i % 5), 0.02, size=len(dates))
        px = 10.0 * np.cumprod(1.0 + rets)
        df_px = pd.DataFrame({"Open": px * 0.999, "Close": px, "Volume": 1e6 * (i + 1)}, index=dates)
        (raw_dir / f"{tk}.pkl").write_bytes(pickle.dumps({"px_adj": df_px, "px_raw": df_px}))

    fx = pd.DataFrame(
        {"xu100": 100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.01, len(dates))),
         "usdtry": np.linspace(5.5, 16.0, len(dates))},
        index=dates,
    )
    m_idx = pd.period_range("2019-01", "2026-12", freq="M")
    macro = pd.DataFrame({"policy": 15.0, "cpi_mom": 1.5}, index=m_idx.to_timestamp("M"))

    months = pd.date_range("2019-10-31", "2022-05-31", freq="ME")
    rows = []
    for dt in months:
        for i, tk in enumerate(tickers):
            rows.append({
                "date": dt,
                "ticker": tk,
                "sector": f"S{i % 5}",
                "tlvol60": float(1e7 * (i + 1)),
                "value_sn_z": float(i - 17) / 10.0 + float(rng.normal(0, 0.05)),
                "fwd_ret_1m": float(rng.normal(0.02, 0.08)),
                "fwd_ret_1m_usd": float(rng.normal(0.01, 0.08)),
            })
    scored = pd.DataFrame(rows)
    scored["R0"] = scored["value_sn_z"]
    scored["C_ident"] = scored["value_sn_z"]

    res = r3.evaluate_scored_panel(
        scored, ["C_ident"], macro, fx, raw_dir, frames_cache={}, n_sel=93, var_sr=0.02335
    )
    v = res["verdicts"]["C_ident"]
    assert v["disc_D_ann_pct"] == pytest.approx(0.0, abs=1e-6)
    assert v["hold_D_ann_pct"] == pytest.approx(0.0, abs=1e-6)
    assert v["hold_dd_usd_diff_vs_R0_pp"] == pytest.approx(0.0, abs=1e-6)
    assert v["verdict"] == "FAIL"
    assert res["switcher_analysis"]["C_ident"]["discovery"]["mean_top20_overlap_pct"] == pytest.approx(100.0)
    assert res["switcher_analysis"]["C_ident"]["holdout"]["mean_top20_overlap_pct"] == pytest.approx(100.0)

    spec = r3.CandidateSpec(name="C_ident", description="Identity check", fn=lambda r, d, c: d["value_sn_z"])
    md = r3.format_candidate_markdown(
        spec, res, res, n_sel=93, var_sr=0.02335,
        prereg_path=tmp_path / "prereg" / "C_ident.md",
        json_path=tmp_path / "out.json",
    )
    assert "FAIL" in md
    assert "DSR at `N_sel = 93`" in md
    assert "KAP-date Panel Sensitivity" in md


def test_write_prereg_and_append_trial_ledger(tmp_path: Path):
    prereg_dir = tmp_path / "prereg"
    ledger_path = tmp_path / "trial_ledger.json"
    ledger_path.write_text(json.dumps({
        "description": "test",
        "as_of": "2026-11-22",
        "studies": [{"study": "base", "family": "stock_selection", "trials": 92, "source": "base"}],
    }), encoding="utf-8")

    n_after = r3.append_trial_ledger("C1_test", "test signal", ledger_path=ledger_path, as_of="2026-11-24")
    assert n_after == 93
    with pytest.raises(ValueError, match="already exists"):
        r3.append_trial_ledger("C1_test", "dup", ledger_path=ledger_path)

    p = r3.write_prereg_file(
        "C1_test",
        formula="score = x_z",
        frozen_params={"window": 12},
        rationale="Economic hypothesis.",
        prereg_dir=prereg_dir,
        n_sel_after=n_after,
    )
    assert r3.verify_prereg("C1_test", prereg_dir) == p
    assert r3.verify_ledger_registered("C1_test", ledger_path) == 93
    with pytest.raises(FileExistsError):
        r3.write_prereg_file("C1_test", formula="x", frozen_params={}, rationale="r", prereg_dir=prereg_dir)


def test_feature_registry_synced():
    r3.sync_feature_registry()
    for name in ("scholar_cbop", "scholar_sue_usd", "scholar_real_cbop_sue"):
        assert name in r3.CANDIDATE_REGISTRY
        spec = r3.CANDIDATE_REGISTRY[name]
        assert callable(spec.fn)
        assert spec.frozen_params


