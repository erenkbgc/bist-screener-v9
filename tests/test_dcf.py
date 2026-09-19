"""dcf eligibility testi, dcf output testi (aralik), unstable denominator testi."""
from core.dcf import is_eligible, calculate_dcf_reference, calculate_wacc_pct


def test_eligibility_fails_without_fcf():
    eligible, reason = is_eligible(fcf_ttm=None, shares_outstanding=1000, market_cap=1e9, beta=1.0)
    assert eligible is False
    assert reason == "no_fcf"

    eligible, reason = is_eligible(fcf_ttm=-5.0, shares_outstanding=1000, market_cap=1e9, beta=1.0)
    assert eligible is False
    assert reason == "no_fcf"


def test_eligibility_fails_without_shares_outstanding():
    eligible, reason = is_eligible(fcf_ttm=100.0, shares_outstanding=None, market_cap=1e9, beta=1.0)
    assert eligible is False
    assert reason == "missing_shares_outstanding"


def test_eligibility_fails_without_market_cap():
    eligible, reason = is_eligible(fcf_ttm=100.0, shares_outstanding=1000, market_cap=None, beta=1.0)
    assert eligible is False
    assert reason == "missing_market_cap"


def test_eligibility_fails_without_beta():
    eligible, reason = is_eligible(fcf_ttm=100.0, shares_outstanding=1000, market_cap=1e9, beta=None)
    assert eligible is False
    assert reason == "beta_unavailable"


def test_eligibility_passes():
    eligible, reason = is_eligible(fcf_ttm=100.0, shares_outstanding=1000, market_cap=1e9, beta=1.0)
    assert eligible is True
    assert reason is None


def test_wacc_falls_back_to_cost_of_equity_when_no_debt():
    wacc = calculate_wacc_pct(beta=1.0, erp=5.0, risk_free_annual_pct=20.0, market_cap=1e9,
                               net_debt=0.0, financial_expenses_ttm=None, tax_rate_pct=25.0)
    assert wacc == 25.0  # risk_free + beta*erp = 20 + 1*5


def test_wacc_blends_cost_of_debt_when_levered():
    # net_debt=5e8 (D), market_cap=1e9 (E) -> D/V=1/3, E/V=2/3
    # cost_of_equity = 20 + 1*5 = 25, cost_of_debt = 1e8/5e8*100 = 20 -> after-tax (25% tax) = 15
    wacc = calculate_wacc_pct(beta=1.0, erp=5.0, risk_free_annual_pct=20.0, market_cap=1e9,
                               net_debt=5e8, financial_expenses_ttm=1e8, tax_rate_pct=25.0)
    expected = (2 / 3) * 25.0 + (1 / 3) * 15.0
    assert abs(wacc - expected) < 1e-9


def test_dcf_output_is_a_range_not_single_number(temp_db):
    result = calculate_dcf_reference(
        "2026-09-10", "BBB", fcf_ttm=1e9, shares_outstanding=1e8, current_price=50.0,
        beta=1.0, risk_free_annual_pct=20.0, market_cap=5e9, net_debt=0.0,
        financial_expenses_ttm=None,
    )
    assert result["null_reason"] is None
    assert result["fair_value_low"] is not None
    assert result["fair_value_high"] is not None
    assert result["fair_value_low"] <= result["fair_value_high"]
    assert result["growth_low_pct"] < result["growth_base_pct"] < result["growth_high_pct"]
    assert result["premium_discount_low_pct"] is not None
    assert result["premium_discount_high_pct"] is not None


def test_dcf_ineligible_company_returns_none_and_reason(temp_db):
    result = calculate_dcf_reference(
        "2026-09-10", "CCC", fcf_ttm=None, shares_outstanding=1e8, current_price=50.0,
        beta=1.0, risk_free_annual_pct=20.0, market_cap=5e9, net_debt=0.0,
        financial_expenses_ttm=None,
    )
    assert result["null_reason"] == "no_fcf"
    assert result["fair_value_low"] is None
    assert result["fair_value_high"] is None


def test_dcf_unstable_denominator(temp_db):
    """wacc - g <= 0 ise hesaplanmaz, null_reason='unstable_denominator'."""
    # equity_risk_premium=5, g=5 (config). risk_free=-4 -> cost_of_equity=1,
    # borcsuz sirket icin wacc=cost_of_equity=1, wacc-g=-4 <= 0.
    result = calculate_dcf_reference(
        "2026-09-10", "DDD", fcf_ttm=1e9, shares_outstanding=1e8, current_price=50.0,
        beta=1.0, risk_free_annual_pct=-4.0, market_cap=5e9, net_debt=0.0,
        financial_expenses_ttm=None,
    )
    assert result["null_reason"] == "unstable_denominator"
    assert result["fair_value_low"] is None


def test_dcf_small_positive_spread_is_also_unstable(temp_db):
    """Outlier guard: wacc-g sifirin UZERINDE ama equity_risk_premium_pct'nin
    ALTINDA kalirsa (orn. %0.5) da null -- aksi halde absurd (fiyatin onlarca
    kati) bir fair_value 'gecerli' gibi donerdi. equity_risk_premium=5, g=5
    (config); risk_free=0.5, beta=1, borcsuz -> wacc=cost_of_equity=5.5,
    wacc-g=0.5 < erp(5)."""
    result = calculate_dcf_reference(
        "2026-09-10", "EEE", fcf_ttm=1e9, shares_outstanding=1e8, current_price=50.0,
        beta=1.0, risk_free_annual_pct=0.5, market_cap=5e9, net_debt=0.0,
        financial_expenses_ttm=None,
    )
    assert result["null_reason"] == "unstable_denominator"
    assert result["fair_value_low"] is None


def test_dcf_outlier_guard_rejects_extreme_valuations(temp_db):
    """Outlier guard: Eger fcf_ttm cok yuksekse ve hesaplanan adil deger mevcut fiyatin
    3 katini asarsa (orn. fiyat 50 iken fair value 300+ ise), model bunu tekillik/veri
    anomalisi olarak gorup null_reason='outlier_valuation' ile reddeder."""
    # fcf_ttm=1e10 (10 milyar TL), shares=1e8 -> fcf_ps = 100 TL.
    # risk_free=20, beta=1, erp=5 -> wacc=25. spread=20.
    # fcf_next * 1.05 / 0.20 = 100 * 1.05 * 1.05 / 0.20 = 551 TL (fiyat 50 TL iken 11x kat!).
    result = calculate_dcf_reference(
        "2026-09-10", "OUTL", fcf_ttm=1e10, shares_outstanding=1e8, current_price=50.0,
        beta=1.0, risk_free_annual_pct=20.0, market_cap=5e9, net_debt=0.0,
        financial_expenses_ttm=None,
    )
    assert result["null_reason"] == "outlier_valuation"
    assert result["fair_value_low"] is None
    assert result["fair_value_high"] is None
