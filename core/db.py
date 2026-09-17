"""SQLite schema and connection helpers.

Tum yazma islemleri bu modul uzerinden yapilir. dashboard.py bu modulden
yalnizca read_only=True ile baglanti acar (INSERT/UPDATE/DELETE calistiramaz,
bu core/dashboard tarafinda ayrica statik/test ile de dogrulanir).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bist_history.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS regime_log (
    as_of_date TEXT PRIMARY KEY,
    short_selling_ban_active INTEGER,
    ban_end_date TEXT,
    vbts_stock_count INTEGER,
    policy_rate_pct REAL,
    bond_2y_pct REAL,
    cpi_yoy_pct REAL,
    usdtry_spot REAL,
    xu100_level REAL,
    regime_change_flag INTEGER,
    real_rate_regime TEXT,
    inflation_trend TEXT,
    fx_regime TEXT
);

CREATE TABLE IF NOT EXISTS universe_snapshot (
    as_of_date TEXT, ticker TEXT, name TEXT, sector TEXT, supersector TEXT,
    ratio_profile TEXT, regulator TEXT, market_cap REAL, avg_volume_tl_20d REAL,
    tedbir_level INTEGER, tedbir_end_date TEXT, listing_days INTEGER,
    exclusion_reason TEXT, ingested_at TEXT,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    as_of_date TEXT, ticker TEXT, period_end TEXT, reporting_basis TEXT,
    pe REAL, pb REAL, ev_ebitda REAL, ev_sales REAL, roe REAL,
    eps_ttm REAL, ebitda_ttm REAL, net_debt REAL, nav_discount REAL,
    dividend_per_share_ttm REAL, payout_ratio REAL, fcf_ttm REAL,
    fcf_yield_usd REAL, null_reason TEXT, source TEXT,
    published_at TEXT, available_at TEXT, effective_at TEXT, ingested_at TEXT,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS piotroski_scores (
    as_of_date TEXT, ticker TEXT, criteria_met INTEGER, criteria_computable INTEGER,
    normalized_score REAL, null_reason TEXT,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS earnings_quality (
    as_of_date TEXT, ticker TEXT, sloan_accrual_ratio REAL, peer_percentile REAL,
    elevated_risk_flag INTEGER, null_reason TEXT,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS dividend_sustainability (
    as_of_date TEXT, ticker TEXT, fcf_payout_coverage REAL, dividend_streak_years INTEGER,
    payout_ratio_trend_3p TEXT, passes_sustainability INTEGER, null_reason TEXT,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS beta_metrics (
    as_of_date TEXT, ticker TEXT, beta_60_120d REAL,
    hurdle_rate_beta_adjusted_pct REAL, excess_over_beta_hurdle_pct REAL,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS upcoming_events (
    ticker TEXT, event_type TEXT, event_date TEXT, source TEXT, coverage_note TEXT
);

CREATE TABLE IF NOT EXISTS ownership (
    as_of_date TEXT, ticker TEXT, investor_count INTEGER, investor_count_change_1m REAL,
    retail_pct REAL, institutional_pct REAL, free_float_pct REAL, foreign_pct REAL,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS prices (
    date TEXT, ticker TEXT, open REAL, high REAL, low REAL, close REAL,
    volume REAL, atr20 REAL, sma20 REAL, sma50 REAL, volume_ratio_20d REAL,
    volatility_60d REAL,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS kap_disclosures (
    ticker TEXT, disclosure_id TEXT, category TEXT, title TEXT, summary TEXT,
    impact_sign TEXT, weight REAL, url TEXT, published_at TEXT, available_at TEXT,
    effective_at TEXT
);

CREATE TABLE IF NOT EXISTS scores (
    as_of_date TEXT, ticker TEXT, bucket TEXT, candidate_state TEXT,
    valuation_z REAL, catalyst_score REAL, ownership_z REAL, low_vol_z REAL,
    final_score REAL,
    peer_group_used TEXT, peer_n INTEGER, confidence TEXT, filtered_by TEXT
);

CREATE TABLE IF NOT EXISTS gordon_reference (
    as_of_date TEXT, ticker TEXT, dividend_per_share REAL,
    discount_rate_low REAL, discount_rate_base REAL, discount_rate_high REAL,
    fair_value_low REAL, fair_value_high REAL, null_reason TEXT,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS dcf_reference (
    as_of_date TEXT, ticker TEXT, fcf_per_share REAL, wacc_pct REAL,
    growth_low_pct REAL, growth_base_pct REAL, growth_high_pct REAL,
    terminal_growth_pct REAL, fair_value_low REAL, fair_value_high REAL,
    premium_discount_low_pct REAL, premium_discount_high_pct REAL, null_reason TEXT,
    PRIMARY KEY (as_of_date, ticker)
);

CREATE TABLE IF NOT EXISTS correlation_flags (
    as_of_date TEXT, ticker_a TEXT, ticker_b TEXT, correlation_60d REAL
);

CREATE TABLE IF NOT EXISTS predictions (
    as_of_date TEXT, ticker TEXT, bucket TEXT, entry_price REAL, target_price REAL,
    stop_loss REAL, horizon_days INTEGER, expected_roi_pct REAL, hurdle_rate_pct REAL,
    excess_over_hurdle_pct REAL, real_return_pct REAL, usd_return_pct REAL,
    rationale_hash TEXT,
    -- current_price: bist_mcp.get_current_price()'in dondurdugu "anlik" fiyat
    -- (entry_price'tan farkli olabilir -- kisa vadede entry_price bilincli bir
    -- pullback seviyesidir, SMA20; current_price ise raporun uretildigi andaki
    -- gercek/en-guncel fiyattir). price_source: 'live' | 'vwap_fallback' | 'last_close'.
    current_price REAL, price_source TEXT,
    -- transaction_cost_model (v10 roadmap): bilgi amacli, hard_filter DEGISTIRMEZ
    -- (core/hurdle.py::net_expected_roi_pct/net_excess_over_hurdle_pct).
    net_expected_roi_pct REAL, net_excess_over_hurdle_pct REAL, transaction_cost_pct REAL,
    -- volume_ratio_20d: report/templates/newsletter.html.j2 kisa vade kartinda
    -- gosterilir ("Hacim teyidi") ama HICBIR yerde persist edilmiyordu -- bu,
    -- report/validate.py::find_orphan_numbers'in HER kisa vade STRONG_OPPORTUNITY/
    -- OPPORTUNITY adayinda (coğu zaman baska hicbir alanla CAKISMAYAN bir deger
    -- oldugu icin) orphan-number hatasi vermesine ve e-postanin SESSIZCE
    -- GONDERILMEMESINE yol aciyordu (canli testte dogrulandi: orphan_numbers=['3.31']).
    volume_ratio_20d REAL,
    -- dynamic entry / stop / position sizing (v12 roadmap P0-1)
    entry_low REAL, entry_high REAL, position_size_pct REAL,
    -- valuation triangle (v13 roadmap P0-3)
    fair_value_low REAL, fair_value_base REAL, fair_value_high REAL, valuation_method TEXT
);

CREATE TABLE IF NOT EXISTS invalidation_checks (
    as_of_date TEXT, ticker TEXT, condition_field TEXT, condition_operator TEXT,
    condition_value TEXT, triggered_at TEXT, resolved INTEGER
);

CREATE TABLE IF NOT EXISTS outcomes (
    as_of_date TEXT, ticker TEXT, horizon_days INTEGER, return_pct REAL,
    xu100_return_pct REAL, deposit_return_pct REAL, usd_return_pct REAL,
    excess_vs_index_pct REAL, excess_vs_deposit_pct REAL, evaluated_at TEXT
);

CREATE TABLE IF NOT EXISTS quarantine (
    as_of_date TEXT, ticker TEXT, field TEXT, value_a REAL, value_b REAL,
    source_a TEXT, source_b TEXT, deviation_pct REAL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT, as_of_date TEXT UNIQUE, status TEXT, run_level_state TEXT,
    started_at TEXT, finished_at TEXT, email_sent INTEGER, error_message TEXT
);

CREATE TABLE IF NOT EXISTS backtest_results (
    run_id TEXT PRIMARY KEY,
    strategy_name TEXT,
    ticker TEXT,
    start_date TEXT,
    end_date TEXT,
    initial_capital REAL,
    final_capital REAL,
    total_return_pct REAL,
    cagr_pct REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    max_drawdown_pct REAL,
    hit_rate_pct REAL,
    profit_factor REAL,
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    commission_pct REAL,
    slippage_pct REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    ticker TEXT,
    entry_date TEXT,
    exit_date TEXT,
    entry_price REAL,
    exit_price REAL,
    target_price REAL,
    stop_loss REAL,
    position_size_pct REAL,
    shares REAL,
    pnl_tl REAL,
    return_pct REAL,
    exit_reason TEXT
);
"""


def get_connection(read_only: bool = False) -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if read_only:
        if not DB_PATH.exists():
            # create empty schema once so read-only mode has a valid file to open
            init_db()
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# Tablolara sema evrimi sirasinda eklenen kolonlar. "CREATE TABLE IF NOT
# EXISTS" zaten var olan (repoya commit'li) bir veritabani dosyasini ASLA
# degistirmez -- bu yuzden 2026-09-14 production run'inda "table predictions
# has no column named current_price" hatasiyla 3+ saatlik taramanin sonunda
# cokmustu. Herhangi bir tabloya yeni kolon eklendiginde buraya da eklenmeli.
_TABLE_MIGRATIONS = {
    "predictions": [
        ("current_price", "REAL"),
        ("price_source", "TEXT"),
        ("net_expected_roi_pct", "REAL"),
        ("net_excess_over_hurdle_pct", "REAL"),
        ("transaction_cost_pct", "REAL"),
        ("volume_ratio_20d", "REAL"),
        ("entry_low", "REAL"),
        ("entry_high", "REAL"),
        ("position_size_pct", "REAL"),
        ("fair_value_low", "REAL"),
        ("fair_value_base", "REAL"),
        ("fair_value_high", "REAL"),
        ("valuation_method", "TEXT"),
    ],
    "prices": [
        ("volatility_60d", "REAL"),
    ],
    "scores": [
        ("low_vol_z", "REAL"),
    ],
}


def _migrate_existing_tables(conn: sqlite3.Connection) -> None:
    for table, migrations in _TABLE_MIGRATIONS.items():
        existing_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.executescript(SCHEMA)
        _migrate_existing_tables(conn)
        conn.commit()
    finally:
        conn.close()


def executemany(sql: str, rows: Iterable[tuple]) -> None:
    conn = get_connection()
    try:
        conn.executemany(sql, list(rows))
        conn.commit()
    finally:
        conn.close()


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = get_connection(read_only=False)
    try:
        cur = conn.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()
