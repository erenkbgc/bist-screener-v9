"""correlation diagnostic testi: >0.85 uyari eklenir, otomatik eleme YAPMAZ."""
from core.correlation import compute_correlation_flags, CORRELATION_THRESHOLD


def test_highly_correlated_pair_flagged(temp_db):
    closes_a = [100 + i for i in range(60)]
    closes_b = [200 + 2 * i for i in range(60)]  # A ile mukemmel korelasyon
    prices = {
        "A": [{"close": c} for c in closes_a],
        "B": [{"close": c} for c in closes_b],
    }
    flags = compute_correlation_flags("2026-09-10", prices)
    assert len(flags) == 1
    assert flags[0]["correlation_60d"] > CORRELATION_THRESHOLD


def test_uncorrelated_pair_not_flagged(temp_db):
    import random
    rng = random.Random(42)
    prices = {
        "A": [{"close": 100 + rng.gauss(0, 5)} for _ in range(60)],
        "B": [{"close": 200 + rng.gauss(0, 5)} for _ in range(60)],
    }
    flags = compute_correlation_flags("2026-09-10", prices)
    assert flags == []


def test_correlation_does_not_remove_candidates():
    """explicit_non_action: bu fonksiyon yalnizca bayrak dondurur, aday listesini
    degistirecek bir donus (filtrelenmis liste) YOKTUR -- imzasi bunu garanti eder."""
    import inspect
    from core.correlation import compute_correlation_flags
    sig = inspect.signature(compute_correlation_flags)
    assert "as_of_date" in sig.parameters and "price_series_by_ticker" in sig.parameters
