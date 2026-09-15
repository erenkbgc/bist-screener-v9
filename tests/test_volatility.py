"""low_vol_z testi."""
from core.volatility import compute_low_vol_z


def _pool(*vols):
    return [{"volatility_60d": v} for v in vols]


def test_missing_own_volatility_returns_zero():
    assert compute_low_vol_z({"volatility_60d": None}, _pool(0.01, 0.02, 0.03)) == 0.0


def test_insufficient_population_returns_zero():
    assert compute_low_vol_z({"volatility_60d": 0.01}, _pool(0.01)) == 0.0


def test_none_values_excluded_from_population():
    population = [{"volatility_60d": None}, {"volatility_60d": 0.01}, {"volatility_60d": 0.02}]
    result = compute_low_vol_z({"volatility_60d": 0.01}, population)
    assert result != 0.0


def test_lower_volatility_scores_higher():
    population = _pool(0.01, 0.02, 0.05)
    low = compute_low_vol_z({"volatility_60d": 0.01}, population)
    high = compute_low_vol_z({"volatility_60d": 0.05}, population)
    assert low > high


def test_zero_variance_population_returns_zero():
    assert compute_low_vol_z({"volatility_60d": 0.02}, _pool(0.02, 0.02, 0.02)) == 0.0
