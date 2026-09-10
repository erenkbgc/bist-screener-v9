"""target_price_engine: uzun ve kisa vade hedef fiyat hesaplari.

mandatory_downstream (spec): "Her hedef hurdle_engine'den gecmeden rapora
giremez." -> Bu dosya yalnizca target/entry/stop uretir; hurdle gecisi
core/scoring.py ve core/payload.py asamasinda ayrica uygulanir.
"""
from __future__ import annotations

from statistics import median

from core.ranking import build_peer_group


def _peer_median(peers: list[dict], metric: str) -> float | None:
    values = [p[metric] for p in peers if p.get(metric) is not None]
    return median(values) if values else None


def compute_long_term_target(candidate: dict, all_candidates: list[dict]) -> dict:
    peers, peer_level, confidence = build_peer_group(candidate, all_candidates)
    ratio_profile = candidate["ratio_profile"]

    if ratio_profile == "bank":
        pe_med = _peer_median(peers, "pe")
        leg1 = pe_med * candidate["eps_ttm"] if (pe_med and candidate.get("eps_ttm")) else None
        legs = [v for v in (leg1,) if v is not None]
    elif ratio_profile == "holding":
        nav_disc_med = _peer_median(peers, "nav_discount")
        # NAV iskontosu medyani: mevcut piyasa degerinin, medyan iskontoya gore ima ettigi deger.
        # NAV hesaplanamiyorsa (spec) skorlanmaz.
        legs = []
        if nav_disc_med is not None and candidate.get("market_cap"):
            implied_nav = candidate["market_cap"] / (1 - nav_disc_med) if nav_disc_med < 1 else None
            if implied_nav:
                legs.append(implied_nav / candidate["market_cap"] * candidate.get("entry_price", 0))
    else:
        pe_med = _peer_median(peers, "pe")
        ev_ebitda_med = _peer_median(peers, "ev_ebitda")
        leg1 = pe_med * candidate["eps_ttm"] if (pe_med and candidate.get("eps_ttm")) else None
        leg2 = None
        if ev_ebitda_med and candidate.get("ebitda_ttm") is not None and candidate.get("net_debt") is not None \
                and candidate.get("shares_outstanding"):
            enterprise_value = ev_ebitda_med * candidate["ebitda_ttm"]
            equity_value = enterprise_value - candidate["net_debt"]
            leg2 = equity_value / candidate["shares_outstanding"]
        legs = [v for v in (leg1, leg2) if v is not None]

    target_price = sum(legs) / len(legs) if legs else None
    return {
        "target_price": target_price, "horizon_days": 180,
        "peer_group_used": peer_level, "peer_n": len(peers), "confidence": confidence,
        "legs_used": len(legs),
    }


def compute_short_term_target(current_price: float, atr20: float, sma20: float) -> dict:
    return {
        "entry_price": sma20 if sma20 else current_price,
        "target_price": current_price + 2.5 * atr20,
        "stop_loss": current_price - 1.2 * atr20,
        "horizon_days": 20,
    }
