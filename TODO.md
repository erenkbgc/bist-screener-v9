# BIST Screener — v10/v11/v12/v13 Yol Haritasi (To-Do)

## v13 Stratejik Yol Haritasi ve Oncelik Siralamasi (2026-09-17)

### P0 — Acil & Cok Yuksek Etki
- [x] **1. Dinamik Entry / Stop-Loss / Position Sizing** — TAMAMLANDI (2026-09-17).
  - ATR bazli alis bandi: `entry_low = current_price - 0.5 * ATR20`, `entry_high = current_price + 0.2 * ATR20`.
  - Dinamik stop-loss: `stop_loss = entry_low - 1.5 * ATR20` (veya son swing dusuk destegi).
  - Kademeli alim: %50 alt bant, %50 ust bant (`effective_entry = 0.5 * entry_low + 0.5 * entry_high`).
  - Sabit kesirli pozisyon buyuklugu: hesap bakiyesinin %1–2'si (varsayilan %1.5) / risk_yuzdesi (`max_position_size_pct` tavan korumali).
  - `core/targets.py::compute_dynamic_risk_levels` eklendi; `compute_short_term_target` genisletildi.
  - `run.py` uzerinde hem uzun hem kisa vade adaylarina dynamic risk seviyeleri entegre edildi.
  - `predictions` tablosuna `entry_low`, `entry_high`, `position_size_pct` eklendi, otomatik migrasyon yazildi.
  - Bulten sablonuna kademeli alis bandi, dinamik stop-loss ve pozisyon buyuklugu metrikleri eklendi.
  - Testler: `tests/test_dynamic_risk.py` eklendi (9/9 basarili, genel suite 158/158 geciyor).
- [x] **2. Backtesting Altyapisi** — TAMAMLANDI (2026-09-17).
  - Walk-forward motoru (`core/backtest.py::WalkForwardEngine`): look-ahead bias icermeyen adim adim simülasyon.
  - Komisyon (%0.15) ve kayma/slippage (%0.10) gercekci maliyet modeli.
  - Metrikler: CAGR, Sharpe Orani, Sortino Orani, Max Drawdown, Hit Rate, Profit Factor.
  - Backtrader entegrasyonu: `core/backtest.py::BacktraderDynamicRiskStrategy` ve Cerebro calistiricisi.
  - Veritabani tablolari: `backtest_results` (ozet performans) ve `backtest_trades` (tekil islem kayitlari).
  - Canli test: `FORTE` hissesi uzerinde gercek 215 gunluk veriyle test edildi (8 islem, MDD sinirlamasi dogrulandi).
  - Testler: `tests/test_backtest.py` eklendi (4/4 basarili, genel suite 162/162 geciyor).
- [x] **3. Coklu Degerleme Metodolojisi (Degerleme Ucgeni)** — TAMAMLANDI (2026-09-17).
  - DCF (%40): WACC, TCMB enflasyon hedefi (terminal g), FCF senaryolari (%0, %5, %10 buyume) `core/valuation_triangle.py::compute_dcf_leg`.
  - Emsal Carpanlar (%35): Sanayi/teknoloji icin F/K, FD/FAVOK, PD/DD; Banka/Sigorta/GYO icin EV/EBITDA yasagi savunma hatti `core/valuation_triangle.py::compute_peers_leg`.
  - Kalite Primi (%25): ROE vs Sermaye Maliyeti (Graham-Buffett EVA ekonomik kar), Piotroski F-Score mali saglik primi (+10%/0%/-10%), Dusuk Borc/Net Nakit bilanco gucu primi (+10%/+5%/0%/-10%) `core/valuation_triangle.py::compute_quality_leg`.
  - GYO & Holding NAV: Yatirim Amacli Gayrimenkuller + Stoklar - Net Borc / Pay Sayisi ile hisse basina NAV ve `nav_discount` dolumu (`core/live_data.py::live_fundamentals`, `_val` DataFrame duplicate row destegi).
  - Dinamik agirlik normalizasyonu: Herhangi bir bilesen verisizlik/uygunsuzluk nedeniyle hesaplanamazsa agirliklar diger bilesenler arasinda oransal olarak yeniden normalize edilir.
  - Hedef fiyat = agirlikli ortalama fair value (`target_price = fair_value_base`).
  - Ciktilar: `fair_value_low`, `fair_value_base`, `fair_value_high`, `valuation_method`, `predictions` tablosuna ve newsletter sablonuna entegre edildi.
  - Canli testler: `FORTE` (Fiyat: 100.3, Hedef: 212.41, Adil Deger: 123.55 - 301.26 TL, DCF+Emsal+Kalite) ve `EKGYO` (Fiyat: 19.24, NAV/pay: 75.48 TL, NAV iskontosu: %74.5, Hedef: 20.48 TL) uzerinde canli verilerle dogrulandi.
  - Testler: `tests/test_valuation_triangle.py` eklendi (10/10 basarili, genel suite 172/172 geciyor).
- [ ] **4. Veri Kalitesi ve Survivorship Bias**
  - Delist / iflas eden hisselerin arsivlenmesi.
  - Fiyat duzeltmeleri: temettu, bedelsiz, sermaye artirimi.
  - Alternatif kaynaklar: KAP direkt, Fintables, Investing.
  - Cikti: `data_quality_report`, duzeltilmis fiyat serisi.

### P1 — Yuksek Oncelik (2–6 hafta)
- [ ] **5. Portfoy Optimizasyonu**
  - Risk Parity, Min Variance, Max Sharpe secenekleri.
  - Korelasyon > 0.8 olan hisselerden yalnizca birini secme kurali.
  - Sektor limiti: max %30. Cikti: `recommended_portfolio_weights`.
- [ ] **6. Faktor Ifsa Raporu**
  - `final_score` katki analizi: valuation_z * 0.5, catalyst * 0.25, ownership * 0.15, low_vol * 0.1.
  - "Bu skoru ne artirdi, ne dusurdu?" aciklamasi. Cikti: `factor_contribution` tablosu.
- [ ] **7. Sektor Notrlestirme**
  - `valuation_z` sektor ici z-skoru / supersector normalizasyonu.
  - `peer_n < 5` ise supersector'a dusme. Cikti: `valuation_z_sector_neutral`.
- [ ] **8. Kurumsal Aksiyon Takvimi**
  - `event_calendar` tablosu: tarih, tur, etki. Fiyat duzeltmesi otomatik. Entry/exit sinyal uyarilari.

### P2 — Orta Oncelik (6–12 hafta)
- [ ] **9. Duygu Analizi / NLP** (KAP bildirimleri + haber basliklari, FinBERT/lexicon, katalizor skoruna %20 agirlik).
- [ ] **10. Makro Rejim Modeli** (Faiz, enflasyon, FX rejimine gore dinamik agirliklar).
- [ ] **11. UI / Raporlama** (Streamlit/Dash dashboard gelistirmesi, canli filtreler).

### P3 — Dusuk Oncelik (12+ hafta)
- [ ] **12. Otomatik Emir Entegrasyonu** (Broker API - AlgoTrader/Matriks).
- [ ] **13. Coklu Varlik Sinifi** (ETF, tahvil, emtia).
- [ ] **14. API Servisi** (FastAPI + Docker).

---

## v12 (2026-09-17) — butunluk onarimi (kidemli analist incelemesi + canli dogrulama)

Kaynak: kod tabaninin uctan uca denetimi + BIST muhasebe/piyasa yapisina dair
GERCEK web arastirmasi + canli veriyle ampirik olcum (v11'in aksine disaridan
yapistirilmis bir rapor DEGIL, dogrudan denetim). Tam spec:
`bist_screener_v12_roadmap.json`. Bulgu: mimari saglam, ama bir dizi kontrol
**sessizce devre disi** — sistem vermedigi guvenceleri veriyormus gibi
gorunuyor. Once bunlar onarilacak, sonra kapsam bosluklari, en son yeni
faktorler ele alinacak. `momentum_factor_short_window` (asagida v11
bolumunde P0 olarak listeli) bu yuzden bilincli olarak v12 T0 maddelerinden
SONRAYA alindi.

### Tier 0 — butunluk onarimi (P0, hicbiri yeni sinyal eklemiyor, mevcut ciktinin guvenilirligini onariyor)

- [x] **prediction_horizon_evaluation_mismatch** — TAMAMLANDI (2026-09-17).
  `core/evaluate.py::HORIZONS_DAYS` listesine 180 eklendi (`[5, 20, 60, 180]`).
  `independence_caveat` metni 180 gunluk uzun vadeli tezlerin 20 gunluk kisa vadeli
  adaylarla ayni kesitte ortusebilecegini ve her ufkun ayri gosterildigini belirtecek
  sekilde guncellendi. `tests/test_evaluate.py` icinde 180 gunluk tahminlerin
  olgunlastiginda degerlendirildigi ve kisa/uzun vadeli tahminlerin bagimsiz
  olculdugu regresyon testleriyle dogrulandi.
- [x] **dead_hard_filters_repair** — TAMAMLANDI (2026-09-17).
  (1) `core/live_data.py::live_fundamentals` mali tablo hicbir sablonda cekilemediginde
  (bs VE inc None) artik `reporting_basis='unknown'` sinyali uretiyor; `core/fundamentals.py`
  bu sinyali regulator kuraliyla ezmeyip koruyor, boylece `basis_guard.unknown_ratio` (%30 halt kapisi)
  ve `reporting_basis!='unknown'` hard filter'i gercek veri bosluklarinda aktiflesiyor.
  (2) `core/ranking.py::compute_valuation_z` icinde `profile['forbidden_metrics']` savunma
  hatti olarak filtreleniyor (bank/insurance/reit'e ev_ebitda sizmasi onlendi).
  (3) `live_tedbir_level` gercek veri kaynagi entegre edilene kadar gecici 0 donusu
  `report/render.py` ve newsletter sablonunda `KNOWN_LIMITATIONS_TR` ile acikca ifsa edildi.
  `tests/test_fundamentals.py` ve `tests/test_ranking.py` testleri eklendi.
- [x] **inflation_basis_truthful_labeling** — TAMAMLANDI (2026-09-17).
  (1) `core/basis_guard.py::resolve_reporting_basis` SPK_TFRS icin otomatik 'adjusted'
  iddiasini kaldirdi; Is Yatirim veri saglayicisinin gercekte nominal/tarihi maliyetli
  olmasi nedeniyle SPK_TFRS ve BDDK durustce `'nominal'` olarak etiketlendi.
  (2) `core/piotroski.py::calculate_piotroski_scores` donem-karsilastirmali kriterler (3, 5, 6, 8, 9)
  icin `basis_guard.basis_break(reporting_basis, prior_basis)` cagrisini gerceklestiriyor;
  baz kirigi durumunda bu kriterler None yapiliyor.
  (3) Yuksek enflasyon ortaminda nominal tablolarda cari hasilatin tarihi maliyetli aktife
  oranlanmasiyla mekanik olarak sisen aktif devir hizi (kriter 9: `turn0 > turn1`), nominal
  beslemede hesaplanamaz (`None`) isaretlendi (`core/live_data.py` ve `core/piotroski.py`).
  (4) `KNOWN_LIMITATIONS_TR` ve sablona nominal mali tablo ve donem-karsilastirmali aktif devir
  hizi sinirlamasi ifsasi eklendi; `report/validate.py`'ye "29" eklendi.
  `tests/test_basis_guard.py` ve `tests/test_piotroski.py` genisletildi.
- [ ] **point_in_time_publication_lag** (3-4 gun) — `core/fundamentals.py:18`
  `published_at = period_end` ("basitlestirilmis mock varsayimi") CANLI
  modda da yururlukte; gercek beyanlar 6-10 hafta sonra gelir ->
  P11_lookahead_bias ihlali. `live_kap_disclosures` zaten gercek
  `published_at` uretiyor, `_earnings_dates_cached` zaten cache'leniyor
  ama yanlis tuketiciye (`live_upcoming_events`) bagli — bunlar
  `effective_at` turetmek icin yeniden kullanilmali. KAP toplu API
  (asagida onaylandi) bunu tek sorguda saglayabilir.
- [ ] **nominal_real_consistency_in_valuation_addons** (2 gun) — Canli
  olcum (2026-09-17): `bond_2y=%40.61` nominal iskonto + `g=%5.0`
  (dusuk-enflasyon rejimi terminal buyume) ayni formulde -> spread ~40pp
  -> ima edilen terminal carpan 2.5-2.65x FCF, neredeyse her sirket
  "asiri degerli" cikiyor. DCF/Gordon reel terimlere gecirilmeli (TCMB
  EVDS enflasyon girdisiyle); girdi yoksa `None+null_reason`, VARSAYIM
  UYDURULMAZ. Mevcut kucuk-spread outlier guard'ina simetrik bir
  buyuk-spread guard'i eklenmeli.

### Tier 1 — kapsam bosluklari (P1, Tier 0 canli dogrulanmadan baslatilmaz)

- [ ] **ev_ebitda_net_debt_recovery** (2-3 gun) — DB kaniti: `ev_ebitda`
  ve `net_debt` 1606/1606 satirda `None` (borsapy ust kaynak kazimasi
  bu alanlari pratikte hic doldurmuyor). Industrial profilinin 7
  metriginden 3'u, `targets.py` EV/FAVOK bacagi ve
  `dividend_sustainability` kaldirac kontrolu bu yuzden olu. Bilanco/
  gelir tablosu bilesenlerinden dogrudan hesaplanabilir (net borc =
  finansal borclar - nakit; FAVOK = faaliyet kari + amortisman).
- [ ] **reit_ffo_and_holding_nav** (4-5 gun) — 62 GYO tickeri yalnizca
  PD/DD ile siralaniyor (`ffo_yield`/`nav_discount` hep None -> reit
  profili fiilen 1/3 metrik). 69 holding tickeri `nav_discount` hep None
  oldugu icin **hicbir zaman** uzun vadeli hedef fiyat alamiyor
  (`targets.py`'deki holding bacaginda `legs` hep bos). FFO ve
  borsada-islem-goren-kisim NAV'i (acikca ALT SINIR olarak ifsa edilerek)
  eklenmeli.
- [ ] **insurance_peer_floor_and_financial_sector_ratios** (2-3 gun) —
  Evrende 7 sigorta tickeri var, `MIN_PEER_N=8` -> her sigorta ismi
  kosulsuz `insufficient_peers` ile eleniyor (mali tablolari 2026-09-17'de
  acilmis olsa bile). `npl_ratio`/`nim` UFRS tablolarindan hesaplanabilir
  (`car` durustce None kalir, ayri BDDK beyaninda). `roa/nim/npl_ratio/
  car/combined_ratio/ffo_yield` icin `fundamentals` tablosunda KOLON YOK
  — yalnizca bellekte, payload/dashboard/validate.py'den gorunmez;
  kolonlar eklenmeli.
- [ ] **ownership_quality_z_truthful_scope** (1-2 gun ifsa / arastirma
  veri kaynagi) — final_score'un %15'ini tasiyan `ownership_quality_z`,
  canli modda `retail_pct`/`institutional_pct`/`investor_count` hep None
  oldugu icin fiilen TEK BASINA `free_float_pct` z-skoru; uc risk kurali
  kalici False. `payout_ratio_trend_3p="stabil"` sabit stringi de
  uydurma bir deger, kaldirilmali (None donmeli).

### Tier 2 — yeni sinyal (P2, Tier 0/1'den sonra)

- [ ] **momentum_factor_short_window** — asagidaki v11 girdisiyle AYNI
  madde; v12'de bilincli olarak Tier 0/1'den SONRAYA siralandi (gerekce:
  bozuk bir olcum/filtre altyapisina yeni faktor eklemek o faktorun kendi
  degerini de belirsiz kilar).

### Yeni arastirma parcalari (kod degisikligi degil, arastirma/izleme)

- **`tms29_adjusted_statement_source`**: gercekten TMS 29 duzeltmeli
  tablo kaynagi (KAP XBRL veya ucuncu taraf) — `inflation_basis_truthful_
  labeling` yalnizca ETIKETI durustlestiriyor, veriyi duzeltmiyor.
- **`tms29_exit_watch`**: Turkiye IAS 29 listesinden ciktiginda yeni bir
  baz kirigi olusacak; `basis_guard` tarih/konfig-duyarli hale getirilip
  periyodik izlenmeli.

### Bu oturumda onaylanan yeni veri kaynaklari

Kullanici 2026-09-17'de dordunu de onayladi: **KAP resmi-olmayan JSON
API** (v11'de acik onay bekliyordu, artik onaylandi — `point_in_time_
publication_lag` ve `kap_direct_api_alternative` bunu kullanabilir),
**TCMB EVDS** (`nominal_real_consistency_in_valuation_addons` icin
enflasyon girdisi), **BIST VBTS/tedbir listesi** (`dead_hard_filters_
repair`), **ucuncu taraf mali tablo** (`tms29_adjusted_statement_source`
ve `ev_ebitda_net_debt_recovery` icin yedek kaynak).

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
- [x] **test_suite_live_mode_leak_fix** — TAMAMLANDI (2026-09-17). Kok neden
  bulundu: gelistirme makinesindeki `.env` `BIST_DATA_MODE=live` tutuyor;
  `run.py` import edildiginde kosulsuz `load_dotenv()` cagiriyor (python-dotenv
  zaten os.environ'da olani EZMEZ). `tests/conftest.py` test toplama
  basinda `BIST_DATA_MODE`'u acikca "mock"a sabitlemedigi icin `run_mod.run()`
  cagiran HER test (orn. `test_idempotency.py`) SESSIZCE canli moda geciyor
  ve ~800 ticker'lik TAM evrene gercek Is Yatirim/TradingView (websocket
  dahil) istekleri atiyordu -- faulthandler stack dump'iyla dogrulandi.
  Onceki oturumlarda "full test suite 120sn'de timeout oluyor" olarak not
  dusulen gizemin kok nedeni buydu (S147, 2026-09-16). Fix: `tests/conftest.py`
  artik ilk satirlarda `os.environ["BIST_DATA_MODE"] = "mock"` sabitliyor
  (herhangi bir test modulu -- ve dolayisiyla run.py -- import edilmeden
  once). Sonuc: tam suite 133->137 test (bugunku yeni testler dahil)
  ~10 dakikadan **8 saniyeye** dustu; ayrica bununla ilgisiz sanilan
  `test_evaluate.py::test_xu100_return_comes_from_real_series_not_hardcoded_zero`
  basarisizligi da AYNI sizintinin kurbaniymis, o da duzeldi.
- [x] **ci_push_race_condition_fix** — TAMAMLANDI (2026-09-16).
  `.github/workflows/daily-screener.yml` push adimina fetch+rebase retry
  eklendi; kosu surerken lokalden master'a push yapilirsa artik gunun
  DB/rapor guncellemesi kaybolmuyor (2026-09-15'te oldugu gibi).
- [ ] **dcf_historical_multiple_band_reference** (1-2 gun, P2) — `valuation_engine_v2_dcf_addon`
  spec'inin AYRI/opsiyonel alt-bileseni: sirketin kendi F/K veya PD/DD'sinin
  son 5 yillik gozlemlenen araligi icinde persentili, "gecmis performans
  gelecegin garantisi degildir" notuyla. valuation_z'nin bir parcasi DEGIL.
- [x] **long_term_target_price_outlier_cap** — TAMAMLANDI (2026-09-17).
  Kok neden (winsorization DEGIL): 2026-09-15 kosusunda ucunun de
  `sector='BILINMIYOR'` gelmesi (fintables entegrasyonundan ONCE) yuzunden
  `ratio_profile='industrial'`e dusup PE+EV/EBITDA ile TAMAMEN alakasiz
  emsallere (GLRYH holding, A1CAP araci kurum/BDDK, IHLGM GYO) karsi
  degerlenmesiydi -- `data/bist_history.db::universe_snapshot`'tan dogrulandi.
  fintables entegrasyonu (ef6237e, 2026-09-16) siniflandirmayi zaten
  duzeltmisti; bugun ek olarak `core/targets.py::compute_long_term_target`
  "reit" profilini "bank"/"insurance" ile ayni PE-only bacagina eklendi
  (RATIO_PROFILES'da reit icin de `forbidden_metrics: ["ev_ebitda"]` var
  ama targets.py bunu hic kontrol etmiyordu -- ayni sinif hata, GYO'larda
  amortisman/yeniden degerleme EBITDA'yi carpitir). `compute_long_term_target`
  DAHA ONCE HIC TEST EDILMIYORDU -- `tests/test_targets_long_term.py`
  (yeni, 4 test) eklendi.
- [ ] **momentum_factor_short_window** (1-2 gun, v11'de P0 idi; **v12'de
  Tier 0/1 butunluk onarimi maddelerinden SONRAYA alindi**, bkz. yukaridaki
  v12 bolumu) — 6ay-1ay momentum, mevcut 140 gunluk fiyat penceresiyle
  simdi yapilabilir. Klasik 12ay-1ay icin pencere genisletmek borsapy
  throttle/hang riskini artirir, ERTELENDI.
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
- [ ] **non_bank_bddk_data_source_gap** (belirsiz sure, P2, veri kaynagi
  arastirmasi gerektirir) — `financial_institution_data_source`
  kapsaminda ortaya cikti: Faktoring (6 ticker: CRDFA, DSTKF, GARFA,
  LIDFA, ULUFA, VAKFA), Finansal Kiralama (5: ISFIN, QNBFK, QNBFL, SEKFK,
  VAKFN), Tasarruf Finansman (1: KTLEV), Varlık Yonetimi (3: BRKVY,
  GLCVY, SMRVA) -- toplam 15 ticker -- Is Yatirim'de NE XI_29 NE UFRS
  sablonunda hic veri donmuyor (canli test, 2026-09-17). financial_group
  parametresiyle cozulmuyor; kaynagin kendisinde eksik. Cozum icin
  `financial_institution_data_source`'un candidate_sources listesindeki
  KAP XBRL veya TBB benzeri bir kaynak gerekir. Bu 15 ticker halen
  Piotroski/Sloan/valuation_z'den (statement-bagimli kisimlar) haric.
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
- [x] **financial_institution_data_source** — TAMAMLANDI (2026-09-17).
  Kok neden: `core/live_data.py::_statements_cached` borsapy'ye hic
  `financial_group` vermiyordu; Is Yatirim'in "Finansal Tablolar" endpoint'i
  banka/sigorta icin AYRI bir sablon (`financial_group="UFRS"`) istiyor, ayrica
  TEK bir try/except ucu tabloyu (bilanco/gelir/nakit akis) birlikte
  yonetiyordu -- nakit akis basarisiz olunca (bankalarda HIC mevcut degil)
  basarili olabilecek bilanco/gelir de atiliyordu. Canli test (2026-09-17,
  20 gercek ticker): 17/20 artik `criteria_computable > 0` (acceptance_test
  esigi: >=10). AKBNK icin gercekci ROE %18.5/ROA %1.7 dogrulandi.
  Kapsam: `_classify_sector` sigorta/emeklilik'i 'bank'tan ayri 'insurance'
  profiline ayirdi (RATIO_PROFILES'da zaten ayrik tanimliydi ama hic
  uretilmiyordu); `_statements_cached` UFRS basarisiz olursa XI_29'a
  fallback yapiyor (araci kurumlar -- ISMEN/GEDIK -- gercekte XI_29
  kullaniyor); UFRS/sigorta etiket varyantlari (TA/equity/NI/current
  assets-liabilities) eklendi; Piotroski `bit()` fonksiyonundaki gizli
  bug duzeltildi (Python'un `and` kisa devresi None'u False'a
  donusturuyordu -- "hesaplanamiyor" ile "kriter karsilanmadi" birbirine
  KARISIYORDU); `core/targets.py` insurance'i bank ile ayni PE-only
  bacagina soktu (generic bacak yasakli EV/EBITDA carpani kullanirdi).
  Test: `tests/test_live_data.py` (yeni dosya), `tests/test_live_data_sector.py`,
  `tests/test_sloan.py` guncellendi.
  **Kalan bilinen bosluk** (kapsam DISI birakildi, ayri madde asagida):
  Faktoring(6)/Finansal Kiralama(5)/Tasarruf Finansman(1)/Varlık
  Yonetimi(3) = 15 ticker'da Is Yatirim'de HICBIR sablonda (ne XI_29 ne
  UFRS) veri yok -- kod/parametre sorunu degil, kaynagin kendisinde eksik.
- [x] **valuation_engine_v2_dcf_addon** — TAMAMLANDI (2026-09-16). `core/dcf.py`,
  `core/gordon.py` ile ayni mimari desende (deneysel, final_score'a/hard_filters'a
  girmez, 3 senaryolu fair-value araligi: dusuk/baz/yuksek buyume senaryosu,
  tek sayi asla gosterilmez). WACC: CAPM (beta x ERP + risk-free) + borc
  agirlikli maliyet (net_debt/finansal_giderler proxy'si, `config/equity_risk_premium.yaml::
  corporate_tax_rate_pct` ile vergi sonrasi). `wacc - g <= 0` -> `null_reason=
  'unstable_denominator'` (gordon.py ile ayni kural). Rapor/dashboard/skill
  entegrasyonu (`report/templates/newsletter.html.j2`, `dashboard.py`,
  `skills/bist-valuation-addon/scripts/dcf.py`) ve footer'da "DENENMEMIS
  VARSAYIM" ifsasi tamam. `tests/test_dcf.py` (10 test) + gercek canli veriyle
  (30 tickerlik ornek evren) dogrulandi: `validate_report` `is_valid=True`,
  3 aday gercek 3-senaryolu aralik uretti, 13 aday dogru `null_reason` ile
  atlandi. Tarihsel carpan bandi (`historical_multiple_band_reference`)
  spec'te AYRI/opsiyonel bilgi bloku olarak isaretli -- bu kapsamda YAPILMADI,
  ayri bir takip maddesi olarak yukariya (v11 bolumu) eklendi.

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

v12 maddeleri (Tier 0/1/2, `verified_claims_log`, `design_tensions_flagged`,
yeni arastirma parcalari) icin `bist_screener_v12_roadmap.json::modules`
altina bakin. Daha eski modullerin tam spec'i (inputs, formula,
hard_constraints, acceptance_test) icin `bist_screener_v10_roadmap.json::
modules` altina bakin. Yeni testler
icin bkz. `testing_additions_required`.
