"""Shadow forward record: variant construction, append-only csv, return fill, evaluation."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import shadow_record as sr  # noqa: E402
from core import factor_backtest as fb  # noqa: E402


def _decision(date: str, n: int = 40, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    ranking = []
    for i in range(n):
        mcap = float(rng.uniform(1e9, 1e10))
        ranking.append({"ticker": f"T{i:02d}", "market_cap": mcap,
                        "bm": float(rng.uniform(0.1, 3)), "ep": float(rng.normal(0.05, 0.1)),
                        "sp": float(rng.uniform(0.2, 5)), "ey": float(rng.uniform(-0.1, 0.4)),
                        "inputs": {"ttm_op_profit": float(rng.normal(0.08, 0.1)) * mcap}})
    return {"rebalance_date": date, "status": "ok", "rule_version": "R0-2026-10-12", "ranking": ranking}


def _sectors(_dt):
    return {f"T{i:02d}": ("A" if i < 20 else "B") for i in range(40)}


def _prices(tmp: Path, dates: list[str], n: int = 40) -> Path:
    d = tmp / "prices"
    d.mkdir()
    for i in range(n):
        px = [10.0 + i * 0.1 * k for k in range(len(dates))]
        pd.DataFrame({"date": dates, "open": px, "close": px, "adj_close": px, "volume": 1.0}) \
            .to_csv(d / f"T{i:02d}.csv", index=False)
    return d


def test_r0_matches_manual_value_sn_and_topn():
    prep = sr.build_prep(_decision("2026-12-01"), _sectors(None))
    manual = prep[["date", "sector"]].copy()
    manual["vz"] = pd.concat([prep.groupby("date")[k].transform(fb.winsorize_z)
                              for k in ("bm", "ep", "sp", "ey")], axis=1).mean(axis=1)
    expected = fb.sector_neutralize(manual, "vz")
    sc = sr.variant_scores(prep)
    assert np.allclose(sc["R0_top20"], expected)
    p = sr.picks(prep)
    assert len(p["R0_top20"]) == 8 and len(p["R0_top10"]) == 4
    assert list(p["R0_top10"]["ticker"]) == list(p["R0_top20"]["ticker"][:4])


def test_variants_change_only_their_leg():
    prep = sr.build_prep(_decision("2026-12-01"), _sectors(None))
    sc = sr.variant_scores(prep)
    # all E/P positive -> floor has no effect
    prep2 = prep.copy()
    prep2["ep"] = prep2["ep"].abs() + 0.01
    prep2["ep_z"] = sr.vv._leg_z(prep2, prep2["ep"])
    s2 = sr.variant_scores(prep2)
    assert np.allclose(s2["vlab_ep_floor0"], s2["R0_top20"])
    assert not np.allclose(sc["vlab_op_mcap"], sc["R0_top20"])


def test_financials_dropped():
    sec = _sectors(None)
    sec["T00"] = "Bankacılık"
    prep = sr.build_prep(_decision("2026-12-01"), sec)
    assert "T00" not in set(prep["ticker"]) and len(prep) == 39


def test_update_append_only_and_return_fill(tmp_path):
    csv = tmp_path / "sr.csv"
    pdir = _prices(tmp_path, ["2026-12-02", "2027-01-04", "2027-02-02"])
    d1, d2 = _decision("2026-12-01", seed=1), _decision("2027-01-03", seed=2)
    rec = sr.update_record([d1], path=csv, prices_dir=pdir, sector_fn=_sectors)
    assert rec["ret"].isna().all() and set(rec["variant"]) == set(sr.VARIANTS)
    first = rec.copy()
    # second decision changes nothing already written, only fills returns of month 1
    d1_mut = {**d1, "ranking": list(reversed(d1["ranking"]))[:5]}
    rec = sr.update_record([d1_mut, d2], path=csv, prices_dir=pdir, sector_fn=_sectors)
    m1 = rec[rec["rebalance_date"] == "2026-12-01"].reset_index(drop=True)
    assert list(m1["ticker"]) == list(first["ticker"])
    assert m1["ret"].notna().all()
    row = m1.iloc[0]
    i = int(row["ticker"][1:])
    assert row["entry_date"] == "2026-12-02" and row["exit_date"] == "2027-01-04"
    assert np.isclose(row["ret"], (10 + i * 0.1) / 10 - 1)
    assert rec[rec["rebalance_date"] == "2027-01-03"]["ret"].isna().all()
    assert rec["counted"].astype(str).str.lower().eq("true").all()


def test_pre_start_decisions_not_counted(tmp_path):
    pdir = _prices(tmp_path, ["2026-11-02", "2026-12-02"])
    rec = sr.update_record([_decision("2026-11-01"), _decision("2026-12-01")], path=tmp_path / "x.csv",
                           prices_dir=pdir, sector_fn=_sectors)
    assert sr.monthly_returns(rec).empty
    assert not sr.monthly_returns(rec, counted_only=False).empty


def test_evaluate_rule():
    idx = [f"m{i:02d}" for i in range(24)]
    rng = np.random.default_rng(3)
    base = pd.Series(rng.normal(0.02, 0.05, 24), index=idx)
    monthly = pd.DataFrame({"R0_top20": base, "R0_top10": base + 0.01 + rng.normal(0, 0.005, 24),
                            "vlab_ep_floor0": base - 0.01, "vlab_op_mcap": base + rng.normal(0, 0.03, 24)})
    out = sr.evaluate(monthly)["variants"]
    assert out["R0_top10"]["status"] == "PASS"
    assert out["vlab_ep_floor0"]["status"] == "FAIL"
    short = sr.evaluate(monthly.iloc[:10])["variants"]
    assert all(v["status"] == "pending" for v in short.values())
