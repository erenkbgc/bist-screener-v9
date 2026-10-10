from core import diagnostics as dg


def _rows(closes):
    return [{"date": f"d{i}", "close": c, "adj_close": c} for i, c in enumerate(closes)]


def test_crash_from_5y_peak_flagged():
    closes = [100.0] * 300 + [50.0] * 300 + [15.0] * 700
    out = dg.diagnose({"eps_ttm": 1.0}, _rows(closes))
    assert out["drawdown_from_5y_peak_pct"] == -85.0
    assert out["max_drawdown_5y_pct"] == -85.0
    assert out["dist_52w_high_pct"] == 0.0
    assert "crash_5y" in out["risk_flag_codes"]
    assert "far_52w" not in out["risk_flag_codes"]


def test_peak_older_than_5y_ignored():
    closes = [1000.0] * 100 + [100.0] * dg.LOOKBACK_DAYS
    out = dg.price_diagnostics(_rows(closes))
    assert out["drawdown_from_5y_peak_pct"] == 0.0
    assert out["price_history_years"] == 5.0


def test_max_drawdown_after_recovery():
    closes = [100.0] * 300 + [30.0] * 300 + [100.0] * 700
    out = dg.price_diagnostics(_rows(closes))
    assert out["drawdown_from_5y_peak_pct"] == 0.0
    assert out["max_drawdown_5y_pct"] == -70.0


def test_adj_close_used_over_raw():
    # 1:1 bedelsiz: ham kapanis yariya iner, duzeltilmis seri duz kalir.
    rows = [{"close": 100.0, "adj_close": 50.0}] * 300 + [{"close": 50.0, "adj_close": 50.0}] * 300
    out = dg.price_diagnostics(rows)
    assert out["drawdown_from_5y_peak_pct"] == 0.0


def test_loss_and_distress_flags():
    c = {"eps_ttm": -2.0, "ratio_profile": "industrial", "pb": 1.0,
         "ebitda_ttm": 100.0, "net_debt": 600.0, "net_debt_ebitda": None}
    out = dg.diagnose(c, _rows([10.0] * 1300))
    assert out["loss_flag"] is True
    assert out["distress_flag"] is True
    assert out["risk_flag_codes"] == ["loss", "distress"]


def test_distress_negative_equity_and_coverage():
    assert dg.distress_flag({"pb": -0.5}) is True
    assert dg.distress_flag({"ebitda_ttm": 10.0, "net_debt": 5.0, "financial_expenses_ttm": -20.0}) is True
    assert dg.distress_flag({"ebitda_ttm": 100.0, "net_debt": 50.0, "financial_expenses_ttm": 10.0}) is False


def test_bank_distress_not_applicable():
    assert dg.distress_flag({"ratio_profile": "bank", "pb": -1.0}) is None


def test_missing_data_returns_none():
    out = dg.diagnose({}, [])
    assert out["drawdown_from_5y_peak_pct"] is None
    assert out["loss_flag"] is None
    assert out["distress_flag"] is None
    assert out["risk_flags"] == []


def test_short_history_flag():
    out = dg.diagnose({"eps_ttm": 1.0}, _rows([10.0] * 500))
    assert "short_history" in out["risk_flag_codes"]


def test_flag_labels_contain_no_digits():
    # report/validate.py orphan kontrolu metindeki rakamlari payload'da arar.
    for label in dg.FLAG_LABELS.values():
        assert not any(ch.isdigit() for ch in label)
