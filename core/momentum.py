"""core/momentum.py: 12-1 Ay Capraz Kesitsel Momentum ve Trend Puruzsuzluk Modulu.

Quant Level-Up Faz 2:
1. 12-1 Ay Momentum (Jegadeesh & Titman 1993, Carhart 1997):
   Son 1 yillik getiriden son 1 ay (21 is gunu) cikarilir. Boylece kisa vadeli
   tersine donus (mean-reversion) gurultusu elenir ve ana kurumsal trend olculur.
2. Trend Puruzsuzlugu (R^2 Trend Smoothness):
   ln(fiyat) uzerine lineer regresyon egimi ve determinasyon katsayisi (R^2).
   Sert spekulatif sicramalari degil, istikrarli yukselen hisseleri odullendirir.
3. BIST 100 Goreli Guc (Relative Strength vs. XU100):
   Hissenin endekse karsi 60 gunluk fazla getirisi (alpha).
"""
from __future__ import annotations

import numpy as np


def calculate_12_1_momentum(closes: list[float] | np.ndarray) -> float | None:
    """12-1 Ay momentumu hesaplar (P_{t-21} / P_{t-252} - 1).
    
    closes: Kronolojik kapanis serisi (en eski -> en yeni).
    """
    if closes is None or len(closes) < 40:
        return None
    arr = np.array(closes, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 40:
        return None

    # Son 21 gunu (1 ay) cikar
    p_end = arr[-21] if len(arr) >= 21 else arr[-1]
    
    # 252 gunluk baz (1 yil) veya mevcut en eski baz
    lookback = min(len(arr), 252)
    p_start = arr[-lookback]

    if p_start <= 0:
        return None

    raw_ret = float(p_end / p_start - 1.0)

    # Eger 252 gunden az veri varsa yilliklandir (annualize)
    effective_days = lookback - 21
    if effective_days > 20 and lookback < 252:
        annualized_ret = float(((1.0 + raw_ret) ** (231.0 / effective_days)) - 1.0)
        return round(annualized_ret * 100.0, 2)

    return round(raw_ret * 100.0, 2)


def calculate_trend_smoothness(closes: list[float] | np.ndarray, window: int = 120) -> float | None:
    """ln(fiyat) uzerine OLS regresyonu ile trend puruzsuzlugunu (R^2) hesaplar.
    
    Egim pozitifse +R^2 (0 ile +1 arasi), negatifse -R^2 (-1 ile 0 arasi) doner.
    """
    if closes is None or len(closes) < 20:
        return None
    arr = np.array(closes[-window:], dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) < 20 or np.any(arr <= 0):
        return None

    y = np.log(arr)
    x = np.arange(len(y), dtype=float)

    # OLS regresyon: y = a + b*x
    n = len(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    ss_xx = np.sum((x - x_mean) ** 2)
    if ss_xx < 1e-8:
        return 0.0

    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    slope = ss_xy / ss_xx

    y_pred = y_mean + slope * (x - x_mean)
    ss_tot = np.sum((y - y_mean) ** 2)
    if ss_tot < 1e-8:
        return 0.0

    ss_res = np.sum((y - y_pred) ** 2)
    r2 = max(0.0, min(1.0, 1.0 - (ss_res / ss_tot)))

    signed_r2 = float(r2 if slope >= 0 else -r2)
    return round(signed_r2, 3)


def calculate_relative_strength(
    stock_closes: list[float] | np.ndarray,
    index_closes: list[float] | np.ndarray,
    window: int = 60,
) -> float | None:
    """Hissenin endekse (XU100) gore window gunluk fazla getirisini (%) hesaplar."""
    if stock_closes is None or index_closes is None:
        return None
    s_arr = np.array(stock_closes, dtype=float)
    i_arr = np.array(index_closes, dtype=float)
    if len(s_arr) < window or len(i_arr) < window:
        # Mevcut en kisa uzunluk
        min_len = min(len(s_arr), len(i_arr))
        if min_len < 15:
            return None
        window = min_len

    s_ret = (s_arr[-1] / s_arr[-window]) - 1.0
    i_ret = (i_arr[-1] / i_arr[-window]) - 1.0

    excess_ret = float(s_ret - i_ret)
    return round(excess_ret * 100.0, 2)


def compute_momentum_metrics(
    stock_prices: list[dict] | list[float],
    index_prices: list[dict] | list[float] | None = None,
) -> dict:
    """Tek bir hissenin tum momentum bilesenlerini ve 0-100 arasi normalize skorunu uretir."""
    if isinstance(stock_prices, list) and stock_prices and isinstance(stock_prices[0], dict):
        s_closes = [float(p["close"]) for p in stock_prices if p.get("close") is not None]
    else:
        s_closes = list(stock_prices) if stock_prices else []

    if index_prices and isinstance(index_prices[0], dict):
        i_closes = [float(p["close"]) for p in index_prices if p.get("close") is not None]
    elif index_prices:
        i_closes = list(index_prices)
    else:
        i_closes = None

    mom_12_1 = calculate_12_1_momentum(s_closes)
    smoothness = calculate_trend_smoothness(s_closes, window=120)
    rs_60 = calculate_relative_strength(s_closes, i_closes, window=60) if i_closes else None

    # Bilesik momentum skoru (0 - 100 arasi puan)
    # Temel: 50 puan
    # mom_12_1 katkisi: %50 getiri -> +15 puan, -%30 -> -15 puan (clip -30..+30)
    # smoothness katkisi: R^2 +1.0 -> +15 puan, -1.0 -> -15 puan
    # rs_60 katkisi: +%20 alpha -> +10 puan, -%20 -> -10 puan
    base = 50.0
    score = base

    if mom_12_1 is not None:
        score += np.clip(mom_12_1 * 0.3, -25.0, 25.0)

    if smoothness is not None:
        score += smoothness * 15.0  # smoothness -1..+1

    if rs_60 is not None:
        score += np.clip(rs_60 * 0.5, -15.0, 15.0)

    score = float(np.clip(score, 0.0, 100.0))

    return {
        "mom_12_1_pct": mom_12_1,
        "trend_smoothness_r2": smoothness,
        "rs_xu100_60d_pct": rs_60,
        "momentum_score": round(score, 1),
    }
