"""priors_disclosure testi: methodology bolumunde agirliklarin denenmemis
varsayim oldugunu belirten metin bulunmali."""
from report.render import render_newsletter


def _base_context():
    return {
        "as_of_date": "2026-09-10", "regime": None, "regime_taxonomy_tag": None,
        "decision_diff": {"regime_status": "unchanged", "entered": [], "exited": [],
                           "catalyst_deltas": [], "macro_deltas": []},
        "concentration_warnings": [], "long_term_candidates": [], "short_term_candidates": [],
        "filtered_candidates": [], "unscored_count": 0, "no_action_today": True,
        "invalidation_triggered": [], "evaluation_summary": None,
        "weights": {"valuation_z": 0.55, "catalyst_score": 0.30, "ownership_quality_z": 0.15,
                    "piotroski_normalized_score_threshold": 0.55, "equity_risk_premium_pct": 5.0},
    }


def test_methodology_declares_undemonstrated_priors():
    html = render_newsletter(_base_context())
    assert "DENENMEMIS" in html
    assert "0.55" in html and "0.30" in html and "0.15" in html


def test_disclaimer_present():
    html = render_newsletter(_base_context())
    assert "Yatirim danismanligi degildir" in html
