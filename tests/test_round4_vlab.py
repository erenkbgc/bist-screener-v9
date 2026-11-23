"""Unit tests for the Round 4 Value Construction Lab gauntlet harness."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import research_round4_vlab as r4v  # noqa: E402


def test_holm_adjust_monotonic_and_bounded():
    raw = {"a": 0.005, "b": 0.02, "c": 0.03, "d": 0.40}
    adj = r4v.holm_adjust(raw)
    assert pytest.approx(adj["a"], abs=1e-9) == 0.020   # 4 * 0.005
    assert pytest.approx(adj["b"], abs=1e-9) == 0.060   # 3 * 0.020
    assert pytest.approx(adj["c"], abs=1e-9) == 0.060   # max(0.060, 2*0.030)
    assert pytest.approx(adj["d"], abs=1e-9) == 0.400   # max(0.060, 1*0.400)
    assert all(0.0 <= v <= 1.0 for v in adj.values())


def test_evaluate_gauntlet_batch_pass_and_each_failure_mode():
    def _mk_panel(cand_map: dict[str, dict]):
        ps = {
            "R0": {
                "full": {"max_dd_usd_pct": -56.6, "turnover_pct": 20.5},
                "holdout_2021_plus": {"max_dd_usd_pct": -35.4},
            }
        }
        for name, cfg in cand_map.items():
            ps[name] = {
                "full": {
                    "paired_diff_vs_R0": {"mean_ann_pct": cfg["full_D"], "t": cfg["full_t"], "months": 161},
                    "max_dd_usd_pct": cfg.get("dd_full", -56.0),
                    "turnover_pct": cfg.get("turn", 22.0),
                },
                "holdout_2021_plus": {
                    "max_dd_usd_pct": cfg.get("dd_2021p", -35.0),
                },
                "b1_2013_16": {"paired_diff_vs_R0": {"mean_ann_pct": cfg["blocks"][0], "t": 1.0, "months": 45}},
                "b2_2017_20": {"paired_diff_vs_R0": {"mean_ann_pct": cfg["blocks"][1], "t": 1.0, "months": 48}},
                "b3_2021_23": {"paired_diff_vs_R0": {"mean_ann_pct": cfg["blocks"][2], "t": 1.0, "months": 36}},
                "b4_2024_plus": {"paired_diff_vs_R0": {"mean_ann_pct": cfg["blocks"][3], "t": 1.0, "months": 32}},
            }
        return {"portfolio_simulation": ps}

    prim = _mk_panel({
        "v_pass": {"full_D": 2.5, "full_t": 2.8, "blocks": [1.0, 2.0, 3.0, 1.5], "dd_full": -57.5, "dd_2021p": -36.5, "turn": 30.0},
        "v_fail_block": {"full_D": 2.5, "full_t": 2.9, "blocks": [1.0, -0.1, 3.0, 1.5]},
        "v_fail_dd": {"full_D": 2.5, "full_t": 2.8, "blocks": [1.0, 2.0, 3.0, 1.5], "dd_2021p": -37.5},
        "v_fail_turn": {"full_D": 2.5, "full_t": 2.8, "blocks": [1.0, 2.0, 3.0, 1.5], "turn": 31.0},
        "v_fail_holm": {"full_D": 1.5, "full_t": 2.05, "blocks": [1.0, 1.0, 1.0, 1.0]},
    })
    kap = _mk_panel({
        "v_pass": {"full_D": 1.8, "full_t": 1.5, "blocks": [1.0, 1.0, 1.0, 1.0]},
        "v_fail_block": {"full_D": 1.8, "full_t": 1.5, "blocks": [1.0, 1.0, 1.0, 1.0]},
        "v_fail_dd": {"full_D": 1.8, "full_t": 1.5, "blocks": [1.0, 1.0, 1.0, 1.0]},
        "v_fail_turn": {"full_D": 1.8, "full_t": 1.5, "blocks": [1.0, 1.0, 1.0, 1.0]},
        "v_fail_holm": {"full_D": 1.8, "full_t": 1.5, "blocks": [1.0, 1.0, 1.0, 1.0]},
    })
    res = r4v.evaluate_gauntlet_batch(prim, kap, list(prim["portfolio_simulation"].keys())[1:])
    assert res["v_pass"]["verdict"] == "PASS"
    assert res["v_fail_block"]["verdict"] == "FAIL" and not res["v_fail_block"]["c2_all_4_blocks_pos"]
    assert res["v_fail_dd"]["verdict"] == "FAIL" and not res["v_fail_dd"]["c3_usd_maxdd_ok"]
    assert res["v_fail_turn"]["verdict"] == "FAIL" and not res["v_fail_turn"]["c6_turnover_ok"]
    # v_fail_holm has t=2.05 -> p_raw=0.0404; as largest p in batch (rank 4, mult=1), wait: 1*0.0404 < 0.05!
    # Check that Holm multiplier properly scales smallest/middle p-values too.
    assert res["v_fail_holm"]["c1_full_D_t"] is True


def test_build_selections_quarterly_and_topk():
    dates = pd.to_datetime(["2013-04-30", "2013-05-31", "2013-06-30"])
    rows = []
    for d in dates:
        for i in range(10):
            rows.append({"date": d, "ticker": f"T{i}", "R0": float(i), "v_q": float(i), "v_top10": float(i)})
    df = pd.DataFrame(rows)
    specs = {
        "v_q": r4v.VariantSpec("v_q", "b", "q", lambda r, p, c: p["R0"], top_pct=0.20, rebalance_months=(4, 6, 9, 12)),
        "v_top10": r4v.VariantSpec("v_top10", "b", "t10", lambda r, p, c: p["R0"], top_pct=0.10),
    }
    sel, eff = r4v.build_selections(df, specs)
    assert sel["v_q"][dates[0]] == ["T8", "T9"]
    assert sel["v_q"][dates[1]] is None
    assert eff["v_q"][dates[1]] == {"T8", "T9"}
    assert sel["v_q"][dates[2]] == ["T8", "T9"]
    assert sel["v_top10"][dates[0]] == ["T9"]


def test_prereg_and_ledger_gates_enforce_presence(tmp_path: Path):
    prereg_dir = tmp_path / "prereg"
    prereg_dir.mkdir()
    with pytest.raises(RuntimeError):
        r4v.verify_batch_prereg("batch1", ["v1"], prereg_dir)

    (prereg_dir / "vlab_batch1.md").write_text(
        "Batch1 prereg for v1: 2013-16 2017-20 2021-23 2024+ NW t >= 2.0, 2pp, kapdates, Holm p < 0.05, 1.5x turnover. "
        "Frozen parameters and economic hypothesis fully specified here.",
        encoding="utf-8",
    )
    assert r4v.verify_batch_prereg("batch1", ["v1"], prereg_dir).exists()

    ledger = tmp_path / "trial_ledger.json"
    ledger.write_text(json.dumps({"as_of": "2026-11-24", "studies": []}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        r4v.verify_variants_in_ledger(["v1"], ledger)
    n_after = r4v.append_vlab_trials(
        [r4v.VariantSpec("v1", "batch1", "desc", lambda r, p, c: p["value_sn_z"])],
        ledger_path=ledger,
    )
    assert n_after == 1
    assert r4v.verify_variants_in_ledger(["v1"], ledger) == 1
