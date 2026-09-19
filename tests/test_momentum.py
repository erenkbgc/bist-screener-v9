"""tests/test_momentum.py: 12-1 Ay Momentum, Trend Puruzsuzlugu ve BIST 100 R-S testleri."""
from __future__ import annotations

import numpy as np
import pytest

from core.momentum import (
    calculate_12_1_momentum,
    calculate_relative_strength,
    calculate_trend_smoothness,
    compute_momentum_metrics,
)


def test_calculate_12_1_momentum_sufficient_data():
    # 252 gunluk duzenli artan fiyat serisi (100 TL -> 200 TL)
    closes = np.linspace(100.0, 200.0, 252)
    mom = calculate_12_1_momentum(closes)
    assert mom is not None
    # t-21 gunluk fiyat ~183 TL, 183 / 100 - 1 = +83%
    assert 75.0 < mom < 95.0


def test_calculate_12_1_momentum_insufficient_data():
    # 30 bar: momentum hesaplanamaz, None donmeli
    closes = np.linspace(100.0, 110.0, 30)
    mom = calculate_12_1_momentum(closes)
    assert mom is None


def test_calculate_trend_smoothness_perfect_uptrend():
    # Puruzsuz eksponansiyel yukselis (ln(P) lineer)
    t = np.arange(120)
    closes = 50.0 * np.exp(0.01 * t)
    r2 = calculate_trend_smoothness(closes, window=120)
    assert r2 is not None
    assert r2 > 0.98  # neredeyse mukemmel R^2


def test_calculate_trend_smoothness_downtrend():
    # Duzenli dusen trend: negatif R^2 donmeli
    t = np.arange(120)
    closes = 100.0 * np.exp(-0.01 * t)
    r2 = calculate_trend_smoothness(closes, window=120)
    assert r2 is not None
    assert r2 < -0.95


def test_calculate_trend_smoothness_noisy():
    # Cok gurultulu / yatay testere piyasa
    np.random.seed(42)
    closes = 100.0 + np.random.normal(0, 10, 120)
    r2 = calculate_trend_smoothness(closes, window=120)
    assert r2 is not None
    assert abs(r2) < 0.35


def test_calculate_relative_strength():
    stock = [100.0] * 30 + [120.0] * 30  # +20%
    index = [100.0] * 30 + [105.0] * 30  # +5%
    rs = calculate_relative_strength(stock, index, window=60)
    assert rs is not None
    # 20% - 5% = +15%
    assert abs(rs - 15.0) < 0.1


def test_compute_momentum_metrics_end_to_end():
    # Dict formatinda fiyat serisi
    stock_prices = [{"close": 50.0 + i * 0.5} for i in range(150)]
    index_prices = [{"close": 100.0 + i * 0.2} for i in range(150)]

    metrics = compute_momentum_metrics(stock_prices, index_prices)
    assert "mom_12_1_pct" in metrics
    assert "trend_smoothness_r2" in metrics
    assert "rs_xu100_60d_pct" in metrics
    assert "momentum_score" in metrics
    assert 0.0 <= metrics["momentum_score"] <= 100.0
    # Guclu yukseliste momentum skoru ortalama 50'nin belirgin ustunde olmali
    assert metrics["momentum_score"] > 60.0
