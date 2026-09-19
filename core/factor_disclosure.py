"""core/factor_disclosure.py: Faktor Ifsa ve Skor Katki Analizi Modulu.

v13 Roadmap P1-6:
1. final_score bilesen analizi:
   valuation_z * 0.50, catalyst_score * 0.25, ownership_z * 0.15, low_vol_z * 0.10.
2. "Bu skoru ne artirdi, ne dusurdu?" kural-tabanli aciklama uretimi.
3. factor_contributions tablosu ve DB persistansi.
4. Rapor ve bultenler icin seffaf faktor ayrisimi.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from core import db

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).resolve().parent.parent / "config" / "weights.yaml"


def load_scoring_weights() -> dict[str, float]:
    """weights.yaml dosyasindan guncel faktor agirliklarini okur."""
    try:
        with open(_WEIGHTS_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            w = cfg.get("scoring_weights", {})
            return {
                "valuation_z": float(w.get("valuation_z", 0.50)),
                "catalyst_score": float(w.get("catalyst_score", 0.25)),
                "ownership_quality_z": float(w.get("ownership_quality_z", 0.15)),
                "low_vol_z": float(w.get("low_vol_z", 0.10)),
            }
    except Exception as e:
        logger.warning("weights.yaml okunamadi, varsayilan agirliklar kullaniliyor: %s", e)
        return {
            "valuation_z": 0.50,
            "catalyst_score": 0.25,
            "ownership_quality_z": 0.15,
            "low_vol_z": 0.10,
        }


FACTOR_NAMES_TR = {
    "valuation_z": "Değerleme İskontosu (Z-Skor)",
    "catalyst_score": "Katalizör ve Büyüme Skoru",
    "ownership_quality_z": "Ortaklık / Kurumsal Kalite",
    "low_vol_z": "Düşük Volatilite / Risk Anomalisi",
}


def explain_candidate_score(candidate: dict, weights: dict[str, float] | None = None) -> dict[str, Any]:
    """Tek bir hisse adayinin final_score bilesenlerini ve 'ne artirdi, ne dusurdu' aciklamasini turetir."""
    if weights is None:
        weights = load_scoring_weights()

    val_z = float(candidate.get("valuation_z") or 0.0)
    cat_s = float(candidate.get("catalyst_score") or 0.0)
    own_z = float(candidate.get("ownership_z") or 0.0)
    vol_z = float(candidate.get("low_vol_z") or 0.0)

    val_contrib = round(weights["valuation_z"] * val_z, 4)
    cat_contrib = round(weights["catalyst_score"] * cat_s, 4)
    own_contrib = round(weights["ownership_quality_z"] * own_z, 4)
    vol_contrib = round(weights["low_vol_z"] * vol_z, 4)

    final_score = round(val_contrib + cat_contrib + own_contrib + vol_contrib, 4)

    contrib_map = {
        "valuation_z": val_contrib,
        "catalyst_score": cat_contrib,
        "ownership_quality_z": own_contrib,
        "low_vol_z": vol_contrib,
    }

    # Pozitif ve negatif itici gucler
    sorted_factors = sorted(contrib_map.items(), key=lambda x: x[1], reverse=True)
    top_pos_key, top_pos_val = sorted_factors[0]
    bottom_key, bottom_val = sorted_factors[-1]

    top_pos_name = FACTOR_NAMES_TR.get(top_pos_key, top_pos_key)
    top_neg_name = FACTOR_NAMES_TR.get(bottom_key, bottom_key) if bottom_val < 0 else None

    # Gorece paylar (mutlak deger bazinda yuzde katkilar)
    abs_sum = sum(abs(v) for v in contrib_map.values())
    if abs_sum > 0:
        factor_shares = {k: round((abs(v) / abs_sum) * 100.0, 1) for k, v in contrib_map.items()}
    else:
        factor_shares = {k: 25.0 for k in contrib_map}

    # Dogal dil ifsa metni olustur
    ticker = candidate.get("ticker", "ADAY")
    pos_parts = [f"{FACTOR_NAMES_TR[k]} (+{v:.2f})" for k, v in sorted_factors if v > 0]
    neg_parts = [f"{FACTOR_NAMES_TR[k]} ({v:.2f})" for k, v in sorted_factors if v < 0]

    if pos_parts and neg_parts:
        explanation = (
            f"{ticker} toplam skoru ({final_score:.2f}); en çok {', '.join(pos_parts)} ile desteklenirken, "
            f"{', '.join(neg_parts)} faktörleri skoru baskılamıştır."
        )
    elif pos_parts:
        explanation = (
            f"{ticker} toplam skoru ({final_score:.2f}); tüm temel faktörler ({', '.join(pos_parts)}) "
            f"tarafından pozitif yönde desteklenmiştir."
        )
    elif neg_parts:
        explanation = (
            f"{ticker} toplam skoru ({final_score:.2f}); negatif faktörler ({', '.join(neg_parts)}) "
            f"nedeniyle baskı altında kalmıştır."
        )
    else:
        explanation = f"{ticker} için faktör katkıları nötr seviyededir."

    return {
        "ticker": ticker,
        "bucket": candidate.get("bucket", "long_term"),
        "final_score": final_score,
        "valuation_contrib": val_contrib,
        "catalyst_contrib": cat_contrib,
        "ownership_contrib": own_contrib,
        "low_vol_contrib": vol_contrib,
        "top_positive_factor": top_pos_name,
        "top_negative_factor": top_neg_name or "Yok (Negatif etki yok)",
        "explanation": explanation,
        "factor_shares_pct": factor_shares,
    }


def compute_and_save_factor_contributions(
    candidates: list[dict],
    as_of_date: str,
    weights: dict[str, float] | None = None,
    save_to_db: bool = True,
) -> list[dict]:
    """Aday listesindeki tum puanlanmis sirketler icin faktor katki analizini hesaplar ve DB'ye yazar."""
    if weights is None:
        weights = load_scoring_weights()
    results: list[dict] = []
    db_rows: list[tuple] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for c in candidates:
        if c.get("candidate_state") in ("NO_ACTION", "QUARANTINE"):
            continue
        if c.get("final_score") is None and c.get("valuation_z") is None:
            continue

        exp = explain_candidate_score(c, weights)
        c["factor_attribution"] = exp
        results.append(exp)

        db_rows.append((
            as_of_date,
            exp["ticker"],
            exp["bucket"],
            exp["final_score"],
            exp["valuation_contrib"],
            exp["catalyst_contrib"],
            exp["ownership_contrib"],
            exp["low_vol_contrib"],
            exp["top_positive_factor"],
            exp["top_negative_factor"],
            exp["explanation"],
            now_iso,
        ))

    if save_to_db and db_rows:
        conn = db.get_connection()
        try:
            conn.executemany(
                """INSERT INTO factor_contributions
                   (as_of_date, ticker, bucket, final_score, valuation_contrib, catalyst_contrib,
                    ownership_contrib, low_vol_contrib, top_positive_factor, top_negative_factor,
                    explanation, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(as_of_date, ticker, bucket) DO UPDATE SET
                     final_score=excluded.final_score,
                     valuation_contrib=excluded.valuation_contrib,
                     catalyst_contrib=excluded.catalyst_contrib,
                     ownership_contrib=excluded.ownership_contrib,
                     low_vol_contrib=excluded.low_vol_contrib,
                     top_positive_factor=excluded.top_positive_factor,
                     top_negative_factor=excluded.top_negative_factor,
                     explanation=excluded.explanation,
                     created_at=excluded.created_at""",
                db_rows,
            )
            conn.commit()
        finally:
            conn.close()

    return results


def get_factor_contributions_from_db(as_of_date: str, ticker: str | None = None) -> list[dict]:
    """DB'de kayitli faktor katki analizlerini dondurur."""
    if ticker:
        rows = db.query(
            "SELECT * FROM factor_contributions WHERE as_of_date = ? AND ticker = ?",
            (as_of_date, ticker.upper()),
        )
    else:
        rows = db.query(
            "SELECT * FROM factor_contributions WHERE as_of_date = ? ORDER BY final_score DESC",
            (as_of_date,),
        )
    return [dict(r) for r in rows]
