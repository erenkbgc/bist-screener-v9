"""decay testi."""
from core.decay import effective_weight


def test_effective_weight_at_zero_days_equals_base():
    assert effective_weight(3, 0, 75) == 3


def test_effective_weight_halves_at_half_life():
    result = effective_weight(4, 20, 20)
    assert abs(result - 2.0) < 1e-9


def test_effective_weight_decreases_over_time():
    w10 = effective_weight(3, 10, 75)
    w50 = effective_weight(3, 50, 75)
    assert w50 < w10


def test_effective_weight_zero_half_life_returns_zero():
    assert effective_weight(3, 5, 0) == 0.0
