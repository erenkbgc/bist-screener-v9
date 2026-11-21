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


def test_core_pit_panel_exposes_undo_and_bridge():
    assert pit_panel.undo_reexpression is undo_reexpression
    assert pit_panel.bridge_ttm is bridge_ttm


def test_build_pit_panel_applies_undo_bridge_and_isy_mcap(tmp_path):
    from build_pit_panel import build_panel_from_raw

    # Synthetic 2-year daily price series + quarterly statements + CPI + reexpression class + Is Yatirim PD
    dates = pd.bdate_range("2023-01-02", "2025-06-30")
    px = pd.DataFrame({"Close": 10.0, "Volume": 1000.0}, index=dates)
    periods = ["2023Q1", "2023Q2", "2023Q3", "2023Q4", "2024Q1", "2024Q2", "2024Q3", "2024Q4", "2025Q1"]
    bs = pd.DataFrame(
        {p: [1000.0, 500.0, 100.0, 50.0, 200.0] for p in periods},
        index=["TOPLAM VARLIKLAR", "Ana Ortaklığa Ait Özkaynaklar", "Ödenmiş Sermaye",
               "Nakit ve Nakit Benzerleri", "Finansal Borçlar"],
    )
    inc = pd.DataFrame(
        {p: [100.0 * int(p[-1]), 40.0 * int(p[-1]), 20.0 * int(p[-1]), 15.0 * int(p[-1])] for p in periods},
        index=["Satış Gelirleri", "BRÜT KAR (ZARAR)", "FAALİYET KARI (ZARARI)", "Ana Ortaklık Payları"],
    )
    months = pd.date_range("2022-01-31", "2025-12-31", freq="ME")
    pd.DataFrame({"cpi_mom": [3.0] * len(months)}, index=months).to_parquet(tmp_path / "macro_monthly.parquet")
    pd.DataFrame({"ticker": ["AAA"], "cls": ["reexpressed"]}).to_parquet(tmp_path / "reexpression_class.parquet")
    pd.DataFrame({"ticker": ["AAA"] * len(months), "date": months, "mcap": [2500.0] * len(months)}).to_parquet(
        tmp_path / "market_cap_monthly.parquet"
    )
    raw = {"AAA": {"bs": bs, "inc": inc, "px_raw": px, "px_adj": px, "splits": None}}
    stats = build_panel_from_raw(raw, {"AAA": "Sanayi"}, research_dir=tmp_path, out_dir=tmp_path, write_definition=True)
    assert stats["c1"] is True
    assert stats["undo_reexpression"] is True
    assert stats["bridge_ttm"] is True
    assert stats["isyatirim_mcap"] is True
    assert stats["values_divided"] > 0
    f = pd.read_parquet(tmp_path / "factors_monthly.parquet")
    assert (f["mcap_source"] == "isyatirim_pd").all()
    assert (f["mcap"] == 2500.0).all()
    assert (tmp_path / "PANEL_DEFINITION.txt").exists()
    assert (tmp_path / "quarterly_ext.parquet").exists()
