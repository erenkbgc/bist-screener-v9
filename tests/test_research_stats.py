"""core/research_stats: OLS-NW, DSR, PBO, bootstrap ve Brinson kontrolleri."""
import numpy as np
import pandas as pd
import pytest

from core import research_stats as rs


def test_ols_nw_recovers_coefficients():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(size=400))
    y = 0.5 + 2.0 * x + rng.normal(scale=0.1, size=400)
    out = rs.ols_nw(y, pd.DataFrame({"x": x}))
    assert out["coef"]["alpha"] == pytest.approx(0.5, abs=0.02)
    assert out["coef"]["x"] == pytest.approx(2.0, abs=0.02)
    assert out["t"]["x"] > 50 and out["r2"] > 0.99


def test_brinson_splits_allocation_and_selection():
    m = pd.DataFrame({"ticker": list("ABCD"), "sector": ["X", "X", "Y", "Y"], "ret": [0.10, 0.00, 0.02, 0.02]})
    alloc, sel = rs.brinson(m, {"A", "C"})
    # portfoy agirliklari evrenle ayni -> dagilim 0; X icinde A sektorun 5 puan ustunde
    assert alloc == pytest.approx(0.0)
    assert sel == pytest.approx(0.5 * 0.05)
    # toplam = portfoy - evren
    assert alloc + sel == pytest.approx((0.10 + 0.02) / 2 - 0.035)


def test_dsr_drops_with_more_trials():
    rng = np.random.default_rng(1)
    r = rng.normal(0.01, 0.03, size=160)
    one = rs.deflated_sharpe(r, 1, 0.01)
    many = rs.deflated_sharpe(r, 200, 0.01)
    assert one["sr0"] == 0.0 and many["sr0"] > 0
    assert many["dsr"] < one["dsr"]


def test_pbo_high_for_pure_noise_low_for_dominant_variant():
    rng = np.random.default_rng(2)
    noise = pd.DataFrame(rng.normal(size=(160, 20)))
    assert rs.pbo_cscv(noise, n_blocks=8)["pbo"] > 0.3
    strong = noise.copy()
    strong[0] += 1.0
    assert rs.pbo_cscv(strong, n_blocks=8)["pbo"] < 0.05


def test_stationary_bootstrap_ci_covers_mean():
    rng = np.random.default_rng(3)
    x = rng.normal(0.005, 0.02, size=120)
    lo, hi = rs.stationary_bootstrap_ci(x, reps=500)
    assert lo < 1200 * x.mean() < hi
