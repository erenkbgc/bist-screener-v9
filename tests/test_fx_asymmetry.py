"""Kur betasi tahmini ve NW regresyonu."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import research_fx_asymmetry as fa  # noqa: E402


def test_fx_beta_recovers_exposure_beyond_market():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2015-01-31", periods=40, freq="ME")
    mkt = pd.Series(rng.normal(0, 0.05, 40), index=idx)
    dfx = pd.Series(rng.normal(0.01, 0.03, 40), index=idx)
    ret = pd.DataFrame({"EXP": 1.0 * mkt + 0.8 * dfx + rng.normal(0, 0.001, 40),
                        "IMP": 1.0 * mkt - 0.5 * dfx + rng.normal(0, 0.001, 40),
                        "NEW": [np.nan] * 30 + list(rng.normal(0, 0.05, 10))}, index=idx)
    b = fa.fx_betas(ret, mkt, dfx, idx[-1], ["EXP", "IMP", "NEW"])
    assert abs(b["EXP"] - 0.8) < 0.05 and abs(b["IMP"] + 0.5) < 0.05
    assert "NEW" not in b.index  # 24 aydan az gozlem


def test_ols_nw_slope():
    rng = np.random.default_rng(1)
    x = rng.normal(size=300)
    y = 0.02 + 0.5 * x + rng.normal(scale=0.1, size=300)
    b, t = fa.ols_nw(y, x)
    assert abs(b[1] - 0.5) < 0.03 and t[1] > 20
