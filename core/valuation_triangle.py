"""core/valuation_triangle.py: Coklu Degerleme Metodolojisi (Degerleme Ucgeni).

Spec (v13 roadmap P0-3):
- DCF (%40): WACC, terminal buyume (g) config'den. FCF buyume senaryolari (dusuk/baz/yuksek).
- Emsal Carpanlar (%35): F/K, FD/FAVOK, PD/DD, GYO/Holding icin NAV iskontosu (sektor medyani).
- Kalite Primi (%25): Piotroski F-Score, ROE vs Sermaye Maliyeti, Dusuk Borc / Net Nakit.
- GYO icin NAV (Net Aktif Degeri): Portfoy degeri - net borc / pay sayisi (nav_discount dolumu).
- Cikti: fair_value_low, fair_value_base, fair_value_high, valuation_method.
- Hedef fiyat = agirlikli ortalama fair value (fair_value_base).
"""
from __future__ import annotations

from pathlib import Path
from statistics import median
import yaml

from core.dcf import (
    calculate_wacc_pct,
    _fair_value_per_share,
    GROWTH_LOW_PCT,
    GROWTH_BASE_PCT,
    GROWTH_HIGH_PCT,
)
from core.weight_optimizer import (
    compute_harmonic_mean,
    derive_scenario_probabilities,
    load_optimized_weights,
)

_ERP_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "equity_risk_premium.yaml"
_WEIGHTS_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "weights.yaml"

DEFAULT_TRIANGLE_WEIGHTS = {
    "dcf": 0.40,
    "peer_multiples": 0.35,
    "quality_premium": 0.25,
}


def load_erp_config() -> dict:
    if _ERP_CONFIG_PATH.exists():
        with open(_ERP_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "equity_risk_premium_pct": 5.0,
        "tcmb_long_term_inflation_target_pct": 5.0,
        "corporate_tax_rate_pct": 25.0,
    }


def load_triangle_weights(use_optimized: bool = False) -> dict:
    if use_optimized:
        opt = load_optimized_weights()
        if opt and "valuation_triangle_weights" in opt:
            return opt["valuation_triangle_weights"]
    if _WEIGHTS_CONFIG_PATH.exists():
        with open(_WEIGHTS_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if data.get("use_optimized_weights"):
                opt = load_optimized_weights()
                if opt and "valuation_triangle_weights" in opt:
                    return opt["valuation_triangle_weights"]
            return data.get("valuation_triangle_weights", DEFAULT_TRIANGLE_WEIGHTS)
    return DEFAULT_TRIANGLE_WEIGHTS


def _peer_agg(peers: list[dict], metric: str) -> float | None:
    """Carpan rasyolarinda yansiz Harmonik Ortalama, diger metriklerde medyan."""
    values = [p[metric] for p in peers if p.get(metric) is not None and p[metric] == p[metric]]
    if not values:
        return None
    # F/K, FD/FAVOK, PD/DD payinda fiyat tasidigi icin Harmonik Ortalama kullanilir
    if metric in ("pe", "ev_ebitda", "pb"):
        h_mean = compute_harmonic_mean(values)
        if h_mean is not None:
            return h_mean
    return median(values)


def _peer_median(peers: list[dict], metric: str) -> float | None:
    # Geriye donuk tam uyumluluk ve diger metrikler icin
    return _peer_agg(peers, metric)


# ---------------------------------------------------------------------------
# 1. GYO / REIT & Holding NAV Calculation
# ---------------------------------------------------------------------------

def compute_reit_nav(candidate: dict) -> dict:
    """GYO icin NAV (Net Aktif Degeri) ve hisse basina NAV hesabi:
    Portfoy degeri = Yatirim Amacli Gayrimenkuller + Stoklar (+ Maddi Duran Varliklar)
    NAV = Portfoy degeri - Net Borc
    nav_per_share = NAV / shares_outstanding
    nav_discount = (NAV - Market Cap) / NAV
    """
    portfolio_value = candidate.get("_portfolio_value")
    total_assets = candidate.get("_total_assets") or candidate.get("total_assets")
    net_debt = candidate.get("net_debt")
    shares = candidate.get("shares_outstanding") or candidate.get("_shares_outstanding")
    market_cap = candidate.get("market_cap")

    if not portfolio_value and total_assets:
        portfolio_value = total_assets

    if portfolio_value is None or portfolio_value <= 0:
        return {
            "portfolio_value": None,
            "nav": None,
            "nav_per_share": None,
            "nav_discount": candidate.get("nav_discount"),
        }

    effective_debt = net_debt if net_debt is not None else 0.0
    nav = portfolio_value - effective_debt
    nav_per_share = (nav / shares) if (shares and shares > 0) else None
    nav_discount = ((nav - market_cap) / nav) if (market_cap and market_cap > 0 and nav > 0) else None

    return {
        "portfolio_value": portfolio_value,
        "nav": nav,
        "nav_per_share": nav_per_share,
        "nav_discount": nav_discount if nav_discount is not None else candidate.get("nav_discount"),
    }


# ---------------------------------------------------------------------------
# 2. Leg 1: DCF (Discounted Cash Flow) Component (Weight: 40%)
# ---------------------------------------------------------------------------

def compute_dcf_leg(candidate: dict, macro_snapshot: dict | None = None) -> dict | None:
    """Serbest nakit akisi (FCF) iskonto modeli bacagi:
    WACC, TCMB enflasyon hedefi (terminal g), FCF senaryolari (%0, %5, %10 buyume).
    """
    fcf_ttm = candidate.get("fcf_ttm")
    shares = candidate.get("shares_outstanding") or candidate.get("_shares_outstanding")
    market_cap = candidate.get("market_cap")
    beta = candidate.get("beta_60_120d") or candidate.get("beta")
    if beta is None:
        beta = 1.0  # default beta

    entry_price = candidate.get("entry_price") or candidate.get("current_price") or 0.0
    if (not shares or shares <= 0) and entry_price > 0 and market_cap and market_cap > 0:
        shares = market_cap / entry_price

    if not fcf_ttm or fcf_ttm <= 0 or not shares or shares <= 0 or not market_cap or market_cap <= 0:
        return None

    cfg = load_erp_config()
    erp = cfg.get("equity_risk_premium_pct", 5.0)
    g = cfg.get("tcmb_long_term_inflation_target_pct", 5.0)
    tax_rate = cfg.get("corporate_tax_rate_pct", 25.0)
    risk_free = (macro_snapshot or {}).get("bond_2y_pct", 45.0)

    net_debt = candidate.get("net_debt")
    fin_exp = candidate.get("financial_expenses_ttm") or candidate.get("_financial_expenses_ttm")

    wacc = calculate_wacc_pct(
        beta=beta,
        erp=erp,
        risk_free_annual_pct=risk_free,
        market_cap=market_cap,
        net_debt=net_debt,
        financial_expenses_ttm=fin_exp,
        tax_rate_pct=tax_rate,
    )

    # Denominator guard (wacc - g >= erp)
    if wacc - g < erp:
        return None

    fcf_per_share = fcf_ttm / shares
    fv_low = _fair_value_per_share(fcf_per_share, GROWTH_LOW_PCT, g, wacc, erp)
    fv_base = _fair_value_per_share(fcf_per_share, GROWTH_BASE_PCT, g, wacc, erp)
    fv_high = _fair_value_per_share(fcf_per_share, GROWTH_HIGH_PCT, g, wacc, erp)

    valid_vals = [v for v in (fv_low, fv_base, fv_high) if v is not None and v > 0]
    if not valid_vals:
        return None

    # Outlier guard: DCF adil degeri mevcut fiyatin 3 katini asamaz (> %200 prim) veya 0.2 katindan kucuk olamaz
    if entry_price > 0 and (max(valid_vals) > entry_price * 3.0 or min(valid_vals) < entry_price * 0.2):
        return None

    return {
        "fair_value_low": min(valid_vals),
        "fair_value_base": fv_base if fv_base else sum(valid_vals) / len(valid_vals),
        "fair_value_high": max(valid_vals),
        "wacc_pct": wacc,
        "fcf_per_share": fcf_per_share,
        "eligible": True,
    }


# ---------------------------------------------------------------------------
# 3. Leg 2: Peer Multiples (Emsal Carpanlar) Component (Weight: 35%)
# ---------------------------------------------------------------------------

def compute_peers_leg(candidate: dict, peers: list[dict]) -> dict | None:
    """Emsal Carpanlar bacagi:
    - Sanayi / Diger: F/K, FD/FAVOK, PD/DD
    - Banka / Sigorta: F/K, PD/DD (FD/FAVOK yasakli)
    - GYO: NAV Iskontosu, PD/DD, F/K (FD/FAVOK yasakli)
    - Holding: NAV Iskontosu, PD/DD, F/K
    """
    ratio_profile = candidate.get("ratio_profile", "industrial")
    entry_price = candidate.get("entry_price") or candidate.get("current_price") or 0.0
    shares = candidate.get("shares_outstanding") or candidate.get("_shares_outstanding")
    if (not shares or shares <= 0) and entry_price > 0 and candidate.get("market_cap"):
        shares = candidate["market_cap"] / entry_price

    legs_detail = {}

    pe_med = _peer_median(peers, "pe")
    pb_med = _peer_median(peers, "pb")
    ev_ebitda_med = _peer_median(peers, "ev_ebitda")
    nav_disc_med = _peer_median(peers, "nav_discount")
    if ratio_profile == "holding":
        # holding.note: "NAV hesaplanamiyorsa skorlanmaz."
        if nav_disc_med is not None and candidate.get("market_cap") and 0 <= nav_disc_med < 1.0:
            implied_nav = candidate["market_cap"] / (1 - nav_disc_med)
            if implied_nav and candidate["market_cap"] > 0 and entry_price > 0:
                legs_detail["holding_nav"] = implied_nav / candidate["market_cap"] * entry_price
    else:
        # 1. PE bileseni
        eps_ttm = candidate.get("eps_ttm")
        if pe_med and pe_med > 0 and eps_ttm and eps_ttm > 0:
            legs_detail["pe"] = pe_med * eps_ttm

        # 2. EV/EBITDA bileseni (yalnizca bank, insurance, reit, holding DISINDA)
        if ratio_profile not in ("bank", "insurance", "reit", "holding"):
            ebitda_ttm = candidate.get("ebitda_ttm")
            net_debt = candidate.get("net_debt")
            if ev_ebitda_med and ev_ebitda_med > 0 and ebitda_ttm and ebitda_ttm > 0 and shares and shares > 0 and net_debt is not None:
                ev = ev_ebitda_med * ebitda_ttm
                equity_val = ev - net_debt
                if equity_val > 0:
                    legs_detail["ev_ebitda"] = equity_val / shares

        # 3. PB bileseni
        bvps = None
        pb = candidate.get("pb")
        if entry_price > 0 and pb and pb > 0:
            bvps = entry_price / pb
        elif candidate.get("equity") and shares and shares > 0:
            bvps = candidate["equity"] / shares

        if pb_med and pb_med > 0 and bvps and bvps > 0:
            legs_detail["pb"] = pb_med * bvps

        # 4. GYO NAV bileseni
        if ratio_profile == "reit":
            nav_info = compute_reit_nav(candidate)
            nav_per_share = nav_info.get("nav_per_share") or candidate.get("_nav_per_share")
            if nav_per_share and nav_per_share > 0:
                target_disc = nav_disc_med if (nav_disc_med is not None and 0 <= nav_disc_med < 0.90) else 0.35
                legs_detail["reit_nav"] = nav_per_share * (1 - target_disc)

    # Outlier guard: her bir emsal carpan bileseni mevcut fiyattan 3.5 kattan fazla veya 0.2 kattan dusuk sapamaz
    filtered_legs = {}
    for k, v in legs_detail.items():
        if v is None or v <= 0:
            continue
        if entry_price > 0 and (v > entry_price * 3.5 or v < entry_price * 0.2):
            continue
        filtered_legs[k] = v

    valid_vals = [v for v in filtered_legs.values() if v is not None and v > 0]
    if not valid_vals:
        return None

    base = sum(valid_vals) / len(valid_vals)
    low = min(valid_vals) if len(valid_vals) >= 2 else base * 0.85
    high = max(valid_vals) if len(valid_vals) >= 2 else base * 1.15

    return {
        "fair_value_low": low,
        "fair_value_base": base,
        "fair_value_high": high,
        "legs_used": len(valid_vals),
        "legs_detail": filtered_legs,
        "eligible": True,
    }


# ---------------------------------------------------------------------------
# 4. Leg 3: Quality Premium (Kalite Primi) Component (Weight: 25%)
# ---------------------------------------------------------------------------

def compute_quality_leg(candidate: dict, macro_snapshot: dict | None = None) -> dict | None:
    """Kalite Primi bacagi:
    - ROE vs Sermaye Maliyeti (Graham-Buffett ekonomik kar / EVA)
    - Piotroski F-Score (0-9 mali saglik)
    - Dusuk Borc / Net Nakit (bilanco gucu)
    """
    entry_price = candidate.get("entry_price") or candidate.get("current_price") or 0.0
    roe = candidate.get("roe")
    if roe is None or roe <= 0:
        return None

    pb = candidate.get("pb")
    shares = candidate.get("shares_outstanding") or candidate.get("_shares_outstanding")

    cfg = load_erp_config()
    erp = cfg.get("equity_risk_premium_pct", 5.0)
    risk_free = (macro_snapshot or {}).get("bond_2y_pct", 45.0)
    beta = candidate.get("beta_60_120d") or candidate.get("beta") or 1.0
    cost_of_equity = risk_free + beta * erp

    # Book Value Per Share (bvps)
    bvps = None
    if entry_price > 0 and pb and pb > 0:
        bvps = entry_price / pb
    elif candidate.get("equity") and shares and shares > 0:
        bvps = candidate["equity"] / shares

    # Fundamental Anchor
    if bvps and bvps > 0 and roe is not None and roe > 0 and cost_of_equity > 0:
        # Justified P/B = ROE / Cost of Equity
        justified_pb = max(0.5, min(4.0, (roe / 100.0) / (cost_of_equity / 100.0)))
        anchor = bvps * justified_pb
        if entry_price > 0:
            anchor = max(entry_price * 0.3, min(entry_price * 2.5, anchor))
    elif entry_price > 0:
        anchor = entry_price
    else:
        return None

    # Quality Modifiers
    # 1. Piotroski F-Score (+10% / 0% / -10%)
    pio_norm = candidate.get("piotroski_normalized_score")
    pio_adj = 0.0
    if pio_norm is not None:
        if pio_norm >= 0.77:  # score >= 7/9
            pio_adj = 0.10
        elif pio_norm < 0.44:  # score <= 3/9
            pio_adj = -0.10

    # 2. Net Borc / Bilanço Gucu (+10% / +5% / 0% / -10%)
    net_debt = candidate.get("net_debt")
    ebitda_ttm = candidate.get("ebitda_ttm")
    debt_adj = 0.0
    if net_debt is not None and net_debt < 0:
        # Net nakit sirket
        debt_adj = 0.10
    elif net_debt is not None and ebitda_ttm and ebitda_ttm > 0:
        nd_ebitda = net_debt / ebitda_ttm
        if nd_ebitda <= 1.5:
            debt_adj = 0.05
        elif nd_ebitda > 3.0:
            debt_adj = -0.10

    # 3. Yuksek ROE primi
    roe_adj = 0.0
    if roe is not None:
        if roe >= 40.0:
            roe_adj = 0.05
        elif roe < 0:
            roe_adj = -0.15

    total_multiplier = max(0.60, min(1.50, 1.0 + pio_adj + debt_adj + roe_adj))
    base = anchor * total_multiplier
    low = base * 0.90
    high = base * 1.10

    return {
        "fair_value_low": low,
        "fair_value_base": base,
        "fair_value_high": high,
        "quality_multiplier": total_multiplier,
        "anchor": anchor,
        "eligible": True,
    }


# ---------------------------------------------------------------------------
# 5. Multi-Factor Synthesis: Valuation Triangle (Degerleme Ucgeni)
# ---------------------------------------------------------------------------

def compute_valuation_triangle(
    candidate: dict,
    peers: list[dict],
    macro_snapshot: dict | None = None,
    custom_weights: dict | None = None,
    prob_up: float | None = None,
) -> dict:
    """Degerleme Ucgeni sentezi:
    DCF (%40) + Emsal Carpanlar (%35) + Kalite Primi (%25).

    Eger bilesenlerden biri verisizlik nedeniyle hesaplanamazsa, agirliklar
    hesaplanabilen diger bilesenler arasinda oransal olarak yeniden normalize edilir.
    """
    weights_config = custom_weights or load_triangle_weights()
    w_dcf_raw = weights_config.get("dcf", 0.40)
    w_peers_raw = weights_config.get("peer_multiples", 0.35)
    w_quality_raw = weights_config.get("quality_premium", 0.25)

    dcf_leg = compute_dcf_leg(candidate, macro_snapshot)
    peers_leg = compute_peers_leg(candidate, peers)
    quality_leg = compute_quality_leg(candidate, macro_snapshot)

    active_legs = {}
    if dcf_leg and dcf_leg.get("eligible"):
        active_legs["dcf"] = (w_dcf_raw, dcf_leg)
    if peers_leg and peers_leg.get("eligible"):
        active_legs["peers"] = (w_peers_raw, peers_leg)
    if quality_leg and quality_leg.get("eligible"):
        active_legs["quality"] = (w_quality_raw, quality_leg)

    if not active_legs:
        return {
            "target_price": None,
            "fair_value_low": None,
            "fair_value_base": None,
            "fair_value_high": None,
            "valuation_method": "none",
            "weights_used": {},
            "dcf_leg": None,
            "peers_leg": None,
            "quality_leg": None,
            "legs_used": 0,
            "scenario_probabilities": None,
        }

    # Normalize active weights to sum to 1.0
    total_raw_weight = sum(w for w, _ in active_legs.values())
    normalized_weights = {k: w / total_raw_weight for k, (w, _) in active_legs.items()}

    fv_base = sum(normalized_weights[k] * leg["fair_value_base"] for k, (_, leg) in active_legs.items())
    fv_low = sum(normalized_weights[k] * leg["fair_value_low"] for k, (_, leg) in active_legs.items())
    fv_high = sum(normalized_weights[k] * leg["fair_value_high"] for k, (_, leg) in active_legs.items())

    # Rejim ve Trend olasilik agirlikli sentetik hedef sentezi (sifir manuel agirlik)
    effective_prob_up = prob_up
    if effective_prob_up is None and macro_snapshot:
        effective_prob_up = macro_snapshot.get("prob_up")
    if effective_prob_up is None:
        effective_prob_up = candidate.get("prob_up")

    if effective_prob_up is not None:
        scenario_probs = derive_scenario_probabilities(effective_prob_up)
        target_price = (
            scenario_probs["bull"] * fv_high
            + scenario_probs["base"] * fv_base
            + scenario_probs["bear"] * fv_low
        )
    else:
        scenario_probs = {"bull": 0.0, "base": 1.0, "bear": 0.0}
        target_price = fv_base

    # Outlier guard: Sentetik hedef fiyat fiyatin 2.5 katini asamaz (> %150) veya 0.3 katindan kucuk olamaz
    entry_price = candidate.get("entry_price") or candidate.get("current_price") or 0.0
    if entry_price > 0 and (target_price > entry_price * 2.5 or target_price < entry_price * 0.3):
        return {
            "target_price": None,
            "fair_value_low": None,
            "fair_value_base": None,
            "fair_value_high": None,
            "valuation_method": "none",
            "weights_used": {},
            "dcf_leg": None,
            "peers_leg": None,
            "quality_leg": None,
            "legs_used": 0,
            "scenario_probabilities": None,
        }

    # Build descriptive valuation method string
    method_parts = []
    if "dcf" in active_legs:
        method_parts.append("DCF")
    if "peers" in active_legs:
        method_parts.append("Emsal")
    if "quality" in active_legs:
        method_parts.append("Kalite")
    valuation_method = f"Değerleme Üçgeni ({' + '.join(method_parts)})"

    return {
        "target_price": target_price,
        "fair_value_low": round(fv_low, 2),
        "fair_value_base": round(fv_base, 2),
        "fair_value_high": round(fv_high, 2),
        "valuation_method": valuation_method,
        "weights_used": {k: round(v, 4) for k, v in normalized_weights.items()},
        "dcf_leg": dcf_leg,
        "peers_leg": peers_leg,
        "quality_leg": quality_leg,
        "scenario_probabilities": scenario_probs,
        "legs_used": sum(
            (peers_leg.get("legs_used", 1) if k == "peers" else 1)
            for k in active_legs
        ),
    }
