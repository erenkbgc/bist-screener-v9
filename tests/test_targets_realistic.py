"""tests/test_targets_realistic.py: Gercekci hedef fiyat ve oynaklik konisi testleri."""
import math

import pytest

from core.targets import (
    compute_volatility_cone_envelope,
    compute_long_term_target,
    compute_short_term_target,
)
from core.valuation_triangle import compute_valuation_triangle


def test_volatility_cone_envelope_clamping():
    # 100 TL hisse, %40 yillik oynaklik, 180 gun vade. volatility_60d GUNLUK
    # stdev'dir (live_data/mock_data ile ayni birim): 0.40 / sqrt(252).
    upper_envelope = compute_volatility_cone_envelope(
        current_price=100.0,
        volatility_60d=0.40 / math.sqrt(252),
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
        "volatility_60d": 0.35 / math.sqrt(252),
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


def test_volatility_cone_uses_daily_sigma_annualized():
    # Regresyon (2026-09-27): gunluk sigma (0.02) yillik gibi kullanilinca tavan
    # ~P0*1.2'ye cokuyor ve 180 gunluk hurdle (~%18) yapisal olarak gecilemiyordu.
    ceiling = compute_volatility_cone_envelope(
        current_price=100.0, volatility_60d=0.02, horizon_days=180,
        risk_free_annual_pct=40.0, z=2.5,
    )
    # yillik sigma ~0.32 -> tavan belirgin bicimde %60'in uzerinde olmali
    assert ceiling > 160.0


def test_long_term_target_fairly_priced_stock_earns_cost_of_equity():
    # Adil fiyatli (FV == P) bir hissenin 180 gunluk beklenen getirisi k_e'nin
    # ufka bilesik karsiligi olmali; rf hurdle'inin ustunde kalmali.
    from core.hurdle import hurdle_rate_pct
    from core.targets import cost_of_equity_pct
    rf = 40.0
    k_e = cost_of_equity_pct(rf)
    expected = ((1 + k_e / 100) ** (180 / 365) - 1) * 100
    assert expected > hurdle_rate_pct(rf, 180)


def test_convergence_alpha_from_weights_yaml_not_optimized_json():
    from core.targets import convergence_alpha
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "weights.yaml").read_text(encoding="utf-8"))
    assert convergence_alpha() == cfg["target_convergence_alpha"] == 0.05


def test_valuation_excess_is_alpha_times_gap():
    from core.targets import convergence_alpha
    candidate = {
        "ticker": "TEST2", "entry_price": 100.0, "current_price": 100.0,
        "market_cap": 1_000_000_000.0, "shares_outstanding": 10_000_000.0,
        "ratio_profile": "industrial", "reporting_basis": "adjusted",
        "sector": "S1", "supersector": "XUSIN", "pe": 8.0, "eps_ttm": 12.0,
        "volatility_60d": 0.35 / math.sqrt(252), "atr20": 3.0,
    }
    peers = [{"ticker": f"P{i}", "pe": 20.0, "eps_ttm": 10.0, "ratio_profile": "industrial",
              "reporting_basis": "adjusted", "sector": "S1", "supersector": "XUSIN", "entry_price": 100.0}
             for i in range(5)]
    res = compute_long_term_target(candidate, peers + [candidate])
    fv = res["terminal_fair_value"]
    assert fv > 100.0
    assert abs(res["valuation_excess_pct"] - convergence_alpha() * (fv - 100.0)) < 1e-9
