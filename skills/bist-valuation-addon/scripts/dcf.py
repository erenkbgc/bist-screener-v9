#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import db
from bist_mcp import server as bist_mcp
from macro_mcp import server as macro_mcp
from core.beta_hurdle import calculate_beta
from core.mock_data import mock_prices
from core.dcf import calculate_dcf_reference


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
    prices = bist_mcp.get_prices(args.ticker, args.as_of_date, days=140)
    current_price = prices[-1]["close"] if prices else None

    shares_outstanding = None
    if size["market_cap"] and raw.get("pe") and raw.get("eps_ttm"):
        shares_outstanding = size["market_cap"] / (raw["pe"] * raw["eps_ttm"])

    # core/beta_hurdle.py::calculate_beta_adjusted_hurdle ile AYNI kaynak
    # (mock_prices("XU100_INDEX", ...)) -- tutarlilik icin; ana run.py
    # kosusunun urettigi beta_60_120d ile bu betanin ayni olmasi gerekir.
    market_prices = mock_prices("XU100_INDEX", args.as_of_date, days=140)
    beta = calculate_beta(prices, market_prices)

    result = calculate_dcf_reference(
        args.as_of_date, args.ticker, raw.get("fcf_ttm"), shares_outstanding, current_price,
        beta, macro["bond_2y_pct"], size["market_cap"], raw.get("net_debt"),
        raw.get("_financial_expenses_ttm"),
    )
    print(result)


if __name__ == "__main__":
    main()
