"""Is Yatirim TMS 29 yeniden ifadesinin geri alinmasi (docs/research/first_published_panel.md)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from rebuild_panels_first_published import bridge_ttm, undo_reexpression  # noqa: E402

from core import pit_panel  # noqa: E402


def _cpi():
    months = pd.period_range("2022-01", "2026-12", freq="M")
    return pd.Series(1.03 ** np.arange(len(months)), index=months)


def test_undo_matches_first_published_model():
    cpi = _cpi()
    c = lambda p: cpi[pit_panel.period_end(p).to_period("M")]  # noqa: E731
    periods = ["2024Q2", "2024Q4", "2025Q2", "2025Q4", "2026Q2"]
    first = {p: 100.0 * c(p) for p in periods}  # ilk yayin, kendi birimi
    rows = []
    for tk, reexp in (("TL", True), ("USDF", False)):
        for p in periods:
            nxt = f"{int(p[:4]) + 1}{p[4:]}"
            last = min(nxt, "2026Q2")
            inc_f = c(nxt) / c(p) if (reexp and nxt <= "2026Q2") else 1.0
            bs_f = (c(last) / c(p) if last > p else 1.0) if (reexp and p.endswith("Q4")) else 1.0
            if p.endswith("Q4"):
                inc_f = bs_f
            rows += [{"ticker": tk, "period": p, "item": "revenue", "value": first[p] * inc_f},
                     {"ticker": tk, "period": p, "item": "total_assets", "value": first[p] * bs_f}]
    classes = pd.DataFrame({"ticker": ["TL", "USDF"], "cls": ["reexpressed", "not_reexpressed"]})
    out, stats = undo_reexpression(pd.DataFrame(rows), classes, cpi)
    for r in out.itertuples():
        assert r.value == pytest.approx(first[r.period]), (r.ticker, r.period, r.item)
    assert stats["reexpressed_tickers"] == 1


def test_bridge_q4_ttm_is_annual_ytd():
    cpi = _cpi()
    long = pd.DataFrame([{"ticker": "X", "period": p, "item": "revenue", "value": v} for p, v in
                         (("2023Q1", 30.0), ("2023Q2", 70.0), ("2023Q3", 110.0), ("2023Q4", 100.0))])
    q = pit_panel.quarterly_table(long, cpi=cpi)
    q = bridge_ttm(q, long, cpi)
    assert q.loc[q["period"] == "2023Q4", "ttm_revenue"].iloc[0] == pytest.approx(100.0)
