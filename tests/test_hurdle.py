"""hurdle testi."""
from core.hurdle import compute_all, sensitivity_table


def test_hurdle_gate_passes_when_excess_positive():
    macro = {"bond_2y_pct": 39.6, "cpi_yearend_expectation_pct": 29.4,
             "usdtry_spot": 48.4, "usdtry_12m_expectation": 57.4}
    result = compute_all(100, 130, 180, macro)
    assert result["passes_gate"] is True
    assert result["excess_over_hurdle_pct"] > 0


def test_hurdle_gate_fails_when_excess_negative():
    macro = {"bond_2y_pct": 39.6, "cpi_yearend_expectation_pct": 29.4,
             "usdtry_spot": 48.4, "usdtry_12m_expectation": 57.4}
    result = compute_all(100, 101, 180, macro)
    assert result["passes_gate"] is False


def test_hurdle_rate_scales_with_horizon():
    macro = {"bond_2y_pct": 36.5, "cpi_yearend_expectation_pct": 29.4,
             "usdtry_spot": 48.4, "usdtry_12m_expectation": 57.4}
    short = compute_all(100, 110, 20, macro)
    long = compute_all(100, 110, 180, macro)
    assert short["hurdle_rate_pct"] < long["hurdle_rate_pct"]


def test_sensitivity_table_counts_decrease_as_shock_increases():
    candidates = [{"expected_roi_pct": 15, "hurdle_rate_pct": 10},
                  {"expected_roi_pct": 12, "hurdle_rate_pct": 10}]
    table = sensitivity_table(candidates)
    assert table[-100] >= table[300]
