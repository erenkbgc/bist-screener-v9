"""scoring: final_score hesaplar, hard_filters uygular, candidate_state atar.

KRITIK (regime_taxonomy.explicit_non_action): Bu dosya core/regime_taxonomy.py'yi
ASLA import ETMEZ. tests/test_regime_taxonomy_static.py bunu kaynak taramasiyla
dogrular; regime etiketleri yalnizca raporda gorunur, buraya veri akisi yoktur.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core import db
from core.ranking import compute_valuation_scores, percentile_rank
from core.momentum import is_value_trap_risk
from core.weight_optimizer import load_optimized_weights

_WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "config" / "weights.yaml"


def load_weights() -> dict:
    with open(_WEIGHTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_regime_weights(regime: str | None = None, weights_cfg: dict | None = None, use_optimized: bool = False) -> dict[str, float]:
    """Piyasa rejimine gore dinamik faktor agirliklarini dondurur (Quant Level-Up Faz 1).
    
    1. Oncelik: use_optimized=True ise veri-gudumlu test edilip optimize edilmis faktor agirliklari.
    2. Oncelik: Konfigurasyon tablosu (weights.yaml).
    """
    if use_optimized:
        opt = load_optimized_weights()
        if opt:
            if regime and "regime_scoring_weights" in opt and regime in opt["regime_scoring_weights"]:
                rw = opt["regime_scoring_weights"][regime]
                tot = sum(float(v) for v in rw.values())
                return {k: float(v) / tot for k, v in rw.items()} if tot > 0 else rw
            if not regime and "scoring_weights" in opt:
                base_opt = opt["scoring_weights"]
                tot = sum(float(v) for v in base_opt.values())
                return {k: float(v) / tot for k, v in base_opt.items()} if tot > 0 else base_opt

    if weights_cfg is None:
        weights_cfg = load_weights()
    base_w = dict(weights_cfg.get("scoring_weights", {}))
    if not regime:
        return {k: float(v) for k, v in base_w.items()}
    regime_map = weights_cfg.get("regime_scoring_weights", {})
    if regime in regime_map:
        rw = regime_map[regime]
        tot = sum(float(v) for v in rw.values())
        if tot > 0:
            return {k: float(v) / tot for k, v in rw.items()}
        return {k: float(v) for k, v in rw.items()}
    return {k: float(v) for k, v in base_w.items()}


def redistribute_catalyst_weight(w: dict[str, float]) -> dict[str, float]:
    """Katalizor verisi YOKSA (KAP cekilemedi) agirligi digerlerine oransal dagitir.
    Toplam agirlik korunur; boylece skorlar veri olan hisselerle ayni olcekte kalir.
    Veri varken bildirim olmamasi (skor 0) bu duruma GIRMEZ."""
    wc = float(w.get("catalyst_score", 0.0))
    rest = {k: v for k, v in w.items() if k != "catalyst_score"}
    rest_sum = sum(rest.values())
    if wc <= 0 or rest_sum <= 0:
        return dict(w)
    scale = (rest_sum + wc) / rest_sum
    return {**{k: v * scale for k, v in rest.items()}, "catalyst_score": 0.0}


def _is_quarantined(as_of_date: str, ticker: str) -> bool:
    rows = db.query("SELECT 1 FROM quarantine WHERE as_of_date=? AND ticker=? LIMIT 1", (as_of_date, ticker))
    return bool(rows)


def hard_filters_passed(candidate: dict, as_of_date_cutoff: str) -> tuple[bool, str | None]:
    checks: list[tuple[bool, str]] = [
        (candidate["tedbir_level"] <= 1, "tedbir_level"),
        (candidate["reporting_basis"] != "unknown", "reporting_basis"),
        (candidate["confidence"] != "insufficient_peers", "confidence"),
        (candidate["listing_days"] >= 90, "listing_days"),
        # canli veri modunda free_float_pct None olabilir (fast_info cekilemedi,
        # bkz. core/live_data.py); dogrulanamayan halka aciklik guvenlik icin
        # elenir (sahte bir "gecti" varsayimi yapilmaz).
        (candidate["free_float_pct"] is not None and candidate["free_float_pct"] >= 15, "free_float_pct"),
        (candidate["excess_over_hurdle_pct"] is not None and candidate["excess_over_hurdle_pct"] > 0, "hurdle"),
        # Outlier ROI guard: 180 gunluk gercekci olmayan asiri getiri vaatleri (> %200) guvenlik icin elenir
        (candidate.get("expected_roi_pct") is None or candidate["expected_roi_pct"] <= 200.0, "outlier_roi"),
        (candidate["effective_at"] is not None and candidate["effective_at"] <= as_of_date_cutoff, "point_in_time"),
        # Piotroski sert filtresi kaldirildi (plan_2026-10-21 P2-1): long_term_preregistration.md
        # H4b (F7 <= 2 disla) ve H2b (dd5y <= -70% ve F7 <= 3 disla) deger portfoyunu iyilestirmedi.
        # Piotroski yalnizca bilgi kolonu ve STRONG_OPPORTUNITY etiketinde kullanilir.
    ]
    if candidate["bucket"] == "long_term":
        # Hurdle (beklenen getiri > rf) CAPM buyumesi yuzunden adil degerin
        # ALTINDA islem goren hisselerde de gecer. Uzun vade tezi degerlemedir:
        # senaryo-agirlikli adil deger fiyatin ustunde olmali. Deger None ise
        # (volatilite/ATR yok, yakinsama uygulanmadi) bu kapi uygulanmaz.
        v = candidate.get("valuation_excess_pct")
        checks.append((v is None or v > 0, "valuation_upside"))
        # Hedef fiyat k_e = rf + beta*ERP ile buyutuldugu icin sabit rf hurdle'i
        # beta > 0 olan her hissede otomatik gecilir. Ayni k_e'yi kullanan
        # beta-duzeltilmis hurdle tutarli kiyastir (beta hesaplanamadiysa uygulanmaz).
        b = candidate.get("excess_over_beta_hurdle_pct")
        checks.append((b is None or b > 0, "beta_hurdle"))
    if candidate["bucket"] == "short_term":
        checks.append((candidate.get("volume_ratio_20d") is not None and candidate["volume_ratio_20d"] >= 1.5,
                       "volume_breakout"))

    for passed, name in checks:
        if not passed:
            return False, name
    return True, None


# Sert filtrede None iken gecen (uygulanmayan) kapilar. Veri yoksa kapi
# "gecti" sayilmaz: aday elenmez ama en fazla WATCHLIST olur (UNKNOWN).
UNKNOWN_GATES = {
    "long_term": ("expected_roi_pct", "valuation_excess_pct", "excess_over_beta_hurdle_pct"),
    "short_term": ("expected_roi_pct",),
}


def unknown_checks(candidate: dict) -> list[str]:
    """Verisi olmadigi icin degerlendirilemeyen kapilarin alan adlari."""
    return [k for k in UNKNOWN_GATES.get(candidate["bucket"], ()) if candidate.get(k) is None]


def score_candidates(as_of_date: str, raw_candidates: list[dict], as_of_date_cutoff: str, regime: str | None = None) -> list[dict]:
    """raw_candidates: her biri fundamentals + universe + ownership + catalyst + hurdle + piotroski
    alanlarini zaten birlestirilmis halde tasir (bkz. run.py). bucket alani 'long_term' veya
    'short_term' olmalidir.
    """
    weights = load_weights()
    w = get_regime_weights(regime, weights)
    piotroski_threshold = weights["piotroski"]["normalized_score_threshold"]
    top_n = weights["top_n_per_bucket"]

    valuations: dict[int, dict] = {}
    for bucket in {c["bucket"] for c in raw_candidates}:
        members = [x for x in raw_candidates if x["bucket"] == bucket]
        valuations.update(zip(map(id, members), compute_valuation_scores(members)))

    scored: list[dict] = []
    for c in raw_candidates:
        if _is_quarantined(as_of_date, c["ticker"]):
            c["candidate_state"] = "QUARANTINE"
            c["filtered_by"] = "quarantine"
            c["final_score"] = None
            scored.append(c)
            continue

        val = valuations[id(c)]
        for k in ("valuation_z", "peer_group_used", "peer_n", "confidence", "valid_metric_count", "metrics_used"):
            c[k] = val[k]
        c["value_trap_risk"] = is_value_trap_risk(c)
        c["unknown_checks"] = unknown_checks(c)

        passed, filtered_by = hard_filters_passed(c, as_of_date_cutoff)

        if not passed:
            c["candidate_state"] = "NO_ACTION"
            c["filtered_by"] = filtered_by
            c["final_score"] = None
            scored.append(c)
            continue

        wc = w if c.get("catalyst_available", True) else redistribute_catalyst_weight(w)
        final_score = (wc["valuation_z"] * (c["valuation_z"] or 0)
                       + wc["catalyst_score"] * (c["catalyst_score"] or 0)
                       + wc["ownership_quality_z"] * (c["ownership_z"] or 0)
                       + wc["low_vol_z"] * (c.get("low_vol_z") or 0)
                       + wc.get("momentum_z", 0.0) * (c.get("momentum_z") or 0))
        c["final_score"] = final_score
        c["scoring_weights_used"] = wc
        c["market_regime_used"] = regime
        c["filtered_by"] = None
        c["candidate_state"] = "WATCHLIST"  # asagidaki dilim/confidence mantigiyla kesinlestirilecek gecici deger
        scored.append(c)

    # bucket ici top-dilim belirlemek icin final_score persentili (yalnizca gecen adaylar arasinda)
    by_bucket: dict[str, list[dict]] = {}
    for c in scored:
        by_bucket.setdefault(c["bucket"], []).append(c)

    for bucket, items in by_bucket.items():
        passing = [c for c in items if c["candidate_state"] not in ("NO_ACTION", "QUARANTINE")]
        pool = [c["final_score"] for c in passing]
        for c in passing:
            top_tier = percentile_rank(c["final_score"], pool) >= 0.75 if len(pool) >= 2 else True
            positive_margin = c["excess_over_hurdle_pct"] > 0
            if c["unknown_checks"]:
                c["candidate_state"] = "WATCHLIST"
            elif c["confidence"] == "high" and top_tier and positive_margin and \
                    (c["piotroski_normalized_score"] or 0) >= piotroski_threshold and not c["value_trap_risk"]:
                c["candidate_state"] = "STRONG_OPPORTUNITY"
            elif positive_margin and c["confidence"] in ("high", "degraded") and not c["value_trap_risk"]:
                # Eski kural "not top_tier or degraded" idi: ust dilimde olup STRONG
                # kosullarindan birini kaciran hisse WATCHLIST'e dusuyor, daha asagi
                # siradaki (value-trap bayrakli olsa bile) OPPORTUNITY oluyordu.
                c["candidate_state"] = "OPPORTUNITY"
            else:
                c["candidate_state"] = "WATCHLIST"

        # Kanitsiz kova firsata yukseltilmez (config: short_term_opportunities_enabled).
        if bucket == "short_term" and not weights.get("short_term_opportunities_enabled", True):
            for c in passing:
                if c["candidate_state"] in ("STRONG_OPPORTUNITY", "OPPORTUNITY"):
                    c["candidate_state"] = "WATCHLIST"
                c["experimental"] = True

        passing.sort(key=lambda c: (c["final_score"] is None, -(c["final_score"] or 0)))
        for rank, c in enumerate(passing):
            c["_rank_in_bucket"] = rank
            if rank >= top_n:
                c["candidate_state"] = "WATCHLIST" if c["candidate_state"] != "STRONG_OPPORTUNITY" else c["candidate_state"]

    _persist(as_of_date, scored)
    return scored


def _persist(as_of_date: str, scored: list[dict]) -> None:
    rows = [{
        "as_of_date": as_of_date, "ticker": c["ticker"], "bucket": c["bucket"],
        "candidate_state": c["candidate_state"], "valuation_z": c.get("valuation_z"),
        "catalyst_score": c.get("catalyst_score"), "ownership_z": c.get("ownership_z"),
        "low_vol_z": c.get("low_vol_z"), "momentum_z": c.get("momentum_z"),
        "final_score": c.get("final_score"), "peer_group_used": c.get("peer_group_used"),
        "peer_n": c.get("peer_n"), "confidence": c.get("confidence"), "filtered_by": c.get("filtered_by"),
        "valid_metric_count": c.get("valid_metric_count"),
        "metrics_used": ",".join(c["metrics_used"]) if c.get("metrics_used") is not None else None,
    } for c in scored]
    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO scores (as_of_date, ticker, bucket, candidate_state, valuation_z,
               catalyst_score, ownership_z, low_vol_z, momentum_z, final_score, peer_group_used, peer_n,
               confidence, filtered_by, valid_metric_count, metrics_used)
               VALUES (:as_of_date, :ticker, :bucket, :candidate_state, :valuation_z, :catalyst_score,
                       :ownership_z, :low_vol_z, :momentum_z, :final_score, :peer_group_used, :peer_n, :confidence,
                       :filtered_by, :valid_metric_count, :metrics_used)""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def run_level_state(scored: list[dict]) -> str:
    has_action = any(c["candidate_state"] in ("STRONG_OPPORTUNITY", "OPPORTUNITY") for c in scored)
    return "NORMAL" if has_action else "NO_ACTION_TODAY"
