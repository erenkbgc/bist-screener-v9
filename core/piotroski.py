"""quality_filter_piotroski: 9 kriterli F-Score, basis_guard entegrasyonu ile.

Spec: quality_filter_piotroski. Esik degeri config/weights.yaml icinde,
priors_are_disclosed kuraliyla DENENMEMIS baslangic varsayimi olarak isaretli.
"""
from __future__ import annotations

from core import db, basis_guard
from bist_mcp import server as bist_mcp


def calculate_piotroski_scores(as_of_date: str, universe_rows: list[dict],
                               fundamentals_by_ticker: dict | None = None) -> list[dict]:
    rows = []
    for u in universe_rows:
        ticker = u["ticker"]
        fnd = fundamentals_by_ticker.get(ticker) if fundamentals_by_ticker else None
        if fnd and fnd.get("reporting_basis"):
            reporting_basis = fnd["reporting_basis"]
        else:
            reporting_basis = basis_guard.resolve_reporting_basis(u["regulator"], None)

        if not basis_guard.is_scorable(reporting_basis):
            rows.append({"as_of_date": as_of_date, "ticker": ticker, "criteria_met": 0,
                         "criteria_computable": 0, "normalized_score": None,
                         "null_reason": "unknown_reporting_basis"})
            continue

        raw = dict(bist_mcp.get_piotroski_raw_criteria(ticker, as_of_date, u["ratio_profile"]))

        # inflation_basis_truthful_labeling (v12 T0-3):
        # 1. basis_break kontrolu: cari donem ile onceki donem arasinda baz farkliligi
        #    varsa (orn. nominal vs adjusted) veya onceki donem baz bilgisi yoksa
        #    tum donem-karsilastirmali kriterler (3, 5, 6, 8, 9) None yapilir.
        prior_basis = u.get("prior_reporting_basis", reporting_basis)
        if basis_guard.basis_break(reporting_basis, prior_basis):
            for c in ("criterion_3", "criterion_5", "criterion_6", "criterion_8", "criterion_9"):
                if c in raw:
                    raw[c] = None

        # 2. Nominal besleme enflasyon kirlenmesi: Is Yatirim beslemesi nominal/tarihi
        #    maliyetli oldugundan, yuksek enflasyonda hasilat cari TL ile artarken
        #    aktifler tarihi maliyetle kalir. Aktif devir hizi (kriter 9 = hasilat / aktifler)
        #    bu yuzden mekanik olarak siser ve neredeyse her sirkete yapay puan verir.
        #    Nominal bazda kriter 9 guvenilir olmadigindan hesaplanamaz (None) kabul edilir.
        if reporting_basis == "nominal" and "criterion_9" in raw:
            raw["criterion_9"] = None

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
