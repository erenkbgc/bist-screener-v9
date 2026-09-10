"""ownership testi: risk_rules (retail yogunlasma, free_float, penalize)."""
import pytest

from core.ownership import fetch_ownership, compute_ownership_z, PENALTY_FACTOR
from bist_mcp import server as bist_mcp


def _prices_with_return(pct_return):
    # 21 gunluk fiyat serisi, ilk kapanis 100, son kapanis 100*(1+pct/100)
    base = 100.0
    end = base * (1 + pct_return / 100)
    step = (end - base) / 20
    return [{"close": base + i * step} for i in range(21)]


def test_short_term_rejected_when_high_retail_and_high_return(temp_db, monkeypatch):
    monkeypatch.setattr(bist_mcp, "get_ownership", lambda t, d: {
        "investor_count": 1000, "investor_count_change_1m": 5, "retail_pct": 85,
        "institutional_pct": 10, "free_float_pct": 30, "foreign_pct": 5,
    })
    row = fetch_ownership("2026-09-10", "AAA", _prices_with_return(35))
    assert row["_short_term_rejected"] is True


def test_not_rejected_when_return_below_threshold(temp_db, monkeypatch):
    monkeypatch.setattr(bist_mcp, "get_ownership", lambda t, d: {
        "investor_count": 1000, "investor_count_change_1m": 5, "retail_pct": 85,
        "institutional_pct": 10, "free_float_pct": 30, "foreign_pct": 5,
    })
    row = fetch_ownership("2026-09-10", "AAA", _prices_with_return(10))
    assert row["_short_term_rejected"] is False


def test_penalize_flag_set_for_investor_surge(temp_db, monkeypatch):
    monkeypatch.setattr(bist_mcp, "get_ownership", lambda t, d: {
        "investor_count": 1000, "investor_count_change_1m": 60, "retail_pct": 75,
        "institutional_pct": 10, "free_float_pct": 30, "foreign_pct": 5,
    })
    row = fetch_ownership("2026-09-10", "AAA", _prices_with_return(5))
    assert row["_penalize"] is True


def test_ownership_z_applies_penalty_factor():
    candidate = {"institutional_pct": 50, "free_float_pct": 40, "retail_pct": 10, "_penalize": True}
    population = [candidate,
                  {"institutional_pct": 10, "free_float_pct": 20, "retail_pct": 70, "_penalize": False},
                  {"institutional_pct": 20, "free_float_pct": 20, "retail_pct": 60, "_penalize": False}]
    z_penalized = compute_ownership_z(candidate, population)

    candidate_no_penalty = dict(candidate, _penalize=False)
    population2 = [candidate_no_penalty, population[1], population[2]]
    z_unpenalized = compute_ownership_z(candidate_no_penalty, population2)

    assert abs(z_penalized) < abs(z_unpenalized)
    assert z_penalized == pytest.approx(z_unpenalized * PENALTY_FACTOR)
