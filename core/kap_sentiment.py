"""KAP bildirim metni -> FinBERT duygu skoru (BILGI amacli katman).

Neden: baslik tabanli kural siniflandirici (core/live_data.py::_CATEGORY_RULES)
bildirimlerin ~%91'ini "material_event_other" (notr, sinyal yok) birakiyor;
"Ozel Durum Aciklamasi (Genel)" basligi 150 ucaklik siparisi de rutin bir
duyuruyu da ayni kovaya atar. Bu modul bildirim GOVDESINI okur.

Yontem (deterministik, sabit agirlikli modeller; uretken LLM DEGIL):
  1. KAP HTML -> "Ozet Bilgi" + "Aciklamalar" govdesi (kap.org.tr Next.js sayfasi)
  2. Turkce -> Ingilizce: Helsinki-NLP/opus-mt-tr-en (MarianMT)
  3. ProsusAI/finbert (Financial PhraseBank uzerinde egitilmis BERT)
     sentiment = P(positive) - P(negative), [-1, +1]

SINIR: final_score'a BAGLI DEGIL. Modelin BIST/KAP uzerinde isabeti olculmedi
(priors_are_disclosed); outcomes tablosu dolup olay-getiri iliskisi test
edilmeden skorlamaya eklenmemeli. Ceviri adimi hata ekleyebilir.
"""
from __future__ import annotations

import re
from functools import lru_cache

TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-tr-en"
SENTIMENT_MODEL = "ProsusAI/finbert"
MAX_BODY_CHARS = 2500

_BODY_MARKER = "oda_ExplanationTextBlock|"
_SUMMARY_MARKER = "Özet Bilgi"
# Govde sonundaki yasal kalip/ekler; duygu sinyali tasimaz.
_BODY_END_RE = re.compile(
    r"Yukarıdaki açıklamalarımızın|Ek Açıklamalar|Ekler|Bildirimin İngilizce|"
    r"Yukarıdaki açıklamaların|Kamuya duyurulur|Saygılarımızla", re.I)
_ODA_FIELD_RE = re.compile(r"oda_\w+\|")
# KAP form alanlari (govdeye karisan evet/hayir sorulari); duygu tasimaz.
_FORM_NOISE_RE = re.compile(
    r"Yapılan [Aa]çıklama[^?]{0,60}\?\s*(Evet|Hayır)?(\s*\((Yes|No)\))*|"
    r"Konuya İlişkin Daha Önce Yapılan Açıklamanın Tarihi[\s\d.]*", re.I)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")


def extract_disclosure_text(html: str) -> dict:
    """KAP bildirim sayfasindan ozet ve govde metnini cikarir.
    Govde isaretcisi yoksa (tablo agirlikli bildirimler) body bos doner."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()

    summary = ""
    i = text.find(_SUMMARY_MARKER)
    if i >= 0:
        rest = text[i + len(_SUMMARY_MARKER):].strip()
        # Ozet, ilk "[", "İlgili Şirketler" veya oda_ alanina kadar
        m = re.search(r"\[|İlgili Şirketler|oda_|Yapılan [Aa]çıklama", rest)
        summary = (rest[:m.start()] if m else rest[:200]).strip()

    body = ""
    j = text.find(_BODY_MARKER)
    if j >= 0:
        rest = text[j + len(_BODY_MARKER):]
        m = _BODY_END_RE.search(rest)
        body = rest[:m.start()] if m else rest
        body = _ODA_FIELD_RE.split(body)[0]
        body = _FORM_NOISE_RE.sub(" ", body)
        body = re.sub(r"\s+", " ", body).strip()[:MAX_BODY_CHARS]
    return {"summary": summary, "body": body}


@lru_cache(maxsize=1)
def _translator():
    from transformers import MarianMTModel, MarianTokenizer
    tok = MarianTokenizer.from_pretrained(TRANSLATION_MODEL)
    model = MarianMTModel.from_pretrained(TRANSLATION_MODEL).eval()
    return tok, model


@lru_cache(maxsize=1)
def _finbert():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL).eval()
    return tok, model


def translate_tr_en(text: str, batch_size: int = 8) -> str:
    import torch

    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return ""
    tok, model = _translator()
    out: list[str] = []
    with torch.no_grad():
        for k in range(0, len(sentences), batch_size):
            batch = tok(sentences[k:k + batch_size], return_tensors="pt", padding=True,
                        truncation=True, max_length=256)
            gen = model.generate(**batch, num_beams=1, max_new_tokens=256)
            out.extend(tok.batch_decode(gen, skip_special_tokens=True))
    return " ".join(out)


def finbert_sentiment(text_en: str) -> dict:
    """Cumle bazli FinBERT; cumle olasiliklari ortalanir (uzun metinde 512 token
    kesilmesinden kacinmak icin). Donus: label, score (P+ - P-), olasiliklar."""
    import torch

    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text_en) if len(s.split()) >= 3]
    if not sentences:
        return {"label": "neutral", "score": 0.0, "p_positive": 0.0, "p_negative": 0.0,
                "p_neutral": 1.0, "n_sentences": 0}
    tok, model = _finbert()
    with torch.no_grad():
        enc = tok(sentences, return_tensors="pt", padding=True, truncation=True, max_length=256)
        sent_probs = torch.softmax(model(**enc).logits, dim=-1)
    probs = sent_probs.mean(dim=0)
    labels = [model.config.id2label[i].lower() for i in range(probs.shape[0])]
    p = {lab: float(probs[i]) for i, lab in enumerate(labels)}
    # Ortalama, uzun hukuki metinde notr kaliplarla seyrelir (orn. 150 ucaklik
    # siparis +0.07 cikti). En belirgin cumle ayrica raporlanir.
    ipos, ineg = labels.index("positive"), labels.index("negative")
    per_sentence = (sent_probs[:, ipos] - sent_probs[:, ineg]).tolist()
    k = max(range(len(per_sentence)), key=lambda n: abs(per_sentence[n]))
    return {
        "label": max(p, key=p.get),
        "score": round(p.get("positive", 0.0) - p.get("negative", 0.0), 4),
        "p_positive": round(p.get("positive", 0.0), 4),
        "p_negative": round(p.get("negative", 0.0), 4),
        "p_neutral": round(p.get("neutral", 0.0), 4),
        "n_sentences": len(sentences),
        "peak_score": round(per_sentence[k], 4),
        "peak_sentence": sentences[k][:300],
    }


def analyze_disclosure_html(html: str) -> dict:
    parts = extract_disclosure_text(html)
    source_tr = " ".join(x for x in (parts["summary"] + ".", parts["body"]) if x.strip(". "))
    text_en = translate_tr_en(source_tr) if source_tr.strip(". ") else ""
    return {**parts, "text_en": text_en, **finbert_sentiment(text_en)}
