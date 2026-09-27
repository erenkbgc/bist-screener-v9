"""pit_panel.merge_statement_batches: tekrarlanan satir adlari batch sayisiyla
katlanmamali (borsapy 0.11 join hatasi, 15 batch'te 2^15 kopya)."""
import pandas as pd

from core import pit_panel


def _batch(cols, rows):
    idx = pd.Index([r[0] for r in rows], name="Item")
    return pd.DataFrame([r[1] for r in rows], index=idx, columns=cols)


def test_duplicate_labels_not_multiplied():
    batches = [
        _batch([f"{y}Q2"], [("  Finansal Borçlar", [10.0 + y]), ("Toplam", [1.0]), ("  Finansal Borçlar", [20.0 + y])])
        for y in range(2010, 2025)
    ]
    merged = pit_panel.merge_statement_batches(batches)
    assert len(merged) == 3
    assert merged.shape[1] == 15
    fd = pit_panel._pick(merged, ("Finansal Borçlar",), sum_dupes=True)
    assert fd["2024Q2"] == 10.0 + 2024 + 20.0 + 2024


def test_first_occurrence_kept_in_order():
    a = _batch(["2026Q2"], [("  Diğer Alacaklar", [1.0]), ("  Diğer Alacaklar", [2.0])])
    b = _batch(["2025Q2"], [("  Diğer Alacaklar", [3.0]), ("  Diğer Alacaklar", [4.0])])
    s = pit_panel._pick(pit_panel.merge_statement_batches([a, b]), ("Diğer Alacaklar",), sum_dupes=False)
    assert s["2026Q2"] == 1.0 and s["2025Q2"] == 3.0


def test_item_missing_in_old_template():
    new = _batch(["2026Q2"], [("A", [1.0]), ("  Kullanım Hakkı Varlıkları", [5.0])])
    old = _batch(["2014Q2"], [("A", [2.0])])
    merged = pit_panel.merge_statement_batches([new, old, pd.DataFrame()])
    assert len(merged) == 2
    assert pd.isna(merged.loc["  Kullanım Hakkı Varlıkları", "2014Q2"])


def test_empty():
    assert pit_panel.merge_statement_batches([]).empty
