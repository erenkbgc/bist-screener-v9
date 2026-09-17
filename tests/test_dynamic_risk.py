"""tests/test_dynamic_risk.py: Dinamik Entry / Stop-Loss / Position Sizing testleri (v12 roadmap P0-1)."""
from core.targets import compute_dynamic_risk_levels, compute_short_term_target
from core import db


def test_dynamic_entry_band_calculation():
    current_price = 100.0
    atr20 = 4.0
    res = compute_dynamic_risk_levels(current_price=current_price, atr20=atr20)

    # entry_low = current - 0.5 * ATR20 = 100 - 2 = 98
    assert res["entry_low"] == 98.0
    # entry_high = current + 0.2 * ATR20 = 100 + 0.8 = 100.8
    assert res["entry_high"] == 100.8
    # effective_entry = 0.5 * 98 + 0.5 * 100.8 = 99.4
    assert res["effective_entry"] == 99.4


def test_dynamic_stop_loss_calculation():
    current_price = 100.0
    atr20 = 4.0
    res = compute_dynamic_risk_levels(current_price=current_price, atr20=atr20)

    # base stop = entry_low - 1.5 * ATR20 = 98.0 - 6.0 = 92.0
    assert res["stop_loss"] == 92.0


def test_dynamic_stop_loss_with_recent_swing_low():
    current_price = 100.0
    atr20 = 4.0
    # swing low lower than base stop (90 < 92) -> stop moves to swing low for wider protection
    res1 = compute_dynamic_risk_levels(current_price=current_price, atr20=atr20, recent_swing_low=90.0)
    assert res1["stop_loss"] == 90.0

    # swing low higher than base stop (94 > 92) but below entry_low (94 < 98) -> min(92, 94) = 92
    res2 = compute_dynamic_risk_levels(current_price=current_price, atr20=atr20, recent_swing_low=94.0)
    assert res2["stop_loss"] == 92.0

    # swing low higher than entry_low (invalid support for stop) -> base stop used
    res3 = compute_dynamic_risk_levels(current_price=current_price, atr20=atr20, recent_swing_low=99.0)
    assert res3["stop_loss"] == 92.0


def test_position_sizing_fixed_fractional():
    current_price = 100.0
    atr20 = 4.0
    # effective_entry = 99.4, stop_loss = 92.0
    # risk_per_share = 7.4
    # risk_pct = 7.4 / 99.4 ~= 0.074446... (~7.44%)
    # with account_risk_pct = 1.5%: position_size_pct = 1.5 / 0.074446 ~= 20.15%
    res = compute_dynamic_risk_levels(current_price=current_price, atr20=atr20, account_risk_pct=1.5)
    assert 20.0 <= res["position_size_pct"] <= 20.3


def test_position_sizing_capped_at_max():
    # If ATR is extremely small, risk distance is tiny, position size shouldn't exceed max cap
    current_price = 100.0
    atr20 = 0.1
    res = compute_dynamic_risk_levels(current_price=current_price, atr20=atr20, max_position_size_pct=25.0)
    assert res["position_size_pct"] == 25.0


def test_missing_or_zero_atr_fallback():
    current_price = 100.0
    # Missing atr20 falls back to 2% volatility proxy (atr = 2.0)
    res = compute_dynamic_risk_levels(current_price=current_price, atr20=None)
    assert res["entry_low"] == 99.0
    assert res["entry_high"] == 100.4
    assert res["stop_loss"] > 0
    assert res["position_size_pct"] > 0


def test_non_positive_price_defensive():
    res = compute_dynamic_risk_levels(current_price=0.0, atr20=2.0)
    assert res["position_size_pct"] == 0.0
    assert res["stop_loss"] == 0.0


def test_compute_short_term_target_includes_dynamic_fields():
    res = compute_short_term_target(current_price=100.0, atr20=2.0, sma20=98.0)
    assert "entry_low" in res
    assert "entry_high" in res
    assert "dynamic_stop_loss" in res
    assert "position_size_pct" in res
    # backward-compatible fields
    assert res["entry_price"] == 98.0
    assert res["target_price"] == 100.0 + 2.5 * 2.0
    assert res["stop_loss"] == 100.0 - 1.2 * 2.0


def test_db_schema_and_persistence(temp_db):
    conn = db.get_connection()
    # Check predictions table info
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(predictions)").fetchall()}
    assert "entry_low" in cols
    assert "entry_high" in cols
    assert "position_size_pct" in cols

    # Test insert and read
    conn.execute(
        """INSERT INTO predictions (as_of_date, ticker, bucket, entry_price, target_price,
           stop_loss, horizon_days, expected_roi_pct, hurdle_rate_pct, excess_over_hurdle_pct,
           real_return_pct, usd_return_pct, rationale_hash, current_price, price_source,
           entry_low, entry_high, position_size_pct)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-09-17", "THYAO", "long_term", 300.0, 450.0, 275.0, 180, 50.0, 25.0, 25.0,
         35.0, 20.0, "hash123", 300.0, "live", 290.0, 305.0, 18.5)
    )
    conn.commit()

    row = conn.execute("SELECT entry_low, entry_high, position_size_pct FROM predictions WHERE ticker='THYAO'").fetchone()
    assert row["entry_low"] == 290.0
    assert row["entry_high"] == 305.0
    assert row["position_size_pct"] == 18.5
    conn.close()
