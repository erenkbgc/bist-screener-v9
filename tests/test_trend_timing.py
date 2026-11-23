"""core/trend_timing: durum makineleri, gecikmeli uygulama, limit kurali, katman simulasyonu."""
import numpy as np
import pandas as pd

from core import trend_timing as tt


def _ohlc(c, spread=0.5):
    c = np.asarray(c, dtype=float)
    return c + spread, c - spread, c


def _up_then_down(n_up=60, n_down=40):
    return np.concatenate([np.full(30, 100.0), np.linspace(100, 160, n_up), np.linspace(160, 100, n_down)])


def test_donchian_long_on_breakout_flat_after_drop():
    h, lo, c = _ohlc(_up_then_down())
    st = tt.donchian_state(h, lo, c)
    assert st[:30].sum() == 0          # duz piyasada kirilim yok
    assert st[35] == 1                 # yukselis kanal ustunu kirar
    assert st[-1] == 0                 # dusus 10 gunluk dibi kirar
    assert st[29 + 60 + 5] == 0


def test_supertrend_flips_with_trend():
    h, lo, c = _ohlc(_up_then_down())
    st = tt.supertrend_state(h, lo, c)
    assert st[80] == 1 and st[-1] == 0


def test_ema_pullback_needs_pullback_then_confirmation():
    base = list(np.linspace(100, 150, 80))
    # geri cekilme: EMA20'nin altina iner, sonra onceki tepenin ustunde kapanir
    seq = base + [146, 142, 140, 143, 147, 150, 152]
    h, lo, c = _ohlc(seq, spread=0.3)
    st = tt.ema_pullback_state(h, lo, c)
    assert st[:80].sum() == 0
    assert st[-1] == 1


def test_execute_lags_one_day_and_respects_limit():
    state = np.array([0, 1, 1, 1, 0, 0], dtype=np.int8)
    c = np.array([100, 101, 102, 103, 104, 105.0])
    assert tt.execute(state, c).tolist() == [0, 0, 1, 1, 1, 0]
    c_lock = np.array([100, 101, 112, 113, 114, 115.0])  # gun 2 tavan: alim gun 3'e kayar
    assert tt.execute(state, c_lock).tolist() == [0, 0, 0, 1, 1, 0]


def test_overlay_flat_slot_earns_cash_and_base_holds_stock():
    days = pd.bdate_range("2020-01-01", periods=45)
    months = [days[0], days[20], days[40]]
    d0_of = {t: t for t in months}
    close = pd.DataFrame({"A": np.linspace(100, 120, 45)}, index=days)
    uni = {t: pd.DataFrame({"rank_pct": [0.1], "bench": [0.0], "bench_usd": [0.0], "fx_ret": [0.0]}, index=["A"])
           for t in months}
    rf = pd.Series(0.001, index=days)
    xu = pd.Series(100.0, index=days)
    base = tt.simulate_overlay(months, uni, close, None, rf, xu, d0_of)
    assert np.isclose(base.iloc[0]["port"], close["A"].iloc[20] / close["A"].iloc[0] - 1)
    flat = tt.simulate_overlay(months, uni, close, pd.DataFrame({"A": 0}, index=days), rf, xu, d0_of)
    assert np.isclose(flat.iloc[0]["port"], 1.001 ** 20 - 1)
    assert flat.iloc[0]["invested"] == 0
