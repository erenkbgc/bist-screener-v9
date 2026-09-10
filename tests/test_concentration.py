"""concentration testi."""
from core.concentration import check_concentration


def test_warns_when_ratio_profile_over_50pct():
    candidates = [{"ratio_profile": "industrial", "sector": "XGIDA"} for _ in range(6)] + \
                 [{"ratio_profile": "bank", "sector": "XBANK"} for _ in range(4)]
    warnings = check_concentration(candidates)
    assert any(w["dimension"] == "ratio_profile" and w["value"] == "industrial" for w in warnings)


def test_no_warning_when_balanced():
    candidates = [{"ratio_profile": "industrial", "sector": "XGIDA"} for _ in range(3)] + \
                 [{"ratio_profile": "bank", "sector": "XBANK"} for _ in range(3)] + \
                 [{"ratio_profile": "holding", "sector": "XHOLD"} for _ in range(3)]
    warnings = check_concentration(candidates)
    assert warnings == []


def test_empty_candidates_no_warning():
    assert check_concentration([]) == []
