import numpy as np
import pandas as pd

from core import entry_timing as et


def _arrays(closes, lows=None, opens=None):
    n = len(closes)
    c = np.array(closes, dtype=float)
    a = {"Close": c, "Open": np.array(opens if opens is not None else c, dtype=float),
         "Low": np.array(lows if lows is not None else c, dtype=float), "High": c.copy(),
         "atr20": np.full(n, 2.0), "rsi14": np.full(n, 50.0),
         "sma20": np.full(n, 1e9), "sma50": np.full(n, 1e9)}
    return a


def test_e0_and_e1_wait_for_recent_winner():
    a = _arrays(range(100, 200))
    assert et.e0(a, 10, {}) == [(11, 111.0, 1.0)]
    assert et.e1(a, 10, {"ret_quintile": 4}) == [(32, 132.0, 1.0)]
    assert et.e1(a, 10, {"ret_quintile": 2})[0][0] == 11


def test_limit_fill_at_limit_or_gap_open():
    closes = [100.0] * 40
    lows = [100.0] * 40
    lows[15] = 97.0  # P0 - 1*ATR = 98 -> dolar
    a = _arrays(closes, lows)
    assert et.e2a(a, 10, {}) == [(15, 98.0, 1.0)]
    opens = [100.0] * 40
    opens[15] = 96.5  # acilis limitin altinda -> acilistan dolar
    a = _arrays(closes, lows, opens)
    assert et.e2a(a, 10, {}) == [(15, 96.5, 1.0)]
    assert et.e2b(a, 10, {}) == [(31, 100.0, 1.0)]  # 96 limitine hic inmedi -> d21 kapanis


def test_e4_trend_confirmation_and_deadline():
    a = _arrays([100.0] * 120)
    a["sma50"][40] = 50.0
    assert et.e4(a, 10, {}) == [(40, 100.0, 1.0)]
    a = _arrays([100.0] * 120)
    assert et.e4(a, 10, {}) == [(73, 100.0, 1.0)]


def test_e5_three_legs_and_e6_only_for_losers():
    a = _arrays(range(100, 200))
    legs = et.e5(a, 10, {})
    assert [i for i, _, _ in legs] == [11, 21, 31] and abs(sum(w for *_, w in legs) - 1) < 1e-12
    assert et.e6(a, 10, {"ret_quintile": 3})[0][0] == 11
    a["sma20"][14] = 0.0
    assert et.e6(a, 10, {"ret_quintile": 0})[0][0] == 14


def test_improvement_market_and_cash():
    a = _arrays([100.0] * 12 + [90.0] * 30)
    xu = np.array([1000.0] * 12 + [950.0] * 30)
    legs = [(15, 90.0, 1.0)]
    r = et.improvement(a, xu, 10, legs, policy_pct=0.0)
    assert abs(r["i_mkt"] - (np.log(100 / 90) - np.log(1000 / 950))) < 1e-12
    assert abs(r["i_cash"] - np.log(100 / 90)) < 1e-12
    assert r["wait_days"] == 4
    r2 = et.improvement(a, xu, 10, legs, policy_pct=50.0)
    assert r2["i_cash"] > r["i_cash"]


def test_indicators_columns():
    idx = pd.bdate_range("2020-01-01", periods=80)
    c = pd.Series(np.linspace(10, 20, 80), index=idx)
    px = pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c})
    out = et.indicators(px)
    assert {"atr20", "rsi14", "sma20", "sma50"} <= set(out.columns)
    assert out["rsi14"].iloc[-1] == 100.0  # yalniz yukselis
    assert abs(out["sma50"].iloc[-1] - c.iloc[-50:].mean()) < 1e-9
