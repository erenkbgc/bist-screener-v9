"""tests/test_weight_optimizer.py: Sifir manuel agirlik matematiksel testleri."""
import numpy as np
import pandas as pd
import pytest

from core.weight_optimizer import (
    derive_scenario_probabilities,
    compute_harmonic_mean,
    optimize_ensemble_weights,
    optimize_valuation_weights,
    optimize_factor_weights,
    calibrate_volatility_cone_and_convergence,
)


def test_derive_scenario_probabilities_trinomial_sum():
    for p in [0.0, 0.1, 0.35, 0.50, 0.72, 0.85, 1.0]:
        probs = derive_scenario_probabilities(p)
        tot = sum(probs.values())
        assert abs(tot - 1.0) < 1e-4, f"Olasiliklar toplami 1.0 olmali, p={p}, tot={tot}"
        assert 0.0 <= probs["bull"] <= 1.0
        assert 0.0 <= probs["base"] <= 1.0
        assert 0.0 <= probs["bear"] <= 1.0


def test_derive_scenario_probabilities_behavior():
    # p=0.5 -> tam simetrik merkezcil dagilim
    neutral = derive_scenario_probabilities(0.5)
    assert neutral["bull"] == 0.25
    assert neutral["base"] == 0.50
    assert neutral["bear"] == 0.25

    # p=0.8 -> boga agirlikli
    bullish = derive_scenario_probabilities(0.8)
    assert bullish["bull"] > bullish["bear"]
    assert bullish["bull"] == 0.64
    assert bullish["bear"] == 0.04

    # p=0.2 -> ayi agirlikli
    bearish = derive_scenario_probabilities(0.2)
    assert bearish["bear"] > bearish["bull"]
    assert bearish["bear"] == 0.64
    assert bearish["bull"] == 0.04


def test_compute_harmonic_mean():
    # Eşit değerlerde harmonik ortalama o değere eşittir
    vals = [10.0, 10.0, 10.0, 10.0]
    assert abs(compute_harmonic_mean(vals) - 10.0) < 1e-6

    # 2 ve 6'nın harmonik ortalaması 2 / (1/2 + 1/6) = 2 / (4/6) = 3.0
    assert abs(compute_harmonic_mean([2.0, 6.0]) - 3.0) < 1e-6

    # Negatif veya sifir degerler filtrelenir
    assert abs(compute_harmonic_mean([2.0, 6.0, -5.0, 0.0]) - 3.0) < 1e-6

    # Bos veya gecersiz girdi None doner
    assert compute_harmonic_mean([]) is None
    assert compute_harmonic_mean([-2.0, 0.0]) is None


def test_optimize_ensemble_weights():
    y_true = np.array([1, 1, 1, 0, 0, 0, 1, 1, 0, 0])
    # Model 1 (RF) mukemmel tahmin yapiyor
    p_rf = np.array([0.9, 0.85, 0.95, 0.1, 0.05, 0.15, 0.88, 0.92, 0.12, 0.08])
    # Model 2 (LR) rastgele tahmin yapiyor
    p_lr = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    w_rf, w_lr = optimize_ensemble_weights(y_true, p_rf, p_lr)
    assert abs((w_rf + w_lr) - 1.0) < 1e-4
    assert w_rf > w_lr, "Ustun olan model 1 daha yuksek agirlik almali"
    assert w_rf > 0.80


def test_optimize_valuation_weights():
    # 3 bacakli degerleme sentetik tahmini
    np.random.seed(42)
    actual_prices = [100.0 + i for i in range(25)]
    # Leg 1: cok yakin (dusuk hata)
    leg1 = [p + np.random.normal(0, 2) for p in actual_prices]
    # Leg 2: cok hatali
    leg2 = [p + np.random.normal(0, 20) for p in actual_prices]
    # Leg 3: orta derece hatali
    leg3 = [p + np.random.normal(0, 8) for p in actual_prices]

    val_dict = {"leg1": leg1, "leg2": leg2, "leg3": leg3}
    weights = optimize_valuation_weights(val_dict, actual_prices)

    assert abs(sum(weights.values()) - 1.0) < 1e-3
    assert weights["leg1"] > weights["leg2"], "Hatasi en kucuk bacak en yuksek agirligi almali"


def test_optimize_factor_weights():
    # Faktör 1 getiriyle cok yuksek sirali pozitif korelasyona sahip
    factor1 = list(range(20))
    factor2 = list(reversed(range(20)))
    forward_returns = pd.Series([float(x) for x in range(20)])
    factor_df = pd.DataFrame({"f1": factor1, "f2": factor2})

    weights = optimize_factor_weights(factor_df, forward_returns)
    assert abs(sum(weights.values()) - 1.0) < 1e-3
    assert weights["f1"] > weights["f2"]


def test_calibrate_volatility_cone_and_convergence():
    # 300 gunluk sentetik fiyat serisi
    dates = pd.date_range("2024-01-01", periods=300, freq="B")
    prices = pd.Series(100.0 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, 300))), index=dates)

    z_star, alpha_star = calibrate_volatility_cone_and_convergence(prices, horizon_days=60)
    assert 1.0 <= z_star <= 3.0
    assert 0.1 <= alpha_star <= 0.8
