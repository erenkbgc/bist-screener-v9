#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db
from bist_mcp import server as bist_mcp
from macro_mcp import server as macro_mcp
from core.dividend_sustainability import check_dividend_sustainability
from core.gordon import calculate_gordon_reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--regulator", default="SPK_TFRS")
    parser.add_argument("--ratio-profile", default="industrial")
    args = parser.parse_args()
    db.init_db()

    raw = bist_mcp.get_fundamentals(args.ticker, args.as_of_date, args.regulator, args.ratio_profile)
    size = bist_mcp.get_listing_and_size(args.ticker, args.as_of_date)
    macro = macro_mcp.get_macro_snapshot(args.as_of_date)
    fundamentals_row = {**raw, "market_cap": size["market_cap"], "_raw": raw}

    div_sustain = check_dividend_sustainability(args.as_of_date, args.ticker, fundamentals_row)
    result = calculate_gordon_reference(
        args.as_of_date, args.ticker, raw["dividend_per_share_ttm"], macro["bond_2y_pct"],
        div_sustain["dividend_streak_years"], bool(div_sustain["passes_sustainability"]),
    )
    print(result)


if __name__ == "__main__":
    main()
