"""compute_short_term_target likidite bazli dinamik stop/hedef testi."""
from core.targets import compute_short_term_target, _liquidity_buffer_multiplier


def test_no_volume_data_keeps_base_multipliers():
    result = compute_short_term_target(100.0, atr20=2.0, sma20=98.0, avg_volume_tl_20d=None)
    assert result["liquidity_buffer_multiplier"] == 1.0
    assert result["target_price"] == 100.0 + 2.5 * 2.0
    assert result["stop_loss"] == 100.0 - 1.2 * 2.0


def test_liquidity_floor_gets_max_buffer():
    assert _liquidity_buffer_multiplier(10_000_000) == 1.3
    assert _liquidity_buffer_multiplier(5_000_000) == 1.3


def test_liquidity_ceiling_and_above_gets_no_buffer():
    assert _liquidity_buffer_multiplier(50_000_000) == 1.0
    assert _liquidity_buffer_multiplier(900_000_000) == 1.0


def test_liquidity_midpoint_interpolates():
    result = _liquidity_buffer_multiplier(30_000_000)
    assert abs(result - 1.15) < 1e-9


def test_low_liquidity_widens_stop_and_target():
    base = compute_short_term_target(100.0, atr20=2.0, sma20=98.0, avg_volume_tl_20d=None)
    illiquid = compute_short_term_target(100.0, atr20=2.0, sma20=98.0, avg_volume_tl_20d=10_000_000)
    assert illiquid["target_price"] > base["target_price"]
    assert illiquid["stop_loss"] < base["stop_loss"]
    assert illiquid["liquidity_buffer_multiplier"] == 1.3
