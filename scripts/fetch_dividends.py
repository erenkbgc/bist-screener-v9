#!/usr/bin/env python3
"""Panel evrenindeki hisselerin nakit temettu gecmisi (borsapy / Is Yatirim)
-> data/research/dividends.parquet (ticker, ex_date, total_dividend).

Hata veren hisse `failed` listesine yazilir; temettusu olmayan hisse bos donmesi
ile ayirt edilir (docs/research/dividend_yield_preregistration.md).

    python scripts/fetch_dividends.py
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"


def fetch(ticker: str) -> pd.DataFrame:
    import borsapy as bp
    for attempt in range(3):
        try:
            d = bp.Ticker(ticker).dividends
            if d is None or len(d) == 0:
                return pd.DataFrame(columns=["ticker", "ex_date", "total_dividend"])
            return pd.DataFrame({"ticker": ticker, "ex_date": pd.to_datetime(d.index).tz_localize(None),
                                 "total_dividend": pd.to_numeric(d["TotalDividend"], errors="coerce").to_numpy()})
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(ticker)


def main() -> None:
    tickers = sorted(pd.read_parquet(RESEARCH / "factors_monthly.parquet", columns=["ticker"])["ticker"].unique())
    frames, failed = [], []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch, t): t for t in tickers}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                frames.append(f.result())
            except Exception:  # noqa: BLE001
                failed.append(futs[f])
            if n % 100 == 0:
                print(f"  {n}/{len(tickers)}", flush=True)
    out = pd.concat(frames, ignore_index=True)
    out.to_parquet(RESEARCH / "dividends.parquet", index=False)
    (RESEARCH / "dividends_failed.json").write_text(json.dumps(sorted(failed)))
    print(f"hisse {len(tickers)}, basarisiz {len(failed)}, temettu satiri {len(out)}, "
          f"odeyen hisse {out['ticker'].nunique()}")


if __name__ == "__main__":
    sys.exit(main())
