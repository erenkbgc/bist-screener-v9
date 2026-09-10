"""dashboard read-only testi, dashboard tutarlilik testi."""
import re
from pathlib import Path

from core import db

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_source_has_no_write_statements():
    source = (REPO_ROOT / "dashboard.py").read_text(encoding="utf-8")
    # yorum/docstring disi gercek SQL metinlerinde INSERT/UPDATE/DELETE aranir
    forbidden = re.compile(r"\b(INSERT INTO|UPDATE\s+\w+\s+SET|DELETE FROM)\b", re.IGNORECASE)
    assert not forbidden.search(source)


def test_dashboard_uses_read_only_connection():
    source = (REPO_ROOT / "dashboard.py").read_text(encoding="utf-8")
    assert "read_only=True" in source
    # build_report_payload core/db.query (yazma izinli baglanti) kullanir; dashboard
    # bunu KULLANMAMALI (aciklayici yorumlarda gecmesi sorun degil, gercek bir
    # cagri -- "build_report_payload(" -- OLMAMALI).
    assert "build_report_payload(" not in source


def test_dashboard_reads_same_rows_as_direct_query(temp_db):
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO scores (as_of_date, ticker, bucket, candidate_state, final_score) VALUES (?, ?, ?, ?, ?)",
        ("2026-09-10", "AAA", "long_term", "OPPORTUNITY", 0.42),
    )
    conn.commit()
    conn.close()

    ro_conn = db.get_connection(read_only=True)
    try:
        rows = [dict(r) for r in ro_conn.execute(
            "SELECT * FROM scores WHERE as_of_date=?", ("2026-09-10",)
        ).fetchall()]
    finally:
        ro_conn.close()

    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAA"
    assert rows[0]["final_score"] == 0.42


def test_read_only_connection_rejects_writes(temp_db):
    ro_conn = db.get_connection(read_only=True)
    try:
        import sqlite3
        import pytest
        with pytest.raises(sqlite3.OperationalError):
            ro_conn.execute(
                "INSERT INTO scores (as_of_date, ticker, bucket, candidate_state) VALUES (?, ?, ?, ?)",
                ("2026-09-10", "ZZZ", "long_term", "NO_ACTION"),
            )
    finally:
        ro_conn.close()
