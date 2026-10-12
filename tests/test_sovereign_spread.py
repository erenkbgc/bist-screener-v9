"""Ulke riski spread'i: UST egrisi enterpolasyonu ve medyan bond spread'i."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
pytest.importorskip("statsmodels")  # arastirma bagimliligi (requirements-research.txt); CI kurmaz
import research_sovereign_spread as ss  # noqa: E402


def test_ust_curve_interpolates_and_flat_outside():
    row = pd.Series({"^FVX": 4.0, "^TNX": 4.5, "^TYX": 5.0})
    assert ss.ust_curve(row, 7.5) == 4.25
    assert ss.ust_curve(row, 2.0) == 4.0 and ss.ust_curve(row, 40.0) == 5.0


def test_spread_series_median_and_maturity_window():
    d = pd.Timestamp("2020-06-30")
    eb = pd.DataFrame({"month": d, "date": d, "isin": ["a", "b", "c", "d"],
                       "maturity": pd.to_datetime(["2021-06-30", "2025-06-30", "2030-06-30", "2040-06-30"]),
                       "yield": [3.0, 6.0, 7.0, 8.0]})
    ust = pd.DataFrame({"^FVX": [1.0], "^TNX": [2.0], "^TYX": [3.0]}, index=[d])
    sp = ss.spread_series(eb, ust)
    # 1 yillik tahvil (a) disarida; 5y: 6-1=5, 10y: 7-2=5, 20y: 8-2.5=5.5 -> medyan 5.0
    assert abs(sp[d] - 5.0) < 0.01
