#!/usr/bin/env python3
"""KAP bildirimlerini ceker (zaten kategorize edilmis), decay uygulanmis
katalizor skorunu yazdirir. Ham bildirim metni bu scriptin disina, ozellikle
bir LLM'e ASLA verilmez."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db
from core.catalysts import fetch_kap_catalysts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--tickers", required=True, help="virgulle ayrilmis ticker listesi")
    parser.add_argument("--lookback-days", type=int, default=14)
    args = parser.parse_args()
    db.init_db()
    tickers = args.tickers.split(",")
    scores = fetch_kap_catalysts(args.as_of_date, tickers, lookback_days=args.lookback_days)
    for t, s in scores.items():
        print(f"{t}: catalyst_score={s['catalyst_score']:.3f} volatility_event={s['volatility_event']}")


if __name__ == "__main__":
    main()
