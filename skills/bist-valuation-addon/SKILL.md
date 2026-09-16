---
name: bist-valuation-addon
description: Deneysel Gordon buyume referansi, DCF referansi, temettu surdurulebilirlik on-kosulu ve beta-duzeltmeli hurdle. Hicbiri final_score'a veya hard_filters'a girmez.
---

# bist-valuation-addon

Yontemi tasir; hesap `core/gordon.py`, `core/dcf.py`, `core/dividend_sustainability.py`,
`core/beta_hurdle.py` icindedir. Equity risk premium, TCMB uzun donem
enflasyon hedefi ve kurumlar vergisi orani `config/equity_risk_premium.yaml`'dadir.

## Kullanim
```
python scripts/gordon.py --as-of-date 2026-09-10 --ticker THYAO
python scripts/dcf.py --as-of-date 2026-09-10 --ticker THYAO
python scripts/dividend_sustainability.py --as-of-date 2026-09-10 --ticker THYAO
python scripts/beta_hurdle.py --as-of-date 2026-09-10 --ticker THYAO
```
