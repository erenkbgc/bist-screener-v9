"""point_in_time testi: build_report_payload/evaluate_past_predictions yalnizca
effective_at <= as_of_date_cutoff olan satirlari kullanir."""
from core import db
from core.payload import build_report_payload


def test_fundamentals_future_effective_at_excluded(temp_db):
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO fundamentals (as_of_date, ticker, period_end, reporting_basis, pe,
               effective_at) VALUES (?, ?, ?, ?, ?, ?)""",
            ("2026-09-10", "FUTURE", "2026-06-30", "adjusted", 10, "2026-09-15"),
        )
        conn.execute(
            """INSERT INTO fundamentals (as_of_date, ticker, period_end, reporting_basis, pe,
               effective_at) VALUES (?, ?, ?, ?, ?, ?)""",
            ("2026-09-10", "PAST", "2026-06-30", "adjusted", 12, "2026-09-01"),
        )
        conn.commit()
    finally:
        conn.close()

    payload = build_report_payload("2026-09-10")
    tickers = {f["ticker"] for f in payload["fundamentals"]}
    assert "PAST" in tickers
    assert "FUTURE" not in tickers
