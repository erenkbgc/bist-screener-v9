"""Ramazan / tatil oncesi takvim bayraklari ve NW kukla regresyonu."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_ramadan_holiday as rh  # noqa: E402


def test_ramadan_ranges_match_diyanet_spot_checks():
    r = dict((a.year, (a, b)) for a, b in rh.ramadan_ranges())
    assert r[2024][0] == pd.Timestamp("2024-03-11") and r[2024][1] == pd.Timestamp("2024-04-09")
    assert r[2025][0] == pd.Timestamp("2025-03-01")
    assert r[2023][1] == pd.Timestamp("2023-04-20")  # bayram 21.04


def test_pre_holiday_flag_ignores_weekends():
    days = pd.DatetimeIndex(["2023-04-19", "2023-04-20", "2023-04-24", "2023-04-25", "2023-04-28", "2023-05-02"])
    f = rh.pre_holiday_flag(days)
    # 20.04 Prs -> 21.04 Cuma kapali; 25.04 Sali -> 26.04 islem yok (ornek); 28.04 Cuma -> Pzt 01.05 kapali
    assert list(f) == [False, True, False, True, True, False]


def test_dummy_regression_recovers_difference():
    rng = np.random.default_rng(1)
    d = pd.Series(np.arange(2000) % 10 == 0)
    r = pd.Series(rng.normal(0, 0.001, 2000)) + 0.001 * d
    out = rh.dummy_regression(r, d)
    assert abs(out["b_daily_bps"] - 10) < 1.5 and out["t"] > 10
