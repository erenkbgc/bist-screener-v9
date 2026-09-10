"""gordon eligibility testi, gordon sustainability testi, gordon output testi (aralik)."""
from core.gordon import is_eligible, calculate_gordon_reference
from core.dividend_sustainability import check_dividend_sustainability


def test_eligibility_fails_with_short_history():
    eligible, reason = is_eligible(dividend_streak_years=1, passes_sustainability=True)
    assert eligible is False
    assert reason == "dividend_history_insufficient"


def test_eligibility_fails_when_not_sustainable():
    eligible, reason = is_eligible(dividend_streak_years=5, passes_sustainability=False)
    assert eligible is False
    assert reason == "dividend_not_sustainable"


def test_eligibility_passes():
    eligible, reason = is_eligible(dividend_streak_years=4, passes_sustainability=True)
    assert eligible is True
    assert reason is None


def test_sustainability_fails_when_coverage_below_one(temp_db, monkeypatch):
    """gordon sustainability testi: fcf_payout_coverage < 1 olan sirket icin
    gordon hesaplanmamali."""
    fundamentals_row = {
        "fcf_ttm": 100.0, "payout_ratio": 0.9, "net_debt": 50.0,
        "_raw": {"pe": 10, "ebitda_ttm": 200}, "market_cap": 1000.0,
    }

    import core.dividend_sustainability as ds_mod
    monkeypatch.setattr(
        ds_mod.bist_mcp, "get_dividend_history",
        lambda ticker, as_of_date: {"dividend_streak_years": 5, "payout_ratio_trend_3p": "stabil"},
    )

    div_sustain = check_dividend_sustainability("2026-09-10", "AAA", fundamentals_row)
    # net_income_ttm = market_cap/pe = 100, dividend_paid_ttm = payout*net_income = 90
    # coverage = 90/100 = 0.9 < 1 -> surdurulemez
    assert div_sustain["passes_sustainability"] == 0

    result = calculate_gordon_reference(
        "2026-09-10", "AAA", dividend_per_share=5.0, risk_free_annual_pct=39.6,
        dividend_streak_years=div_sustain["dividend_streak_years"],
        passes_sustainability=bool(div_sustain["passes_sustainability"]),
    )
    assert result["null_reason"] == "dividend_not_sustainable"
    assert result["fair_value_low"] is None


def test_gordon_output_is_a_range_not_single_number(temp_db):
    result = calculate_gordon_reference(
        "2026-09-10", "BBB", dividend_per_share=5.0, risk_free_annual_pct=39.6,
        dividend_streak_years=5, passes_sustainability=True,
    )
    assert result["null_reason"] is None
    assert result["fair_value_low"] is not None
    assert result["fair_value_high"] is not None
    assert result["fair_value_low"] <= result["fair_value_high"]
    assert result["discount_rate_low"] < result["discount_rate_base"] < result["discount_rate_high"]


def test_gordon_unstable_denominator(temp_db):
    """discount_rate - g <= 0 ise hesaplanmaz, null_reason='unstable_denominator'."""
    # cok dusuk risk-free ile discount_rate g'nin altina dusebilir; equity_risk_premium=5,
    # g=5 (config), discount_rate_base = risk_free + 5. risk_free=-4 -> base=1, base-g=-4 <=0
    result = calculate_gordon_reference(
        "2026-09-10", "CCC", dividend_per_share=5.0, risk_free_annual_pct=-4.0,
        dividend_streak_years=5, passes_sustainability=True,
    )
    assert result["null_reason"] == "unstable_denominator"
