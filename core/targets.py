"""target_price_engine: uzun ve kisa vade hedef fiyat hesaplari.

mandatory_downstream (spec): "Her hedef hurdle_engine'den gecmeden rapora
giremez." -> Bu dosya yalnizca target/entry/stop uretir; hurdle gecisi
core/scoring.py ve core/payload.py asamasinda ayrica uygulanir.
"""
from __future__ import annotations

from statistics import median

import math

from core.ranking import build_peer_group
from core.valuation_triangle import compute_valuation_triangle
from core.weight_optimizer import load_optimized_weights

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


def compute_volatility_cone_envelope(
    current_price: float,
    volatility_60d: float | None = None,
    atr20: float | None = None,
    horizon_days: int = 180,
    risk_free_annual_pct: float = 45.0,
    z: float | None = None,
) -> float:
    """Geometrik Brownian Hareketi ve Volatilite Konisi (Black-Scholes / Hull):
    Belirli bir vadedeki (T = horizon_days / 252) istatistiki %95-97 tavan fiyat:
      Upper = P0 * exp((mu - 0.5 * sigma^2)*T + z * sigma * sqrt(T))
    z katsayisi ampirik kalibrasyondan gelir (varsayilan z=1.75).
    """
    if current_price <= 0:
        return current_price

    if volatility_60d and volatility_60d > 0.01:
        sigma = float(volatility_60d)
    elif atr20 and atr20 > 0:
        sigma = float((atr20 / current_price) * math.sqrt(252))
    else:
        sigma = 0.35  # BIST piyasa taban oynakligi

    T = horizon_days / 252.0
    mu = (risk_free_annual_pct / 100.0) * 0.5

    if z is None:
        opt = load_optimized_weights()
        z = float(opt.get("calibrated_z_score", 1.75)) if opt else 1.75

    exponent = (mu - 0.5 * (sigma ** 2)) * T + z * sigma * math.sqrt(T)
    upper_bound = current_price * math.exp(exponent)
    return bist_tick_round(round(upper_bound, 2)) or round(upper_bound, 2)


def compute_long_term_target(
    candidate: dict,
    all_candidates: list[dict],
    macro_snapshot: dict | None = None,
    prob_up: float | None = None,
) -> dict:
    """Coklu Degerleme Metodolojisi / Degerleme Ucgeni (v13 roadmap P0-3).
    DCF (%40) + Emsal Carpanlar (%35) + Kalite Primi (%25).
    GYO ve Holding icin NAV hesaplamasi.

    Gercekci Hedef Fiyat & Volatilite Konisi:
    - Eger volatilite veya ATR bilgisi varsa 180 gunluk gerceklesme konisi (z*)
      ve ampirik piyasa yakinsama hizi (alpha*) ile hedefler gercekci zarfa oturur.
    - Sinirlanmamis deger 'terminal_fair_value' olarak muhafaza edilir.
    """
    peers, peer_level, confidence = build_peer_group(candidate, all_candidates)
    effective_prob_up = prob_up if prob_up is not None else candidate.get("prob_up")
    triangle = compute_valuation_triangle(
        candidate, peers, macro_snapshot=macro_snapshot, prob_up=effective_prob_up
    )

    raw_target = triangle["target_price"]
    current_price = candidate.get("entry_price") or candidate.get("current_price") or 0.0

    volatility_60d = candidate.get("volatility_60d")
    atr20 = candidate.get("atr20")
    rf_rate = (macro_snapshot or {}).get("bond_2y_pct", 45.0)

    ceiling = None
    actionable_target = raw_target

    # Yalnizca hissede volatilite/ATR bilgisi mevcutsa (gercek piyasa verisi) koni ve yakinsama uygula
    if current_price > 0 and raw_target is not None and (volatility_60d or atr20):
        ceiling = compute_volatility_cone_envelope(
            current_price=current_price,
            volatility_60d=volatility_60d,
            atr20=atr20,
            horizon_days=180,
            risk_free_annual_pct=rf_rate,
        )
        opt = load_optimized_weights()
        alpha = float(opt.get("calibrated_alpha", 0.40)) if opt else 0.40

        # Enflasyonel nominal suruklenme
        cpi_exp = (macro_snapshot or {}).get("cpi_yearend_expectation_pct", 25.0) or 25.0
        drift_nominal = current_price * ((cpi_exp / 100.0) * (180.0 / 365.0) * 0.4)

        projected = current_price + alpha * (raw_target - current_price) + drift_nominal
        if ceiling and ceiling > current_price:
            actionable_target = min(projected, ceiling)
        else:
            actionable_target = projected

        actionable_target = max(0.01, bist_tick_round(round(actionable_target, 2)))

    return {
        "target_price": actionable_target,
        "terminal_fair_value": raw_target,
        "volatility_cone_ceiling": ceiling,
        "fair_value_low": triangle["fair_value_low"],
        "fair_value_base": triangle["fair_value_base"],
        "fair_value_high": triangle["fair_value_high"],
        "valuation_method": triangle["valuation_method"],
        "weights_used": triangle["weights_used"],
        "scenario_probabilities": triangle.get("scenario_probabilities"),
        "dcf_leg": triangle["dcf_leg"],
        "peers_leg": triangle["peers_leg"],
        "quality_leg": triangle["quality_leg"],
        "horizon_days": 180,
        "peer_group_used": peer_level,
        "peer_n": len(peers),
        "confidence": confidence,
        "legs_used": triangle["legs_used"],
    }


def bist_tick_round(price: float | None) -> float | None:
    """BIST Pay Piyasasi resmi fiyat adimi (tick size) tablosuna gore yuvarlar:
      - 0.01 - 19.99 TL  -> 0.01 TL (1 kurus)
      - 20.00 - 49.99 TL -> 0.02 TL (2 kurus)
      - 50.00 - 99.99 TL -> 0.05 TL (5 kurus)
      - 100.00 TL ve ustu-> 0.10 TL (10 kurus)
    """
    if price is None or price <= 0:
        return price
    if price < 20.0:
        step = 0.01
    elif price < 50.0:
        step = 0.02
    elif price < 100.0:
        step = 0.05
    else:
        step = 0.10
    return round(round(price / step) * step, 2)


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
    - entry_low = current_price - 0.5 * ATR20 (BIST tick rounded)
    - entry_high = current_price + 0.2 * ATR20 (BIST tick rounded)
    - stop_loss = entry_low - 1.5 * ATR20 (veya son swing dusuk destegi)
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

    entry_low = bist_tick_round(round(max(0.01, current_price - 0.5 * effective_atr), 2))
    entry_high = bist_tick_round(round(current_price + 0.2 * effective_atr, 2))
    effective_entry = bist_tick_round(round(0.5 * entry_low + 0.5 * entry_high, 2))

    base_stop = entry_low - 1.5 * buffer_mult * effective_atr
    if recent_swing_low is not None and 0 < recent_swing_low < entry_low:
        stop_loss = round(min(base_stop, recent_swing_low), 2)
    else:
        stop_loss = round(base_stop, 2)
    stop_loss = max(0.01, stop_loss)
    stop_loss = bist_tick_round(stop_loss)

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
                              recent_swing_low: float | None = None,
                              recent_swing_high: float | None = None,
                              upper_bb: float | None = None) -> dict:
    buffer_mult = _liquidity_buffer_multiplier(avg_volume_tl_20d)
    risk = compute_dynamic_risk_levels(
        current_price=current_price,
        atr20=atr20,
        recent_swing_low=recent_swing_low,
        avg_volume_tl_20d=avg_volume_tl_20d,
    )
    raw_target = current_price + 2.5 * buffer_mult * atr20
    target_price = bist_tick_round(round(raw_target, 2))

    # Yapisal direncler (swing high veya Bollinger ust bandi) varsa hedefi tavanla
    structural_ceiling = None
    if recent_swing_high and recent_swing_high > current_price:
        structural_ceiling = recent_swing_high
    if upper_bb and upper_bb > current_price:
        structural_ceiling = min(structural_ceiling, upper_bb) if structural_ceiling else upper_bb

    if structural_ceiling and target_price > structural_ceiling:
        target_price = bist_tick_round(round(structural_ceiling, 2))

    raw_stop = current_price - 1.2 * buffer_mult * atr20
    stop_loss = bist_tick_round(round(raw_stop, 2))

    # Risk / Kazanc (Reward-to-Risk) Orani
    risk_dist = max(0.01, current_price - risk["stop_loss"])
    reward_dist = max(0.0, target_price - current_price)
    risk_reward_ratio = round(reward_dist / risk_dist, 2)

    return {
        "entry_price": sma20 if sma20 else current_price,
        "effective_entry": risk["effective_entry"],
        "target_price": target_price,
        "stop_loss": stop_loss,
        "horizon_days": 20,
        "liquidity_buffer_multiplier": buffer_mult,
        "entry_low": risk["entry_low"],
        "entry_high": risk["entry_high"],
        "dynamic_stop_loss": risk["stop_loss"],
        "position_size_pct": risk["position_size_pct"],
        "risk_reward_ratio": risk_reward_ratio,
        "take_profit_1": bist_tick_round(round(min(target_price, current_price + 1.5 * buffer_mult * atr20), 2)),
        "take_profit_2": target_price,
        "structural_ceiling": structural_ceiling,
    }

