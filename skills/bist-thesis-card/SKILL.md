---
name: bist-thesis-card
description: Investment Thesis Card'i (thesis_bullets, why_now, main_risk, invalidation_condition, upcoming_events) zaten hesaplanmis sayisal alanlardan deterministik olarak kurar. Hicbir sayi uydurmaz.
---

# bist-thesis-card

Yontemi tasir; sablon `templates/thesis_card.md.j2` (proje kokundeki
`report/templates/thesis_card.md.j2` ile ayni icerik sozlesmesini paylasir),
uretim mantigi `core/thesis.py`'dedir. Bozulma kosulu kontrolu `core/invalidation.py`
(`scripts/invalidation.py` buraya ince bir CLI sarmalayicisidir).

ai_role_boundaries.allowed = [explain, summarize, challenge, communicate]:
Bu skill hicbir zaman fiyat/skor/esik UYDURMAZ, yalnizca mevcut alanlari
cumleye cevirir. tone_rules: "Her tez icin karsi argüman zorunlu."

## Kullanim
```
python scripts/invalidation.py check --as-of-date 2026-09-10
```
