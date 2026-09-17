"""target_price_engine: uzun ve kisa vade hedef fiyat hesaplari.

mandatory_downstream (spec): "Her hedef hurdle_engine'den gecmeden rapora
giremez." -> Bu dosya yalnizca target/entry/stop uretir; hurdle gecisi
core/scoring.py ve core/payload.py asamasinda ayrica uygulanir.
"""
from __future__ import annotations

from statistics import median

from core.ranking import build_peer_group
from core.valuation_triangle import compute_valuation_triangle

# core/universe.py::MIN_VOLUME_TL_DEFAULT ile ayni taban: evrenin en ince ucundaki
# hisseler (hacim tabanina yakin) burada baslar.
LIQUIDITY_FLOOR_TL = 10_000_000
# Bu hacmin ustunde ek genisletme uygulanmaz (yeterince derin kabul edilir).
LIQUIDITY_CEILING_TL = 50_000_000
# Tabanin hemen ustundeki hisselerde stop/hedef mesafesi en fazla bu kadar genisler.
MAX_LIQUIDITY_BUFFER = 1.3


def _peer_median(peers: list[dict], metric: str) -> float | None:
    values = [p[metric] for p in peers if p.get(metric) is not None]
    return median(values) if values else None


def _liquidity_buffer_multiplier(avg_volume_tl_20d: float | None) -> float:
    """Hisse defteri ince oldukca (evrenin hacim tabanina yakin) stop ve hedef
    mesafesini genisletir. Amac ek getiri degil: ince kitapta spread/kayma
    gurultusu daha buyuk, ayni ATR mesafesi gercek trendden once spread
    sicramasiyla tetiklenebilir. avg_volume_tl_20d None ise (veri yok)
    genisletme uygulanmaz -- eksik veriyle iyimser/kotumser varsayim
    uretilmez, taban davranis (1.0x) korunur."""
    if not avg_volume_tl_20d or avg_volume_tl_20d >= LIQUIDITY_CEILING_TL:
        return 1.0
    if avg_volume_tl_20d <= LIQUIDITY_FLOOR_TL:
        return MAX_LIQUIDITY_BUFFER
    span = LIQUIDITY_CEILING_TL - LIQUIDITY_FLOOR_TL
    frac = (avg_volume_tl_20d - LIQUIDITY_FLOOR_TL) / span
    return MAX_LIQUIDITY_BUFFER - frac * (MAX_LIQUIDITY_BUFFER - 1.0)


def compute_long_term_target(
    candidate: dict,
    all_candidates: list[dict],
    macro_snapshot: dict | None = None,
) -> dict:
    """Coklu Degerleme Metodolojisi / Degerleme Ucgeni (v13 roadmap P0-3).
    DCF (%40) + Emsal Carpanlar (%35) + Kalite Primi (%25).
    GYO ve Holding icin NAV hesaplamasi.
    """
    peers, peer_level, confidence = build_peer_group(candidate, all_candidates)
    triangle = compute_valuation_triangle(candidate, peers, macro_snapshot=macro_snapshot)

    return {
        "target_price": triangle["target_price"],
        "fair_value_low": triangle["fair_value_low"],
        "fair_value_base": triangle["fair_value_base"],
        "fair_value_high": triangle["fair_value_high"],
        "valuation_method": triangle["valuation_method"],
        "weights_used": triangle["weights_used"],
        "dcf_leg": triangle["dcf_leg"],
        "peers_leg": triangle["peers_leg"],
        "quality_leg": triangle["quality_leg"],
        "horizon_days": 180,
        "peer_group_used": peer_level,
        "peer_n": len(peers),
        "confidence": confidence,
        "legs_used": triangle["legs_used"],
    }


def compute_dynamic_risk_levels(
    current_price: float,
    atr20: float | None = None,
    recent_swing_low: float | None = None,
    account_risk_pct: float = 1.5,
    max_position_size_pct: float = 25.0,
    avg_volume_tl_20d: float | None = None,
) -> dict:
    """Dinamik Entry / Stop-Loss / Position Sizing (v12 roadmap P0-1).

    Kurallar ve Formuller:
    - entry_low = current_price - 0.5 * ATR20
    - entry_high = current_price + 0.2 * ATR20
    - stop_loss = entry_low - 1.5 * ATR20 (veya son swing dusuk)
    - Kademeli alim: %50 alt bant, %50 ust bant -> effective_entry = 0.5 * entry_low + 0.5 * entry_high
    - Pozisyon buyuklugu: hesap bakiyesinin %1-2'si / (entry - stop)
    - Cikti: entry_low, entry_high, stop_loss, position_size_pct, effective_entry, risk_per_share
    """
    if current_price <= 0:
        return {
            "entry_low": 0.0,
            "entry_high": 0.0,
            "effective_entry": 0.0,
            "stop_loss": 0.0,
            "position_size_pct": 0.0,
            "risk_per_share": 0.0,
            "risk_pct": 0.0,
            "liquidity_buffer_multiplier": 1.0,
        }

    # ATR yoksa veya <= 0 ise defansif %2 volatilite vekili
    effective_atr = atr20 if (atr20 is not None and atr20 > 0) else current_price * 0.02
    buffer_mult = _liquidity_buffer_multiplier(avg_volume_tl_20d)

    entry_low = round(max(0.01, current_price - 0.5 * effective_atr), 2)
    entry_high = round(current_price + 0.2 * effective_atr, 2)
    effective_entry = round(0.5 * entry_low + 0.5 * entry_high, 2)

    base_stop = entry_low - 1.5 * buffer_mult * effective_atr
    if recent_swing_low is not None and 0 < recent_swing_low < entry_low:
        stop_loss = round(min(base_stop, recent_swing_low), 2)
    else:
        stop_loss = round(base_stop, 2)
    stop_loss = max(0.01, stop_loss)

    risk_per_share = round(max(0.0, effective_entry - stop_loss), 2)
    risk_pct = (risk_per_share / effective_entry) if effective_entry > 0 else 0.0

    if risk_pct > 0:
        # hesap bakiyesinin risk_pct'ye orani (%1-2 arasi, varsayilan 1.5)
        raw_size = account_risk_pct / risk_pct
        position_size_pct = round(min(max_position_size_pct, max(0.0, raw_size)), 2)
    else:
        position_size_pct = 0.0

    return {
        "entry_low": entry_low,
        "entry_high": entry_high,
        "effective_entry": effective_entry,
        "stop_loss": stop_loss,
        "position_size_pct": position_size_pct,
        "risk_per_share": risk_per_share,
        "risk_pct": round(risk_pct * 100, 2),
        "liquidity_buffer_multiplier": buffer_mult,
    }


def compute_short_term_target(current_price: float, atr20: float, sma20: float,
                              avg_volume_tl_20d: float | None = None,
                              recent_swing_low: float | None = None) -> dict:
    buffer_mult = _liquidity_buffer_multiplier(avg_volume_tl_20d)
    risk = compute_dynamic_risk_levels(
        current_price=current_price,
        atr20=atr20,
        recent_swing_low=recent_swing_low,
        avg_volume_tl_20d=avg_volume_tl_20d,
    )
    return {
        "entry_price": sma20 if sma20 else current_price,
        "target_price": current_price + 2.5 * buffer_mult * atr20,
        "stop_loss": current_price - 1.2 * buffer_mult * atr20,
        "horizon_days": 20,
        "liquidity_buffer_multiplier": buffer_mult,
        "entry_low": risk["entry_low"],
        "entry_high": risk["entry_high"],
        "dynamic_stop_loss": risk["stop_loss"],
        "position_size_pct": risk["position_size_pct"],
    }
