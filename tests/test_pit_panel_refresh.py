"""Tests for incremental PIT panel refresh helpers in scripts/build_pit_panel.py."""
from __future__ import annotations

from datetime import date

import pandas as pd

from scripts.build_pit_panel import last_ended_quarter, merge_updated_statement, quarter_periods


def test_last_ended_quarter_calendar_boundaries():
    # November must include Q3 (2026, 9), unlike borsapy's _get_periods cutoff
    assert last_ended_quarter(date(2026, 11, 22)) == (2026, 9)
    assert last_ended_quarter(date(2026, 10, 1)) == (2026, 9)
    assert last_ended_quarter(date(2026, 9, 30)) == (2026, 9)
    assert last_ended_quarter(date(2026, 9, 29)) == (2026, 6)
    assert last_ended_quarter(date(2026, 6, 30)) == (2026, 6)
    assert last_ended_quarter(date(2026, 4, 15)) == (2026, 3)
    assert last_ended_quarter(date(2026, 1, 15)) == (2025, 12)
    assert last_ended_quarter(date(2026, 12, 31)) == (2026, 12)


def test_quarter_periods_sequence():
    p = quarter_periods(8, as_of=date(2026, 11, 22))
    assert p == [
        (2026, 9), (2026, 6), (2026, 3), (2025, 12),
        (2025, 9), (2025, 6), (2025, 3), (2024, 12),
    ]


def test_merge_updated_statement_preserves_history_and_replaces_overlap():
    idx = pd.Index(["TOPLAM VARLIKLAR", "Finansal Borçlar", "Finansal Borçlar"])
    old = pd.DataFrame(
        {
            "2026Q2": [100.0, 10.0, 20.0],
            "2025Q4": [90.0, 9.0, 18.0],
            "2024Q3": [70.0, 7.0, 14.0],
        },
        index=idx,
    )
    fresh = pd.DataFrame(
        {
            "2026Q3": [120.0, 12.0, 24.0],
            "2026Q2": [100.0, 10.0, 20.0],
            "2025Q4": [95.0, 9.5, 19.0],  # IAS 29 re-expressed
        },
        index=idx,
    )
    merged = merge_updated_statement(old, fresh)
    assert list(merged.columns) == ["2026Q3", "2026Q2", "2025Q4", "2024Q3"]
    assert len(merged) == 3  # no Cartesian explosion on duplicate "Finansal Borçlar"
    assert merged.loc["TOPLAM VARLIKLAR", "2026Q3"] == 120.0
    assert merged.loc["TOPLAM VARLIKLAR", "2025Q4"] == 95.0  # fresh overwrote old
    assert merged.loc["TOPLAM VARLIKLAR", "2024Q3"] == 70.0  # history preserved


def test_merge_updated_statement_handles_missing_sides():
    df = pd.DataFrame({"2026Q2": [1.0]}, index=["TOPLAM VARLIKLAR"])
    assert merge_updated_statement(df, None) is df
    assert merge_updated_statement(None, df) is df
