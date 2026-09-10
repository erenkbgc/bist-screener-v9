"""earnings_quality_sloan: tahakkuk orani, PEER GRUBU ICI kesitsel persentil (mutlak esik degil).

Spec: earnings_quality_sloan. scoring_impact: final_score'a girmez, hard_filter degildir.
"""
from __future__ import annotations

from core import db, basis_guard
from core.ranking import percentile_rank
from bist_mcp import server as bist_mcp

TOP_DECILE_THRESHOLD = 0.90  # persentilin ust ondalik dilimi (en yuksek tahakkuk = en supheli)


def calculate_earnings_quality(as_of_date: str, universe_rows: list[dict], fundamentals_by_ticker: dict) -> list[dict]:
    raw_ratios: dict[str, dict] = {}
    for u in universe_rows:
        ticker = u["ticker"]
        fnd = fundamentals_by_ticker.get(ticker)
        if not fnd or fnd["reporting_basis"] == "unknown":
            continue
        if fnd.get("null_reason") == "basis_break":
            continue
        pe = fnd["_raw"]["pe"] if "_raw" in fnd else fnd.get("pe")
        eps = fnd["_raw"]["eps_ttm"] if "_raw" in fnd else fnd.get("eps_ttm")
        market_cap = u["market_cap"]
        if not pe or pe == 0:
            continue
        net_income_ttm = market_cap / pe  # earnings-yield esdegeri, hisse sayisina gerek kalmadan
        cf = bist_mcp.get_cashflow_for_sloan(ticker, as_of_date, net_income_ttm)
        avg_assets = cf["average_total_assets"]
        if not avg_assets:
            continue
        ratio = (net_income_ttm - cf["operating_cashflow_ttm"]) / avg_assets
        raw_ratios[ticker] = {
            "ratio": ratio, "reporting_basis": fnd["reporting_basis"],
            "ratio_profile": u["ratio_profile"],
        }

    rows = []
    for u in universe_rows:
        ticker = u["ticker"]
        if ticker not in raw_ratios:
            fnd = fundamentals_by_ticker.get(ticker)
            null_reason = "basis_break" if (fnd and fnd.get("reporting_basis") == "unknown") else "not_computable"
            rows.append({"as_of_date": as_of_date, "ticker": ticker, "sloan_accrual_ratio": None,
                         "peer_percentile": None, "elevated_risk_flag": 0, "null_reason": null_reason})
            continue

        this = raw_ratios[ticker]
        peer_pool = [v["ratio"] for t, v in raw_ratios.items()
                     if t != ticker and v["reporting_basis"] == this["reporting_basis"]
                     and v["ratio_profile"] == this["ratio_profile"]]
        percentile = percentile_rank(this["ratio"], peer_pool) if peer_pool else 0.5
        elevated = percentile >= TOP_DECILE_THRESHOLD
        rows.append({
            "as_of_date": as_of_date, "ticker": ticker, "sloan_accrual_ratio": this["ratio"],
            "peer_percentile": percentile, "elevated_risk_flag": int(elevated), "null_reason": None,
        })

    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO earnings_quality (as_of_date, ticker, sloan_accrual_ratio, peer_percentile,
               elevated_risk_flag, null_reason)
               VALUES (:as_of_date, :ticker, :sloan_accrual_ratio, :peer_percentile, :elevated_risk_flag, :null_reason)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 sloan_accrual_ratio=excluded.sloan_accrual_ratio, peer_percentile=excluded.peer_percentile,
                 elevated_risk_flag=excluded.elevated_risk_flag, null_reason=excluded.null_reason""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return rows
