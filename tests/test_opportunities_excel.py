"""Firsatlar Excel'i: payload'dan uretilir, durum sirasi ve bos gun korunur."""
from openpyxl import load_workbook

from report.opportunities_excel import write_opportunities_excel


def _c(ticker, state, score, bucket="long_term"):
    return {"ticker": ticker, "bucket": bucket, "candidate_state": state, "final_score": score,
            "entry_price": 10.0, "target_price": 11.0, "fair_value_base": 12.0, "sector": "S",
            "factor_attribution": {"top_positive_factor": "Değerleme"}}


def test_sheets_order_and_values(tmp_path):
    payload = {
        "passing_candidates": [_c("WWW", "WATCHLIST", 0.9), _c("SSS", "STRONG_OPPORTUNITY", 0.1),
                               _c("OOO", "OPPORTUNITY", 0.5), _c("KKK", "OPPORTUNITY", 0.2, "short_term")],
        "run_health": {"status": "DEGRADED", "issues": ["kap_unavailable"]},
        "regime": {"xu100_level": 13000.0, "bond_2y_pct": 40.0, "usdtry_spot": 49.0},
        "weights": {"valuation_z": 0.5, "catalyst_score": 0.25},
    }
    path = write_opportunities_excel(tmp_path / "f.xlsx", "2026-10-02", payload)
    wb = load_workbook(path)
    assert wb.sheetnames == ["Özet", "Uzun Vade", "Kısa Vade", "Açıklamalar"]
    lt = wb["Uzun Vade"]
    # durum sirasi skordan once gelir: guclu > firsat > izleme
    assert [lt.cell(row=r, column=1).value for r in (2, 3, 4)] == ["SSS", "OOO", "WWW"]
    headers = [c.value for c in lt[1]]
    gap = lt.cell(row=2, column=headers.index("Adil değer farkı %") + 1).value
    assert abs(gap - 20.0) < 1e-9
    assert wb["Kısa Vade"].cell(row=2, column=1).value == "KKK"
    summary = {r[0]: r[1] for r in wb["Özet"].iter_rows(min_row=3, values_only=True) if r[0]}
    assert summary["Veri sağlığı"].startswith("Kısmi")


def test_empty_day(tmp_path):
    wb = load_workbook(write_opportunities_excel(tmp_path / "e.xlsx", "2026-10-02", {}))
    assert "aday yok" in wb["Uzun Vade"].cell(row=2, column=1).value
