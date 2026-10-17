"""Sanayi uretimi: yillik buyume, surpriz tanimi ve yayin gecikmesi hizalamasi."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_signals_and_release_alignment():
    pytest.importorskip("statsmodels")  # arastirma bagimliligi (requirements-research.txt); CI kurmaz
    import research_industrial_production as ip
    idx = pd.date_range("2010-01-31", periods=30, freq="ME")
    ipi = pd.Series(100 * 1.01 ** np.arange(30), index=idx)  # sabit %1/ay -> yillik buyume sabit
    sig = ip.signals(ipi)
    assert np.isclose(sig["g"].iloc[12], 12 * np.log(1.01))
    assert np.isclose(sig["surprise"].iloc[25], 0.0)  # sabit buyume -> surpriz yok
    r = pd.Series(np.arange(40, dtype=float), index=pd.date_range("2010-01-31", periods=40, freq="ME"))
    a = ip.align(sig, r)
    # Ocak 2011 verisi Mart 2011'de haber (I1), Nisan 2011 getirisini tahmin eder (I2/I3)
    row = a.loc[pd.Timestamp("2011-01-31")]
    assert row["release"] == pd.Timestamp("2011-03-31")
    assert row["r_release"] == r[pd.Timestamp("2011-03-31")] and row["r_next"] == r[pd.Timestamp("2011-04-30")]
