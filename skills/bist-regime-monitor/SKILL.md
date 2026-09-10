---
name: bist-regime-monitor
description: Makro rejimi izler (regime_monitor) ve okunabilir etiketlere cevirir (regime_taxonomy). Etiketler yalnizca raporlama icindir, otomatik skor onyargisi YOKTUR.
---

# bist-regime-monitor

Yontemi tasir; hesap `core/regime.py` + `core/regime_taxonomy.py` icindedir.

KRITIK: `core/regime_taxonomy.py`'den `core/scoring.py`'ye HICBIR import/veri
akisi yoktur. Bu, `tests/test_regime_taxonomy_static.py` ile statik olarak
dogrulanir.

## Kullanim
```
python scripts/regime.py --as-of-date 2026-09-10
python scripts/regime_taxonomy.py --as-of-date 2026-09-10
```
