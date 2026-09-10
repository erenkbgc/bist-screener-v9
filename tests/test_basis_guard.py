"""basis_guard testi."""
from core.basis_guard import resolve_reporting_basis, basis_break, is_scorable, unknown_ratio


def test_bddk_resolves_nominal():
    assert resolve_reporting_basis("BDDK", "2026-06-30") == "nominal"


def test_spk_tfrs_resolves_adjusted():
    assert resolve_reporting_basis("SPK_TFRS", "2026-06-30") == "adjusted"


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
