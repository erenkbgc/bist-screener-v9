"""core/event_study: pencere getirisi, Dimson piyasa modeli, CAR, toparlanma, karar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import event_study as es


def test_event_pos_rolls_weekend_to_next_session():
    days = pd.bdate_range("2016-07-11", periods=10)  # Pzt..
    assert days[es.event_pos(days, "2016-07-16")] == pd.Timestamp("2016-07-18")  # Cmt -> Pzt
    assert days[es.event_pos(days, "2016-07-15")] == pd.Timestamp("2016-07-15")


def test_window_return_uses_close_before_a():
    level = np.array([100, 110, 121, 133.1])
    assert np.isclose(es.window_return(level, 2, 0, 0), 0.10)  # 110 -> 121
    assert np.isclose(es.window_return(level, 2, -1, 1), 0.331)  # 100 -> 133.1
    assert np.isnan(es.window_return(level, 2, 0, 5))


def test_market_model_recovers_dimson_betas_and_car_is_residual():
    rng = np.random.default_rng(0)
    n = 400
    rm = rng.normal(0, 0.01, n)
    r = np.r_[np.nan, 0.0002 + 0.8 * rm[1:] + 0.3 * rm[:-1]]
    rm = np.r_[np.nan, rm[1:]]
    i0 = 350
    r[i0] += -0.05  # olay gunu soku
    a, b0, b1 = es.market_model(r, rm, i0)
    assert np.isclose(b0, 0.8, atol=1e-6) and np.isclose(b1, 0.3, atol=1e-6)
    assert np.isclose(es.car(r, rm, (a, b0, b1), i0, 0, 5), -0.05, atol=1e-6)


def test_recovery_days():
    level = np.array([100, 100, 90, 95, 101])
    assert es.recovery_days(level, 2) == 2
    assert es.recovery_days(np.array([100, 100, 90, 95]), 2) == es.RECOVERY_CAP


def test_verdict_requires_p_sign_and_count():
    t = es.cross_event_test([-0.02] * 9 + [0.001, 0.002])
    assert t["n_neg"] == 9 and t["p"] < 0.0167
    assert es.verdict(t, 8, 0.0167, "UP", "DOWN") == "DOWN"
    assert es.verdict(t, 10, 0.0167, "UP", "DOWN") == "FAIL"
    assert es.verdict({"n": 2}, 8, 0.0167, "UP", "DOWN") == "INSUFFICIENT"
