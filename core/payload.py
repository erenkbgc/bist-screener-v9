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
from core.dcf import GROWTH_LOW_PCT, GROWTH_BASE_PCT, GROWTH_HIGH_PCT, load_corporate_tax_rate_pct
from core.evaluate import summarize_outcomes
from core.decision_diff import diff_against_previous_run


def build_report_payload(
    as_of_date: str,
    concentration_warnings: list[dict] | None = None,
    portfolio_summary: dict | None = None,
    trend_forecast: dict | None = None,
    passing_candidates: list[dict] | None = None,
) -> dict:
    as_of_date_cutoff = as_of_date

    regime = db.query("SELECT * FROM regime_log WHERE as_of_date=?", (as_of_date,))
    scores = db.query("SELECT * FROM scores WHERE as_of_date=?", (as_of_date,))
    predictions = db.query(
        "SELECT * FROM predictions WHERE as_of_date=?", (as_of_date,)
    )
    gordon = db.query("SELECT * FROM gordon_reference WHERE as_of_date=?", (as_of_date,))
    dcf = db.query("SELECT * FROM dcf_reference WHERE as_of_date=?", (as_of_date,))
    beta = db.query("SELECT * FROM beta_metrics WHERE as_of_date=?", (as_of_date,))
    sloan = db.query("SELECT * FROM earnings_quality WHERE as_of_date=?", (as_of_date,))
    piotroski = db.query("SELECT * FROM piotroski_scores WHERE as_of_date=?", (as_of_date,))
    ownership = db.query("SELECT * FROM ownership WHERE as_of_date=?", (as_of_date,))
    fundamentals = db.query(
        "SELECT * FROM fundamentals WHERE as_of_date=? AND effective_at<=?",
        (as_of_date, as_of_date_cutoff),
    )
    universe = db.query("SELECT * FROM universe_snapshot WHERE as_of_date=?", (as_of_date,))
    factor_contributions = db.query("SELECT * FROM factor_contributions WHERE as_of_date=?", (as_of_date,))
    portfolio_allocations = db.query("SELECT * FROM portfolio_allocations WHERE as_of_date=?", (as_of_date,))
    eligible_count = db.query(
        "SELECT COUNT(*) AS n FROM universe_snapshot WHERE as_of_date=? AND exclusion_reason IS NULL",
        (as_of_date,),
    )[0]["n"]
    scored_ticker_count = db.query(
        "SELECT COUNT(DISTINCT ticker) AS n FROM scores WHERE as_of_date=?", (as_of_date,)
    )[0]["n"]
    unscored_count = max(0, eligible_count - scored_ticker_count)
    # report/render.py "hicbir hesap yapmaz" kuralina uymak icin: sablonda
    # {{ filtered_candidates | length }} gibi bir Jinja hesabi YAPILMAZ (bu,
    # report/validate.py::find_orphan_numbers'in yakalamasi gereken tam da
    # boyle bir "orphan" sayi uretirdi) -- sayim burada, payload'in kendisinde
    # yapilir.
    no_action_count = sum(1 for s in scores if s["candidate_state"] == "NO_ACTION")
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

    from core.weight_optimizer import load_optimized_weights
    opt = load_optimized_weights()
    tri_weights = (opt.get("valuation_triangle_weights") if opt else None) or weights.get("valuation_triangle_weights", {})

    payload = {
        "as_of_date": as_of_date,
        "weights": {
            "valuation_z": weights["scoring_weights"]["valuation_z"],
            "catalyst_score": weights["scoring_weights"]["catalyst_score"],
            "ownership_quality_z": weights["scoring_weights"]["ownership_quality_z"],
            "low_vol_z": weights["scoring_weights"]["low_vol_z"],
        },
        "reference_inputs": {
            "policy_rate_pct": regime[0]["policy_rate_pct"] if regime else None,
            "bond_2y_pct": regime[0]["bond_2y_pct"] if regime else None,
            "cpi_yoy_pct": regime[0]["cpi_yoy_pct"] if regime else None,
            "usdtry_spot": regime[0]["usdtry_spot"] if regime else None,
            "piotroski_normalized_score_threshold": weights["piotroski"]["normalized_score_threshold"],
            "equity_risk_premium_pct": load_equity_risk_premium_pct(),
            "dcf_growth_low_pct": GROWTH_LOW_PCT,
            "dcf_growth_base_pct": GROWTH_BASE_PCT,
            "dcf_growth_high_pct": GROWTH_HIGH_PCT,
            "dcf_corporate_tax_rate_pct": load_corporate_tax_rate_pct(),
            "valuation_triangle_dcf_pct": tri_weights.get("dcf", 0.40) * 100,
            "valuation_triangle_peers_pct": tri_weights.get("peer_multiples", 0.35) * 100,
            "valuation_triangle_quality_pct": tri_weights.get("quality_premium", 0.25) * 100,
        },
        "regime": as_dicts(regime)[0] if regime else None,
        "scores": as_dicts(scores),
        "predictions": as_dicts(predictions),
        "gordon_reference": as_dicts(gordon),
        "dcf_reference": as_dicts(dcf),
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
        "factor_contributions": as_dicts(factor_contributions),
        "portfolio_allocations": as_dicts(portfolio_allocations),
        "portfolio_summary": portfolio_summary or {},
        "trend_forecast": trend_forecast or {},
        "passing_candidates": passing_candidates or [],
        "concentration_warnings": concentration_warnings or [],
        "no_action_today": not any(s["candidate_state"] in ("STRONG_OPPORTUNITY", "OPPORTUNITY") for s in scores),
        "unscored_count": unscored_count,
        "no_action_count": no_action_count,
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
