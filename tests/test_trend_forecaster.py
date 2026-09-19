"""tests/test_trend_forecaster.py: Trend ve yon tahmin motoru birim testleri."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.trend_forecaster import (
    FEATURE_COLUMNS,
    compute_indicators,
    TrendForecastingEngine,
    walk_forward_backtest,
)


def _generate_synthetic_ohlcv(days: int = 400) -> pd.DataFrame:
    """Sentetik deterministik OHLCV serisi."""
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=days, freq="B")
    
    # Trendli ve dalgali fiyat serisi
    t = np.linspace(0, 10, days)
    drift = 100.0 * np.exp(0.0015 * np.arange(days))
    wave = 15.0 * np.sin(t)
    noise = np.random.normal(0, 2.0, days)
    close = drift + wave + noise
    
    high = close + np.random.uniform(0.5, 2.0, days)
    low = close - np.random.uniform(0.5, 2.0, days)
    open_p = (high + low) / 2.0
    vol = np.random.uniform(1e6, 5e6, days)
    
    return pd.DataFrame({
        "Open": open_p,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": vol,
    }, index=dates)


def test_compute_indicators_shape_and_features():
    df = _generate_synthetic_ohlcv(300)
    feat_df = compute_indicators(df)
    
    for col in FEATURE_COLUMNS:
        assert col in feat_df.columns, f"{col} gostergesi eksik!"
    
    # 200 gunluk SMA nedeniyle ilk 200 bar NaN olabilir, sonraki barlar dolu olmali
    valid_slice = feat_df.iloc[210:]
    for col in FEATURE_COLUMNS:
        assert not valid_slice[col].isna().all(), f"{col} tamamen NaN!"


def test_trend_engine_fit_and_predict():
    df = _generate_synthetic_ohlcv(500)
    feat_df = compute_indicators(df)
    
    engine = TrendForecastingEngine(horizon=10, random_state=42)
    engine.fit(feat_df)
    
    assert engine.is_fitted
    assert len(engine.feature_importances_) == len(FEATURE_COLUMNS)
    
    pred = engine.predict_current(feat_df)
    assert "prob_up" in pred
    assert 0.0 <= pred["prob_up"] <= 1.0
    assert "trend_score" in pred
    assert -100 <= pred["trend_score"] <= 100
    assert pred["regime"] in [
        "STRONG_BULL", "MILD_BULL", "NEUTRAL",
        "CORRECTION_CHOPPY", "STRONG_BEAR", "OVERSOLD_REVERSAL"
    ]
    assert "recommended_stance" in pred
    assert "indicators" in pred


def test_trend_engine_unfitted_raises_error():
    engine = TrendForecastingEngine(horizon=10)
    df = _generate_synthetic_ohlcv(100)
    with pytest.raises(RuntimeError, match="Model henuz egitilmedi"):
        engine.predict_current(df)


def test_walk_forward_backtest_execution():
    df = _generate_synthetic_ohlcv(800)
    res = walk_forward_backtest(df, horizon=5, train_window=250, step=30)
    
    assert "samples_count" in res
    assert res["samples_count"] > 0
    assert "accuracy_pct" in res
    assert 0.0 <= res["accuracy_pct"] <= 100.0
    assert "strategy_cumulative_ret_pct" in res
    assert "strategy_sharpe" in res


def test_predict_market_regime():
    from core.trend_forecaster import predict_market_regime

    # 1. Test with synthetic dataframe (deep history)
    df_deep = _generate_synthetic_ohlcv(450)
    pred_deep = predict_market_regime(df_deep)
    assert "regime" in pred_deep
    assert "prob_up" in pred_deep
    assert pred_deep["regime"] in [
        "STRONG_BULL", "MILD_BULL", "NEUTRAL",
        "CORRECTION_CHOPPY", "STRONG_BEAR", "OVERSOLD_REVERSAL"
    ]

    # 2. Test with limited bars fallback
    df_limited = _generate_synthetic_ohlcv(200)
    pred_limited = predict_market_regime(df_limited)
    assert pred_limited["confidence"] == "heuristic_limited_bars"

    # 3. Test with list of dicts (short series fallback)
    short_rows = [{"close": 100 + i, "open": 100 + i, "high": 101 + i, "low": 99 + i, "volume": 1000} for i in range(30)]
    pred_short = predict_market_regime(short_rows)
    assert pred_short["regime"] == "MILD_BULL"
    assert pred_short["confidence"] == "heuristic_short_history"


