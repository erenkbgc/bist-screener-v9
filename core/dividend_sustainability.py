"""dividend_sustainability_engine: 'gecmiste temettu odedi' kapisini
'bu temettu surdurulebilir mi' sorusuyla siklastirir.

Bu bir hard_filter DEGIL, yalnizca gordon_growth_reference'in bir on-kosuludur.
"""
from __future__ import annotations

from core import db
from bist_mcp import server as bist_mcp

HIGH_LEVERAGE_NET_DEBT_EBITDA = 4.0


def check_dividend_sustainability(as_of_date: str, ticker: str, fundamentals_row: dict) -> dict:
    raw = fundamentals_row.get("_raw", fundamentals_row)
    fcf_ttm = fundamentals_row["fcf_ttm"]
    payout_ratio = fundamentals_row["payout_ratio"]
    pe = raw.get("pe")
    market_cap_hint = fundamentals_row.get("market_cap")

    hist = bist_mcp.get_dividend_history(ticker, as_of_date)
    streak = hist["dividend_streak_years"]
    trend = hist["payout_ratio_trend_3p"]

    # net_income_ttm ~ market_cap / pe (bkz. core/sloan.py'deki ayni yaklasim)
    net_income_ttm = (market_cap_hint / pe) if (market_cap_hint and pe) else None
    dividend_paid_ttm = (payout_ratio * net_income_ttm) if (payout_ratio and net_income_ttm) else 0.0

    if fcf_ttm is None:
        null_reason = "missing_fcf"
        coverage = None
        passes = False
    elif fcf_ttm <= 0:
        coverage = None
        null_reason = None
        passes = False  # negatif FCF -> dikkat bayragi, surdurulemez kabul edilir
    else:
        coverage = dividend_paid_ttm / fcf_ttm
        null_reason = None
        net_debt_ebitda = (fundamentals_row["net_debt"] / raw["ebitda_ttm"]) if raw.get("ebitda_ttm") else None
        high_leverage_risk = (net_debt_ebitda is not None and net_debt_ebitda > HIGH_LEVERAGE_NET_DEBT_EBITDA
                               and trend == "artiyor")
        passes = coverage >= 1 and not high_leverage_risk

    row = {
        "as_of_date": as_of_date, "ticker": ticker, "fcf_payout_coverage": coverage,
        "dividend_streak_years": streak, "payout_ratio_trend_3p": trend,
        "passes_sustainability": int(bool(passes)), "null_reason": null_reason,
    }

    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO dividend_sustainability (as_of_date, ticker, fcf_payout_coverage,
               dividend_streak_years, payout_ratio_trend_3p, passes_sustainability, null_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 fcf_payout_coverage=excluded.fcf_payout_coverage,
                 dividend_streak_years=excluded.dividend_streak_years,
                 payout_ratio_trend_3p=excluded.payout_ratio_trend_3p,
                 passes_sustainability=excluded.passes_sustainability,
                 null_reason=excluded.null_reason""",
            (row["as_of_date"], row["ticker"], row["fcf_payout_coverage"], row["dividend_streak_years"],
             row["payout_ratio_trend_3p"], row["passes_sustainability"], row["null_reason"]),
        )
        conn.commit()
    finally:
        conn.close()
    return row
