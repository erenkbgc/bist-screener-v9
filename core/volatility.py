"""low_vol_z: kesitsel dusuk-volatilite fakt oru.

BIST'te negatif risk-getiri iliskisi (dusuk riskli hisselerin yuksek riskli
hisseleri gecmesi) literaturde gozlenen bir anomali -- ancak bu projenin
KENDI outcomes verisiyle henuz dogrulanmadi (bkz. config/weights.yaml
priors_are_disclosed notu). Burada uygulanan agirlik DENENMEMIS BIR
BASLANGIC VARSAYIMIDIR.
"""
from __future__ import annotations

from statistics import mean, pstdev


def compute_low_vol_z(candidate: dict, population: list[dict]) -> float:
    """Kesitsel z-skor: dusuk volatility_60d (60 gunluk gunluk getiri stdev'i)
    iyi kabul edilir, bu yuzden ham deger -volatility_60d'dir.

    volatility_60d None olan adaylar (yetersiz fiyat gecmisi -- bkz.
    core/live_data.py/core/mock_data.py) havuzdan (pool) COMPLETELY disarida
    birakilir (0.0 ile doldurulmaz); aksi halde "veri yok" durumu yanlislikla
    "ortalama volatilite" gibi yorumlanirdi. Havuzda yeterli gozlem yoksa
    veya adayin kendi degeri None ise 0.0 katki doner."""
    pool = [-o["volatility_60d"] for o in population if o.get("volatility_60d") is not None]
    if candidate.get("volatility_60d") is None or len(pool) < 2:
        return 0.0
    mu, sigma = mean(pool), pstdev(pool)
    if sigma == 0:
        return 0.0
    return (-candidate["volatility_60d"] - mu) / sigma
