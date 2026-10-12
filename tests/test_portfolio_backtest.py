"""core/portfolio_backtest: gunluk defter, ertesi gun islem, maliyet ve delist mekanigi."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import portfolio_backtest as pb

ZERO = pb.Costs(commission_bps=0, spread_bps=(0, 0, 0), impact_k=0, impact_cap=0)


def _market(prices: dict[str, list[float]], days: pd.DatetimeIndex, adv: float = 1e9, rf: float = 0.0):
    close = pd.DataFrame(prices, index=days, dtype=float)
    return pb.Market(close=close, open=close.copy(), adv=pd.DataFrame(adv, index=days, columns=close.columns),
                     sigma=pd.DataFrame(0.02, index=days, columns=close.columns),
                     rf_daily=pd.Series(rf, index=days))


def _setup(n_days=60):
    days = pd.bdate_range("2020-01-01", periods=n_days)
    months = [days[9], days[29], days[49]]
    d0_of = {t: t for t in months}
    return days, months, d0_of


def test_next_day_fill_misses_jump_on_fill_day():
    days, months, d0_of = _setup()
    px = [100.0] * 10 + [150.0] * 50  # d0'dan sonraki ilk gun (islem gunu) %50 sicrama
    mkt = _market({"A": px}, days)
    out = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e6 for t in months}, costs=ZERO)
    # Kapanista alindigi icin sicrama kacirilir; ilk ay getirisi 0
    assert abs(out.iloc[0]["port"]) < 1e-12
    out_open = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e6 for t in months},
                           costs=ZERO, fill="open")
    assert abs(out_open.iloc[0]["port"]) < 1e-12  # acilis = kapanis bu testte


def test_costs_charged_on_first_buy():
    days, months, d0_of = _setup()
    mkt = _market({"A": [100.0] * 60, "B": [100.0] * 60}, days)
    liq = {t: np.array([1.0, 2.0, 3.0]) for t in months}  # adv=1e9 -> ust ucte bir -> 5 bps
    c = pb.Costs(commission_bps=10, spread_bps=(5, 15, 30), impact_k=0.0)
    out = pb.simulate({t: ["A", "B"] for t in months}, months, d0_of, mkt, liq, {t: 1e6 for t in months}, costs=c)
    first = out.iloc[0]
    assert np.isclose(first["cost"], 15e-4)
    assert np.isclose(first["port"], -15e-4, atol=1e-6)
    assert np.isclose(first["turnover"], 1.0)
    # ikinci ay liste ayni, fiyat sabit: islem yok, maliyet yok
    assert out.iloc[1]["cost"] == 0


def test_impact_grows_with_capital():
    days, months, d0_of = _setup()
    mkt = _market({"A": [100.0] * 60}, days, adv=1e6)
    small = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e4 for t in months})
    big = pb.simulate({t: ["A"] for t in months}, months, d0_of, mkt, {}, {t: 1e7 for t in months})
    assert big.iloc[0]["impact"] > small.iloc[0]["impact"]
    assert big.iloc[0]["fills_over_10pct_adv"] == 1 and small.iloc[0]["fills_over_10pct_adv"] == 0


def test_delisted_name_closed_with_haircut():
    days, months, d0_of = _setup()
    px_a = [100.0] * 15 + [np.nan] * 45  # 15. gunden sonra islem yok
    mkt = _market({"A": px_a, "B": [100.0] * 60}, days)
    out = pb.simulate({months[0]: ["A", "B"]}, months, d0_of, mkt, {}, {t: 1e6 for t in months},
                      costs=ZERO, haircut=0.5)
    assert out.attrs["delist_events"] == 1
    # 1. ay: A son fiyatindan tasinir (getiri 0). 2. ay: liste bos; A islem gormedigi icin
    # satilamaz (takili), B satilir; A 20 gun fiyatsiz kalinca yarisi kaybedilerek kapanir.
    assert np.isclose(out.iloc[0]["port"], 0.0)
    assert np.isclose(out.iloc[1]["port"], -0.25)


def test_cash_earns_deposit_rate_when_no_targets():
    days, months, d0_of = _setup()
    mkt = _market({"A": [100.0] * 60}, days, rf=0.001)
    out = pb.simulate({t: [] for t in months}, months, d0_of, mkt, {}, {t: 1e6 for t in months}, costs=ZERO)
    assert np.isclose(out.iloc[0]["port"], 1.001 ** 20 - 1)
