#!/usr/bin/env python3
"""Uretim DB'sine (data/bist_history.db) sizmis mock/test satirlarini temizler.

Varsayilan DRY-RUN: yalnizca silinecek satir sayilarini yazar. Silmek icin:
    python scripts/purge_mock_rows.py --apply
Once yedek alin: cp data/bist_history.db data/bist_history.pre_mock_purge.db

Kanit (2026-09-27 incelemesi, origin/master DB'si uzerinde tekrar dogrulandi):
- 2026-09-17 tamamen mock: regime_log'da mock makro (policy 37.0, TUFE 31.5,
  bond 39.6, XU100 15.427 -- gercek ~13.100), 41 hisselik evren, 27 saniyelik
  kosu; tahmin fiyatlari gercek kapanislarla uyusmuyor (PETKM 98.76 vs 21.54).
- 2026-09-19 tarih-bazli SILINMEZ: fundamentals (530, live), evren (809) ve
  regime_log canli. Yalnizca tek tahmin satiri mock (KOZAL 101.66; gercek
  kapanis ~50).
- 2026-09-18 ARCLK 451.77 tahmini mock (gercek 89.75; ayni gunun 89.75'lik
  satiri canli).
- Ayni (tarih, ticker, bucket, entry_price) ile birebir tekrarlanan tahminler
  (ayni gun birden fazla kosu) tekillestirilir; aksi halde outcomes cok sayilir.
- 2026-09-18'de 23 ticker'in fundamentals satiri source='bist-data (mock)';
  ayni ticker'larin o gunku turetilmis tablolari da (piotroski, sloan, ...) mock.
- Test fikstur sizintilari: portfolio_allocations/factor_contributions (2027+),
  data_quality_reports (2024), corporate_actions TESTCORP, event_calendar
  test_simulation, kap_disclosures'ta kap.org.tr URL'i olmayan mock bildirimler.
Not: 2026-09-11/12 fundamentals 'mock' etiketi eski bir etiket hatasidir
(evren 807 hisse, canli makro) -- bunlar SILINMEZ.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "bist_history.db"
MOCK_DATES = ("2026-09-17",)
DERIVED_PER_TICKER = ["fundamentals", "piotroski_scores", "earnings_quality", "ownership",
                      "dividend_sustainability", "beta_metrics", "gordon_reference", "dcf_reference"]


def plan(conn: sqlite3.Connection) -> list[tuple[str, str, tuple]]:
    stmts: list[tuple[str, str, tuple]] = []
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")]
    for t in tables:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
        if "as_of_date" in cols:
            q = ",".join("?" * len(MOCK_DATES))
            stmts.append((f"{t}@mock_dates", f"FROM {t} WHERE as_of_date IN ({q})", MOCK_DATES))
    mock18 = tuple(r[0] for r in conn.execute(
        "SELECT ticker FROM fundamentals WHERE as_of_date='2026-09-18' AND source LIKE '%mock%'"))
    if mock18:
        q = ",".join("?" * len(mock18))
        for t in DERIVED_PER_TICKER:
            stmts.append((f"{t}@2026-09-18", f"FROM {t} WHERE as_of_date='2026-09-18' AND ticker IN ({q})", mock18))
    stmts += [
        ("predictions@mock_price", "FROM predictions WHERE (as_of_date='2026-09-18' AND ticker='ARCLK' AND entry_price > 400)"
                                   " OR (as_of_date='2026-09-19' AND ticker='KOZAL' AND entry_price > 90)", ()),
        ("predictions@exact_duplicate", "FROM predictions WHERE rowid NOT IN (SELECT MIN(rowid) FROM predictions"
                                        " GROUP BY as_of_date, ticker, bucket, entry_price)", ()),
        ("portfolio_allocations@test", "FROM portfolio_allocations WHERE as_of_date >= '2027-01-01'", ()),
        ("factor_contributions@test", "FROM factor_contributions WHERE as_of_date >= '2027-01-01'", ()),
        ("data_quality_reports@test", "FROM data_quality_reports WHERE as_of_date < '2026-01-01'", ()),
        ("corporate_actions@test", "FROM corporate_actions WHERE ticker='TESTCORP' OR source='test'", ()),
        ("event_calendar@test", "FROM event_calendar WHERE source='test_simulation'", ()),
        ("kap_disclosures@mock", "FROM kap_disclosures WHERE url IS NULL OR url NOT LIKE 'https://www.kap.org.tr%'", ()),
    ]
    return stmts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Satirlari gercekten sil")
    args = ap.parse_args()
    conn = sqlite3.connect(DB)
    try:
        for label, where, params in plan(conn):
            n = conn.execute(f"SELECT COUNT(*) {where}", params).fetchone()[0]
            if not n:
                continue
            print(f"{label:40s} {n:6d}")
            if args.apply:
                conn.execute(f"DELETE {where}", params)
        if args.apply:
            conn.commit()
            conn.execute("VACUUM")
            print("Silindi.")
        else:
            print("DRY-RUN. Silmek icin --apply ekleyin.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
