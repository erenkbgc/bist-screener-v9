"""factor_backtest: sentetik panelde bilinen sinyal geri bulunmali, gurultu bulunmamali."""
import numpy as np
import pandas as pd

from core import factor_backtest as fb


def _panel(n_months=60, n_names=80, beta=0.02, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.date_range("2016-01-31", periods=n_months, freq="ME"):
        sig = rng.normal(size=n_names)
        noise = rng.normal(size=n_names)
        ret = beta * sig + 0.05 * rng.normal(size=n_names)
        for i in range(n_names):
            rows.append({"date": d, "ticker": f"T{i}", "tlvol60": 1e6 + i, "bm": sig[i],
                         "vol60": -sig[i], "sue": noise[i], "fwd_ret_1m": ret[i]})
    return pd.DataFrame(rows)


def test_signal_recovered_with_sign_flip():
    df = fb.prepare(_panel(), ["bm", "vol60", "sue"], liq_drop_pct=0.0)
    for col in ("bm_z", "vol60_z"):  # vol60 SIGNS=-1 ile ayni yone doner
        _, t, _ = fb.newey_west_t(fb.rank_ic(df, col, "fwd_ret_1m"), 1)
        assert t > 5
    _, t_noise, _ = fb.newey_west_t(fb.rank_ic(df, "sue_z", "fwd_ret_1m"), 1)
    assert abs(t_noise) < 3


def test_fama_macbeth_slope_scale():
    df = fb.prepare(_panel(beta=0.02), ["bm"], liq_drop_pct=0.0)
    fm = fb.fama_macbeth(df, ["bm_z"], "fwd_ret_1m")
    assert abs(fm["bm_z"].mean() - 0.02) < 0.005


def test_quintile_spread_positive_and_turnover_bounds():
    df = fb.prepare(_panel(), ["bm"], liq_drop_pct=0.0)
    q = fb.quintile_spread(df, "bm_z", "fwd_ret_1m")
    assert (q["spread"].mean() > 0) and q["turnover"].between(0, 1).all()


def test_liquidity_filter_and_min_names():
    p = _panel(n_months=2, n_names=40)
    assert len(fb.prepare(p, ["bm"], liq_drop_pct=0.5)) == 0  # 20 < min_names 30
    assert fb.prepare(p, ["bm"], liq_drop_pct=0.25).groupby("date").size().eq(30).all()


def test_newey_west_matches_plain_t_without_lags():
    x = pd.Series(np.random.default_rng(1).normal(0.1, 1, 500))
    m, t, n = fb.newey_west_t(x, 0)
    plain = x.mean() / (x.std(ddof=0) / np.sqrt(len(x)))
    assert n == 500 and abs(t - plain) < 1e-9
