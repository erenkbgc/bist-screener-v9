import numpy as np
import pandas as pd

from core import long_term_research as ltr


def _q(rows):
    base = {"ttm_net_income": np.nan, "q_net_income": np.nan, "ttm_ebit": np.nan, "ttm_op_profit": 10.0,
            "retained": 5.0, "cash": 3.0, "noncurrent_liab": 20.0}
    df = pd.DataFrame([{**base, **r} for r in rows])
    df["period_end"] = pd.to_datetime(df["period_end"])
    return df


def test_weighted_avg_phi_weights():
    assert ltr._weighted_avg([1.0, 1.0, 1.0, 1.0]) == 1.0
    w = np.array([ltr.PHI ** j for j in range(2)])
    assert abs(ltr._weighted_avg([1.0, 0.0]) - w[0] / w.sum()) < 1e-12
    assert np.isnan(ltr._weighted_avg([1.0, np.nan]))


def test_statement_features_f6_and_year_ago():
    common = {"ticker": "X", "q": 2, "current_liab": 50.0, "equity": 100.0}
    q = _q([
        {**common, "period": "2020Q2", "period_end": "2020-06-30", "year": 2020, "total_assets": 200.0,
         "ttm_ni_parent": -10.0, "fin_debt": 80.0, "current_assets": 40.0, "ttm_gross_profit": 20.0,
         "ttm_revenue": 100.0, "q_ni_parent": -2.0},
        {**common, "period": "2021Q2", "period_end": "2021-06-30", "year": 2021, "total_assets": 200.0,
         "ttm_ni_parent": 10.0, "fin_debt": 40.0, "current_assets": 60.0, "ttm_gross_profit": 30.0,
         "ttm_revenue": 120.0, "q_ni_parent": 3.0},
    ])
    s = ltr.statement_features(q).set_index("stmt_period")
    assert np.isnan(s.loc["2020Q2", "f6"])  # yil onceki ceyrek yok
    assert s.loc["2021Q2", "f6"] == 6.0
    tl = 50.0 + 20.0
    expected = 6.56 * (60 - 50) / 200 + 3.26 * 5 / 200 + 6.72 * 10 / 200 + 1.05 * 100 / tl
    assert abs(s.loc["2021Q2", "altman_em"] - expected) < 1e-9


def _panel(n=40, months=("2020-01-31",)):
    rows = []
    for m in months:
        for i in range(n):
            rows.append({"date": pd.Timestamp(m), "ticker": f"T{i}", "value_sn_z": float(i),
                         "fwd_ret_1m": 0.01 * i, "fwd_ret_1m_usd": 0.01 * i, "xs_6m": -0.5 if i == n - 1 else 0.0})
    return pd.DataFrame(rows)


def test_portfolio_exclusion_keeps_universe_benchmark():
    df = _panel()
    base = ltr.portfolio(df, "value_sn_z")
    excl = df["ticker"] == "T39"
    alt = ltr.portfolio(df, "value_sn_z", excl)
    assert base.loc[0, "n"] == 8 and alt.loc[0, "n"] == 8  # 39 kalan aday -> round(7.8)=8
    assert base.loc[0, "uni_fwd_ret_1m"] == alt.loc[0, "uni_fwd_ret_1m"]
    assert alt.loc[0, "top_fwd_ret_1m"] < base.loc[0, "top_fwd_ret_1m"]
    assert base.loc[0, "trap_rate"] == 1 / 8
    assert alt.loc[0, "trap_rate"] == 0.0


def test_flags_missing_data_not_excluded():
    df = pd.DataFrame({
        "date": pd.Timestamp("2020-01-31"), "chs": [np.nan] + list(range(9)),
        "altman_em": [np.nan, 0.5] + [3.0] * 8, "dd_5y_pct": [np.nan, -80.0, -80.0] + [-10.0] * 7,
        "f7": [np.nan, 2.0, 5.0] + [4.0] * 7, "mom_12_1": range(10), "hi52": range(10),
        "vol60": range(10),
    })
    f = ltr.flags(df)
    assert not f["H1a"].iloc[0] and not f["H1b"].iloc[0] and not f["H2a"].iloc[0]
    assert f["H1b"].iloc[1]
    assert f["H2b"].iloc[1] and not f["H2b"].iloc[2]
    assert f["H4b"].iloc[1]
    assert f["H8"].iloc[9] and not f["H8"].iloc[0]


def test_composite_requires_value():
    df = pd.DataFrame({"value_sn_z": [1.0, np.nan], "gpa_z": [np.nan, 1.0]})
    c = ltr.composite(df, "gpa_z")
    assert c.iloc[0] == 0.5 and np.isnan(c.iloc[1])
