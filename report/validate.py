"""validation_gate: HTML raporunun icerik sozlesmesini ihlal edip etmedigini kontrol eder.

report.validation_gate.rule: "HTML icindeki tum sayisal token'lar payload
degerler kumesinde bulunmalidir." on_orphan: "Gonderim iptal."

evaluate_past_predictions_clarification.banned_claims: HTML ciktisinda
yasakli ifadelerden hicbiri gecmemeli.
"""
from __future__ import annotations

import re

from core.payload import all_numeric_tokens, format_number

BANNED_CLAIMS = [
    "kanitlanmis edge", "kanıtlanmış edge",
    "istatistiksel olarak anlamli", "istatistiksel olarak anlamlı",
    "backtest edilmis", "backtest edilmiş",
    "dogrulanmis strateji", "doğrulanmış strateji",
    "sharpe orani", "sharpe oranı",
]

# Raporda gecen ama bir olcum/skor DEGIL, sabit yapisal sayi olan degerler
# (tablo basliklarindaki ufuk gunleri, oran carpanlari vb.). Bunlar
# uydurulmus bir FIYAT/SKOR/ESIK degil, spec'in kendisinde sabit olarak
# gecen yapisal sabitlerdir (bkz. scoring.hard_filters_all_buckets,
# target_price_engine, hurdle_engine.sensitivity_table).
_ALLOWED_STANDALONE_NUMBERS = {"0", "1", "2", "3", "4", "5", "9", "100", "20", "60", "180", "14", "30", "15", "90"}

# ISO tarih (YYYY-MM-DD): once bunlari metinden cikar, aksi halde "-09" gibi
# parcalar sanki negatif bir sayiymis gibi yanlislikla yakalanir.
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# Negatif isaretini yalnizca bir harf/rakamin DEVAMI olmadigi durumda yakala
# (aksi halde "utf-8" gibi metinlerdeki "-8" yanlislikla negatif sayi sanilir).
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])-?\d+(?:[.,]\d+)?")


_HTML_ENTITY_RE = re.compile(r"&#\d+;|&[a-zA-Z]+;")  # &#39; (kacis harfi) ve &rarr; gibi varliklar
_STYLE_ATTR_RE = re.compile(r'style="[^"]*"', re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)  # sablondaki bolum numaralari (<!-- 9. ... -->) veri degildir


def _strip_html_for_scan(html: str) -> str:
    # style etiketi/ozniteligi (CSS piksel degerleri gibi veri-disi sayilar),
    # HTML yorumlari (sablon bolum numaralari) ve HTML karakter varliklarini
    # (orn. kacis isaretinin &#39; hali) taramadan cikar
    html = _HTML_COMMENT_RE.sub(" ", html)
    html = _STYLE_TAG_RE.sub(" ", html)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = _STYLE_ATTR_RE.sub(" ", html)
    html = _HTML_ENTITY_RE.sub(" ", html)
    html = _ISO_DATE_RE.sub(" ", html)
    html = re.sub(r"utf-8", " ", html, flags=re.IGNORECASE)  # <meta charset> vb. veri-disi sabitler
    return html


def find_orphan_numbers(html_content: str, payload: dict) -> list[str]:
    valid_tokens = all_numeric_tokens(payload) | _ALLOWED_STANDALONE_NUMBERS
    text = _strip_html_for_scan(html_content)
    orphans = []
    for match in _NUMBER_RE.finditer(text):
        raw = match.group().replace(",", ".")
        try:
            f = float(raw)
        except ValueError:
            continue
        if format_number(f) in valid_tokens or format_number(abs(f)) in valid_tokens:
            continue
        orphans.append(raw)
    return orphans


def find_banned_claims(html_content: str) -> list[str]:
    lowered = html_content.lower()
    return [claim for claim in BANNED_CLAIMS if claim.lower() in lowered]


def validate_report(html_content: str, payload: dict) -> dict:
    orphans = find_orphan_numbers(html_content, payload)
    banned = find_banned_claims(html_content)
    is_valid = not orphans and not banned
    return {"is_valid": is_valid, "orphan_numbers": orphans, "banned_claims_found": banned}
