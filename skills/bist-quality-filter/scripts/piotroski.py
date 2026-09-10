#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db, universe as universe_mod
from core.piotroski import calculate_piotroski_scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args()
    db.init_db()
    universe_mod.build_universe(args.as_of_date)
    eligible = universe_mod.eligible_tickers(args.as_of_date)
    for row in calculate_piotroski_scores(args.as_of_date, eligible):
        print(row)


if __name__ == "__main__":
    main()
