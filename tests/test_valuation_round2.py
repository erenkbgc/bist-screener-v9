import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from research_valuation_round2 import candidate_legs, leg_parity  # noqa: E402


def _panel_and_q(**q_over):
    panel = pd.DataFrame({"date": [pd.Timestamp("2024-06-30")], "ticker": ["AAA"], "stmt_period": ["2024Q1"],
                          "mcap": [1000.0], "ep": [0.1], "bm": [0.5]})
    q = {"ticker": "AAA", "period": "2024Q1", "ttm_ni_parent": 100.0, "ttm_net_income": 125.0,
         "ttm_deferred_tax": 40.0, "equity_parent": 500.0, "equity": 600.0, "intangibles": 50.0, "goodwill": 30.0}
    q.update(q_over)
    return panel, pd.DataFrame([q])


def test_ep_xdt_removes_parent_share_of_deferred_tax():
    panel, q = _panel_and_q()
    p = candidate_legs(panel, q)
    # parent share 100/125 = 0.8 -> NI ex DT = 100 - 0.8 * 40 = 68
    assert p.loc[0, "ep_xdt"] == pytest.approx(0.068)
    assert p.loc[0, "ep_base"] == pytest.approx(0.1)


def test_ep_xdt_missing_deferred_tax_is_zero_and_share_clipped():
    panel, q = _panel_and_q(ttm_deferred_tax=np.nan)
    assert candidate_legs(panel, q).loc[0, "ep_xdt"] == pytest.approx(0.1)
    panel, q = _panel_and_q(ttm_net_income=50.0)  # share 2.0 -> clipped to 1
    assert candidate_legs(panel, q).loc[0, "ep_xdt"] == pytest.approx((100 - 40) / 1000)


def test_bm_tan_subtracts_intangibles_and_goodwill_and_drops_nonpositive():
    panel, q = _panel_and_q()
    assert candidate_legs(panel, q).loc[0, "bm_tan"] == pytest.approx(0.42)
    panel, q = _panel_and_q(intangibles=600.0)
    assert np.isnan(candidate_legs(panel, q).loc[0, "bm_tan"])


def test_leg_parity_detects_mismatch():
    panel, q = _panel_and_q()
    assert leg_parity(candidate_legs(panel, q))["ok"]
    panel["ep"] = 0.2
    assert not leg_parity(candidate_legs(panel, q))["ok"]
