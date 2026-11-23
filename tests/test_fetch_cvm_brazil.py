import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

_p = Path(__file__).resolve().parents[1] / "scripts" / "fetch_cvm_brazil.py"
_spec = importlib.util.spec_from_file_location("fetch_cvm_brazil", _p)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def _row(pe, ytd, filed):
    return {"cd_cvm": 5410, "period_end": pd.Timestamp(pe), "filed": pd.Timestamp(filed),
            "ytd_revenue": ytd, "ytd_op_profit": ytd / 10, "ytd_net_income": ytd / 20,
            "equity": 500.0, "fin_debt": 100.0, "cash": 50.0, "sh_on": 10.0, "sh_pn": 0.0}


def test_ttm_formula():
    st = pd.DataFrame([_row("2022-06-30", 40, "2022-08-01"), _row("2022-12-31", 100, "2023-02-20"),
                       _row("2023-06-30", 60, "2023-08-01")])
    st = m.add_ttm(st)
    assert st.loc[2, "ttm_revenue"] == 60 + 100 - 40
    assert st.loc[1, "ttm_revenue"] == 100
    assert np.isnan(st.loc[0, "ttm_revenue"])  # missing FY2021


def test_value_legs_match_definitions():
    legs = m.value_legs({"equity": 500.0, "ttm_net_income": 50.0, "ttm_revenue": 1000.0,
                         "ttm_op_profit": 105.0, "fin_debt": 100.0, "cash": 50.0}, 1000.0)
    assert legs == {"bm": 0.5, "ep": 0.05, "sp": 1.0, "ey": 0.1}
    neg = m.value_legs({"equity": -1.0, "ttm_net_income": 1.0, "ttm_revenue": 1.0,
                        "ttm_op_profit": 1.0, "fin_debt": np.nan, "cash": 0.0}, 10.0)
    assert np.isnan(neg["bm"]) and np.isnan(neg["ey"])


def test_point_in_time_uses_filing_date():
    st = m.add_ttm(pd.DataFrame([_row("2022-12-31", 100, "2023-03-20")]))
    px = pd.DataFrame({"date": pd.to_datetime(["2023-02-27", "2023-03-31"]),
                       "ticker": ["WEGE3", "WEGE3"], "close": [10.0, 20.0]})
    p = m.build_panel(st, px, pd.to_datetime(["2023-02-28", "2023-03-31"]))
    assert list(p.date) == [pd.Timestamp("2023-03-31")]  # not usable before filing
    assert p.mcap.iloc[0] == 200.0 and p.bm.iloc[0] == 2.5


def test_parse_cotahist_line():
    line = ("01" + "20240102" + "02" + "WEGE3".ljust(12) + "010" + " " * 81
            + "0000000004012" + " " * 100)
    df = m.parse_cotahist(line.encode("latin1"), ["WEGE"])
    assert df.close.iloc[0] == 40.12 and df.ticker.iloc[0] == "WEGE3"


def test_share_unit_thousands_fix():
    r = _row("2022-12-31", 100, "2023-03-01")
    r.update(equity=5e9, sh_on=1e3)
    st = m.add_ttm(pd.DataFrame([r]))
    px = pd.DataFrame({"date": [pd.Timestamp("2023-03-31")], "ticker": ["WEGE3"], "close": [10.0]})
    p = m.build_panel(st, px, [pd.Timestamp("2023-03-31")])
    assert p.mcap.iloc[0] == 1e7 and bool(p.shares_x1000.iloc[0])
