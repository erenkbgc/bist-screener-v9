"""sloan basis_guard testi, sloan cross-sectional testi."""
from core.sloan import calculate_earnings_quality
from bist_mcp import server as bist_mcp


def _universe_row(ticker, market_cap):
    return {"ticker": ticker, "sector": "XGIDA", "supersector": "XUSIN",
            "ratio_profile": "industrial", "market_cap": market_cap}


def test_sloan_null_for_basis_break(temp_db):
    """basis_break olan donem icin sloan null olmali."""
    universe_rows = [_universe_row("AAA", 1000)]
    fundamentals_by_ticker = {"AAA": {"reporting_basis": "unknown"}}
    rows = calculate_earnings_quality("2026-09-10", universe_rows, fundamentals_by_ticker)
    assert rows[0]["sloan_accrual_ratio"] is None
    assert rows[0]["null_reason"] == "basis_break"


def test_sloan_is_cross_sectional_percentile_not_absolute_threshold(temp_db, monkeypatch):
    """MUTLAK ESIK degil peer grubu ici persentil kullanilmali."""
    universe_rows = [_universe_row(f"T{i}", 1000) for i in range(10)]
    fundamentals_by_ticker = {
        f"T{i}": {"reporting_basis": "adjusted", "_raw": {"pe": 10, "eps_ttm": 1}}
        for i in range(10)
    }

    # her ticker icin farkli operating_cashflow -> farkli sloan orani
    def fake_cashflow(ticker, as_of_date, net_income_hint):
        idx = int(ticker[1:])
        # idx arttikca operating cashflow azalir -> tahakkuk orani artar (daha supheli)
        return {"operating_cashflow_ttm": net_income_hint * (1.5 - idx * 0.1), "average_total_assets": 1000}

    monkeypatch.setattr(bist_mcp, "get_cashflow_for_sloan", fake_cashflow)

    rows = calculate_earnings_quality("2026-09-10", universe_rows, fundamentals_by_ticker)
    by_ticker = {r["ticker"]: r for r in rows}

    # en yuksek tahakkuk orani (T9) ust ondalik dilimde olmali (elevated flag)
    assert by_ticker["T9"]["elevated_risk_flag"] == 1
    # en dusuk tahakkuk orani (T0) elevated OLMAMALI
    assert by_ticker["T0"]["elevated_risk_flag"] == 0
    # persentiller 0..1 araliginda olmali (mutlak deger degil goreli sira)
    for r in rows:
        assert 0.0 <= r["peer_percentile"] <= 1.0
