"""KAP kirmizi bayrak siniflandiricisi: yonetim/regulasyon/finansal sikinti.

KURAL TABANLI (regex), LLM DEGIL: no_free_text_interpretation_of_kap. Girdi
yalnizca KAP'in kendi alanlari: bildirim konusu (subject) ve sirketin yazdigi
kisa ozet (summary). Desenler data/research/kap_archive.parquet'teki 637.454
bildirimin (2010-2026) konu/ozet FREKANS TABLOSU ve elle okunan orneklerle
ayarlandi; getiri verisine BAKILMADI (bkz.
docs/research/kap_red_flags_preregistration.md).

Kural tabanli sonuc esas alinir; core/kap_llm.py'nin deneysel LLM etiketi
yalnizca bu kurallarin kacirdigi bildirimler icin panelde ayrica gosterilir.

Bu modul skor/karar URETMEZ. Catalyst skoru core/live_data.py::_CATEGORY_RULES
ile ayri kalir (agirlik 0, PR #25).

Kapsam disi (deterministik yakalanamiyor):
- Denetci degisikligi: "Bagimsiz Denetim Kurulusunun Belirlenmesi" her yil
  rutin; onceki denetci adi ozette yok.
- Faaliyet durdurma: "Faaliyetlerin ... Durdurulmasi" konusu cogunlukla bakim/
  yillik izin/COVID ("Uretime Ara Verilmesi"); sikinti ile ayrilamiyor.
- VBTS/brut takas Borsa duyurulari: KAP'ta Borsa uyesi adina yayimlanir,
  sirket (IGS) arsivinde yok; canli tarafta live_data'nin vbts kategorisi var.
"""
from __future__ import annotations

import re

# (kategori, Turkce etiket, konu deseni, ozet deseni). Sira = oncelik: bir
# bildirim yalnizca ILK eslesen kategoriye yazilir.
_RULES: list[tuple[str, str, re.Pattern | None, re.Pattern | None]] = [
    ("insolvency", "Konkordato / iflas / borç yapılandırma / sermaye kaybı (TTK)",
     re.compile(r"iflas|TTK'nın 376", re.I),
     # "6736 sayili ... yeniden yapilandirilmasi" vergi affidir, "swap ...
     # yeniden yapilandirma" turev islemidir: ikisi de "finansal"/"borc" kokune
     # baglanarak disarida birakilir.
     re.compile(r"konkordato|iflas|finansal yeniden yapılandır|borç\w*\s+yeniden yapılandır"
                r"|(?<!\w)temerrüt(?! işlemi)|TTK\W{0,3}(nın|nun|'?nin)?\W{0,3}376", re.I)),
    ("going_concern", "İşletmenin sürekliliği şüphesi",
     None,
     # "Yaygin ve sureklilik arz eden iliskili taraf islemleri" rutin rapordur.
     re.compile(r"sürekliliğe ilişkin|işletmenin\s+sürekliliği|hayatının\s+sürekliliği"
                r"|süreklilik\s+(varsayım|esas)", re.I)),
    ("auditor_adverse", "Denetçi olumsuz/şartlı görüş",
     re.compile(r"olumsuz görüş|görüş bildirmekten", re.I),
     re.compile(r"olumsuz görüş|şartlı görüş|görüş bildirmekten kaçın", re.I)),
    ("regulatory_sanction", "SPK / Rekabet / vergi yaptırımı, kayyum, gözaltı",
     None,
     # Sirketin kendisinin yaptigi suc duyurusu (magdur) bayrak DEGIL; yalnizca
     # SPK kaynakli olani sayilir.
     re.compile(r"idari para cezas|(spk|sermaye piyasası kurulu).{0,60}(suç duyuru|işlem yasağı)"
                r"|rekabet\s+(kurulu|kurumu).{0,40}soruşturma|soruşturma.{0,40}rekabet"
                r"|vergi\s+(ceza|incelem|tarhiyat)|kayyum|tmsf.{0,40}(devr|el kon|yönetim)"
                r"|gözaltına", re.I)),
    ("market_sanction", "Gözaltı/yakın izleme pazarı, brüt takas, işlem görmekten men",
     None,
     re.compile(r"gözaltı pazar|yakın izleme pazar|brüt takas|işlem görmekten men", re.I)),
    ("lawsuit_or_seizure", "Şirket aleyhine dava, icra, haciz, ihtiyati tedbir",
     re.compile(r"ortaklık aleyhine dava|icra takip", re.I),
     re.compile(r"aleyh\w*\s+(açıl|yürütül|başlatıl)|aleyhine.{0,80}dava|icra takib|haciz|ihtiyati tedbir", re.I)),
    ("board_resignation", "Yönetim kurulu / genel müdür istifası",
     None,
     re.compile(r"istifa", re.I)),
]

# Lehe sonuc/kapanis haberi: davanin reddi, haczin/tedbirin kaldirilmasi,
# takipsizlik, ust pazara gecis. Yalnizca dava/yaptirim/pazar kategorilerinde
# uygulanir -- "iflas erteleme talebinin reddi" kotu haberdir, insolvency'de
# bu filtre KULLANILMAZ.
_RESOLVED_RE = re.compile(
    r"kaldırıl|takipsizlik|davanın reddi|reddedil|lehine|beraat|feragat|üst pazar|haciz ile alınan", re.I)
_RESOLVABLE = {"regulatory_sanction", "market_sanction", "lawsuit_or_seizure"}

# Istifa yalnizca sirketin ust yonetiminde anlamli; komite/bagli ortaklik/
# iştirak istifalari rutin.
_TOP_MGMT_RE = re.compile(r"yönetim kurulu|\byk\b|genel müdür(?! yardımcı)|ceo|cfo|mali işler|denetçi", re.I)
_SUBSIDIARY_RE = re.compile(r"bağlı ortaklı|iştirak|komite", re.I)

# "Olumsuz gorus bildirilmemesi" (komitenin bagimsiz uye atamasina itirazi
# yok) ve "sehven sartli gorus ... olumlu gorus olarak duzeltilmesi" bayrak
# DEGIL (arsiv ornekleri: KORDS, EGGUB).
_AUDITOR_FALSE_RE = re.compile(r"bildirilmemesi|olarak düzelt", re.I)

RED_FLAG_LABELS: dict[str, str] = {c: label for c, label, _, _ in _RULES}


def classify(subject: str | None, summary: str | None) -> str | None:
    """Kirmizi bayrak kategorisi veya None (bayrak yok)."""
    # Arsivde bos ozet NaN (float) gelir.
    subject = subject if isinstance(subject, str) else ""
    summary = summary if isinstance(summary, str) else ""
    for category, _, subject_re, summary_re in _RULES:
        hit = bool(subject_re and subject_re.search(subject)) or bool(summary_re and summary_re.search(summary))
        if not hit:
            continue
        if category in _RESOLVABLE and _RESOLVED_RE.search(summary):
            continue
        if category == "auditor_adverse" and _AUDITOR_FALSE_RE.search(summary):
            continue
        if category == "market_sanction" and _SUBSIDIARY_RE.search(summary):
            continue
        if category == "board_resignation" and (
                not _TOP_MGMT_RE.search(summary) or _SUBSIDIARY_RE.search(summary)):
            continue
        return category
    return None
