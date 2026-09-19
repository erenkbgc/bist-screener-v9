"""tests/test_hrp_portfolio.py: Hierarchical Risk Parity (HRP) ve CVaR testleri."""
from __future__ import annotations

from datetime import date, timedelta
import numpy as np
import pytest

from core import db
from core.portfolio import (
    compute_portfolio_cvar,
    get_portfolio_allocations,
    optimize_hrp,
    optimize_portfolio,
)


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def test_optimize_hrp_weights_sum_and_risk_allocation():
    # 4 hisse: Farkli volatiliteler ve sektorler
    # Hisse 0 cok guvenli (vol=0.15), Hisse 3 cok riskli (vol=0.45)
    cov = np.diag([0.0225, 0.04, 0.09, 0.2025])
    sectors = ["SEC_A", "SEC_B", "SEC_C", "SEC_D"]

    w, applied = optimize_hrp(cov, sectors, max_sector_weight=0.35)
    assert np.isclose(np.sum(w), 1.0)
    assert np.all(w >= 0.0)

    # Dusuk volatiliteli hisse yuksek volatiliteli hisseden DAHA FAZLA agirlik almali
    assert w[0] > w[3]
    # Sektor tavani (%35) asilmamali
    assert np.all(w <= 0.35001)


def test_compute_portfolio_cvar():
    # 100 gunluk sentetik getiri serisi (normal dagilim: ortalama %0.1, std %2.0)
    np.random.seed(42)
    returns_mat = np.random.normal(0.001, 0.02, size=(100, 3))
    weights = np.array([0.40, 0.35, 0.25])

    cvar = compute_portfolio_cvar(weights, returns_mat, confidence=0.95)
    assert cvar is not None
    # CVaR pozitif bir risk metriğidir (% cinsinden en kotu %5 gunun ortalama kaybi)
    # %2 volatilitede %95 CVaR genellikle %2.5 - %4.5 arasinda cikar
    assert 1.5 < cvar < 6.0


def test_optimize_portfolio_hrp_end_to_end():
    candidates = [
        {"ticker": "ASELS", "sector": "SAVUNMA", "final_score": 2.5, "expected_roi_pct": 45.0},
        {"ticker": "THYAO", "sector": "HAVACILIK", "final_score": 2.2, "expected_roi_pct": 38.0},
        {"ticker": "BIMAS", "sector": "PERAKENDE", "final_score": 2.0, "expected_roi_pct": 32.0},
        {"ticker": "KCHOL", "sector": "HOLDING", "final_score": 1.9, "expected_roi_pct": 28.0},
    ]

    base_d = date(2026, 1, 1)
    price_series = {}
    for i, c in enumerate(candidates):
        t = c["ticker"]
        np.random.seed(100 + i)
        rows = []
        p = 100.0 + i * 20
        for d in range(60):
            d_str = (base_d + timedelta(days=d)).isoformat()
            ret = np.random.normal(0.001, 0.015)
            p *= (1.0 + ret)
            rows.append({"ticker": t, "date": d_str, "close": p})
        price_series[t] = rows

    test_date = "2029-02-15"
    res = optimize_portfolio(
        candidates,
        price_series,
        method="hrp",
        as_of_date=test_date,
        max_sector_weight=0.30,
        save_to_db=True,
    )

    assert res["active_candidates_count"] == 4
    assert res["method"] == "hrp"
    assert "cvar_95_pct" in res
    assert res["cvar_95_pct"] > 0.0
    assert np.isclose(sum(res["recommended_portfolio_weights"].values()), 100.0, atol=0.1)

    for sec, alloc in res["sector_allocations_pct"].items():
        assert alloc <= 30.01

    # DB kayit kontrolu
    db_rows = get_portfolio_allocations(test_date, method="hrp")
    assert len(db_rows) == 4
    assert sum(r["weight_pct"] for r in db_rows) >= 99.8
