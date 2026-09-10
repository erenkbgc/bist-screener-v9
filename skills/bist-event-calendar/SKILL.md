---
name: bist-event-calendar
description: BIST rebalans, VIOP vade, IPO lock-up ve KAP'ta resmen ilan edilmis genel kurul/bilanco tarihlerini toplar. Hicbir tarihi tahmin etmez.
---

# bist-event-calendar

Yontemi tasir; hesap `core/events.py` icindedir (kap_web_mcp.get_upcoming_events'i cagirir).

`rule`: Hicbir tarih tahmin edilmez. `bilanco_aciklama_tarihi` yalnizca sirket
acikca ilan etmisse doldurulur, aksi halde bos doner.

## Kullanim
```
python scripts/events.py --as-of-date 2026-09-10 --tickers THYAO,ASELS
```
