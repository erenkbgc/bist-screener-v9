"""kap.org.tr "Bildirim Sorgu" uc noktasi (disclosure/members/byCriteria).

memberType=IGS: borsada islem goren sirketler (delist olmuslar dahil). Tek
cevap en fazla PAGE_CAP kayit dondurur. KAP ~90 hizli istekte IP'yi
dakikalarca keser ("Server disconnected"); istek sayisi dusuk tutulmali.
Kullananlar: scripts/build_kap_archive.py (arsiv), core/kap_red_flag_panel.py
(canli panel).
"""
from __future__ import annotations

import time
from datetime import date

import httpx

URL = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
PAGE_CAP = 2000
KEEP = ("disclosureIndex", "publishDate", "stockCodes", "subject", "summary",
        "disclosureClass", "disclosureType", "isLate", "ruleType", "attachmentCount")
HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}


def _body(fr: str, to: str) -> dict:
    return {"fromDate": fr, "toDate": to, "year": "", "prd": "", "term": "", "ruleType": "",
            "bdkReview": "", "disclosureClass": "", "index": "", "market": "", "isLate": "",
            "subjectList": [], "mkkMemberOidList": [], "inactiveMkkMemberOidList": [],
            "bdkMemberOidList": [], "mainSector": "", "sector": "", "subSector": "",
            "memberType": "IGS", "fromDateString": "", "toDateString": "", "srcCategory": "",
            "discIndex": []}


def client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, follow_redirects=True)


def fetch_range(http: httpx.Client, fr: date, to: date, retries: int = 8,
                base_wait: float = 30, max_wait: float = 960) -> list[dict]:
    """[fr, to] araligindaki bildirimler. Hata: bekle (base_wait*2^deneme,
    en fazla max_wait), tekrar dene; tukenirse RuntimeError."""
    span = f"{fr}..{to}"
    for attempt in range(retries):
        try:
            r = http.post(URL, json=_body(fr.isoformat(), to.isoformat()), timeout=60)
            r.raise_for_status()
            return [{k: x.get(k) for k in KEEP} for x in r.json()]
        except Exception as exc:  # noqa: BLE001 - ag hatasi: bekle, tekrar dene
            if attempt == retries - 1:
                raise RuntimeError(f"{span} cekilemedi: {exc}") from exc
            wait = min(base_wait * 2 ** attempt, max_wait)
            print(f"[hata] {span}: {exc}; {wait:.0f}s sonra tekrar", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{span} cekilemedi")
