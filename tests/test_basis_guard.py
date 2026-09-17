"""basis_guard testi."""
from core.basis_guard import resolve_reporting_basis, basis_break, is_scorable, unknown_ratio


def test_bddk_resolves_nominal():
    assert resolve_reporting_basis("BDDK", "2026-06-30") == "nominal"


def test_spk_tfrs_resolves_nominal():
    """inflation_basis_truthful_labeling (v12 T0-3): Is Yatirim beslemesi nominal/
    tarihi maliyetli oldugundan SPK_TFRS icin durust etiket 'nominal'dir."""
    assert resolve_reporting_basis("SPK_TFRS", "2026-06-30") == "nominal"


def test_unknown_regulator_resolves_unknown():
    assert resolve_reporting_basis("SOMETHING_ELSE", "2026-06-30") == "unknown"


def test_basis_break_between_different_basis():
    assert basis_break("nominal", "adjusted") is True
    assert basis_break("adjusted", "adjusted") is False


def test_basis_break_when_unknown_involved():
    assert basis_break("unknown", "adjusted") is True


def test_is_scorable():
    assert is_scorable("adjusted") is True
    assert is_scorable("nominal") is True
    assert is_scorable("unknown") is False


def test_unknown_ratio_computation():
    rows = [{"reporting_basis": "adjusted"}, {"reporting_basis": "unknown"},
            {"reporting_basis": "nominal"}, {"reporting_basis": "unknown"}]
    assert unknown_ratio(rows) == 0.5


def test_unknown_ratio_empty_is_zero():
    assert unknown_ratio([]) == 0.0


def test_unfetchable_statements_result_in_unknown_basis_and_unscorable():
    """testing_additions_required: mali tablo cekilemeyen bir senaryoda
    reporting_basis='unknown' ve is_scorable()=False donmeli."""
    basis = resolve_reporting_basis("INVALID_REGULATOR", None)
    assert basis == "unknown"
    assert is_scorable(basis) is False


def test_basis_break_called_in_piotroski_for_period_comparative_criteria(temp_db, monkeypatch):
    """testing_additions_required: basis_break() donem-karsilastirmali bir kriter
    hesaplanirken GERCEKTEN cagrilmali -- baz kirigi varsa (nominal vs adjusted)
    donem-karsilastirmali tum kriterler (3, 5, 6, 8, 9) None yapilir."""
    from core import piotroski as piotroski_mod
    from bist_mcp import server as bist_mcp

    # Tum 9 kriter 1 donuyor olsun
    monkeypatch.setattr(bist_mcp, "get_piotroski_raw_criteria",
                         lambda t, d, ratio_profile=None: {f"criterion_{i}": 1 for i in range(1, 10)})

    # Onceki donem 'adjusted' ama cari donem 'nominal' -> basis_break=True
    universe_rows = [{"ticker": "BRK1", "regulator": "SPK_TFRS", "ratio_profile": "industrial",
                       "prior_reporting_basis": "adjusted"}]
    fundamentals_by_ticker = {"BRK1": {"reporting_basis": "nominal"}}

    rows = piotroski_mod.calculate_piotroski_scores("2026-09-17", universe_rows, fundamentals_by_ticker)
    assert len(rows) == 1
    # 9 kriterden 5'i donem-karsilastirmali (3, 5, 6, 8, 9) -> baz kirigi yuzunden None oldu.
    # Geriye kalan tek-donemli kriterler (1, 2, 4, 7) = 4 kriter kalir.
    assert rows[0]["criteria_computable"] == 4
    assert rows[0]["criteria_met"] == 4
    assert abs(rows[0]["normalized_score"] - 1.0) < 1e-9

