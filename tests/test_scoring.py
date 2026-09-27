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


def test_effective_at_none_fails_point_in_time_without_crashing():
    """point_in_time_publication_lag: gercek KAP bildirim tarihi bulunamadiginda
    (bkz. core/fundamentals.py) effective_at None kalir. None <= str karsilastirmasi
    TypeError firlatmamali; aday guvenlik icin elenmeli (UYDURULMAZ)."""
    passed, reason = hard_filters_passed(_base_candidate(effective_at=None), 0.55, "2026-09-10")
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


def test_hard_filters_fail_on_outlier_roi():
    """180 gunluk gercekci olmayan asiri getiri vaatleri (> %200) guvenlik icin elenir."""
    c_outlier = _base_candidate(expected_roi_pct=1596.0)
    passed, reason = hard_filters_passed(c_outlier, 0.55, "2026-09-10")
    assert passed is False
    assert reason == "outlier_roi"

    c_ok = _base_candidate(expected_roi_pct=45.0)
    passed_ok, reason_ok = hard_filters_passed(c_ok, 0.55, "2026-09-10")
    assert passed_ok is True
    assert reason_ok is None


def test_run_level_state_no_action_today_when_nothing_passes():
    scored = [{"candidate_state": "NO_ACTION"}, {"candidate_state": "WATCHLIST"}]
    assert run_level_state(scored) == "NO_ACTION_TODAY"


def test_run_level_state_normal_when_opportunity_exists():
    scored = [{"candidate_state": "NO_ACTION"}, {"candidate_state": "OPPORTUNITY"}]
    assert run_level_state(scored) == "NORMAL"


def test_get_regime_weights():
    from core.scoring import get_regime_weights

    # Tanimsiz rejim: temel agirliklar donmeli
    w_default = get_regime_weights(None)
    assert w_default["valuation_z"] == 0.50
    assert w_default["catalyst_score"] == 0.25
    assert w_default["momentum_z"] == 0.0

    # STRONG_BULL: Katalizor/momentum artmali
    w_bull = get_regime_weights("STRONG_BULL")
    assert w_bull["catalyst_score"] > w_default["catalyst_score"]
    assert abs(sum(w_bull.values()) - 1.0) < 1e-4

    # STRONG_BEAR: Kalite ve Düşük Volatilite artmali
    w_bear = get_regime_weights("STRONG_BEAR")
    assert w_bear["low_vol_z"] > w_default["low_vol_z"]
    assert w_bear["ownership_quality_z"] > w_default["ownership_quality_z"]
    assert abs(sum(w_bear.values()) - 1.0) < 1e-4



def test_value_trap_blocks_strong_opportunity(temp_db):
    # Ucuz ama dusen hisse (12-1 momentum < 0, trend asagi) en ust dilimde olsa
    # bile STRONG_OPPORTUNITY alamaz. Ayni hisse momentum pozitifken alabilir.
    from core.scoring import score_candidates

    def pool(trap_mom, trap_trend):
        cands = []
        for i in range(6):
            cheap = i == 0
            cands.append(dict(
                _base_candidate(), ticker=f"T{i}", ratio_profile="industrial", sector="S1",
                supersector="X", reporting_basis="adjusted",
                pe=3.0 if cheap else 12.0, pb=0.4 if cheap else 2.0, ev_ebitda=3.0 if cheap else 10.0,
                catalyst_score=0.0, ownership_z=0.0, low_vol_z=0.0, momentum_z=0.0,
                mom_12_1_pct=trap_mom if cheap else 10.0,
                trend_smoothness_r2=trap_trend if cheap else 0.3))
        return {c["ticker"]: c for c in score_candidates("2026-09-10", cands, "2026-09-10")}

    trap = pool(-60.0, -0.8)["T0"]
    assert trap["value_trap_risk"] is True
    assert trap["candidate_state"] != "STRONG_OPPORTUNITY"
    healthy = pool(15.0, 0.5)["T0"]
    assert healthy["value_trap_risk"] is False


def test_long_term_fails_without_valuation_upside():
    # Hurdle gecse bile (CAPM buyumesi) adil degerin altindaki fiyatli hisse elenir.
    passed, reason = hard_filters_passed(_base_candidate(valuation_excess_pct=-0.5), 0.55, "2026-09-10")
    assert not passed and reason == "valuation_upside"
    passed, _ = hard_filters_passed(_base_candidate(valuation_excess_pct=0.5), 0.55, "2026-09-10")
    assert passed


def test_valuation_upside_gate_only_for_long_term():
    c = _base_candidate(bucket="short_term", volume_ratio_20d=2.0, valuation_excess_pct=-5.0)
    passed, _ = hard_filters_passed(c, 0.55, "2026-09-10")
    assert passed
