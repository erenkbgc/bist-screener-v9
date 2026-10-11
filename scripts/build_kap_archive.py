#!/usr/bin/env python3
"""KAP bildirim arsivini kurar (data/research/, git'e girmez).

    python scripts/build_kap_archive.py                       # 2010-01-01 .. bugun
    python scripts/build_kap_archive.py --start 2024-01-01 --end 2024-12-31

Kaynak: kap.org.tr "Bildirim Sorgu" uc noktasi (disclosure/members/byCriteria),
memberType=IGS (borsada islem goren sirketler). Sorgu haftalik pencerelerle
atilir; tek cevap en fazla 2000 kayit dondurur, siniri dolduran hafta gun gun
yeniden sorgulanir (en yogun gunler ~1.200 kayit). KAP ~90 istekte IP'yi
dakikalarca kestigi icin istek sayisi dusuk tutulur. Uye filtresi
verilmedigi icin delist olmus sirketlerin bildirimleri de gelir (survivorship yok).

Ham cevaplar ay basina data/research/kap_raw/<YYYY-MM>.json olarak saklanir;
yarida kesilen kosu kaldigi yerden devam eder. Cikti:
data/research/kap_archive.parquet (bildirim basina tek satir, hisse kodu
basina patlatilmis: stock_code kolonu).

Yalnizca baslik (subject) ve kisa ozet (summary) saklanir; bunlar
core/kap_red_flags.py'de KURAL TABANLI siniflandirilir, LLM'e gitmez
(no_free_text_interpretation_of_kap).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "research"
RAW = OUT / "kap_raw"

URL = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"
PAGE_CAP = 2000
KEEP = ("disclosureIndex", "publishDate", "stockCodes", "subject", "summary",
        "disclosureClass", "disclosureType", "isLate", "ruleType", "attachmentCount")


def _body(fr: str, to: str) -> dict:
    return {"fromDate": fr, "toDate": to, "year": "", "prd": "", "term": "", "ruleType": "",
            "bdkReview": "", "disclosureClass": "", "index": "", "market": "", "isLate": "",
            "subjectList": [], "mkkMemberOidList": [], "inactiveMkkMemberOidList": [],
            "bdkMemberOidList": [], "mainSector": "", "sector": "", "subSector": "",
            "memberType": "IGS", "fromDateString": "", "toDateString": "", "srcCategory": "",
            "discIndex": []}


def fetch_range(client: httpx.Client, fr: date, to: date, retries: int = 8) -> list[dict]:
    day = f"{fr}..{to}"
    for attempt in range(retries):
        try:
            r = client.post(URL, json=_body(fr.isoformat(), to.isoformat()), timeout=60)
            r.raise_for_status()
            return [{k: x.get(k) for k in KEEP} for x in r.json()]
        except Exception as exc:  # noqa: BLE001 - ag hatasi: bekle, tekrar dene
            # KAP hizli istekte IP'yi dakikalarca keser ("Server disconnected");
            # bekleme 30 s'den ~16 dk'ya kadar uzar.
            wait = min(30 * 2 ** attempt, 960)
            print(f"[hata] {day}: {exc}; {wait}s sonra tekrar", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{day} cekilemedi")


def months(start: date, end: date):
    m = date(start.year, start.month, 1)
    while m <= end:
        nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        yield m, min(nxt - timedelta(days=1), end)
        m = nxt


def build_month(client: httpx.Client, first: date, last: date, sleep_s: float) -> Path:
    path = RAW / f"{first:%Y-%m}.json"
    partial = path.with_suffix(".partial.json")
    complete_month = last == (date(first.year + (first.month == 12), first.month % 12 + 1, 1) - timedelta(days=1))
    if path.exists():
        return path
    rows: list[dict] = []
    d = first
    while d <= last:
        week_end = min(d + timedelta(days=6), last)
        chunk = fetch_range(client, d, week_end)
        time.sleep(sleep_s)
        if len(chunk) >= PAGE_CAP and week_end > d:
            chunk = []
            for i in range((week_end - d).days + 1):
                day = d + timedelta(days=i)
                part = fetch_range(client, day, day)
                if len(part) >= PAGE_CAP:
                    print(f"[uyari] {day}: {len(part)} kayit, sayfa siniri -- eksik olabilir", flush=True)
                chunk.extend(part)
                time.sleep(sleep_s)
        rows.extend(chunk)
        d = week_end + timedelta(days=1)
    # Bitmemis ay (bugunun ayi) kalici dosya olarak yazilmaz; sonraki kosuda tekrar cekilir.
    target = path if complete_month and last < date.today() else partial
    target.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"{first:%Y-%m}: {len(rows)} bildirim", flush=True)
    return target


def to_frame(files: list[Path]) -> pd.DataFrame:
    rows = [r for f in files for r in json.loads(f.read_text(encoding="utf-8"))]
    df = pd.DataFrame(rows).drop_duplicates("disclosureIndex")
    df["published_at"] = pd.to_datetime(df["publishDate"], format="%d.%m.%Y %H:%M:%S")
    df["stock_code"] = df["stockCodes"].fillna("").str.split(",")
    df = df.explode("stock_code")
    df["stock_code"] = df["stock_code"].str.strip()
    df = df[df["stock_code"] != ""]
    return (df.drop(columns=["publishDate", "stockCodes"])
              .rename(columns={"disclosureIndex": "disclosure_index"})
              .sort_values(["published_at", "disclosure_index"])
              .reset_index(drop=True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--sleep", type=float, default=1.5, help="Istekler arasi bekleme (s); 0.3 s ~2 ay sonra engellendi")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        files = [build_month(client, a, b, args.sleep) for a, b in months(start, end)]

    df = to_frame(files)
    out = OUT / "kap_archive.parquet"
    df.to_parquet(out, index=False)
    print(f"{out}: {len(df)} satir, {df['stock_code'].nunique()} hisse, "
          f"{df['published_at'].min():%Y-%m-%d} .. {df['published_at'].max():%Y-%m-%d}")


if __name__ == "__main__":
    sys.exit(main())
