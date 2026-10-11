"""correlation_diagnostic: son 60 gunluk log getiriler uzerinden Pearson korelasyonu.

Onceden fiyat SEVIYELERI karsilastiriliyordu; ortak trendli iki seri getirileri
bagimsiz olsa da ~1 korelasyon verir (gunde ~6.900 sahte bayrak, 2026-10-10).

explicit_non_action: Otomatik eleme veya degistirme YAPILMAZ, yalnizca rapora
uyari eklenir.
"""
from __future__ import annotations

from core import db

CORRELATION_THRESHOLD = 0.85
WINDOW_DAYS = 60


def _pearson(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 10:
        return None
    a, b = a[-n:], b[-n:]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    denom = (var_a * var_b) ** 0.5
    if denom == 0:
        return None
    return cov / denom


def _log_returns(series: list[dict]) -> list[float]:
    import math
    closes = [p.get("adj_close") or p["close"] for p in series[-(WINDOW_DAYS + 1):]]
    return [math.log(b / a) for a, b in zip(closes, closes[1:]) if a and b and a > 0 and b > 0]


def compute_correlation_flags(as_of_date: str, price_series_by_ticker: dict[str, list[dict]]) -> list[dict]:
    tickers = list(price_series_by_ticker.keys())
    rets = {t: _log_returns(price_series_by_ticker[t]) for t in tickers}
    flags = []
    for i, ta in enumerate(tickers):
        for tb in tickers[i + 1:]:
            corr = _pearson(rets[ta], rets[tb])
            if corr is not None and corr > CORRELATION_THRESHOLD:
                flags.append({"as_of_date": as_of_date, "ticker_a": ta, "ticker_b": tb, "correlation_60d": corr})

    if flags:
        conn = db.get_connection()
        try:
            conn.executemany(
                """INSERT INTO correlation_flags (as_of_date, ticker_a, ticker_b, correlation_60d)
                   VALUES (:as_of_date, :ticker_a, :ticker_b, :correlation_60d)""",
                flags,
            )
            conn.commit()
        finally:
            conn.close()
    return flags


def effective_bets(price_series_by_ticker: dict[str, list[dict]]) -> dict:
    """Esit agirlikli sepette bagimsiz bahis sayisi: N / (1 + (N-1) * ortalama ciftli korelasyon).
    Bilgi amaclidir; portfoyu degistirmez."""
    tickers = list(price_series_by_ticker.keys())
    rets = {t: _log_returns(price_series_by_ticker[t]) for t in tickers}
    corrs = []
    for i, ta in enumerate(tickers):
        for tb in tickers[i + 1:]:
            c = _pearson(rets[ta], rets[tb])
            if c is not None:
                corrs.append(c)
    n = len(tickers)
    if n < 2 or not corrs:
        return {"n_holdings": n, "avg_pairwise_corr": None, "effective_n": None}
    rho = sum(corrs) / len(corrs)
    return {"n_holdings": n, "avg_pairwise_corr": round(rho, 3),
            "effective_n": round(n / (1 + (n - 1) * rho), 1)}
