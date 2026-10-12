"""Temettu verimi tanimi: 365 gun penceresi, toplam / piyasa degeri, hata veren hisse disarida."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_dividend_yield as ry  # noqa: E402


def test_add_dy_trailing_window_and_failed_dropped():
    df = pd.DataFrame({"ticker": ["A", "A", "B", "C"],
                       "date": pd.to_datetime(["2020-06-30", "2021-07-31", "2020-06-30", "2020-06-30"]),
                       "mcap": [1000.0, 1000.0, 500.0, 100.0]})
    div = pd.DataFrame({"ticker": ["A", "A"], "ex_date": pd.to_datetime(["2020-05-01", "2019-05-01"]),
                        "total_dividend": [50.0, 40.0]})
    out = ry.add_dy(df, div, failed={"C"}).set_index(["ticker", "date"])["dy"]
    assert out[("A", pd.Timestamp("2020-06-30"))] == 0.05      # 2019 odemesi pencere disi
    assert out[("A", pd.Timestamp("2021-07-31"))] == 0.0       # 2020-05 odemesi 365 gunden eski
    assert out[("B", pd.Timestamp("2020-06-30"))] == 0.0       # temettu kaydi yok -> odemeyen
    assert "C" not in out.index.get_level_values(0)
