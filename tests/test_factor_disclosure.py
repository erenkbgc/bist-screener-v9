"""tests/test_factor_disclosure.py: Tests for factor disclosure and score contribution breakdown."""
from __future__ import annotations

import pytest

from core import db
from core.factor_disclosure import (
    compute_and_save_factor_contributions,
    explain_candidate_score,
    get_factor_contributions_from_db,
    load_scoring_weights,
)


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()


def test_load_scoring_weights():
    weights = load_scoring_weights()
    assert weights["valuation_z"] == 0.50
    assert weights["catalyst_score"] == 0.25
    assert weights["ownership_quality_z"] == 0.15
    assert weights["low_vol_z"] == 0.10
    assert sum(weights.values()) == 1.0


def test_explain_candidate_score_mixed():
    cand = {
        "ticker": "FORTE",
        "bucket": "long_term",
        "valuation_z": 2.0,
        "catalyst_score": 1.0,
        "ownership_z": -1.0,
        "low_vol_z": 0.5,
    }
    res = explain_candidate_score(cand)
    # val: 2.0 * 0.50 = 1.0
    # cat: 1.0 * 0.25 = 0.25
    # own: -1.0 * 0.15 = -0.15
    # vol: 0.5 * 0.10 = 0.05
    # total = 1.0 + 0.25 - 0.15 + 0.05 = 1.15
    assert res["valuation_contrib"] == 1.0
    assert res["catalyst_contrib"] == 0.25
    assert res["ownership_contrib"] == -0.15
    assert res["low_vol_contrib"] == 0.05
    assert res["final_score"] == 1.15

    assert "Değerleme" in res["top_positive_factor"]
    assert "Ortaklık" in res["top_negative_factor"]
    assert "desteklenirken" in res["explanation"]
    assert "baskılamıştır" in res["explanation"]


def test_explain_candidate_score_all_positive():
    cand = {
        "ticker": "POSITIVE_STOCK",
        "bucket": "long_term",
        "valuation_z": 1.5,
        "catalyst_score": 2.0,
        "ownership_z": 1.0,
        "low_vol_z": 1.0,
    }
    res = explain_candidate_score(cand)
    assert res["top_negative_factor"] == "Yok (Negatif etki yok)"
    assert "tarafından pozitif yönde desteklenmiştir" in res["explanation"]


def test_compute_and_save_factor_contributions_db():
    candidates = [
        {
            "ticker": "DISC_A",
            "bucket": "long_term",
            "candidate_state": "STRONG_OPPORTUNITY",
            "valuation_z": 1.2,
            "catalyst_score": 0.8,
            "ownership_z": 0.4,
            "low_vol_z": 0.1,
        },
        {
            "ticker": "DISC_B",
            "bucket": "short_term",
            "candidate_state": "NO_ACTION",  # should be skipped
            "valuation_z": -0.5,
            "catalyst_score": 0.0,
            "ownership_z": 0.0,
            "low_vol_z": 0.0,
        },
    ]

    saved = compute_and_save_factor_contributions(candidates, as_of_date="2027-05-20", save_to_db=True)
    assert len(saved) == 1
    assert saved[0]["ticker"] == "DISC_A"

    db_rows = get_factor_contributions_from_db("2027-05-20")
    assert len(db_rows) == 1
    assert db_rows[0]["ticker"] == "DISC_A"
    assert db_rows[0]["final_score"] > 0
