"""Metric-count sensitivity of value_sn (pre-registered, external review P1).

R0 averages the z-scores of whichever of the 4 value legs (bm, ep, sp, ey) are
available. These variants keep R0's score unchanged and only drop stocks whose
score rests on fewer than K legs. Run with:
    python scripts/research_metric_count.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import research_round4_vlab as h  # noqa: E402

BATCH = "metric_count"
LEGS = ("bm", "ep", "sp", "ey")


def leg_count(prep):
    return prep[[f"{k}_z" for k in LEGS]].notna().sum(axis=1)


def _min_legs(k: int):
    def score(raw, prep, ctx):
        return prep["value_sn_z"].where(leg_count(prep) >= k)
    return score


SPECS = [
    ("mc_v1_min2", 2, "R0 score, only stocks with >= 2 valid value legs"),
    ("mc_v2_min3", 3, "R0 score, only stocks with >= 3 valid value legs"),
    ("mc_v3_all4", 4, "R0 score, only stocks with all 4 valid value legs"),
]
for name, k, desc in SPECS:
    h.register_variant(h.VariantSpec(name=name, batch=BATCH, description=desc,
                                     score_fn=_min_legs(k), frozen_params={"min_legs": k}))


if __name__ == "__main__":
    out = h.run_batch(BATCH, [n for n, _, _ in SPECS],
                      prereg_dir=ROOT / "docs" / "research" / "prereg_board",
                      results_dir=ROOT / "docs" / "research" / "prereg_board")
    print(out["md_path"])
    for n, v in out["payload"]["verdicts"].items():
        b = v["blocks_D_ann_pct"]
        print(f"{n:12s} D={v['full_D_ann_pct']:+.2f} t={v['full_t']:+.2f} "
              f"blk={[round(x, 2) for x in b.values()]} dd={v['dd_full_diff_pp']:+.1f}/{v['dd_2021p_diff_pp']:+.1f} "
              f"kap={v['kap_full_D_ann_pct']:+.2f}({v['kap_full_t']:+.2f}) holm={v['p_holm_tdist']:.3f} "
              f"turn={v['turnover_ratio']:.2f} {v['verdict']}")
