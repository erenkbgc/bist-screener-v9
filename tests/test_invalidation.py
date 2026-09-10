"""invalidation monitor testi: excess_over_hurdle_pct negatife dondugunde
ilgili tahmin invalidation_checks tablosuna triggered olarak yazilmali."""
from core import db
from core.invalidation import create_invalidation_condition, check_thesis_invalidation


def test_condition_triggers_when_prediction_excess_turns_negative(temp_db):
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO predictions (as_of_date, ticker, bucket, excess_over_hurdle_pct)
               VALUES (?, ?, ?, ?)""",
            ("2026-09-10", "AAA", "long_term", 5.0),
        )
        conn.commit()
    finally:
        conn.close()

    create_invalidation_condition("2026-09-10", "AAA", "excess_over_hurdle_pct", "<", 0)
    triggered = check_thesis_invalidation("2026-09-10")
    assert triggered == []  # henuz negatif degil

    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO predictions (as_of_date, ticker, bucket, excess_over_hurdle_pct)
               VALUES (?, ?, ?, ?)""",
            ("2026-09-11", "AAA", "long_term", -2.0),
        )
        conn.commit()
    finally:
        conn.close()

    triggered = check_thesis_invalidation("2026-09-11")
    assert len(triggered) == 1
    assert triggered[0]["ticker"] == "AAA"
    assert triggered[0]["condition_field"] == "excess_over_hurdle_pct"


def test_duplicate_open_condition_not_created_twice(temp_db):
    create_invalidation_condition("2026-09-10", "BBB", "excess_over_hurdle_pct", "<", 0)
    create_invalidation_condition("2026-09-11", "BBB", "excess_over_hurdle_pct", "<", 0)
    rows = db.query("SELECT * FROM invalidation_checks WHERE ticker=?", ("BBB",))
    assert len(rows) == 1


def test_unknown_field_rejected(temp_db):
    import pytest
    with pytest.raises(ValueError):
        create_invalidation_condition("2026-09-10", "CCC", "not_a_real_field", "<", 0)
