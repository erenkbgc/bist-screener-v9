#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db
from core.regime import check_market_regime, RegimeHaltError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args()
    db.init_db()
    try:
        print(check_market_regime(args.as_of_date))
    except RegimeHaltError as exc:
        print(f"HALTED: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
