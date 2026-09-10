"""decision_diff_engine: onceki kosuya gore ne degisti."""
from __future__ import annotations

from core import db


def diff_against_previous_run(as_of_date: str) -> dict:
    """scores tablosunu okur (bu asamada zaten persist edilmis olmasi gerekir,
    bkz. architecture.execution_order: ranking/scoring, decision_diff'ten ONCE
    calisir). Boylece bu fonksiyonun urettigi HER sayi (macro_deltas dahil)
    core/payload.py::build_report_payload icine dahil edilebilir ve
    validation_gate tarafindan dogrulanabilir."""
    prev_dates = db.query(
        "SELECT DISTINCT as_of_date FROM scores WHERE as_of_date < ? ORDER BY as_of_date DESC LIMIT 1",
        (as_of_date,),
    )
    current_rows = db.query(
        "SELECT ticker, candidate_state FROM scores WHERE as_of_date=? AND candidate_state IN "
        "('STRONG_OPPORTUNITY','OPPORTUNITY','WATCHLIST')",
        (as_of_date,),
    )
    current_tickers = {r["ticker"] for r in current_rows}

    if not prev_dates:
        return {"regime_status": "unchanged", "entered": sorted(current_tickers), "exited": [],
                "catalyst_deltas": [], "macro_deltas": [], "previous_as_of_date": None}

    prev_date = prev_dates[0]["as_of_date"]
    prev_rows = db.query(
        "SELECT ticker, candidate_state FROM scores WHERE as_of_date=? AND candidate_state IN "
        "('STRONG_OPPORTUNITY','OPPORTUNITY','WATCHLIST')",
        (prev_date,),
    )
    prev_tickers = {r["ticker"] for r in prev_rows}

    entered = sorted(current_tickers - prev_tickers)
    exited = sorted(prev_tickers - current_tickers)

    regime_rows = db.query(
        "SELECT * FROM regime_log WHERE as_of_date IN (?, ?) ORDER BY as_of_date",
        (prev_date, as_of_date),
    )
    macro_deltas = []
    if len(regime_rows) == 2:
        old, new = regime_rows[0], regime_rows[1]
        for field in ("policy_rate_pct", "bond_2y_pct", "cpi_yoy_pct", "usdtry_spot", "xu100_level"):
            if old[field] is not None and new[field] is not None and old[field] != new[field]:
                macro_deltas.append({"field": field, "from": old[field], "to": new[field]})
        regime_status = "changed" if new["regime_change_flag"] else "unchanged"
    else:
        regime_status = "unchanged"

    kap_rows = db.query(
        "SELECT ticker, category, published_at FROM kap_disclosures WHERE published_at > ? AND published_at <= ?",
        (prev_date, as_of_date),
    )
    catalyst_deltas = [{"ticker": r["ticker"], "category": r["category"], "published_at": r["published_at"]}
                       for r in kap_rows]

    return {
        "regime_status": regime_status, "entered": entered, "exited": exited,
        "catalyst_deltas": catalyst_deltas, "macro_deltas": macro_deltas,
        "previous_as_of_date": prev_date,
    }
