"""evaluate_past_predictions testi: xu100_benchmark_integration (v10 roadmap).

Onceki davranis xu100_return_pct icin sabit bir 0.0 yer tutucu kullaniyordu;
bu artik macro_mcp.get_index_return_pct uzerinden gercek/mock endeks
serisinden gelmeli ve cekilemedigi durumda satir SESSIZCE ATLANMALI (sahte
0.0 UYDURULMAMALI, bkz. core/evaluate.py dosya-basi notu)."""
from core import db
from core.evaluate import evaluate_past_predictions
from core import mock_data as md


def _insert_matured_prediction(as_of_date: str, ticker: str, horizon_days: int, entry_price: float):
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO predictions (as_of_date, ticker, bucket, entry_price, target_price,
               stop_loss, horizon_days, expected_roi_pct, hurdle_rate_pct, excess_over_hurdle_pct,
               real_return_pct, usd_return_pct, rationale_hash, current_price, price_source)
               VALUES (?, ?, 'long_term', ?, ?, NULL, ?, 10, 5, 5, NULL, NULL, 'x', ?, 'last_close')""",
            (as_of_date, ticker, entry_price, entry_price * 1.1, horizon_days, entry_price),
        )
        conn.commit()
    finally:
        conn.close()


def test_xu100_return_comes_from_real_series_not_hardcoded_zero(temp_db):
    pred_date = "2026-01-05"
    eval_date = "2026-01-25"  # pred_date + 20 gun (horizon)
    _insert_matured_prediction(pred_date, "AAA", 20, 100.0)

    result = evaluate_past_predictions(eval_date, lookback_months=6)

    rows = db.query("SELECT * FROM outcomes WHERE ticker=?", ("AAA",))
    assert len(rows) == 1
    row = rows[0]

    expected_xu100 = md.mock_index_return_pct("XU100", pred_date, eval_date)
    assert row["xu100_return_pct"] == expected_xu100
    assert row["xu100_return_pct"] != 0.0  # eski hardcoded yer tutucu degil
    assert row["excess_vs_index_pct"] == row["return_pct"] - expected_xu100
    assert result["by_horizon"][20] is not None


def test_row_skipped_when_index_return_unavailable(temp_db, monkeypatch):
    """Endeks serisi cekilemezse (None) satir sessizce atlanir, 0.0 uydurulmaz
    -- ve bir sonraki kosuda tekrar denenebilsin diye 'islendi' olarak
    isaretlenmez (outcomes'a hic yazilmaz)."""
    pred_date = "2026-01-05"
    eval_date = "2026-01-25"
    _insert_matured_prediction(pred_date, "BBB", 20, 100.0)

    import core.evaluate as evaluate_mod
    monkeypatch.setattr(evaluate_mod.macro_mcp, "get_index_return_pct", lambda *a, **k: None)

    evaluate_past_predictions(eval_date, lookback_months=6)

    rows = db.query("SELECT * FROM outcomes WHERE ticker=?", ("BBB",))
    assert rows == []
