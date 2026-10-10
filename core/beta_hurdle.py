"""beta_adjusted_hurdle: yuksek beta'li hisselerin ayni sabit hurdle ile
sistematik olarak odullenmesini gostermek icin bilgi amacli ek metrik.

Ilk spec bunu yalnizca bilgi olarak tanimliyordu. 2026-10 denetimi: uzun vade
hedef fiyati k_e = rf + beta*ERP ile buyutuldugu icin sabit rf hurdle'i beta > 0
olan her hissede otomatik geciliyordu. Bu yuzden uzun vade kovasinda
excess_over_beta_hurdle_pct artik sert filtredir (core/scoring.py, "beta_hurdle").
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core import db

_ERP_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "equity_risk_premium.yaml"


def load_equity_risk_premium_pct() -> float:
    with open(_ERP_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["equity_risk_premium_pct"]


def _daily_returns(closes: list[float]) -> list[float]:
    return [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1]]


def calculate_beta(stock_prices: list[dict], market_prices: list[dict], max_obs: int = 120) -> float | None:
    """Son <=120 gunluk getiri, XU100'e karsi OLS egimi. Seriler TARIHE gore
    hizalanir (eskiden son n satir konumsal eslesiyordu; tatil/eksik gun
    kaymasi getirileri yanlis gunlerle eslestirebiliyordu)."""
    if all("date" in p for p in stock_prices) and all("date" in p for p in market_prices):
        m_by_date = {p["date"]: p.get("adj_close") or p["close"] for p in market_prices if p.get("close")}
        pairs = [(p.get("adj_close") or p["close"], m_by_date[p["date"]]) for p in stock_prices
                 if p.get("close") and p["date"] in m_by_date]
    else:  # tarihsiz seri (eski cagrilar/testler): son n satir konumsal
        n = min(len(stock_prices), len(market_prices))
        pairs = [(a.get("adj_close") or a["close"], b.get("adj_close") or b["close"])
                 for a, b in zip(stock_prices[-n:], market_prices[-n:])
                 if a.get("close") and b.get("close")]
    pairs = pairs[-(max_obs + 1):]
    if len(pairs) < 61:
        return None
    r_stock = _daily_returns([a for a, _ in pairs])
    r_market = _daily_returns([b for _, b in pairs])
    m = min(len(r_stock), len(r_market))
    r_stock, r_market = r_stock[-m:], r_market[-m:]
    mean_s = sum(r_stock) / m
    mean_m = sum(r_market) / m
    cov = sum((r_stock[i] - mean_s) * (r_market[i] - mean_m) for i in range(m)) / m
    var_m = sum((x - mean_m) ** 2 for x in r_market) / m
    if var_m == 0:
        return None
    return cov / var_m


def blume_adjusted_beta(beta: float | None) -> float | None:
    """Blume (1971): beta'lar zamanla 1'e yakinsar; 0.67*ham + 0.33.
    Ozsermaye maliyetinde ham tahmin yerine kullanilir (tahmin gurultusunu azaltir)."""
    return None if beta is None else 0.67 * beta + 0.33


def calculate_beta_adjusted_hurdle(as_of_date: str, ticker: str, stock_prices: list[dict],
                                     risk_free_annual_pct: float, expected_roi_pct: float,
                                     market_prices: list[dict] | None = None,
                                     horizon_days: int = 180) -> dict:
    """market_prices verilmezse (eski cagri) mock XU100'e DUSULMEZ; beta None kalir.
    Eskiden canli modda bile mock_prices("XU100_INDEX") kullaniliyordu (sahte beta).
    Hurdle yillik k_e'nin ufka bilesik olceklenmis halidir: expected_roi_pct
    ufuk getirisi oldugu icin birimler ayni olmali (eskiden yillik ~%45 ile
    180 gunluk getiri karsilastiriliyordu)."""
    beta = calculate_beta(stock_prices, market_prices) if market_prices else None
    erp = load_equity_risk_premium_pct()

    if beta is None:
        row = {"as_of_date": as_of_date, "ticker": ticker, "beta_60_120d": None,
               "hurdle_rate_beta_adjusted_pct": None, "excess_over_beta_hurdle_pct": None}
    else:
        k_e_annual = risk_free_annual_pct + blume_adjusted_beta(beta) * erp
        hurdle_beta_adj = ((1 + k_e_annual / 100) ** (horizon_days / 365) - 1) * 100
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
