#!/usr/bin/env python3
"""Old-Turkey (pre-2013) raw cache: Is Yatirim daily prices/share capital/mcap
(HisseTekil, from 1996-12) and quarterly statements (MaliTablo, from 2008Q1 only).
Probe result and caveats: r5-board/notes/oldtr_feasibility.md. No backtests here.

    python scripts/fetch_old_tr.py THYAO EREGL --out scratch/old_tr
"""
from __future__ import annotations

import argparse
import pickle
import time
from pathlib import Path

import requests

BASE = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/"
HEADERS = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
FIRST_STATEMENT_YEAR = 2008  # MaliTablo returns empty values for every year before this
BANKS = {"AKBNK", "GARAN", "ISCTR", "YKBNK", "VAKBN", "HALKB", "ASYAB", "TSKB", "SKBNK", "ALBRK"}
SLEEP = 2.0


def malitablo_params(code: str, year: int, group: str) -> dict:
    """One call = the four quarters (YTD) of one year."""
    p = {"companyCode": code, "exchange": "TRY", "financialGroup": group}
    for i, q in enumerate((3, 6, 9, 12), 1):
        p[f"year{i}"], p[f"period{i}"] = year, q
    return p


def filled_quarters(items: list[dict]) -> list[int]:
    """Quarter indices (1-4) with any non-empty value."""
    return [i for i in range(1, 5)
            if any(it.get(f"value{i}") not in (None, "", 0, "0") for it in items)]


def get_json(session, endpoint: str, params: dict) -> list[dict]:
    for k in range(3):
        try:
            r = session.get(BASE + endpoint, params=params, headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r.json().get("value", []) or []
        except Exception:  # noqa: BLE001
            time.sleep(SLEEP * 2 ** (k + 1))
    raise RuntimeError(f"{endpoint} {params} failed")


def fetch_one(session, code: str, start_year: int, end_year: int) -> dict:
    px = get_json(session, "HisseTekil", {"hisse": code, "startdate": f"01-01-{start_year}",
                                          "enddate": f"31-12-{end_year}"})
    time.sleep(SLEEP)
    group = "UFRS" if code in BANKS else "XI_29"
    stm = {}
    for y in range(max(start_year, FIRST_STATEMENT_YEAR), end_year + 1):
        stm[y] = get_json(session, "MaliTablo", malitablo_params(code, y, group))
        time.sleep(SLEEP)
    return {"code": code, "group": group, "px": px, "statements": stm}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--start", type=int, default=1996)
    ap.add_argument("--end", type=int, default=2012)
    ap.add_argument("--out", default="scratch/old_tr")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    for c in a.codes:
        d = fetch_one(s, c, a.start, a.end)
        (out / f"{c}.pkl").write_bytes(pickle.dumps(d))
        q = {y: filled_quarters(v) for y, v in d["statements"].items()}
        print(c, len(d["px"]), d["px"][0]["HGDG_TARIH"] if d["px"] else None, q, flush=True)


if __name__ == "__main__":
    main()
