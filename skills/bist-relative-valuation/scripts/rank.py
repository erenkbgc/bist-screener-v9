#!/usr/bin/env python3
"""bist-relative-valuation skill CLI: bir tarih icin esler grubu ici valuation_z hesaplar.

Gercek mantik core/ranking.py + core/universe.py + core/fundamentals.py icindedir;
bu script yalnizca bunlari orkestre eden ince bir komut satiri sarmalayicisidir.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db, universe as universe_mod, fundamentals as fundamentals_mod
from core.ranking import compute_valuation_z


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    args = parser.parse_args()

    db.init_db()
    universe_mod.build_universe(args.as_of_date)
    eligible = universe_mod.eligible_tickers(args.as_of_date)
    fnd_rows = fundamentals_mod.fetch_and_store_fundamentals(args.as_of_date, eligible)

    candidates = []
    for u, f in zip(eligible, fnd_rows):
        c = {**u, **f["_raw"], "reporting_basis": f["reporting_basis"]}
        candidates.append(c)

    for c in candidates:
        result = compute_valuation_z(c, candidates)
        print(f"{c['ticker']:8s} valuation_z={result['valuation_z']!s:>8} "
              f"peer={result['peer_group_used']:10s} n={result['peer_n']:3d} conf={result['confidence']}")


if __name__ == "__main__":
    main()
