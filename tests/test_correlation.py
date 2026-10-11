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


def test_common_trend_with_independent_returns_not_flagged(temp_db):
    # Fiyat seviyesi uzerinden Pearson bu iki seriyi ~1 korelasyonlu sayardi.
    import math
    import random
    rng = random.Random(7)
    a, b = [100.0], [50.0]
    for _ in range(60):
        a.append(a[-1] * math.exp(0.01 + rng.gauss(0, 0.02)))
        b.append(b[-1] * math.exp(0.01 + rng.gauss(0, 0.02)))
    prices = {"A": [{"close": c} for c in a], "B": [{"close": c} for c in b]}
    assert compute_correlation_flags("2026-09-10", prices) == []


def test_effective_bets():
    from core.correlation import effective_bets
    import random
    rng = random.Random(1)
    common = [rng.gauss(0, 0.02) for _ in range(60)]
    def series(noise):
        p, out = 100.0, [{"close": 100.0}]
        for m in common:
            p *= 1 + m + rng.gauss(0, noise)
            out.append({"close": p})
        return out
    tight = effective_bets({t: series(0.001) for t in "ABCD"})
    loose = effective_bets({t: series(0.05) for t in "ABCD"})
    assert tight["n_holdings"] == 4 and tight["effective_n"] < 1.5
    assert loose["effective_n"] > tight["effective_n"]
    assert effective_bets({"A": series(0.01)})["effective_n"] is None


def test_effective_bets_line_passes_validation_gate():
    from report.render import render_mobile_newsletter
    from report.validate import find_orphan_numbers
    rotation = {"rebalance_date": "2026-10-01", "buy": [{"ticker": "AAA"}], "hold": [], "sell": [],
                "n_holdings": 23, "top_pct": 20.0}
    pc = {"n_holdings": 23, "avg_pairwise_corr": 0.312, "effective_n": 2.9}
    payload = {"rotation": rotation, "portfolio_correlation": pc}
    ctx = {"as_of_date": "2026-10-01", "long_term_candidates": [], "short_term_candidates": [],
           "long_term_display_count": 0, "short_term_display_count": 0, "sector_rotation": [],
           "no_action_today": True, "rotation": rotation, "portfolio_correlation": pc}
    html = render_mobile_newsletter(ctx)
    assert "bağımsız bahis" in html
    assert find_orphan_numbers(html, payload) == []
