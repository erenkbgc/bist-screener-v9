"""no_action testi, piotroski gate testi, beta hurdle testi (hard_filter DEGIL),
volume breakout testi."""
from core.scoring import hard_filters_passed, run_level_state


def _base_candidate(**overrides):
    c = {
        "tedbir_level": 0, "reporting_basis": "adjusted", "confidence": "high",
        "listing_days": 500, "free_float_pct": 30, "excess_over_hurdle_pct": 5.0,
        "effective_at": "2026-09-01", "piotroski_normalized_score": 0.7, "bucket": "long_term",
    }
    c.update(overrides)
    return c


def test_hard_filters_pass_for_clean_candidate():
    passed, reason = hard_filters_passed(_base_candidate(), 0.55, "2026-09-10")
    assert passed is True
    assert reason is None


def test_hard_filters_fail_on_tedbir():
    passed, reason = hard_filters_passed(_base_candidate(tedbir_level=2), 0.55, "2026-09-10")
    assert passed is False
    assert reason == "tedbir_level"


def test_hard_filters_fail_on_negative_hurdle():
    passed, reason = hard_filters_passed(_base_candidate(excess_over_hurdle_pct=-1), 0.55, "2026-09-10")
    assert passed is False
    assert reason == "hurdle"


def test_piotroski_gate_fails_below_threshold():
    passed, reason = hard_filters_passed(_base_candidate(piotroski_normalized_score=0.2), 0.55, "2026-09-10")
    assert passed is False
    assert reason == "piotroski"


def test_piotroski_gate_passes_at_threshold():
    passed, reason = hard_filters_passed(_base_candidate(piotroski_normalized_score=0.55), 0.55, "2026-09-10")
    assert passed is True


def test_effective_at_after_cutoff_fails_point_in_time():
    passed, reason = hard_filters_passed(_base_candidate(effective_at="2026-09-15"), 0.55, "2026-09-10")
    assert passed is False
    assert reason == "point_in_time"


def test_short_term_requires_volume_breakout():
    c = _base_candidate(bucket="short_term", volume_ratio_20d=1.0)
    passed, reason = hard_filters_passed(c, 0.55, "2026-09-10")
    assert passed is False
    assert reason == "volume_breakout"


def test_short_term_passes_with_volume_confirmed():
    c = _base_candidate(bucket="short_term", volume_ratio_20d=1.6)
    passed, reason = hard_filters_passed(c, 0.55, "2026-09-10")
    assert passed is True


def test_excess_over_beta_hurdle_not_in_hard_filters():
    """beta_adjusted_hurdle bilgi amaclidir; excess_over_beta_hurdle_pct negatif
    olsa bile hard_filters_passed bunu KONTROL ETMEZ."""
    c = _base_candidate(excess_over_beta_hurdle_pct=-50)
    passed, reason = hard_filters_passed(c, 0.55, "2026-09-10")
    assert passed is True


def test_run_level_state_no_action_today_when_nothing_passes():
    scored = [{"candidate_state": "NO_ACTION"}, {"candidate_state": "WATCHLIST"}]
    assert run_level_state(scored) == "NO_ACTION_TODAY"


def test_run_level_state_normal_when_opportunity_exists():
    scored = [{"candidate_state": "NO_ACTION"}, {"candidate_state": "OPPORTUNITY"}]
    assert run_level_state(scored) == "NORMAL"
