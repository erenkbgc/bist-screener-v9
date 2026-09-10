"""fundamentals: bist-data'dan rasyo/temel verileri ceker, basis_guard uygular,
fcf_yield_usd hesaplar, point_in_time alanlarini doldurur.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import db, basis_guard
from bist_mcp import server as bist_mcp
from macro_mcp import server as macro_mcp


def fetch_and_store_fundamentals(as_of_date: str, universe_rows: list[dict]) -> list[dict]:
    macro = macro_mcp.get_macro_snapshot(as_of_date)
    usdtry_spot = macro.get("usdtry_spot")

    period_end = _quarter_end_before(as_of_date)
    published_at = period_end  # basitlestirilmis mock varsayimi: bilanco donem sonunda aciklanir
    available_at = published_at
    effective_at = published_at
    ingested_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for u in universe_rows:
        ticker = u["ticker"]
        reporting_basis = basis_guard.resolve_reporting_basis(u["regulator"], period_end)
        f = bist_mcp.get_fundamentals(ticker, as_of_date, u["regulator"], u["ratio_profile"])
        f["reporting_basis"] = reporting_basis  # basis_guard'in kurali MCP'nin donusunu ezer

        fcf_yield_usd = None
        null_reason = None
        if reporting_basis == "unknown":
            null_reason = "unknown_reporting_basis"
        elif usdtry_spot and u["market_cap"] and f.get("fcf_ttm") is not None:
            fcf_yield_usd = f["fcf_ttm"] / (u["market_cap"] / usdtry_spot)
        elif f.get("fcf_ttm") is None:
            null_reason = "missing_fcf"

        row = {
            "as_of_date": as_of_date, "ticker": ticker, "period_end": period_end,
            "reporting_basis": reporting_basis,
            "pe": f["pe"], "pb": f["pb"], "ev_ebitda": f["ev_ebitda"], "ev_sales": f["ev_sales"],
            "roe": f["roe"], "eps_ttm": f["eps_ttm"], "ebitda_ttm": f["ebitda_ttm"],
            "net_debt": f["net_debt"], "nav_discount": f["nav_discount"],
            "dividend_per_share_ttm": f["dividend_per_share_ttm"], "payout_ratio": f["payout_ratio"],
            "fcf_ttm": f["fcf_ttm"], "fcf_yield_usd": fcf_yield_usd, "null_reason": null_reason,
            "source": "bist-data (mock)", "published_at": published_at, "available_at": available_at,
            "effective_at": effective_at, "ingested_at": ingested_at,
            # skorlama disi ham alanlar, sonraki motorlar icin bellekte tasinir (DB'ye yazilmaz)
            "_raw": f,
        }
        rows.append(row)

    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO fundamentals
               (as_of_date, ticker, period_end, reporting_basis, pe, pb, ev_ebitda, ev_sales, roe,
                eps_ttm, ebitda_ttm, net_debt, nav_discount, dividend_per_share_ttm, payout_ratio,
                fcf_ttm, fcf_yield_usd, null_reason, source, published_at, available_at, effective_at, ingested_at)
               VALUES (:as_of_date, :ticker, :period_end, :reporting_basis, :pe, :pb, :ev_ebitda, :ev_sales, :roe,
                       :eps_ttm, :ebitda_ttm, :net_debt, :nav_discount, :dividend_per_share_ttm, :payout_ratio,
                       :fcf_ttm, :fcf_yield_usd, :null_reason, :source, :published_at, :available_at, :effective_at, :ingested_at)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 reporting_basis=excluded.reporting_basis, pe=excluded.pe, pb=excluded.pb,
                 ev_ebitda=excluded.ev_ebitda, ev_sales=excluded.ev_sales, roe=excluded.roe,
                 fcf_yield_usd=excluded.fcf_yield_usd, null_reason=excluded.null_reason""",
            [{k: v for k, v in r.items() if k != "_raw"} for r in rows],
        )
        conn.commit()
    finally:
        conn.close()

    return rows


def _quarter_end_before(as_of_date: str) -> str:
    d = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    quarter_month = ((d.month - 1) // 3) * 3 + 1
    q_start = d.replace(month=quarter_month, day=1)
    q_end = q_start - timedelta(days=1)
    return q_end.isoformat()
