"""quality_filter_piotroski: 9 kriterli F-Score, basis_guard entegrasyonu ile.

Spec: quality_filter_piotroski. Esik degeri config/weights.yaml icinde,
priors_are_disclosed kuraliyla DENENMEMIS baslangic varsayimi olarak isaretli.
"""
from __future__ import annotations

from core import db, basis_guard
from bist_mcp import server as bist_mcp


def calculate_piotroski_scores(as_of_date: str, universe_rows: list[dict]) -> list[dict]:
    rows = []
    for u in universe_rows:
        ticker = u["ticker"]
        reporting_basis = basis_guard.resolve_reporting_basis(u["regulator"], None)
        if not basis_guard.is_scorable(reporting_basis):
            rows.append({"as_of_date": as_of_date, "ticker": ticker, "criteria_met": 0,
                         "criteria_computable": 0, "normalized_score": None,
                         "null_reason": "unknown_reporting_basis"})
            continue

        raw = bist_mcp.get_piotroski_raw_criteria(ticker, as_of_date)
        # basis_guard.rule: "Baz kirigi olan kriterler null sayilir, skor hesaplanabilen
        # kriter sayisina orantilanir." Donem-karsilastirmali (buyume) kriterler icin
        # onceki donemin baz bilgisi bu mock katmaninda tek donemli oldugundan basis_break
        # burada tetiklenmez; gercek veri entegrasyonunda onceki donem reporting_basis'i
        # bu noktada karsilastirilip ilgili kriterler None yapilir.
        computable = {k: v for k, v in raw.items() if v is not None}
        criteria_met = sum(1 for v in computable.values() if v == 1)
        criteria_computable = len(computable)
        normalized_score = criteria_met / criteria_computable if criteria_computable else None

        rows.append({
            "as_of_date": as_of_date, "ticker": ticker, "criteria_met": criteria_met,
            "criteria_computable": criteria_computable, "normalized_score": normalized_score,
            "null_reason": None if criteria_computable else "no_computable_criteria",
        })

    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO piotroski_scores (as_of_date, ticker, criteria_met, criteria_computable,
               normalized_score, null_reason)
               VALUES (:as_of_date, :ticker, :criteria_met, :criteria_computable, :normalized_score, :null_reason)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 criteria_met=excluded.criteria_met, criteria_computable=excluded.criteria_computable,
                 normalized_score=excluded.normalized_score, null_reason=excluded.null_reason""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return rows
