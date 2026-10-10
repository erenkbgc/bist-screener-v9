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


def test_long_term_fails_beta_adjusted_hurdle():
    """Hedef k_e = rf + beta*ERP ile buyutuldugu icin sabit rf hurdle'i otomatik
    geciliyordu; uzun vade artik ayni k_e'yi kullanan beta hurdle'ina bakar."""
    c = _base_candidate(excess_over_beta_hurdle_pct=-50)
    passed, reason = hard_filters_passed(c, 0.55, "2026-09-10")
    assert passed is False and reason == "beta_hurdle"
    c_unknown = _base_candidate(excess_over_beta_hurdle_pct=None)
    assert hard_filters_passed(c_unknown, 0.55, "2026-09-10")[0] is True


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


def test_redistribute_catalyst_weight_preserves_total_and_ratios():
    from core.scoring import redistribute_catalyst_weight
    w = {"valuation_z": 0.50, "catalyst_score": 0.25, "ownership_quality_z": 0.15, "low_vol_z": 0.10, "momentum_z": 0.0}
    r = redistribute_catalyst_weight(w)
    assert r["catalyst_score"] == 0.0
    assert abs(sum(r.values()) - sum(w.values())) < 1e-12
    assert abs(r["valuation_z"] / r["ownership_quality_z"] - 0.50 / 0.15) < 1e-12
    assert abs(r["valuation_z"] - 0.50 / 0.75) < 1e-12


def test_catalyst_unavailable_uses_redistributed_weights(temp_db):
    """KAP cekilemeyen hissede katalizor 0 'notr' sayilmaz; agirlik dagitilir."""
    from core.scoring import score_candidates

    def cand(ticker, available):
        return {"ticker": ticker, "bucket": "long_term", "tedbir_level": 0, "reporting_basis": "adjusted",
                "listing_days": 500, "free_float_pct": 30, "excess_over_hurdle_pct": 5.0,
                "effective_at": "2026-09-01", "piotroski_normalized_score": 0.7,
                "catalyst_score": 0.0, "catalyst_available": available, "ownership_z": 0.0,
                "low_vol_z": 0.0, "momentum_z": 0.0, "sector": "S", "supersector": "SS",
                "ratio_profile": "industrial", "pe": 10.0, "pb": 1.0, "ev_ebitda": 5.0, "roe": 10.0}
    peers = [cand(f"PEER{i}", True) for i in range(6)]  # confidence icin >= 5 akran
    scored = score_candidates("2026-09-10", [cand("KAPOK", True), cand("KAPDOWN", False)] + peers, "2026-09-10")
    w = {c["ticker"]: c.get("scoring_weights_used") for c in scored}
    assert w["KAPOK"] and w["KAPDOWN"], [(c["ticker"], c.get("filtered_by")) for c in scored]
    assert w["KAPOK"]["catalyst_score"] > 0
    assert w["KAPDOWN"]["catalyst_score"] == 0.0
    assert w["KAPDOWN"]["valuation_z"] > w["KAPOK"]["valuation_z"]


def test_short_term_never_promoted_when_disabled(temp_db):
    """on-kayitli arama kural bulamadi -> kisa vade en fazla WATCHLIST."""
    from core.scoring import score_candidates

    def cand(ticker, bucket, val):
        return {"ticker": ticker, "bucket": bucket, "tedbir_level": 0, "reporting_basis": "adjusted",
                "listing_days": 500, "free_float_pct": 30, "excess_over_hurdle_pct": 5.0,
                "effective_at": "2026-09-01", "piotroski_normalized_score": 0.9, "volume_ratio_20d": 2.0,
                "catalyst_score": 0.0, "ownership_z": 0.0, "low_vol_z": 0.0, "momentum_z": 0.0,
                "sector": "S", "supersector": "SS", "ratio_profile": "industrial",
                "pe": val, "pb": val / 5, "ev_ebitda": val / 2, "roe": 20.0}
    cands = [cand(f"S{i}", "short_term", 5 + i) for i in range(8)] + \
            [cand(f"L{i}", "long_term", 5 + i) for i in range(8)]
    scored = score_candidates("2026-09-10", cands, "2026-09-10")
    st = [c for c in scored if c["bucket"] == "short_term" and c["candidate_state"] != "NO_ACTION"]
    lt = [c for c in scored if c["bucket"] == "long_term"]
    assert st, [(c["ticker"], c.get("filtered_by")) for c in scored]
    assert all(c["candidate_state"] == "WATCHLIST" and c.get("experimental") for c in st)
    assert any(c["candidate_state"] in ("STRONG_OPPORTUNITY", "OPPORTUNITY") for c in lt)


def test_ownership_penalty_lowers_negative_z():
    """z *= 0.70 negatif z'yi iyilestiriyordu; ceza her zaman asagi olmali."""
    from core.ownership import compute_ownership_z
    pop = [{"free_float_pct": v} for v in (20, 30, 40, 50, 60)]
    weak = {"free_float_pct": 20}
    plain = compute_ownership_z(weak, pop)
    penalized = compute_ownership_z({**weak, "_penalize": True}, pop)
    assert plain < 0 and penalized < plain


def test_top_ranked_non_strong_is_opportunity_and_value_trap_is_watchlist(temp_db):
    """Eski kural: ust dilimde olup STRONG kosullarindan birini kaciran hisse
    WATCHLIST, alt siradaki OPPORTUNITY oluyordu. Value-trap bayragi da yalnizca
    STRONG'u engelliyordu."""
    from core import scoring

    def cand(t, pb, trap=False, pio=0.45):
        return {"ticker": t, "bucket": "long_term", "sector": "XGIDA", "supersector": "XUSIN",
                "ratio_profile": "industrial", "reporting_basis": "adjusted", "tedbir_level": 0,
                "listing_days": 500, "free_float_pct": 30, "excess_over_hurdle_pct": 5.0,
                "effective_at": "2026-09-01", "piotroski_normalized_score": pio,
                "pb": pb, "roe": 10, "catalyst_score": 0.0, "ownership_z": 0.0,
                "mom_12_1_pct": -10 if trap else 10, "trend_smoothness_r2": -0.5 if trap else 0.5}

    cands = [cand(f"T{i}", 1 + i * 0.2) for i in range(8)]
    cands[0]["piotroski_normalized_score"] = 0.40   # en ucuz ama STRONG esiginin altinda
    cands[1].update(mom_12_1_pct=-10, trend_smoothness_r2=-0.5)  # value trap
    out = {c["ticker"]: c for c in scoring.score_candidates("2026-09-10", cands, "2026-09-10")}
    assert out["T0"]["candidate_state"] == "OPPORTUNITY"
    assert out["T1"]["candidate_state"] == "WATCHLIST"
