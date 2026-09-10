"""hurdle_engine: risksiz getiri uzerinden asgari getiri (hurdle) hesaplari.

Spec: hurdle_engine. gate: excess_over_hurdle_pct <= 0 olan aday raporda gosterilmez.
"""
from __future__ import annotations

SHOCKS_BPS = [-100, 0, 100, 200, 300]


def hurdle_rate_pct(risk_free_annual_pct: float, horizon_days: int) -> float:
    return risk_free_annual_pct * (horizon_days / 365)


def expected_roi_pct(entry_price: float, target_price: float) -> float:
    return ((target_price - entry_price) / entry_price) * 100


def excess_over_hurdle_pct(expected_roi: float, hurdle_rate: float) -> float:
    return expected_roi - hurdle_rate


def real_return_pct(roi_pct: float, expected_cpi_for_horizon_pct: float) -> float:
    return ((1 + roi_pct / 100) / (1 + expected_cpi_for_horizon_pct / 100) - 1) * 100


def usd_return_pct(entry_price: float, target_price: float, usdtry_spot: float,
                    expected_usdtry_at_horizon: float) -> float:
    return ((target_price / expected_usdtry_at_horizon) / (entry_price / usdtry_spot) - 1) * 100


def expected_cpi_for_horizon(cpi_yearend_expectation_pct: float, horizon_days: int) -> float:
    """Yil sonu TUFE beklentisini ufka orantili olarak olceklendirir (varsayim, deneysel)."""
    return cpi_yearend_expectation_pct * (horizon_days / 365)


def expected_usdtry_at_horizon(usdtry_spot: float, usdtry_12m_expectation: float, horizon_days: int) -> float:
    frac = min(1.0, horizon_days / 365)
    return usdtry_spot + (usdtry_12m_expectation - usdtry_spot) * frac


def compute_all(entry_price: float, target_price: float, horizon_days: int, macro: dict) -> dict:
    # risk_free_annual (bond_2y_pct) sert gecidin (excess_over_hurdle_pct) tek
    # girdisidir ve HER ZAMAN gercek/mock veriden dolu gelir. real_return_pct
    # ve usd_return_pct ise yalnizca BILGI amaclidir; canli modda TCMB anket
    # bazli beklentiler (cpi_yearend_expectation_pct, usdtry_12m_expectation)
    # ucretsiz kaynakla dogrulanamadigindan None olabilir -- bu durumda
    # uydurma sayi uretmek yerine ilgili alan None birakilir.
    risk_free_annual = macro["bond_2y_pct"]
    hurdle = hurdle_rate_pct(risk_free_annual, horizon_days)
    roi = expected_roi_pct(entry_price, target_price)
    excess = excess_over_hurdle_pct(roi, hurdle)

    cpi_yearend = macro.get("cpi_yearend_expectation_pct")
    real_ret = None
    if cpi_yearend is not None:
        exp_cpi = expected_cpi_for_horizon(cpi_yearend, horizon_days)
        real_ret = real_return_pct(roi, exp_cpi)

    usdtry_spot = macro.get("usdtry_spot")
    usdtry_12m = macro.get("usdtry_12m_expectation")
    usd_ret = None
    if usdtry_spot is not None and usdtry_12m is not None:
        exp_usdtry = expected_usdtry_at_horizon(usdtry_spot, usdtry_12m, horizon_days)
        usd_ret = usd_return_pct(entry_price, target_price, usdtry_spot, exp_usdtry)

    return {
        "hurdle_rate_pct": hurdle, "expected_roi_pct": roi, "excess_over_hurdle_pct": excess,
        "real_return_pct": real_ret,
        "usd_return_pct": usd_ret,
        "passes_gate": excess > 0,
    }


def sensitivity_table(candidates: list[dict]) -> dict:
    """Her sok icin kac adayin excess_over_hurdle_pct > 0 kaldigini sayar.

    candidates: her biri {"expected_roi_pct", "hurdle_rate_pct"} icermeli.
    """
    result = {}
    for shock_bps in SHOCKS_BPS:
        shock_pct = shock_bps / 100
        count = 0
        for c in candidates:
            # basit yaklasim: risksiz oran shock_bps kadar kayar, hurdle_rate_pct de
            # ayni oranda (yillik -> ufka olceklenmis) kayar.
            shocked_hurdle = c["hurdle_rate_pct"] + shock_pct
            shocked_excess = c["expected_roi_pct"] - shocked_hurdle
            if shocked_excess > 0:
                count += 1
        result[shock_bps] = count
    return result
