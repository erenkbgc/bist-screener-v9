"""beta_adjusted_hurdle: yuksek beta'li hisselerin ayni sabit hurdle ile
sistematik olarak odullenmesini gostermek icin bilgi amacli ek metrik.

usage (spec): "hard_filter DEGIL. excess_over_hurdle_pct'in yaninda ek bilgi
olarak gosterilir." Bu yuzden scoring.hard_filters_all_buckets listesine
GIRMEZ (bkz. core/scoring.py ve tests/test_beta_hurdle.py).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core import db
from core.mock_data import mock_prices

_ERP_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "equity_risk_premium.yaml"


def load_equity_risk_premium_pct() -> float:
    with open(_ERP_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["equity_risk_premium_pct"]


def _daily_returns(closes: list[float]) -> list[float]:
    return [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]


def calculate_beta(stock_prices: list[dict], market_prices: list[dict]) -> float | None:
    """60-120 gunluk gunluk getiri serisi, XU100'e karsi regresyon egimi (OLS slope)."""
    n = min(len(stock_prices), len(market_prices))
    if n < 60:
        return None
    stock_closes = [p["close"] for p in stock_prices[-n:]]
    market_closes = [p["close"] for p in market_prices[-n:]]
    r_stock = _daily_returns(stock_closes)
    r_market = _daily_returns(market_closes)
    m = min(len(r_stock), len(r_market))
    if m < 59:
        return None
    r_stock, r_market = r_stock[-m:], r_market[-m:]
    mean_s = sum(r_stock) / m
    mean_m = sum(r_market) / m
    cov = sum((r_stock[i] - mean_s) * (r_market[i] - mean_m) for i in range(m)) / m
    var_m = sum((x - mean_m) ** 2 for x in r_market) / m
    if var_m == 0:
        return None
    return cov / var_m


def calculate_beta_adjusted_hurdle(as_of_date: str, ticker: str, stock_prices: list[dict],
                                     risk_free_annual_pct: float, expected_roi_pct: float) -> dict:
    market_prices = mock_prices("XU100_INDEX", as_of_date, days=140)
    beta = calculate_beta(stock_prices, market_prices)
    erp = load_equity_risk_premium_pct()

    if beta is None:
        row = {"as_of_date": as_of_date, "ticker": ticker, "beta_60_120d": None,
               "hurdle_rate_beta_adjusted_pct": None, "excess_over_beta_hurdle_pct": None}
    else:
        hurdle_beta_adj = risk_free_annual_pct + beta * erp
        row = {
            "as_of_date": as_of_date, "ticker": ticker, "beta_60_120d": beta,
            "hurdle_rate_beta_adjusted_pct": hurdle_beta_adj,
            "excess_over_beta_hurdle_pct": expected_roi_pct - hurdle_beta_adj,
        }

    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO beta_metrics (as_of_date, ticker, beta_60_120d,
               hurdle_rate_beta_adjusted_pct, excess_over_beta_hurdle_pct)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 beta_60_120d=excluded.beta_60_120d,
                 hurdle_rate_beta_adjusted_pct=excluded.hurdle_rate_beta_adjusted_pct,
                 excess_over_beta_hurdle_pct=excluded.excess_over_beta_hurdle_pct""",
            (row["as_of_date"], row["ticker"], row["beta_60_120d"],
             row["hurdle_rate_beta_adjusted_pct"], row["excess_over_beta_hurdle_pct"]),
        )
        conn.commit()
    finally:
        conn.close()
    return row
