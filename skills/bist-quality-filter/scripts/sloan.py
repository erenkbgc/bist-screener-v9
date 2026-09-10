#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db, universe as universe_mod, fundamentals as fundamentals_mod
from core.sloan import calculate_earnings_quality


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args()
    db.init_db()
    universe_mod.build_universe(args.as_of_date)
    eligible = universe_mod.eligible_tickers(args.as_of_date)
    fnd_rows = fundamentals_mod.fetch_and_store_fundamentals(args.as_of_date, eligible)
    fnd_by_ticker = {r["ticker"]: r for r in fnd_rows}
    for row in calculate_earnings_quality(args.as_of_date, eligible, fnd_by_ticker):
        print(row)


if __name__ == "__main__":
    main()
