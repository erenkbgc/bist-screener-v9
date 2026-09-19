"""tests/test_targets_realistic.py: Gercekci hedef fiyat ve oynaklik konisi testleri."""
import pytest

from core.targets import (
    compute_volatility_cone_envelope,
    compute_long_term_target,
    compute_short_term_target,
)
from core.valuation_triangle import compute_valuation_triangle


def test_volatility_cone_envelope_clamping():
    # 100 TL hisse, %40 yillik oynaklik, 180 gun vade
    upper_envelope = compute_volatility_cone_envelope(
        current_price=100.0,
        volatility_60d=0.40,
        horizon_days=180,
        risk_free_annual_pct=45.0,
        z=1.75,
    )
    # Formül: P0 * exp((mu - 0.5*sigma^2)*T + z*sigma*sqrt(T))
    # 100 TL uzerinde mantikli bir tavan (~160-190 TL arasi) olmali, asla 500 TL olamaz
    assert 130.0 <= upper_envelope <= 220.0
    assert upper_envelope > 100.0


def test_long_term_target_realistic_actionable_vs_terminal():
    candidate = {
        "ticker": "TEST1",
        "entry_price": 100.0,
        "current_price": 100.0,
        "market_cap": 1_000_000_000.0,
        "shares_outstanding": 10_000_000.0,
        "ratio_profile": "industrial",
        "reporting_basis": "adjusted",
        "sector": "S1",
        "supersector": "XUSIN",
        "pe": 8.0,
        "eps_ttm": 12.0,  # 8 * 12 = 96 TL
        "volatility_60d": 0.35,
        "atr20": 3.0,
    }
    # Peers PE ortalamasi 20.0 ise teorik peer degeri 20 * 12 = 240 TL (+%140)
    peers = [
        {
            "ticker": f"P{i}",
            "pe": 20.0,
            "eps_ttm": 10.0,
            "ratio_profile": "industrial",
            "reporting_basis": "adjusted",
            "sector": "S1",
            "supersector": "XUSIN",
            "entry_price": 100.0,
        }
        for i in range(5)
    ]

    res = compute_long_term_target(candidate, peers + [candidate])

    assert res["target_price"] is not None
    assert res["terminal_fair_value"] is not None
    assert res["volatility_cone_ceiling"] is not None
    # Aksiyonel 180 gunluk hedef, teorik terminal degerden daha muhafazakar ve gercekcidir
    assert res["target_price"] <= res["terminal_fair_value"]
    # Hedef fiyat volatilite konisi tavanini asamaz
    assert res["target_price"] <= res["volatility_cone_ceiling"]


def test_short_term_target_structural_ceiling():
    # Mevcut fiyat 100 TL, ATR 4 TL -> raw target = 100 + 2.5 * 4 = 110 TL
    # Ancak 105 TL'de guclu bir salinim tepesi (swing high) direnci var
    res = compute_short_term_target(
        current_price=100.0,
        atr20=4.0,
        sma20=98.0,
        recent_swing_high=105.0,
    )
    assert res["structural_ceiling"] == 105.0
    # Hedef fiyat 110 TL yerine 105 TL'ye sinirlanmalidir
    assert res["target_price"] == 105.0


def test_scenario_probabilities_integrated_in_valuation():
    candidate = {
        "ticker": "TEST_BULL",
        "entry_price": 100.0,
        "current_price": 100.0,
        "market_cap": 1_000_000_000.0,
        "shares_outstanding": 10_000_000.0,
        "ratio_profile": "industrial",
        "pe": 10.0,
        "eps_ttm": 10.0,
    }
    peers = [
        {"ticker": f"P{i}", "pe": 15.0, "eps_ttm": 10.0, "ratio_profile": "industrial", "entry_price": 100.0}
        for i in range(5)
    ]

    # Boga rejiminde (prob_up = 0.85) hedef daha yuksek olmali
    bull_res = compute_valuation_triangle(candidate, peers + [candidate], prob_up=0.85)
    # Ayi rejiminde (prob_up = 0.15) hedef daha temkinli olmali
    bear_res = compute_valuation_triangle(candidate, peers + [candidate], prob_up=0.15)

    assert bull_res["target_price"] > bear_res["target_price"]
    assert bull_res["scenario_probabilities"]["bull"] > bear_res["scenario_probabilities"]["bull"]
    assert bear_res["scenario_probabilities"]["bear"] > bull_res["scenario_probabilities"]["bear"]
