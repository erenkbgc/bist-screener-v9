#!/usr/bin/env python3
"""Borsadan cikmis hisselerin fiyat + tablo onbellegi
(docs/research/survivorship_delisted_preregistration.md).

Aday kodlar: data/research/delisted_candidates.txt + KAP arsivinde olup bugunku
sektor haritasinda olmayan her stock_code. Is Yatirim HisseTekil fiyat donduren
ve son islemi orneklem araliginda olan kodlar icin bilanco/gelir tablosu da
cekilir. Cikti: data/research/raw_delisted/<KOD>.pkl ve delisted_meta.json.

    python scripts/fetch_delisted.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import delisted  # noqa: E402
from core.pit_panel import fetch_statement  # noqa: E402

RESEARCH = ROOT / "data" / "research"
OUT = RESEARCH / "raw_delisted"
URL = "https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTekil"
HEADERS = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}


def candidates() -> list[str]:
    kap = pd.read_parquet(RESEARCH / "kap_archive.parquet", columns=["stock_code"]).dropna()
    codes = set(kap["stock_code"].str.split(",").explode().str.strip())
    current = {r["ticker"] for r in json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))}
    listed = {ln.strip() for ln in (RESEARCH / "delisted_candidates.txt").read_text().splitlines() if ln.strip()}
    return sorted((codes - current) | listed)


def hisse_tekil(code: str) -> list[dict] | None:
    for _ in range(3):
        try:
            r = requests.get(URL, params={"hisse": code, "startdate": "01-01-2005", "enddate": "17-10-2026"},
                             headers=HEADERS, timeout=60)
            return r.json().get("value", [])
        except Exception:  # noqa: BLE001
            time.sleep(2)
    return None


def main() -> None:
    codes = candidates()
    with ThreadPoolExecutor(6) as ex:
        prices = dict(zip(codes, ex.map(hisse_tekil, codes)))
    errors = [c for c, v in prices.items() if v is None]
    in_window = {}
    for c, rows in prices.items():
        daily = delisted.daily_frame(rows or [])
        last = delisted.last_trade(daily)
        if last is not None and delisted.TRADE_START <= last <= delisted.TRADE_END and c not in delisted.FINANCIAL_CODES:
            in_window[c] = rows
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"probed": len(codes), "with_prices": sum(bool(v) for v in prices.values()), "errors": errors,
            "in_window_nonfinancial": sorted(in_window), "no_statements": []}
    for c, rows in sorted(in_window.items()):
        bs = fetch_statement(c, "balance_sheet", 60)
        inc = fetch_statement(c, "income_stmt", 60)
        if bs is None or inc is None:
            meta["no_statements"].append(c)
        (OUT / f"{c}.pkl").write_bytes(pickle.dumps({"px": rows, "bs": bs, "inc": inc}))
        print(f"  {c}: bs {None if bs is None else bs.shape[1]} ceyrek, inc {None if inc is None else inc.shape[1]}", flush=True)
    (RESEARCH / "delisted_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Aday {meta['probed']}, fiyatli {meta['with_prices']}, hata {len(errors)}, "
          f"aralikta finansal-disi {len(in_window)}, tablosuz {meta['no_statements']}")


if __name__ == "__main__":
    main()
