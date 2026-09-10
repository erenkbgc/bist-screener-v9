---
name: bist-relative-valuation
description: BIST esler grubu ici kesitsel (cross-sectional) degerleme skoru hesaplar. Sabit F/K, PD/DD, FD/FAVOK esigi kullanmaz; yalnizca ayni reporting_basis + ratio_profile + peer_level icindeki persentil/z-skoru kullanir.
---

# bist-relative-valuation

Bu skill `core/ranking.py` (valuation_engine) ve `core/basis_guard.py`'yi
yontem olarak tasir. Gercek hesap Python'da (`core/ranking.py`) yapilir;
bu skill yalnizca hangi sirayla, hangi kurallarla cagrilacagini belgeler.

## Kurallar (execution_rules'tan)
- `no_fixed_thresholds`: mutlak F/K/PD/DD/FD-FAVOK esigi YOK.
- `no_historical_ratio_comparison`: bir metrik kendi gecmisiyle KARSILASTIRILMAZ.
- `min_peer_n=8`, `fallback_chain=[sector, supersector, market]`.
- `outlier_handling`: 1/99 persentil winsorize.

## Kullanim
```
python scripts/rank.py --as-of-date 2026-09-10
```

## Dosyalar
- `scripts/rank.py`: CLI giris noktasi, `core.ranking` ve `core.universe`'i cagirir.
- `scripts/basis_guard.py`: `core.basis_guard`'a ince bir CLI sarmalayicisi.
- `config/weights.yaml`: proje kokundeki `config/weights.yaml`'a sembolik referans (bkz. dosya-basi not).
