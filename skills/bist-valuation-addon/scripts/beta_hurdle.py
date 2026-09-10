#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db
from bist_mcp import server as bist_mcp
from macro_mcp import server as macro_mcp
from core.hurdle import compute_all
from core.beta_hurdle import calculate_beta_adjusted_hurdle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--target-price", type=float, required=True)
    args = parser.parse_args()
    db.init_db()

    prices = bist_mcp.get_prices(args.ticker, args.as_of_date, days=140)
    macro = macro_mcp.get_macro_snapshot(args.as_of_date)
    entry_price = prices[-1]["close"]
    hurdle = compute_all(entry_price, args.target_price, 180, macro)
    beta = calculate_beta_adjusted_hurdle(
        args.as_of_date, args.ticker, prices, macro["bond_2y_pct"], hurdle["expected_roi_pct"]
    )
    print({"entry_price": entry_price, **hurdle, **beta})


if __name__ == "__main__":
    main()
