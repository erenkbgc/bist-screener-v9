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
                         lambda t, d, ratio_profile=None: {f"c{i}": 1 for i in range(6)} | {f"c{i}": 0 for i in range(6, 9)})
    universe_rows = [{"ticker": "AAA", "regulator": "SPK_TFRS", "ratio_profile": "industrial"}]
    rows = piotroski_mod.calculate_piotroski_scores("2026-09-10", universe_rows)
    assert rows[0]["criteria_met"] == 6
    assert rows[0]["criteria_computable"] == 9
    assert abs(rows[0]["normalized_score"] - 6 / 9) < 1e-9


def test_piotroski_nominal_basis_nulls_criterion_9_due_to_inflation_distortion(temp_db, monkeypatch):
    """inflation_basis_truthful_labeling (v12 T0-3): Is Yatirim beslemesi nominal/
    tarihi maliyetli oldugundan, yuksek enflasyonda aktif devir hizi (kriter 9)
    mekanik olarak siser ve guvenilmezdir. Nominal bazda kriter 9 None yapilmalidir."""
    monkeypatch.setattr(bist_mcp, "get_piotroski_raw_criteria",
                         lambda t, d, ratio_profile=None: {f"criterion_{i}": 1 for i in range(1, 10)})
    universe_rows = [{"ticker": "NOM1", "regulator": "SPK_TFRS", "ratio_profile": "industrial"}]
    fundamentals_by_ticker = {"NOM1": {"reporting_basis": "nominal"}}

    rows = piotroski_mod.calculate_piotroski_scores("2026-09-17", universe_rows, fundamentals_by_ticker)
    assert rows[0]["criteria_computable"] == 8  # 9 kriterden kriter_9 None oldu
    assert rows[0]["criteria_met"] == 8
    assert abs(rows[0]["normalized_score"] - 1.0) < 1e-9


def test_piotroski_basis_break_nulls_all_five_comparative_criteria(temp_db, monkeypatch):
    """Baz kirigi oldugunda tum donem-karsilastirmali kriterler (3, 5, 6, 8, 9) None olur;
    kalan 4 tek-donemli kriter (1, 2, 4, 7) hesaplanabilir kalir."""
    monkeypatch.setattr(bist_mcp, "get_piotroski_raw_criteria",
                         lambda t, d, ratio_profile=None: {f"criterion_{i}": 1 for i in range(1, 10)})
    universe_rows = [{"ticker": "BRK2", "regulator": "SPK_TFRS", "ratio_profile": "industrial",
                       "prior_reporting_basis": "unknown"}]  # unknown -> basis_break = True

    rows = piotroski_mod.calculate_piotroski_scores("2026-09-17", universe_rows)
    assert rows[0]["criteria_computable"] == 4  # 1, 2, 4, 7
    assert rows[0]["criteria_met"] == 4
    assert abs(rows[0]["normalized_score"] - 1.0) < 1e-9

