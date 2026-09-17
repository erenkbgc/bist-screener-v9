"""tests/test_portfolio.py: Tests for portfolio optimization, correlation filtering, and sector caps."""
from __future__ import annotations

import numpy as np
import pytest

from core import db
from core.portfolio import (
    apply_sector_caps,
    filter_correlated_candidates,
    get_portfolio_allocations,
    optimize_min_variance,
    optimize_portfolio,
    optimize_risk_parity,
)


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def test_correlation_filter():
    candidates = [
        {"ticker": "STOCK_A", "final_score": 2.50, "sector": "XUTEK"},
        {"ticker": "STOCK_B", "final_score": 1.80, "sector": "XUTEK"},
        {"ticker": "STOCK_C", "final_score": 2.10, "sector": "XULAS"},
    ]
    # STOCK_A and STOCK_B have 0.95 correlation
    returns_dict = {
        "STOCK_A": np.array([0.01, 0.02, -0.01, 0.03, -0.02] * 5),
        "STOCK_B": np.array([0.011, 0.019, -0.009, 0.031, -0.019] * 5),  # very high corr
        "STOCK_C": np.array([-0.02, 0.01, 0.03, -0.01, 0.02] * 5),
    }

    filtered, dropped = filter_correlated_candidates(candidates, returns_dict, threshold=0.80)
    assert len(filtered) == 2
    kept_tickers = {c["ticker"] for c in filtered}
    assert "STOCK_A" in kept_tickers
    assert "STOCK_C" in kept_tickers
    assert "STOCK_B" not in kept_tickers
    assert len(dropped) == 1
    assert dropped[0]["dropped"] == "STOCK_B"
    assert dropped[0]["kept"] == "STOCK_A"
    assert dropped[0]["correlation"] > 0.80


def test_sector_cap_bounded_simplex():
    # 5 sectors, sector 0 has 50% initial weight
    raw_weights = np.array([0.50, 0.20, 0.15, 0.10, 0.05])
    sectors = ["SEC_A", "SEC_B", "SEC_C", "SEC_D", "SEC_E"]

    w_capped, applied = apply_sector_caps(raw_weights, sectors, max_sector_weight=0.30)
    assert applied is True
    assert np.isclose(np.sum(w_capped), 1.0)
    # SEC_A must be <= 0.30
    assert w_capped[0] <= 0.30001
    for i in range(len(w_capped)):
        assert w_capped[i] <= 0.30001
        assert w_capped[i] >= 0.0


def test_sector_cap_few_sectors_fallback():
    # Only 2 sectors: mathematically cannot be <= 0.30, so must be at most 0.50 each
    raw_weights = np.array([0.80, 0.20])
    sectors = ["SEC_A", "SEC_B"]

    w_capped, applied = apply_sector_caps(raw_weights, sectors, max_sector_weight=0.30)
    assert applied is True
    assert np.isclose(np.sum(w_capped), 1.0)
    assert w_capped[0] <= 0.50001
    assert w_capped[1] <= 0.50001


def test_optimize_risk_parity():
    # Asset with lower volatility should receive higher weight
    cov = np.diag([0.04, 0.16, 0.09, 0.04])  # vols: 0.2, 0.4, 0.3, 0.2
    sectors = ["S1", "S2", "S3", "S4"]

    w, _ = optimize_risk_parity(cov, sectors, max_sector_weight=0.30)
    assert np.isclose(np.sum(w), 1.0)
    # Asset 0 (vol 0.2) should have higher weight than Asset 1 (vol 0.4)
    assert w[0] > w[1]
    assert np.all(w <= 0.30001)


def test_optimize_portfolio_end_to_end():
    candidates = [
        {"ticker": "TK1", "sector": "SEC1", "final_score": 2.2, "expected_roi_pct": 50.0},
        {"ticker": "TK2", "sector": "SEC2", "final_score": 2.0, "expected_roi_pct": 40.0},
        {"ticker": "TK3", "sector": "SEC3", "final_score": 1.8, "expected_roi_pct": 35.0},
        {"ticker": "TK4", "sector": "SEC4", "final_score": 1.7, "expected_roi_pct": 30.0},
    ]

    # Generate synthetic price series
    from datetime import date, timedelta
    base_d = date(2026, 1, 1)
    price_series = {}
    for i, c in enumerate(candidates):
        t = c["ticker"]
        np.random.seed(42 + i)
        rows = []
        p = 100.0 + i * 10
        for d in range(60):
            d_str = (base_d + timedelta(days=d)).isoformat()
            ret = np.random.normal(0.001, 0.015)
            p *= (1.0 + ret)
            rows.append({"ticker": t, "date": d_str, "close": p})
        price_series[t] = rows

    for method in ["risk_parity", "min_variance", "max_sharpe"]:
        test_date = f"2029-01-01"
        res = optimize_portfolio(
            candidates,
            price_series,
            method=method,
            as_of_date=test_date,
            max_sector_weight=0.30,
            save_to_db=True,
        )
        assert res["active_candidates_count"] == 4
        assert np.isclose(sum(res["recommended_portfolio_weights"].values()), 100.0, atol=0.1)
        for sec, alloc in res["sector_allocations_pct"].items():
            assert alloc <= 30.01

        # Check DB persistence
        db_rows = get_portfolio_allocations(test_date, method=method)
        assert len(db_rows) == 4
        assert sum(r["weight_pct"] for r in db_rows) >= 99.8
