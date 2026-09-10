"""build_report_payload: raporun/dashboard'un gosterecegi HER sayiyi tek bir
yerde toplar. no_number_without_source kurali: raporda/dashboard'da gorunen
her sayi bu payload icinde bulunmak zorunda (report/validate.py bunu dogrular).

point_in_time_fields.enforcement_rule: yalnizca effective_at <= as_of_date_cutoff
olan satirlar kullanilir.
"""
from __future__ import annotations

from core import db
from core.scoring import load_weights
from core.beta_hurdle import load_equity_risk_premium_pct
from core.evaluate import summarize_outcomes
from core.decision_diff import diff_against_previous_run


def build_report_payload(as_of_date: str) -> dict:
    as_of_date_cutoff = as_of_date

    regime = db.query("SELECT * FROM regime_log WHERE as_of_date=?", (as_of_date,))
    scores = db.query("SELECT * FROM scores WHERE as_of_date=?", (as_of_date,))
    predictions = db.query(
        "SELECT * FROM predictions WHERE as_of_date=?", (as_of_date,)
    )
    gordon = db.query("SELECT * FROM gordon_reference WHERE as_of_date=?", (as_of_date,))
    beta = db.query("SELECT * FROM beta_metrics WHERE as_of_date=?", (as_of_date,))
    sloan = db.query("SELECT * FROM earnings_quality WHERE as_of_date=?", (as_of_date,))
    piotroski = db.query("SELECT * FROM piotroski_scores WHERE as_of_date=?", (as_of_date,))
    ownership = db.query("SELECT * FROM ownership WHERE as_of_date=?", (as_of_date,))
    fundamentals = db.query(
        "SELECT * FROM fundamentals WHERE as_of_date=? AND effective_at<=?",
        (as_of_date, as_of_date_cutoff),
    )
    universe = db.query("SELECT * FROM universe_snapshot WHERE as_of_date=?", (as_of_date,))
    eligible_count = db.query(
        "SELECT COUNT(*) AS n FROM universe_snapshot WHERE as_of_date=? AND exclusion_reason IS NULL",
        (as_of_date,),
    )[0]["n"]
    scored_ticker_count = db.query(
        "SELECT COUNT(DISTINCT ticker) AS n FROM scores WHERE as_of_date=?", (as_of_date,)
    )[0]["n"]
    unscored_count = max(0, eligible_count - scored_ticker_count)
    events = db.query("SELECT * FROM upcoming_events")
    correlation_flags = db.query("SELECT * FROM correlation_flags WHERE as_of_date=?", (as_of_date,))
    dividend_sustainability = db.query(
        "SELECT * FROM dividend_sustainability WHERE as_of_date=?", (as_of_date,)
    )
    invalidation_triggered = db.query(
        "SELECT * FROM invalidation_checks WHERE triggered_at IS NOT NULL AND resolved=0"
    )

    def as_dicts(rows):
        return [dict(r) for r in rows]

    weights = load_weights()

    payload = {
        "as_of_date": as_of_date,
        "weights": {
            "valuation_z": weights["scoring_weights"]["valuation_z"],
            "catalyst_score": weights["scoring_weights"]["catalyst_score"],
            "ownership_quality_z": weights["scoring_weights"]["ownership_quality_z"],
            "piotroski_normalized_score_threshold": weights["piotroski"]["normalized_score_threshold"],
            "equity_risk_premium_pct": load_equity_risk_premium_pct(),
        },
        "regime": as_dicts(regime)[0] if regime else None,
        "scores": as_dicts(scores),
        "predictions": as_dicts(predictions),
        "gordon_reference": as_dicts(gordon),
        "beta_metrics": as_dicts(beta),
        "earnings_quality": as_dicts(sloan),
        "piotroski_scores": as_dicts(piotroski),
        "ownership": as_dicts(ownership),
        "fundamentals": as_dicts(fundamentals),
        "universe": as_dicts(universe),
        "upcoming_events": as_dicts(events),
        "correlation_flags": as_dicts(correlation_flags),
        "dividend_sustainability": as_dicts(dividend_sustainability),
        "invalidation_triggered": as_dicts(invalidation_triggered),
        "no_action_today": not any(s["candidate_state"] in ("STRONG_OPPORTUNITY", "OPPORTUNITY") for s in scores),
        "unscored_count": unscored_count,
        "evaluation_summary": summarize_outcomes(as_of_date),
        "decision_diff": diff_against_previous_run(as_of_date),
    }
    return payload


def all_numeric_tokens(payload: dict) -> set[str]:
    """validate.py'nin orphan-sayi kontrolu icin payload icindeki tum sayisal
    degerleri duz bir string kumesine cevirir."""
    tokens: set[str] = set()

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            tokens.add(format_number(obj))

    walk(payload)
    return tokens


def format_number(n: float) -> str:
    """Projedeki TEK sayi->metin bicimlendirme kurali (2 ondalik, tam sayilar
    icin ondaliksiz). report/render.py::_fmt ve core/thesis.py bu fonksiyonu
    kullanir; validate_report'un orphan taramasi hepsinin ayni string temsilini
    uretmesine dayanir -- baska hicbir yerde manuel `:.1f`/`:.2f` formati
    KULLANILMAMALIDIR."""
    if isinstance(n, int) or float(n).is_integer():
        return str(int(n))
    return f"{n:.2f}"
