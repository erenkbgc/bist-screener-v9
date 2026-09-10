"""piotroski testi."""
from core import piotroski as piotroski_mod
from bist_mcp import server as bist_mcp


def test_piotroski_unknown_basis_not_scored(temp_db, monkeypatch):
    universe_rows = [{"ticker": "AAA", "regulator": "FOO", "ratio_profile": "industrial"}]
    rows = piotroski_mod.calculate_piotroski_scores("2026-09-10", universe_rows)
    assert rows[0]["null_reason"] == "unknown_reporting_basis"
    assert rows[0]["normalized_score"] is None


def test_piotroski_normalized_score_computed(temp_db, monkeypatch):
    monkeypatch.setattr(bist_mcp, "get_piotroski_raw_criteria",
                         lambda t, d: {f"c{i}": 1 for i in range(6)} | {f"c{i}": 0 for i in range(6, 9)})
    universe_rows = [{"ticker": "AAA", "regulator": "SPK_TFRS", "ratio_profile": "industrial"}]
    rows = piotroski_mod.calculate_piotroski_scores("2026-09-10", universe_rows)
    assert rows[0]["criteria_met"] == 6
    assert rows[0]["criteria_computable"] == 9
    assert abs(rows[0]["normalized_score"] - 6 / 9) < 1e-9
