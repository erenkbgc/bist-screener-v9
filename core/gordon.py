"""gordon_growth_reference: deneysel, ana karara girmeyen temettu iskonto modeli.

hard_constraints (spec): final_score'a ve hard_filters'a hicbir bicimde girmez;
discount_rate - g <= 0 ise hesaplanmaz, null_reason='unstable_denominator'.
output_format: Tek sayi asla gosterilmez, en az 3 senaryoli aralik.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core import db

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "equity_risk_premium.yaml"
DISCOUNT_SHOCK_PCT = 1.0  # base +/- 100bp
MIN_DIVIDEND_STREAK_YEARS = 3  # "Son 5 yilin en az 3'unde temettu odemis olmali" icin proxy


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_eligible(dividend_streak_years: int, passes_sustainability: bool) -> tuple[bool, str | None]:
    if dividend_streak_years < MIN_DIVIDEND_STREAK_YEARS:
        return False, "dividend_history_insufficient"
    if not passes_sustainability:
        return False, "dividend_not_sustainable"
    return True, None


def _fair_value(dividend_per_share: float, g: float, discount_rate_pct: float) -> float | None:
    denom = (discount_rate_pct - g) / 100
    if denom <= 0:
        return None
    return dividend_per_share * (1 + g / 100) / denom


def calculate_gordon_reference(as_of_date: str, ticker: str, dividend_per_share: float | None,
                                 risk_free_annual_pct: float,
                                 dividend_streak_years: int, passes_sustainability: bool) -> dict:
    cfg = _load_config()
    eligible, reason = is_eligible(dividend_streak_years, passes_sustainability)

    if not eligible or dividend_per_share is None or dividend_per_share <= 0:
        row = {"as_of_date": as_of_date, "ticker": ticker, "dividend_per_share": dividend_per_share,
               "discount_rate_low": None, "discount_rate_base": None, "discount_rate_high": None,
               "fair_value_low": None, "fair_value_high": None,
               "null_reason": reason or "no_dividend"}
    else:
        g = cfg["tcmb_long_term_inflation_target_pct"]
        discount_base = risk_free_annual_pct + cfg["equity_risk_premium_pct"]
        discount_low = discount_base - DISCOUNT_SHOCK_PCT
        discount_high = discount_base + DISCOUNT_SHOCK_PCT

        fv_low_scenario = _fair_value(dividend_per_share, g, discount_high)  # yuksek iskonto -> dusuk deger
        fv_base_scenario = _fair_value(dividend_per_share, g, discount_base)
        fv_high_scenario = _fair_value(dividend_per_share, g, discount_low)  # dusuk iskonto -> yuksek deger

        scenarios = [v for v in (fv_low_scenario, fv_base_scenario, fv_high_scenario) if v is not None]
        if not scenarios:
            row = {"as_of_date": as_of_date, "ticker": ticker, "dividend_per_share": dividend_per_share,
                   "discount_rate_low": discount_low, "discount_rate_base": discount_base,
                   "discount_rate_high": discount_high, "fair_value_low": None, "fair_value_high": None,
                   "null_reason": "unstable_denominator"}
        else:
            row = {
                "as_of_date": as_of_date, "ticker": ticker, "dividend_per_share": dividend_per_share,
                "discount_rate_low": discount_low, "discount_rate_base": discount_base,
                "discount_rate_high": discount_high,
                "fair_value_low": min(scenarios), "fair_value_high": max(scenarios),
                "null_reason": None,
            }

    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO gordon_reference (as_of_date, ticker, dividend_per_share,
               discount_rate_low, discount_rate_base, discount_rate_high,
               fair_value_low, fair_value_high, null_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 dividend_per_share=excluded.dividend_per_share,
                 discount_rate_low=excluded.discount_rate_low,
                 discount_rate_base=excluded.discount_rate_base,
                 discount_rate_high=excluded.discount_rate_high,
                 fair_value_low=excluded.fair_value_low,
                 fair_value_high=excluded.fair_value_high,
                 null_reason=excluded.null_reason""",
            (row["as_of_date"], row["ticker"], row["dividend_per_share"], row["discount_rate_low"],
             row["discount_rate_base"], row["discount_rate_high"], row["fair_value_low"],
             row["fair_value_high"], row["null_reason"]),
        )
        conn.commit()
    finally:
        conn.close()
    return row
