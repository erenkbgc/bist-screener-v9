"""tests/test_sector_neutral.py: Tests for sector-neutral valuation z-score and peer fallback."""
from __future__ import annotations

import pytest

from core import db
from core.ranking import (
    MIN_PEER_N,
    build_peer_group,
    compute_sector_neutral_valuation,
    compute_valuation_z,
)


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def _make_candidate(ticker, sector, supersector, pe=15.0, pb=2.0):
    return {
        "ticker": ticker,
        "sector": sector,
        "supersector": supersector,
        "ratio_profile": "industrial",
        "reporting_basis": "nominal",
        "pe": pe,
        "pb": pb,
        "ev_ebitda": 10.0,
        "ev_sales": 2.0,
        "roe": 20.0,
        "net_debt_ebitda": 1.0,
        "fcf_yield": 0.05,
    }


def test_sector_level_when_peer_n_at_least_5():
    cand = _make_candidate("MAIN", "XUTEK", "XUTEK")
    peers = [cand] + [_make_candidate(f"PEER_{i}", "XUTEK", "XUTEK", pe=16.0 + i) for i in range(4)]
    # Total = 5 peers in sector
    res = compute_sector_neutral_valuation(cand, peers)
    assert res["peer_group_used"] == "sector"
    assert res["peer_n"] == 5
    assert res["confidence"] == "high"
    assert res["valuation_z_sector_neutral"] is not None


def test_fallback_to_supersector_when_sector_peers_under_5():
    cand = _make_candidate("MAIN", "XBLSM", "XUTEK")
    # Only 3 peers in same sector XBLSM (< 5)
    same_sec = [cand] + [_make_candidate(f"BLSM_{i}", "XBLSM", "XUTEK") for i in range(2)]
    # Other peers in same supersector XUTEK
    same_sup = [_make_candidate(f"UTEK_{i}", "XILTM", "XUTEK") for i in range(6)]
    all_cand = same_sec + same_sup

    res = compute_sector_neutral_valuation(cand, all_cand)
    assert res["peer_group_used"] == "supersector"
    assert res["confidence"] == "degraded"
    assert res["peer_n"] >= 5


def test_fallback_to_market_when_supersector_under_5():
    cand = _make_candidate("MAIN", "RARE_SEC", "RARE_SUP")
    # Only 2 peers total in supersector
    peers = [cand, _make_candidate("OTHER", "RARE_SEC", "RARE_SUP")]
    res = compute_sector_neutral_valuation(cand, peers)
    assert res["peer_group_used"] == "none"
    assert res["confidence"] == "insufficient_peers"
