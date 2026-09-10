---
name: bist-catalyst-scoring
description: KAP bildirimlerini (once deterministik kategoriye indirgenmis olarak) agirliklandirir ve zaman sonumlu bir katalizor skoru uretir. Bildirim metnini LLM'e ASLA serbest metin olarak vermez.
---

# bist-catalyst-scoring

Yontemi tasir; hesap `core/catalysts.py` + `core/decay.py` icindedir.
Kategori/agirlik/yari-omur tablosu `config/catalyst_decay.yaml`'dadir.

`no_free_text_interpretation_of_kap` kurali: `kap_web_mcp/server.py` bildirimi
zaten kategoriye indirger; bu skill'e ham KAP metni ASLA girmez.

## Kullanim
```
python scripts/categorize.py --as-of-date 2026-09-10 --tickers THYAO,ASELS
```
