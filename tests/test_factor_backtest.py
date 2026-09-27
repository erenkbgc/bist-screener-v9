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


def test_peer_fair_value_ratio_harmonic_mean():
    # 5 akran, hepsinin E/P'si ayni -> HM(P/E)*E/P = 1 (adil fiyatli)
    base = {"sector": "X", "mcap": 100.0, "net_debt": 0.0, "bm": 0.5, "ey": 0.1}
    m = pd.DataFrame([{**base, "ep": 0.1} for _ in range(5)])
    r = fb.peer_fair_value_ratio(m)
    assert np.allclose(r["fv_ratio"], 1.0)
    # E/P'si akranlarin iki kati olan hisse ~2 kat pe bacagi alir
    m.loc[0, "ep"] = 0.2
    hm = 1 / m["ep"].mean()  # 1/0.12
    r = fb.peer_fair_value_ratio(m)
    # pe bacagi hm*0.2; pb ve ev_ebit bacaklari 1.0 -> ortalama
    assert abs(r.loc[0, "fv_ratio"] - (hm * 0.2 + 1.0 + 1.0) / 3) < 1e-9
    assert r.loc[0, "fv_ratio"] > r.loc[1, "fv_ratio"]


def test_peer_fair_value_ratio_guards_and_fallback():
    base = {"mcap": 100.0, "net_debt": 0.0, "bm": 0.5, "ey": 0.1, "ep": 0.1}
    rows = [{**base, "sector": "BIG"} for _ in range(6)] + [{**base, "sector": "TINY", "ep": -0.1, "bm": -1, "ey": -0.1}]
    r = fb.peer_fair_value_ratio(pd.DataFrame(rows))
    assert np.isnan(r.loc[6, "fv_ratio"])  # tum bacaklar negatif -> degerlenemez
    assert np.allclose(r.loc[:5, "fv_ratio"], 1.0)
