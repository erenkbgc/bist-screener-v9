"""beta hurdle testi: excess_over_beta_hurdle_pct hard_filters listesinde
OLMAMALI, yalnizca bilgi alani olmali."""
import inspect

from core.beta_hurdle import calculate_beta, calculate_beta_adjusted_hurdle
from core.scoring import hard_filters_passed


def test_beta_is_positive_for_correlated_stock():
    import random
    rng = random.Random(7)
    market_price, stock_price = 100.0, 100.0
    market, stock = [], []
    for _ in range(120):
        market_ret = rng.gauss(0, 0.01)
        stock_ret = 2 * market_ret  # piyasadan 2x hassas (beta ~= 2), mukemmel korelasyon
        market_price *= (1 + market_ret)
        stock_price *= (1 + stock_ret)
        market.append({"close": market_price})
        stock.append({"close": stock_price})

    beta = calculate_beta(stock, market)
    assert beta is not None
    assert beta > 1.5


def test_beta_none_with_insufficient_history():
    market = [{"close": 100 + i} for i in range(10)]
    stock = [{"close": 100 + i} for i in range(10)]
    assert calculate_beta(stock, market) is None


def test_excess_over_beta_hurdle_not_referenced_in_hard_filters_source():
    """Statik kontrol: core/scoring.py::hard_filters_passed kaynak kodunda
    'excess_over_beta_hurdle_pct' gecmemeli (yalnizca excess_over_hurdle_pct
    kontrol edilir)."""
    source = inspect.getsource(hard_filters_passed)
    assert "excess_over_beta_hurdle_pct" not in source
    assert "excess_over_hurdle_pct" in source


def test_beta_adjusted_hurdle_stored_as_info_field(temp_db):
    prices = [{"close": 100 + i * 0.1, "high": 100 + i * 0.1 + 1, "low": 100 + i * 0.1 - 1}
              for i in range(140)]
    row = calculate_beta_adjusted_hurdle("2026-09-10", "AAA", prices, risk_free_annual_pct=39.6,
                                          expected_roi_pct=20.0)
    assert "excess_over_beta_hurdle_pct" in row
    assert "hurdle_rate_beta_adjusted_pct" in row
