"""KAP bildirimlerine dil modeliyle SABIT SEMALI etiket (deneysel, bilgi amacli).

Kural (bist_screener_v9_prompt.json::no_free_text_interpretation_of_kap):
LLM yalnizca core/kap_red_flags kategori listesinden birini veya "none"
dondurur. Serbest metin, sayi, skor, tahmin URETMEZ. Etiket skora,
siralamaya ve AL/TUT/SAT kararina GIREMEZ; bultende "deneysel" olarak
gosterilir. Her etiket model + prompt hash ile saklanir: ileride on-kayitli,
YALNIZCA ILERIYE DONUK test icin (model egitim verisinden sirketlerin
akibetini bildigi icin gecmise donuk test gecersizdir).

Girdi: kap_feed'deki konu + kisa ozet (regex ile ayni girdi). Saglayici:
OpenAI uyumlu herhangi bir chat/completions ucu; varsayilan Groq ucretsiz
katmani (GROQ_API_KEY repo secret'i). GitHub Models 2026-07-30'da kapatildi
(uc her istege duz "OK" donuyor), bu yuzden ilk surumden tasindi. Anahtar
yoksa veya cagri basarisizsa atlanir; regex paneli calismaya devam eder.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime

import httpx

from core import db
from core.kap_red_flags import RED_FLAG_LABELS

URL = os.environ.get("BIST_LLM_URL", "https://api.groq.com/openai/v1/chat/completions")
MODEL = os.environ.get("BIST_LLM_MODEL", "openai/gpt-oss-120b")
KEY_ENV = "GROQ_API_KEY"
BATCH = 20
# Ucretsiz katman dakika/gun istek limitli; birikmis bildirimler gunler icinde erir.
MAX_REQUESTS = 20
# Groq ucretsiz katmani dakikada 8000 token (TPM); bir batch ~2200 token oldugu
# icin 4. istekten sonra 429 donuyordu ve gunluk 400 bildirimin yalnizca 80'i
# etiketleniyordu (2026-10-21..24 kosulari). Saglayici "try again in 12.4s"
# ile bekleme suresini veriyor: bu sure kadar beklenip tekrar denenir. Daha
# uzun bekleme (gunluk token limiti, TPD) istenirse beklenmez, durulur.
RATE_LIMIT_MAX_WAIT_S = 65.0
RATE_LIMIT_RETRIES = 3
CATEGORIES = [*RED_FLAG_LABELS, "none"]

SYSTEM_PROMPT = (
    "Borsa Istanbul sirketlerinin KAP bildirimlerini siniflandiriyorsun. Her bildirim icin "
    "yalnizca su kategorilerden BIRINI sec:\n"
    + "\n".join(f"- {c}: {label}" for c, label in RED_FLAG_LABELS.items())
    + "\n- none: yukaridakilerden hicbiri; olagan veya olumlu bildirim.\n"
    "Kurallar: Yalnizca sirketin KENDISI icin olumsuz durumlari isaretle. Sirketin magdur oldugu "
    "dava/suc duyurusu, lehe sonuclanan surec, bagli ortaklik veya komite istifasi none'dir. "
    "Emin degilsen none sec. Yorum, aciklama, sayi yazma. "
    'Cevap yalnizca JSON: {"items": [{"id": <verilen id>, "category": "<kategori>"}]}'
)
PROMPT_HASH = hashlib.sha256(f"{MODEL}\n{SYSTEM_PROMPT}".encode()).hexdigest()[:12]


def pending(tickers: list[str], since: str, limit: int) -> list[dict]:
    """Etiketlenmemis bildirimler: once verilen hisseler, sonra en yeniler."""
    marks = ",".join("?" * len(tickers)) or "''"
    rows = db.query(
        f"SELECT f.disclosure_index, MAX(f.subject) AS subject, MAX(f.summary) AS summary, "
        f"MAX(f.published_at) AS published_at, MAX(f.ticker IN ({marks})) AS held "
        f"FROM kap_feed f LEFT JOIN kap_llm_labels l ON l.disclosure_index = f.disclosure_index "
        f"AND l.model = ? AND l.prompt_hash = ? WHERE l.disclosure_index IS NULL AND f.published_at >= ? "
        f"GROUP BY f.disclosure_index ORDER BY held DESC, published_at DESC LIMIT ?",
        (*tickers, MODEL, PROMPT_HASH, since, limit))
    return [dict(r) for r in rows]


def parse(content: str, ids: set[int]) -> dict[int, str]:
    """Model cevabini dogrular: bilinmeyen id ve kategori ATILIR."""
    content = re.sub(r"^\s*```(?:json)?|```\s*$", "", content or "").strip()
    try:
        items = json.loads(content).get("items", [])
    except (ValueError, AttributeError):
        return {}
    out = {}
    for it in items if isinstance(items, list) else []:
        try:
            i, c = int(it["id"]), str(it["category"])
        except (KeyError, TypeError, ValueError):
            continue
        if i in ids and c in CATEGORIES:
            out[i] = c
    return out


class RateLimited(RuntimeError):
    """HTTP 429; wait_s saglayicinin istedigi bekleme (bilinmiyorsa None)."""
    def __init__(self, message: str, wait_s: float | None):
        super().__init__(message)
        self.wait_s = wait_s


def retry_wait_s(headers, text: str) -> float | None:
    """429 cevabindan bekleme suresi: retry-after basligi, yoksa govdedeki 'try again in 1m2.5s'."""
    try:
        return float((headers or {}).get("retry-after"))
    except (TypeError, ValueError):
        pass
    m = re.search(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", text or "")
    return int(m.group(1) or 0) * 60 + float(m.group(2)) if m else None


def _call(http: httpx.Client, token: str, batch: list[dict]) -> dict[int, str]:
    user = json.dumps([{"id": b["disclosure_index"], "konu": b["subject"], "ozet": b["summary"] or ""}
                       for b in batch], ensure_ascii=False)
    r = http.post(URL, headers={"Authorization": f"Bearer {token}"}, timeout=90, json={
        "model": MODEL, "temperature": 0, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]})
    if r.status_code == 429:
        raise RateLimited(f"HTTP 429: {r.text[:300]}", retry_wait_s(getattr(r, "headers", None), r.text))
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    content = r.json()["choices"][0]["message"]["content"]
    return parse(content, {b["disclosure_index"] for b in batch})


def _call_with_wait(http, token: str, batch: list[dict], sleep) -> dict[int, str]:
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            return _call(http, token, batch)
        except RateLimited as exc:
            if attempt == RATE_LIMIT_RETRIES or exc.wait_s is None or exc.wait_s > RATE_LIMIT_MAX_WAIT_S:
                raise
            sleep(exc.wait_s + 1.0)
    raise AssertionError("unreachable")


def label_pending(tickers: list[str], since: str, http: httpx.Client | None = None,
                  sleep=time.sleep) -> dict:
    """Etiketlenmemis bildirimleri etiketler. 429: saglayicinin verdigi kisa sureyi
    bekleyip tekrar dener; diger hata veya uzun bekleme: durur, eldekini saklar."""
    token = os.environ.get(KEY_ENV)
    if not token:
        return {"labeled": 0, "error": f"{KEY_ENV} yok"}
    todo = pending(tickers, since, BATCH * MAX_REQUESTS)
    own = http is None
    http = http or httpx.Client()
    labeled, error = 0, None
    try:
        for k in range(0, len(todo), BATCH):
            batch = todo[k:k + BATCH]
            try:
                labels = _call_with_wait(http, token, batch, sleep)
            except Exception as exc:  # noqa: BLE001 - 429/ag/sema hatasi: panel regex ile devam eder
                error = f"{type(exc).__name__}: {exc}"[:300]
                break
            now = datetime.now().isoformat(timespec="seconds")
            db.executemany(
                "INSERT OR REPLACE INTO kap_llm_labels (disclosure_index, model, prompt_hash, category, labeled_at) "
                "VALUES (?,?,?,?,?)", [(i, MODEL, PROMPT_HASH, c, now) for i, c in labels.items()])
            labeled += len(labels)
    finally:
        if own:
            http.close()
    return {"labeled": labeled, "pending": len(todo), "error": error, "model": MODEL, "prompt_hash": PROMPT_HASH}
