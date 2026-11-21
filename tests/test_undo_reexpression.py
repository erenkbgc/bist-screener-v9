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


def test_undo_q4_only_and_special_fiscal_year_shift():
    from rebuild_panels_first_published import _shift_period

    cpi = _cpi()
    c = lambda p: cpi[pit_panel.period_end(p).to_period("M")]  # noqa: E731
    # Mart sonu ozel hesap donemi (+1 ceyrek): Q4 geri alinir, Q1-Q3 degismez
    f_q4 = c(_shift_period("2025Q4", 1)) / c(_shift_period("2024Q4", 1))
    f_q4_last = c(_shift_period("2026Q1", 1)) / c(_shift_period("2025Q4", 1))
    rows = [
        {"ticker": "MRT", "period": "2024Q4", "item": "revenue", "value": 100.0 * f_q4},
        {"ticker": "MRT", "period": "2024Q4", "item": "total_assets", "value": 500.0 * f_q4},
        {"ticker": "MRT", "period": "2025Q1", "item": "revenue", "value": 40.0},
        {"ticker": "MRT", "period": "2025Q4", "item": "revenue", "value": 120.0 * f_q4_last},
        {"ticker": "MRT", "period": "2026Q1", "item": "revenue", "value": 45.0},
    ]
    classes = pd.DataFrame({"ticker": ["MRT"], "cls": ["reexpressed_q4_only"], "fy_shift_q": [1]})
    out, stats = undo_reexpression(pd.DataFrame(rows), classes, cpi)
    got = {(r.period, r.item): r.value for r in out.itertuples()}
    assert got[("2024Q4", "revenue")] == pytest.approx(100.0)
    assert got[("2024Q4", "total_assets")] == pytest.approx(500.0)
    assert got[("2025Q1", "revenue")] == pytest.approx(40.0)  # Q1-Q3 dokunulmaz
    assert got[("2025Q4", "revenue")] == pytest.approx(120.0)
    assert stats["reexpressed_q4_only_tickers"] == 1


def test_classify_one_share_class_and_multi_item_consensus():
    import classify_reexpression as cr

    # Pay grubu dagitimi (KRDMA benzeri: v_ta / k_ta = 0.2108), 3 kalem de factor'e uyuyor
    raw = {
        "bs": pd.DataFrame({"2025Q2": [210.8]}, index=["TOPLAM VARLIKLAR"]),
        "inc": pd.DataFrame(
            {"2025Q2": [210.8 * 1.3211, 21.08 * 1.3211, 42.16 * 1.3211]},
            index=["Satış Gelirleri", "Ana Ortaklık Payları", "FAALİYET KARI (ZARARI)"],
        ),
    }
    fp = {"total_assets": 1000.0, "revenue": 1000.0, "ni_parent": 100.0, "op_profit": 200.0}
    cls, ratio, note = cr.classify_one(raw, fp, "2025Q2", 1.3211)
    assert cls == "reexpressed"
    assert note == "share_class_ta_norm"
    assert ratio == pytest.approx(1.3211, rel=1e-4)

    # Tek kalem (ni_parent) tesadufen 1.0 iken diger 2 kalem uyusmuyorsa (TGSAS 2024Q2) reddedilmeli
    raw_tgs = {
        "bs": pd.DataFrame({"2024Q2": [1000.0]}, index=["TOPLAM VARLIKLAR"]),
        "inc": pd.DataFrame(
            {"2024Q2": [632.6, 100.0, 126.5]},
            index=["Satış Gelirleri", "Ana Ortaklık Payları", "FAALİYET KARI (ZARARI)"],
        ),
    }
    cls2, _, _ = cr.classify_one(raw_tgs, fp, "2024Q2", 1.3504)
    assert cls2 == "unknown"
