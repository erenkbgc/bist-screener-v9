"""decision_diff testi."""
from core import db
from core.decision_diff import diff_against_previous_run


def _insert_score(as_of_date, ticker, state):
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO scores (as_of_date, ticker, bucket, candidate_state) VALUES (?, ?, ?, ?)""",
            (as_of_date, ticker, "long_term", state),
        )
        conn.commit()
    finally:
        conn.close()


def test_first_run_has_no_previous_date(temp_db):
    _insert_score("2026-09-10", "AAA", "OPPORTUNITY")
    result = diff_against_previous_run("2026-09-10")
    assert result["previous_as_of_date"] is None
    assert "AAA" in result["entered"]


def test_entered_and_exited_detected(temp_db):
    _insert_score("2026-09-10", "AAA", "OPPORTUNITY")
    _insert_score("2026-09-10", "BBB", "WATCHLIST")
    _insert_score("2026-09-11", "AAA", "OPPORTUNITY")
    _insert_score("2026-09-11", "CCC", "STRONG_OPPORTUNITY")

    result = diff_against_previous_run("2026-09-11")
    assert result["entered"] == ["CCC"]
    assert result["exited"] == ["BBB"]


def test_no_action_candidates_excluded_from_diff(temp_db):
    _insert_score("2026-09-10", "AAA", "NO_ACTION")
    result = diff_against_previous_run("2026-09-10")
    assert "AAA" not in result["entered"]
