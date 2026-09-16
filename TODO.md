# BIST Screener — v10/v11 Yol Haritasi (To-Do)

Kaynak: Bir yatirim analisti perspektifinden yapilan disaridan inceleme
(2026-09-11). Tam spec: `bist_screener_v10_roadmap.json` (v9 spec'i
`bist_screener_v9_prompt.json`'u DEGISTIRMEZ, uzerine ekler).

## v11 (2026-09-16) — akademik dogrulama + likidite/dusuk-volatilite

Kaynak: iki disaridan "arastirma raporu" + bunlarin GERCEK web aramasiyla
bagimsiz dogrulanmasi. Tam spec: `bist_screener_v11_roadmap.json`
(`verified_claims_log`: hangi iddia gercek/dogrulandi, hangisi uydurma/atif
hatali -- ozetle BIST dusuk volatilite anomalisi ve deger primi Gokcen (2026,
SSRN #4588551) ile dogrulandi; "Karaomer/Gumushane 6-faktor" atfi hatali
cikti, tekrar kullanilmamali).

- [x] **liquidity_aware_dynamic_targets** — TAMAMLANDI (2026-09-16).
  `core/targets.py`: kisa vade stop/hedef ATR carpanlari `avg_volume_tl_20d`'ye
  gore genisliyor (taban hacimde 1.3x, 50M TL ustunde 1.0x).
- [x] **low_vol_factor** — TAMAMLANDI (2026-09-16). `core/volatility.py`,
  `weights.yaml`'da 0.10 agirlik (valuation 0.55->0.50, catalyst 0.30->0.25
  ile dengelendi). Akademik dayanak dogrulandi (bkz. v11 JSON).
- [x] **validation_gate_orphan_precision_bugfix** — TAMAMLANDI (2026-09-16).
  `report/validate.py::find_orphan_numbers` X.00'a yuvarlanan payload
  degerlerini (43.00, 622.00 gibi) float round-trip yuzunden yanlislikla
  orphan isaretliyordu; 2026-09-15 kosusunda bu yuzden `validation_gate` FAIL
  verdi ve mail hic gitmedi. Fix + regresyon testi eklendi, gercek
  2026-09-15 INVALID payload/HTML ciftiyle dogrulandi.
- [x] **ci_push_race_condition_fix** — TAMAMLANDI (2026-09-16).
  `.github/workflows/daily-screener.yml` push adimina fetch+rebase retry
  eklendi; kosu surerken lokalden master'a push yapilirsa artik gunun
  DB/rapor guncellemesi kaybolmuyor (2026-09-15'te oldugu gibi).
- [ ] **long_term_target_price_outlier_cap** (1-2 gun, P1) — 2026-09-15
  kosusunda bazi dusuk likiditeli hisselerde (GLRYH %2838, A1CAP %972,
  IHLGM %443) peer-relative hedef fiyat asiri uc deger uretti. Veri gercek
  ama gerceki degil; winsorization/cap veya dusuk peer_n'de guven
  seviyesini dusurme onerisi degerlendirilmeli.
- [ ] **momentum_factor_short_window** (1-2 gun, P0) — 6ay-1ay momentum,
  mevcut 140 gunluk fiyat penceresiyle simdi yapilabilir. Klasik 12ay-1ay
  icin pencere genisletmek borsapy throttle/hang riskini artirir, ERTELENDI.
- [ ] **entry_price_support_resistance** (2-3 gun, P2) — pivot kumelenmesiyle
  giris fiyati iyilestirme, skoru degistirmez.
- [ ] **trailing_stop_and_staged_exit** (2-3 gun, P2) — kademeli kar
  realizasyonu + ATR trailing stop.
- [ ] **kap_direct_api_alternative** (1-2 gun + kullanici onayi, P1) —
  `core/live_data.py::live_kap_disclosures` su an borsapy/Is Yatirim mirror'i
  kullaniyor (ticker basina 1 istek, throttle riski). kap.org.tr'nin kendi
  dokumante-edilmemis JSON API'si (`POST /tr/api/disclosure/list/main`)
  2026-09-16'da canli test edildi, calisiyor: tek bulk sorguyla TUM evrenin
  gunluk bildirimleri geliyor. UYARI: resmi olmayan, SLA'siz bir endpoint --
  uygulamadan once bu riski bilerek onaylamak gerekir. Detay: v11 JSON,
  `kap_direct_api_alternative`.
- **parked**: `foreign_ownership_delta_factor` (veri kaynagi yok).
- **rejected**: `regime_conditional_scoring` (mimari invariant ihlali),
  `session_based_atr` (gunluk batch mimariyle uyumsuz).
- **zaten mevcut** (disaridan raporlar yanlislikla "eksik" isaretlemisti):
  sektor bazli degerleme normalizasyonu (`core/ranking.py`), TMS 29
  enflasyon bayragi (`core/basis_guard.py`).

> **Onemli**: Bazi oneriler (tarihsel carpan bandi, walk-forward "backtest",
> portfoy optimizasyonu/pozisyon boyutlandirma) v9'un temel ilkeleriyle
> (no_historical_ratio_comparison, "backtest degildir", "yatirim danismanligi
> degildir") dogrudan gerilimde. Bunlar sessizce yok sayilmadi; roadmap
> JSON'unda `design_tensions_flagged` altinda nasil uzlastirildigi (cekirdek
> mantigi bozmadan, ayri/etiketli/varsayilan-kapali bilesenler olarak)
> aciklandi. Uygulamaya gecmeden once bu uzlasmalari gozden gecirin.

## P0 — Kritik (kisa vadede yatirim tezi icin gerekli)

- [x] **xu100_benchmark_integration** — TAMAMLANDI (2026-09-13). `core/evaluate.py`'deki
  `xu100_return_pct = 0.0` yer tutucusu kaldirildi; `core/live_data.py::live_index_return_pct`
  (`bp.Index("XU100").history(...)`, point-in-time: her iki tarih icin de o tarihe
  kadarki en son kapanis) + `macro_mcp.get_index_return_pct` + mock karsiligi
  (`core/mock_data.py::mock_index_return_pct`) eklendi. Cekilemezse (agsal hata)
  durustluk kurali geregi 0.0 UYDURULMAZ, satir o kosuda atlanir ve bir sonraki
  kosuda tekrar denenir. Test: `tests/test_evaluate.py` (yeni dosya, evaluate.py
  daha once hic test edilmiyordu).
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
- [x] **transaction_cost_model** (tamamlandi, 2026-09-13) — `core/hurdle.py`'ye
  `net_expected_roi_pct`/`net_excess_over_hurdle_pct`/`transaction_cost_pct`
  eklendi (bid/ask spread + `config/transaction_costs.yaml`'daki
  DENENMEMIS komisyon/kayma varsayimlari). Brut `excess_over_hurdle_pct`
  hard-filter olarak DEGISMEDI, yeni alanlar yalnizca bilgi amacli
  (rapor: "Net Getiri (Maliyet Sonrasi)"). bid/ask verisi yoksa (mock modu,
  ya da canli veride spread cekilemezse) net alanlar `None` kalir ve
  raporda gosterilmez. Test: `tests/test_hurdle.py` (net_expected_roi asla
  brutu asmaz, dusuk likiditede net getiri kotulesir, bid/ask yoksa None).

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
