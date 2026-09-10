"""scoring: final_score hesaplar, hard_filters uygular, candidate_state atar.

KRITIK (regime_taxonomy.explicit_non_action): Bu dosya core/regime_taxonomy.py'yi
ASLA import ETMEZ. tests/test_regime_taxonomy_static.py bunu kaynak taramasiyla
dogrular; regime etiketleri yalnizca raporda gorunur, buraya veri akisi yoktur.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core import db
from core.ranking import compute_valuation_z, percentile_rank

_WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "config" / "weights.yaml"


def load_weights() -> dict:
    with open(_WEIGHTS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _is_quarantined(as_of_date: str, ticker: str) -> bool:
    rows = db.query("SELECT 1 FROM quarantine WHERE as_of_date=? AND ticker=? LIMIT 1", (as_of_date, ticker))
    return bool(rows)


def hard_filters_passed(candidate: dict, piotroski_threshold: float, as_of_date_cutoff: str) -> tuple[bool, str | None]:
    checks: list[tuple[bool, str]] = [
        (candidate["tedbir_level"] <= 1, "tedbir_level"),
        (candidate["reporting_basis"] != "unknown", "reporting_basis"),
        (candidate["confidence"] != "insufficient_peers", "confidence"),
        (candidate["listing_days"] >= 90, "listing_days"),
        (candidate["free_float_pct"] >= 15, "free_float_pct"),
        (candidate["excess_over_hurdle_pct"] is not None and candidate["excess_over_hurdle_pct"] > 0, "hurdle"),
        (candidate["effective_at"] <= as_of_date_cutoff, "point_in_time"),
        (candidate["piotroski_normalized_score"] is not None
         and candidate["piotroski_normalized_score"] >= piotroski_threshold, "piotroski"),
    ]
    if candidate["bucket"] == "short_term":
        checks.append((candidate.get("volume_ratio_20d") is not None and candidate["volume_ratio_20d"] >= 1.5,
                       "volume_breakout"))

    for passed, name in checks:
        if not passed:
            return False, name
    return True, None


def score_candidates(as_of_date: str, raw_candidates: list[dict], as_of_date_cutoff: str) -> list[dict]:
    """raw_candidates: her biri fundamentals + universe + ownership + catalyst + hurdle + piotroski
    alanlarini zaten birlestirilmis halde tasir (bkz. run.py). bucket alani 'long_term' veya
    'short_term' olmalidir.
    """
    weights = load_weights()
    w = weights["scoring_weights"]
    piotroski_threshold = weights["piotroski"]["normalized_score_threshold"]
    top_n = weights["top_n_per_bucket"]

    scored: list[dict] = []
    for c in raw_candidates:
        if _is_quarantined(as_of_date, c["ticker"]):
            c["candidate_state"] = "QUARANTINE"
            c["filtered_by"] = "quarantine"
            c["final_score"] = None
            scored.append(c)
            continue

        val = compute_valuation_z(c, [x for x in raw_candidates if x["bucket"] == c["bucket"]])
        c["valuation_z"] = val["valuation_z"]
        c["peer_group_used"] = val["peer_group_used"]
        c["peer_n"] = val["peer_n"]
        c["confidence"] = val["confidence"]

        passed, filtered_by = hard_filters_passed(c, piotroski_threshold, as_of_date_cutoff)

        if not passed:
            c["candidate_state"] = "NO_ACTION"
            c["filtered_by"] = filtered_by
            c["final_score"] = None
            scored.append(c)
            continue

        final_score = (w["valuation_z"] * (c["valuation_z"] or 0)
                       + w["catalyst_score"] * (c["catalyst_score"] or 0)
                       + w["ownership_quality_z"] * (c["ownership_z"] or 0))
        c["final_score"] = final_score
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
            if c["confidence"] == "high" and top_tier and positive_margin and \
                    c["piotroski_normalized_score"] >= piotroski_threshold:
                c["candidate_state"] = "STRONG_OPPORTUNITY"
            elif positive_margin and (not top_tier or c["confidence"] == "degraded"):
                c["candidate_state"] = "OPPORTUNITY"
            else:
                c["candidate_state"] = "WATCHLIST"

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
        "final_score": c.get("final_score"), "peer_group_used": c.get("peer_group_used"),
        "peer_n": c.get("peer_n"), "confidence": c.get("confidence"), "filtered_by": c.get("filtered_by"),
    } for c in scored]
    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO scores (as_of_date, ticker, bucket, candidate_state, valuation_z,
               catalyst_score, ownership_z, final_score, peer_group_used, peer_n, confidence, filtered_by)
               VALUES (:as_of_date, :ticker, :bucket, :candidate_state, :valuation_z, :catalyst_score,
                       :ownership_z, :final_score, :peer_group_used, :peer_n, :confidence, :filtered_by)""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def run_level_state(scored: list[dict]) -> str:
    has_action = any(c["candidate_state"] in ("STRONG_OPPORTUNITY", "OPPORTUNITY") for c in scored)
    return "NORMAL" if has_action else "NO_ACTION_TODAY"
