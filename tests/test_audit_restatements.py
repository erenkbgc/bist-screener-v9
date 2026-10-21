"""scripts/audit_restatements: KAP sayi ayristirma, dipnot atlama, birim farki."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import audit_restatements as ar  # noqa: E402


def test_parse_turkish_numbers():
    assert ar.parse_number("135.503") == 135503
    assert ar.parse_number("(1.234,5)") == -1234.5
    assert ar.parse_number("-814.440") == -814440
    assert ar.parse_number("Total assets") is None


def test_first_value_skips_footnote_reference():
    txt = "|DÖNEM KARI (ZARARI)|PROFIT (LOSS)|19|-295.757|120.000|"
    assert ar.first_value(txt, ("DÖNEM KARI (ZARARI)",)) == -295757
    assert ar.first_value("|TOPLAM VARLIKLAR|Total assets|135.503|109.076|", ("TOPLAM VARLIKLAR",)) == 135503


def test_unit_gap_and_period_mapping():
    k, gap = ar.unit_gap(1_424_193_529_000.0, 1_424_193_529.0)
    assert k == 3 and abs(gap) < 1e-12
    assert ar.unit_gap(5.0, -3.0) is None
    assert ar.period_of(pd.Timestamp("2019-03-05")) == "2018Q4"
    assert ar.period_of(pd.Timestamp("2019-11-06")) == "2019Q3"
    assert ar.period_of(pd.Timestamp("2019-06-30")) is None
