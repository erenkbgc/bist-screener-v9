"""Canli valuation_z == test edilen value_sn_z (scripts/backtest_factor_model.py).

Faz 2 on-kaydi bu paneli test etti; canli skor ayni sayiyi uretmeli. Panel tarafi
factor_backtest.prepare + value ortalamasi + sector_neutralize ile birebir kurulur.
"""
from __future__ import annotations

import random

import numpy as np
import pandas as pd
import pytest

from core import factor_backtest as fb
from core.ranking import compute_valuation_scores


def _universe(seed=7, n=80):
    rng = random.Random(seed)
    sectors = ["Gida", "Tekstil", "Kimya", "Metal", "Enerji", "Insaat", "Teknoloji"]
    out = []
    for i in range(n):
        mcap = 10 ** rng.uniform(8, 11)
        c = {"ticker": f"T{i:02d}", "ratio_profile": rng.choice(["industrial", "industrial", "holding"]),
             "reporting_basis": "nominal",
             # Teknoloji'yi kucuk birak: sector < 5 -> tum kesite gore notrleme
             "sector": "Teknoloji" if i < 3 else rng.choice(sectors[:-1]),
             "supersector": "X", "market_cap": mcap, "current_price": 10.0,
             "pe": rng.lognormvariate(2.3, 0.8), "pb": rng.lognormvariate(0.3, 0.9),
             "revenue_ttm": mcap * rng.lognormvariate(-0.3, 1.0),
             "op_profit_ttm": mcap * rng.gauss(0.08, 0.1),
             "net_debt": mcap * rng.gauss(0.2, 0.5) if rng.random() > 0.1 else None,
             "tl_vol_med60": 10 ** rng.uniform(5, 9)}
        if rng.random() < 0.1:   # zarar eden: F/K yok, negatif EPS
            c["pe"], c["eps_ttm"] = None, -rng.uniform(0.1, 3)
        if rng.random() < 0.1:
            c["pb"] = None
        if rng.random() < 0.05:
            c["revenue_ttm"] = None
        out.append(c)
    out[5]["pe"] = 0.3      # asiri ucuz: eski kod emsal max'ina kirpardi
    return out


def _panel_value_sn(cands):
    from core.ranking import book_to_market, earnings_yield, ebit_yield, sales_yield
    rows = [{"date": pd.Timestamp("2026-09-30"), "ticker": c["ticker"], "sector": c["sector"],
             "tlvol60": c["tl_vol_med60"],
             "ep": (earnings_yield(c) or np.nan) / 100, "bm": book_to_market(c) or np.nan,
             "sp": sales_yield(c) or np.nan, "ey": ebit_yield(c) or np.nan} for c in cands]
    df = fb.prepare(pd.DataFrame(rows), ["bm", "ep", "sp", "ey"])
    df["value_z"] = df[[f + "_z" for f in ["bm", "ep", "sp", "ey"]]].mean(axis=1)
    df["value_sn_z"] = fb.sector_neutralize(df, "value_z")
    return df.set_index("ticker")["value_sn_z"]


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_live_valuation_z_equals_panel_value_sn(seed):
    cands = _universe(seed)
    panel = _panel_value_sn(cands)
    live = {c["ticker"]: r["valuation_z"] for c, r in zip(cands, compute_valuation_scores(cands))}
    assert len(panel) > 40
    for tk, v in panel.items():
        if np.isnan(v):
            assert live[tk] is None
        else:
            assert live[tk] == pytest.approx(v, abs=1e-9), tk
