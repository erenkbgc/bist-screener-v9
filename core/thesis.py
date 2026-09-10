"""Investment Thesis Card icerigini, zaten hesaplanmis sayisal alanlardan
deterministik olarak kurar. ai_role_boundaries.allowed = [explain, summarize,
challenge, communicate]: burada hicbir sayi UYDURULMAZ, yalnizca mevcut
alanlar cumleye donusturulur. tone_rules: "Her tez icin karsi argüman zorunlu."
"""
from __future__ import annotations

from core.payload import format_number

# NOT: butun sayisal deger gosterimleri format_number ile yapilir -- bu,
# core/payload.py::all_numeric_tokens ve report/render.py::_fmt ile BIREBIR
# AYNI string temsilini garanti eder (aksi halde validation_gate orphan-sayi
# hatasi verir, bkz. report/validate.py).


def build_thesis_card(candidate: dict) -> dict:
    bullets = []
    if candidate.get("valuation_z") is not None and candidate["valuation_z"] > 0:
        bullets.append(
            f"Esler grubuna ({candidate['peer_group_used']}, n={candidate['peer_n']}) gore goreli "
            f"degerleme skoru pozitif (valuation_z={format_number(candidate['valuation_z'])})."
        )
    if candidate.get("catalyst_score") and candidate["catalyst_score"] > 0:
        bullets.append(f"Son donem KAP bildirimleri net pozitif katalizor skoru uretiyor "
                        f"(catalyst_score={format_number(candidate['catalyst_score'])}).")
    if candidate.get("excess_over_hurdle_pct") is not None:
        bullets.append(f"Beklenen getiri, {format_number(candidate['hurdle_rate_pct'])}% hurdle oranini "
                        f"{format_number(candidate['excess_over_hurdle_pct'])} puan asiyor.")
    if candidate.get("piotroski_normalized_score") is not None:
        bullets.append(f"Piotroski F-Score (normalize) {format_number(candidate['piotroski_normalized_score'])} "
                        f"ile kalite filtresini geciyor.")

    # tone_rules: "Her tez icin karsi argüman zorunlu" -> main_risk her zaman doldurulur.
    risk_parts = []
    if candidate.get("sloan_flag"):
        risk_parts.append("elevated_earnings_quality_risk (tahakkuk orani esler grubunun ust ondalik diliminde)")
    if candidate.get("confidence") != "high":
        risk_parts.append(f"esler grubu guveni '{candidate.get('confidence')}' seviyesinde, yorum temkinli okunmali")
    if candidate.get("retail_pct", 0) > 60:
        risk_parts.append(f"perakende yatirimci payi yuksek (%{format_number(candidate.get('retail_pct'))})")
    if not risk_parts:
        risk_parts.append("Peer grubu goreceli degerlemesi ve katalizor skoru zamanla tersine donebilir; "
                           "bu bir kesinlik iddiasi degildir.")
    main_risk = "; ".join(risk_parts)

    why_now = "Katalizor penceresi (son 14 gun) ve pozitif hurdle marji ayni anda gecerli." \
        if candidate.get("catalyst_score", 0) > 0 else \
        "Hurdle marji pozitif; yakin donemde belirgin bir katalizor bulunmuyor."

    invalidation_condition_display = "excess_over_hurdle_pct < 0"

    return {
        "thesis_bullets": bullets or ["Hard filtreleri gecti, ancak destekleyici belirgin bir katalizor yok."],
        "why_now": why_now,
        "main_risk": main_risk,
        "invalidation_condition_display": invalidation_condition_display,
    }
