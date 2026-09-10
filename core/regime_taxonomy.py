"""regime_taxonomy: makro rejimi okunabilir ETIKETLERE cevirir.

explicit_non_action (spec): "Bu etiketler final_score, weights.yaml veya
herhangi bir hard_filter icin GIRDI DEGILDIR. Kodda regime_taxonomy
ciktisindan scoring.py'ye hicbir veri akisi olmamalidir, bu statik
taramayla test edilir."

=> Bu dosya core/scoring.py'yi import ETMEZ ve core/scoring.py da bu
dosyayi import ETMEZ. tests/test_regime_taxonomy_static.py bunu kaynak
metni tarayarak dogrular.
"""
from __future__ import annotations

from core import db


def real_rate_regime(policy_rate_pct: float | None, cpi_yoy_pct: float | None) -> str:
    # Canli veri modunda policy_rate_pct/cpi_yoy_pct icin ucretsiz, dogrulanmis
    # bir kaynak bulunamayabilir (bkz. core/live_data.py::live_macro_snapshot);
    # bu durumda uydurma bir etiket uretmek yerine "unknown" donulur.
    if policy_rate_pct is None or cpi_yoy_pct is None:
        return "unknown"
    real_rate = policy_rate_pct - cpi_yoy_pct
    if real_rate < 0:
        return "negative"
    if real_rate < 5:
        return "low_positive"
    return "high_positive"


def inflation_trend(as_of_date: str) -> str:
    rows = db.query(
        "SELECT cpi_yoy_pct FROM regime_log WHERE as_of_date <= ? ORDER BY as_of_date DESC LIMIT 4",
        (as_of_date,),
    )
    vals = [r["cpi_yoy_pct"] for r in rows if r["cpi_yoy_pct"] is not None]
    if len(vals) < 2:
        return "plateau"
    delta = vals[0] - vals[-1]
    if delta > 0.3:
        return "rising"
    if delta < -0.3:
        return "falling"
    return "plateau"


def fx_regime(as_of_date: str) -> str:
    rows = db.query(
        "SELECT usdtry_spot FROM regime_log WHERE as_of_date <= ? ORDER BY as_of_date DESC LIMIT 90",
        (as_of_date,),
    )
    vals = [r["usdtry_spot"] for r in rows if r["usdtry_spot"] is not None]
    if len(vals) < 5:
        return "stable"
    total_change_pct = (vals[0] - vals[-1]) / vals[-1] * 100 if vals[-1] else 0
    daily_rets = [(vals[i] - vals[i + 1]) / vals[i + 1] for i in range(len(vals) - 1) if vals[i + 1]]
    vol = (sum((r - (sum(daily_rets) / len(daily_rets))) ** 2 for r in daily_rets) / len(daily_rets)) ** 0.5 if daily_rets else 0
    if total_change_pct > 8 or vol > 0.015:
        return "depreciating_fast"
    if total_change_pct > 1.5:
        return "depreciating_gradual"
    return "stable"


def compute_taxonomy(as_of_date: str, policy_rate_pct: float, cpi_yoy_pct: float) -> dict:
    labels = {
        "real_rate_regime": real_rate_regime(policy_rate_pct, cpi_yoy_pct),
        "inflation_trend": inflation_trend(as_of_date),
        "fx_regime": fx_regime(as_of_date),
    }
    conn = db.get_connection()
    try:
        conn.execute(
            """UPDATE regime_log SET real_rate_regime=?, inflation_trend=?, fx_regime=?
               WHERE as_of_date=?""",
            (labels["real_rate_regime"], labels["inflation_trend"], labels["fx_regime"], as_of_date),
        )
        conn.commit()
    finally:
        conn.close()
    labels["display_tag"] = f"{labels['real_rate_regime']}_real_rate + {labels['inflation_trend']}_inflation + {labels['fx_regime']}"
    return labels
