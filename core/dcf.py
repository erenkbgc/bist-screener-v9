"""dcf_reference: deneysel, ana karara girmeyen serbest nakit akisi (FCF)
iskonto modeli.

Spec: valuation_engine_v2_dcf_addon (bist_screener_v10_roadmap.json::modules).
core/gordon.py (temettu iskonto modeli) ile AYNI mimari desende: final_score'a
ve hard_filters'a hicbir bicimde girmez, tek sayi ASLA gosterilmez, en az 3
senaryolu (dusuk/baz/yuksek) bir aralik olarak sunulur.

priors_are_disclosed: revenue_growth_scenarios (GROWTH_*_PCT) KEYFI
VARSAYIMDIR, gecmis veriyle kalibre edilmemistir -- rapor altbilgisinde
"DENENMEMIS VARSAYIM" olarak ifsa edilir (bkz. report/templates/newsletter.html.j2).
terminal_growth_g, gordon.py ile AYNI kaynagi (TCMB uzun donem enflasyon
hedefi) kullanir, tutarlilik icin.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core import db

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "equity_risk_premium.yaml"

# KEYFI VARSAYIM (priors_are_disclosed): FCF'nin bir sonraki yil bu oranlarda
# buyuyecegi varsayimi, hicbir gecmis veriyle kalibre edilmemistir.
GROWTH_LOW_PCT = 0.0
GROWTH_BASE_PCT = 5.0
GROWTH_HIGH_PCT = 10.0


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_corporate_tax_rate_pct() -> float:
    return _load_config()["corporate_tax_rate_pct"]


def is_eligible(fcf_ttm: float | None, shares_outstanding: float | None,
                market_cap: float | None, beta: float | None) -> tuple[bool, str | None]:
    if fcf_ttm is None or fcf_ttm <= 0:
        return False, "no_fcf"
    if not shares_outstanding:
        return False, "missing_shares_outstanding"
    if not market_cap or market_cap <= 0:
        return False, "missing_market_cap"
    if beta is None:
        return False, "beta_unavailable"
    return True, None


def _cost_of_debt_pct(financial_expenses_ttm: float | None, net_debt: float | None) -> float | None:
    """net_debt/faiz gideri oranindan proxy (gercek faiz gideri kalemi
    saglayicida yok -- 'Finansal Giderler' en yakin gelir tablosu satiri)."""
    if financial_expenses_ttm is None or not net_debt or net_debt <= 0:
        return None
    return financial_expenses_ttm / net_debt * 100


def calculate_wacc_pct(beta: float, erp: float, risk_free_annual_pct: float,
                        market_cap: float, net_debt: float | None,
                        financial_expenses_ttm: float | None, tax_rate_pct: float) -> float:
    cost_of_equity = risk_free_annual_pct + beta * erp
    debt = max(net_debt or 0.0, 0.0)
    total = market_cap + debt
    if total <= 0 or debt == 0:
        return cost_of_equity
    cost_of_debt = _cost_of_debt_pct(financial_expenses_ttm, net_debt)
    if cost_of_debt is None:
        return cost_of_equity
    weight_equity = market_cap / total
    weight_debt = debt / total
    return weight_equity * cost_of_equity + weight_debt * cost_of_debt * (1 - tax_rate_pct / 100)


def _fair_value_per_share(fcf_per_share: float, growth_pct: float, g: float, wacc_pct: float,
                           min_spread_pct: float) -> float | None:
    spread_pct = wacc_pct - g
    if spread_pct < min_spread_pct:
        return None
    fcf_next = fcf_per_share * (1 + growth_pct / 100)
    return fcf_next * (1 + g / 100) / (spread_pct / 100)


def calculate_dcf_reference(as_of_date: str, ticker: str, fcf_ttm: float | None,
                             shares_outstanding: float | None, current_price: float | None,
                             beta: float | None, risk_free_annual_pct: float,
                             market_cap: float | None, net_debt: float | None,
                             financial_expenses_ttm: float | None) -> dict:
    cfg = _load_config()
    eligible, reason = is_eligible(fcf_ttm, shares_outstanding, market_cap, beta)

    if not eligible:
        row = {"as_of_date": as_of_date, "ticker": ticker, "fcf_per_share": None, "wacc_pct": None,
               "growth_low_pct": None, "growth_base_pct": None, "growth_high_pct": None,
               "terminal_growth_pct": None, "fair_value_low": None, "fair_value_high": None,
               "premium_discount_low_pct": None, "premium_discount_high_pct": None,
               "null_reason": reason}
    else:
        erp = cfg["equity_risk_premium_pct"]
        g = cfg["tcmb_long_term_inflation_target_pct"]
        tax_rate_pct = cfg["corporate_tax_rate_pct"]
        wacc = calculate_wacc_pct(beta, erp, risk_free_annual_pct, market_cap, net_debt,
                                   financial_expenses_ttm, tax_rate_pct)
        fcf_per_share = fcf_ttm / shares_outstanding

        # OUTLIER GUARD: bkz. core/gordon.py ayni desen -- wacc-g sadece <=0
        # degil, erp'nin ALTINDA da kalirsa null (Gordon/DCF tekillik sorunu,
        # kucuk-pozitif spread'lerde absurd -- fiyatin onlarca kati -- ama
        # "gecerli" gorunumlu bir deger uretir).
        if wacc - g < erp:
            row = {"as_of_date": as_of_date, "ticker": ticker, "fcf_per_share": fcf_per_share,
                   "wacc_pct": wacc, "growth_low_pct": GROWTH_LOW_PCT, "growth_base_pct": GROWTH_BASE_PCT,
                   "growth_high_pct": GROWTH_HIGH_PCT, "terminal_growth_pct": g,
                   "fair_value_low": None, "fair_value_high": None,
                   "premium_discount_low_pct": None, "premium_discount_high_pct": None,
                   "null_reason": "unstable_denominator"}
        else:
            fv_low = _fair_value_per_share(fcf_per_share, GROWTH_LOW_PCT, g, wacc, erp)
            fv_base = _fair_value_per_share(fcf_per_share, GROWTH_BASE_PCT, g, wacc, erp)
            fv_high = _fair_value_per_share(fcf_per_share, GROWTH_HIGH_PCT, g, wacc, erp)
            scenarios = [v for v in (fv_low, fv_base, fv_high) if v is not None]
            fair_value_low, fair_value_high = min(scenarios), max(scenarios)
            premium_low = ((fair_value_low / current_price) - 1) * 100 if current_price else None
            premium_high = ((fair_value_high / current_price) - 1) * 100 if current_price else None

            # OUTLIER GUARD: Eger hesaplanan adil deger mevcut fiyatin 3 katini asarsa
            # (premium > %200) veya 0.2 katindan dusukse, bu tek seferlik bir nakit akimi
            # sicramasi veya veri anomalisidir. Tekil Gordon modeli bu uc noktalarda guvenilmezdir.
            if current_price and (fair_value_high > current_price * 3.0 or fair_value_low < current_price * 0.2):
                row = {"as_of_date": as_of_date, "ticker": ticker, "fcf_per_share": fcf_per_share,
                       "wacc_pct": wacc, "growth_low_pct": GROWTH_LOW_PCT, "growth_base_pct": GROWTH_BASE_PCT,
                       "growth_high_pct": GROWTH_HIGH_PCT, "terminal_growth_pct": g,
                       "fair_value_low": None, "fair_value_high": None,
                       "premium_discount_low_pct": None, "premium_discount_high_pct": None,
                       "null_reason": "outlier_valuation"}
            else:
                row = {"as_of_date": as_of_date, "ticker": ticker, "fcf_per_share": fcf_per_share,
                       "wacc_pct": wacc, "growth_low_pct": GROWTH_LOW_PCT, "growth_base_pct": GROWTH_BASE_PCT,
                       "growth_high_pct": GROWTH_HIGH_PCT, "terminal_growth_pct": g,
                       "fair_value_low": fair_value_low, "fair_value_high": fair_value_high,
                       "premium_discount_low_pct": premium_low, "premium_discount_high_pct": premium_high,
                       "null_reason": None}

    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO dcf_reference (as_of_date, ticker, fcf_per_share, wacc_pct,
               growth_low_pct, growth_base_pct, growth_high_pct, terminal_growth_pct,
               fair_value_low, fair_value_high, premium_discount_low_pct, premium_discount_high_pct,
               null_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 fcf_per_share=excluded.fcf_per_share, wacc_pct=excluded.wacc_pct,
                 growth_low_pct=excluded.growth_low_pct, growth_base_pct=excluded.growth_base_pct,
                 growth_high_pct=excluded.growth_high_pct, terminal_growth_pct=excluded.terminal_growth_pct,
                 fair_value_low=excluded.fair_value_low, fair_value_high=excluded.fair_value_high,
                 premium_discount_low_pct=excluded.premium_discount_low_pct,
                 premium_discount_high_pct=excluded.premium_discount_high_pct,
                 null_reason=excluded.null_reason""",
            (row["as_of_date"], row["ticker"], row["fcf_per_share"], row["wacc_pct"],
             row["growth_low_pct"], row["growth_base_pct"], row["growth_high_pct"],
             row["terminal_growth_pct"], row["fair_value_low"], row["fair_value_high"],
             row["premium_discount_low_pct"], row["premium_discount_high_pct"], row["null_reason"]),
        )
        conn.commit()
    finally:
        conn.close()
    return row
