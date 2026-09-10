"""correlation_diagnostic: son 60 gunluk kapanislar uzerinden Pearson korelasyonu.

explicit_non_action: Otomatik eleme veya degistirme YAPILMAZ, yalnizca rapora
uyari eklenir.
"""
from __future__ import annotations

from core import db

CORRELATION_THRESHOLD = 0.85


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


def compute_correlation_flags(as_of_date: str, price_series_by_ticker: dict[str, list[dict]]) -> list[dict]:
    tickers = list(price_series_by_ticker.keys())
    closes = {t: [p["close"] for p in price_series_by_ticker[t][-60:]] for t in tickers}
    flags = []
    for i, ta in enumerate(tickers):
        for tb in tickers[i + 1:]:
            corr = _pearson(closes[ta], closes[tb])
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
