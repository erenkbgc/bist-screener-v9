"""thesis_invalidation_monitor: thesis_card.invalidation_condition'i
makine-okunabilir bir kurala cevirir ve evaluate_past_predictions sirasinda kontrol eder.

language_rule: Bu bir SATIS SINYALI degildir, bir UYARIDIR. Emir cumlesi kullanilmaz.
"""
from __future__ import annotations

from core import db

_FIELD_LOOKUP = {
    "excess_over_hurdle_pct": ("predictions", "excess_over_hurdle_pct"),
    "piotroski_normalized_score": ("piotroski_scores", "normalized_score"),
    "confidence": ("scores", "confidence"),
    "reporting_basis": ("fundamentals", "reporting_basis"),
    "tedbir_level": ("universe_snapshot", "tedbir_level"),
}


def create_invalidation_condition(as_of_date: str, ticker: str, field: str, operator: str, value) -> None:
    """Ayni ticker/kosul icin zaten ACIK (henuz tetiklenmemis, cozulmemis) bir
    kayit varsa yeni bir tane daha eklenmez -- aksi halde ayni aday art arda
    birden fazla gun tahmin uretince rapor 'Bozulan Tezler' bolumunde ayni
    ticker/kosulu birden fazla kez gosterir."""
    if field not in _FIELD_LOOKUP:
        raise ValueError(f"Bilinmeyen invalidation alani: {field}")

    conn = db.get_connection()
    try:
        existing = conn.execute(
            """SELECT 1 FROM invalidation_checks
               WHERE ticker=? AND condition_field=? AND condition_operator=? AND condition_value=?
                 AND resolved=0 AND triggered_at IS NULL LIMIT 1""",
            (ticker, field, operator, str(value)),
        ).fetchone()
        if existing:
            return
        conn.execute(
            """INSERT INTO invalidation_checks (as_of_date, ticker, condition_field, condition_operator,
               condition_value, triggered_at, resolved)
               VALUES (?, ?, ?, ?, ?, NULL, 0)""",
            (as_of_date, ticker, field, operator, str(value)),
        )
        conn.commit()
    finally:
        conn.close()


def _current_value(ticker: str, field: str, as_of_date: str):
    table, column = _FIELD_LOOKUP[field]
    rows = db.query(
        f"SELECT {column} AS v FROM {table} WHERE ticker=? AND as_of_date<=? ORDER BY as_of_date DESC LIMIT 1",
        (ticker, as_of_date),
    )
    return rows[0]["v"] if rows else None


def _evaluate(current, operator: str, target: str) -> bool:
    if current is None:
        return False
    if operator == "changed_to":
        return str(current) == target
    try:
        current_f, target_f = float(current), float(target)
    except (TypeError, ValueError):
        return False
    if operator == "<":
        return current_f < target_f
    if operator == ">":
        return current_f > target_f
    if operator == "==":
        return current_f == target_f
    raise ValueError(f"Bilinmeyen operator: {operator}")


def check_thesis_invalidation(as_of_date: str) -> list[dict]:
    open_checks = db.query(
        "SELECT rowid, * FROM invalidation_checks WHERE resolved=0 AND triggered_at IS NULL"
    )
    triggered = []
    conn = db.get_connection()
    try:
        for row in open_checks:
            current = _current_value(row["ticker"], row["condition_field"], as_of_date)
            if _evaluate(current, row["condition_operator"], row["condition_value"]):
                conn.execute(
                    "UPDATE invalidation_checks SET triggered_at=? WHERE rowid=?",
                    (as_of_date, row["rowid"]),
                )
                triggered.append({
                    "ticker": row["ticker"], "condition_field": row["condition_field"],
                    "condition_operator": row["condition_operator"], "condition_value": row["condition_value"],
                    "current_value": current, "triggered_at": as_of_date,
                })
        conn.commit()
    finally:
        conn.close()
    return triggered
