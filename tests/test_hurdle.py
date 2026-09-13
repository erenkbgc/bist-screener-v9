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


# --- transaction_cost_model (v10 roadmap) ---

def test_net_expected_roi_is_none_without_bid_ask():
    """bid/ask cekilemediginde (mock modda hep boyle) net_* alanlari None
    kalmali -- eksik maliyet varsayimiyla sahte-iyimser bir net getiri
    UYDURULMAZ (durustluk kurali)."""
    macro = {"bond_2y_pct": 39.6, "cpi_yearend_expectation_pct": 29.4,
             "usdtry_spot": 48.4, "usdtry_12m_expectation": 57.4}
    result = compute_all(100, 130, 180, macro)
    assert result["net_expected_roi_pct"] is None
    assert result["net_excess_over_hurdle_pct"] is None


def test_net_expected_roi_never_exceeds_gross():
    """acceptance_test (roadmap): net_expected_roi_pct her zaman
    expected_roi_pct'den kucuk veya esit olmali (maliyet asla negatif
    katki yapmamali)."""
    macro = {"bond_2y_pct": 39.6, "cpi_yearend_expectation_pct": 29.4,
             "usdtry_spot": 48.4, "usdtry_12m_expectation": 57.4}
    result = compute_all(100, 130, 180, macro, bid=99.5, ask=100.5, volume_ratio_20d=1.2)
    assert result["net_expected_roi_pct"] is not None
    assert result["net_expected_roi_pct"] <= result["expected_roi_pct"]
    assert result["net_excess_over_hurdle_pct"] <= result["excess_over_hurdle_pct"]
    assert result["transaction_cost_pct"] > 0


def test_net_expected_roi_worsens_with_low_liquidity():
    """dusuk hacimde (volume_ratio_20d kucuk) varsayilan kayma artmali ->
    net getiri daha fazla dusmeli."""
    macro = {"bond_2y_pct": 39.6, "cpi_yearend_expectation_pct": 29.4,
             "usdtry_spot": 48.4, "usdtry_12m_expectation": 57.4}
    liquid = compute_all(100, 130, 180, macro, bid=99.5, ask=100.5, volume_ratio_20d=2.0)
    illiquid = compute_all(100, 130, 180, macro, bid=99.5, ask=100.5, volume_ratio_20d=0.2)
    assert illiquid["transaction_cost_pct"] > liquid["transaction_cost_pct"]
    assert illiquid["net_expected_roi_pct"] < liquid["net_expected_roi_pct"]
