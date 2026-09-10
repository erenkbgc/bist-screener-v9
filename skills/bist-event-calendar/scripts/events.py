#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db
from core.events import fetch_upcoming_events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--tickers", required=True)
    args = parser.parse_args()
    db.init_db()
    events = fetch_upcoming_events(args.as_of_date, args.tickers.split(","))
    for t, evs in events.items():
        for e in evs:
            print(f"{t}: {e['event_type']} @ {e['event_date']} (kaynak: {e['source']}, kapsam: {e['coverage_note']})")


if __name__ == "__main__":
    main()
