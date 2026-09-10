#!/usr/bin/env python3
"""core/invalidation.py'ye ince CLI sarmalayicisi."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db
from core.invalidation import check_thesis_invalidation, create_invalidation_condition


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("--as-of-date", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--as-of-date", required=True)
    p_create.add_argument("--ticker", required=True)
    p_create.add_argument("--field", required=True)
    p_create.add_argument("--operator", required=True, choices=["<", ">", "==", "changed_to"])
    p_create.add_argument("--value", required=True)

    args = parser.parse_args()
    db.init_db()

    if args.cmd == "check":
        for t in check_thesis_invalidation(args.as_of_date):
            print(t)
    else:
        create_invalidation_condition(args.as_of_date, args.ticker, args.field, args.operator, args.value)
        print("olusturuldu")


if __name__ == "__main__":
    main()
