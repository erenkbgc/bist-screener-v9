---
name: bist-quality-filter
description: Piotroski F-Score (9 kriter) ve Sloan tahakkuk orani (kesitsel persentil) ile kalite filtresi uygular. Sloan MUTLAK ESIK kullanmaz.
---

# bist-quality-filter

Yontemi tasir; hesap `core/piotroski.py` ve `core/sloan.py` icindedir.

- Piotroski esigi `config/weights.yaml -> piotroski.normalized_score_threshold`
  icindedir ve `priors_are_disclosed` kuraliyla DENENMEMIS varsayim olarak
  isaretlidir.
- Sloan bayragi (`elevated_earnings_quality_risk`) final_score'a girmez,
  yalnizca ayni (reporting_basis, ratio_profile) esler grubu icindeki ust
  ondalik dilimi isaretler.

## Kullanim
```
python scripts/piotroski.py --as-of-date 2026-09-10
python scripts/sloan.py --as-of-date 2026-09-10
```
