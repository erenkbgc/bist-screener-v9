"""ownership_quality: MKK aylik yatirimci verisine dayali sahiplik kalitesi.

Spec: ownership_quality.risk_rules, P9_retail_concentration.
"""
from __future__ import annotations

from statistics import mean, pstdev

from core import db
from bist_mcp import server as bist_mcp

PENALTY_FACTOR = 0.70  # "Skoru yuzde 30 cezalandir" -> final carpani 0.70


def _return_20d(prices: list[dict]) -> float | None:
    if len(prices) < 21:
        return None
    closes = [p["close"] for p in prices]
    return (closes[-1] / closes[-21] - 1) * 100


def fetch_ownership(as_of_date: str, ticker: str, prices: list[dict]) -> dict:
    own = bist_mcp.get_ownership(ticker, as_of_date)
    ret20 = _return_20d(prices)

    # Canli veri modunda retail_pct/investor_count_change_1m MKK/TSPB kaynakli
    # olup ucretsiz API ile cekilemiyor (bkz. core/live_data.py::live_ownership);
    # bu durumda None doner ve asagidaki kurallar GUVENLE atlanir (sahte
    # varsayim uretilmez, sadece ilgili risk bayragi hesaplanamaz).
    retail_pct = own["retail_pct"]
    free_float_pct = own["free_float_pct"]
    investor_count_change_1m = own["investor_count_change_1m"]

    short_term_rejected = bool(retail_pct is not None and retail_pct > 80
                                and ret20 is not None and ret20 > 30)
    remove_candidate = bool(free_float_pct is not None and free_float_pct < 15)
    penalize = bool(investor_count_change_1m is not None and investor_count_change_1m > 50
                     and retail_pct is not None and retail_pct > 70)

    row = {
        "as_of_date": as_of_date, "ticker": ticker, "investor_count": own["investor_count"],
        "investor_count_change_1m": own["investor_count_change_1m"], "retail_pct": own["retail_pct"],
        "institutional_pct": own["institutional_pct"], "free_float_pct": own["free_float_pct"],
        "foreign_pct": own["foreign_pct"],
        "_short_term_rejected": short_term_rejected, "_remove_candidate": remove_candidate,
        "_penalize": penalize,
    }

    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO ownership (as_of_date, ticker, investor_count, investor_count_change_1m,
               retail_pct, institutional_pct, free_float_pct, foreign_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 investor_count=excluded.investor_count,
                 investor_count_change_1m=excluded.investor_count_change_1m,
                 retail_pct=excluded.retail_pct, institutional_pct=excluded.institutional_pct,
                 free_float_pct=excluded.free_float_pct, foreign_pct=excluded.foreign_pct""",
            (as_of_date, ticker, own["investor_count"], own["investor_count_change_1m"],
             own["retail_pct"], own["institutional_pct"], own["free_float_pct"], own["foreign_pct"]),
        )
        conn.commit()
    finally:
        conn.close()

    return row


def compute_ownership_z(candidate: dict, population: list[dict]) -> float:
    """Kesitsel z-skor: yuksek institutional_pct + yuksek free_float, dusuk retail_pct iyi kabul edilir.

    Canli veri modunda institutional_pct/retail_pct None olabilir (bkz.
    core/live_data.py::live_ownership); bu durumda o bilesen 0 katkida
    bulunur (free_float_pct her zaman gercek ve mevcut kalir)."""
    def raw(o):
        institutional = o.get("institutional_pct") or 0.0
        free_float = o.get("free_float_pct") or 0.0
        retail = o.get("retail_pct") or 0.0
        return institutional + free_float - retail

    pool = [raw(o) for o in population]
    if len(pool) < 2:
        return 0.0
    mu, sigma = mean(pool), pstdev(pool)
    if sigma == 0:
        return 0.0
    z = (raw(candidate) - mu) / sigma
    if candidate.get("_penalize"):
        z *= PENALTY_FACTOR
    return z
