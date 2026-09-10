# BIST Screener — v10 Yol Haritasi (To-Do)

Kaynak: Bir yatirim analisti perspektifinden yapilan disaridan inceleme
(2026-09-11). Tam spec: `bist_screener_v10_roadmap.json` (v9 spec'i
`bist_screener_v9_prompt.json`'u DEGISTIRMEZ, uzerine ekler).

> **Onemli**: Bazi oneriler (tarihsel carpan bandi, walk-forward "backtest",
> portfoy optimizasyonu/pozisyon boyutlandirma) v9'un temel ilkeleriyle
> (no_historical_ratio_comparison, "backtest degildir", "yatirim danismanligi
> degildir") dogrudan gerilimde. Bunlar sessizce yok sayilmadi; roadmap
> JSON'unda `design_tensions_flagged` altinda nasil uzlastirildigi (cekirdek
> mantigi bozmadan, ayri/etiketli/varsayilan-kapali bilesenler olarak)
> aciklandi. Uygulamaya gecmeden once bu uzlasmalari gozden gecirin.

## P0 — Kritik (kisa vadede yatirim tezi icin gerekli)

- [ ] **xu100_benchmark_integration** (1-2 gun) — `core/evaluate.py`'deki
  `xu100_return_pct` yer tutucusunu (0.0) `bp.Index("XU100").history(...)`
  ile gercek gostergeye bagla. Etki: goreli getiri/`excess_vs_index_pct`
  anlamli hale gelir.
- [ ] **financial_institution_data_source** (3-5 gun) — Banka/sigorta/
  finansal kiralama sirketleri icin bilanco/gelir tablosu kaynagi arastir
  (KAP XBRL, TBB, alternatif saglayici). Etki: su an `reporting_basis=
  'unknown'` ile elenen BIST'in onemli bir kismi (~15-20 banka/sigorta
  tickeri) Piotroski/Sloan/valuation_z'ye dahil olur.
- [ ] **valuation_engine_v2_dcf_addon** (5-7 gun) — `core/gordon.py` ile
  ayni desende (deneysel, final_score'a girmez, 3 senaryolu aralik) bir DCF
  referansi ekle. Tarihsel carpan bandi SADECE ayri, acikca etiketli bir
  bilgi bloku olarak (cekirdek kesitsel degerlemeyi degistirmeden).

## P1 — Onemli (orta vadede portfoy/guvenilirlik icin)

- [ ] **position_sizing_diagnostics** (3-4 gun) — `core/concentration.py` +
  `core/correlation.py`'yi genislet: korelasyon-agirlikli yogunlasma,
  emir DEGIL teshis. Ciktida asla "X TL/oraninda al/azalt" gibi bir ifade
  olmamali (yeni bir banned-phrase taramasi eklenmeli).
- [ ] **walk_forward_diagnostic** (3-4 gun) — Varsayilan KAPALI
  (`WALK_FORWARD_DIAGNOSTIC_ENABLED=false`). Ortusmeyen pencereli tanimlayici
  takip metrigi; "backtest edilmis/kanitlanmis edge" gibi ifadeler
  `banned_claims` listesine eklenmeli.
- [ ] **transaction_cost_model** (2-3 gun) — `hurdle_engine`'e
  `net_expected_roi_pct` (spread+komisyon+kayma dusulmus) ekle. Mevcut
  brut `excess_over_hurdle_pct` hard-filter olarak DEGISMEZ.

## P2 — Faydali (raporlama/derinlik)

- [ ] **investment_memo_generator** (3-4 gun) — `core/thesis.py` +
  `report/render.py` deseninde, sablon-tabanli (LLM serbest metni yok)
  PDF/HTML yatirim notu. Mevcut `validation_gate`'ten gecmeli.
- [ ] **qualitative_governance_score** (3-5 gun) — Ortaklik yapisi + KAP
  bildirim sikligindan kural-tabanli skor. Once informational (final_score'a
  girmeden), veri kaynagi (bagimsiz uye orani) bulunamazsa `null_reason` ile
  sessizce devre disi kalmali.

## P3 — Dusuk oncelik

- [ ] **point_in_time_dataset** (5+ gun) — Restatement/delisting/M&A log
  tablosu (`point_in_time_events`). Mevcut semalari degistirmez.

## Detaylar

Her modulun tam spec'i (inputs, formula, hard_constraints, acceptance_test)
icin `bist_screener_v10_roadmap.json::modules` altina bakin. Yeni testler
icin bkz. `testing_additions_required`.
