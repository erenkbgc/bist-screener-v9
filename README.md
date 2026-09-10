# Autonomous BIST AI Investment Screener (v9)

Kisisel kullanim icin gunluk calisan bir BIST (Borsa Istanbul) tarama sistemi.
Spec: `bist_screener_v9_prompt.json`. Bu README, bu spec'in uygulanmis halinin
nasil calistirilacagini ve nerede durdugunu anlatir.

## Veri katmani: mock (varsayilan) vs. live (gercek)

`BIST_DATA_MODE` ortam degiskeni (`.env`) veri kaynagini secer:

- **`mock`** (varsayilan, testlerde de budur): `core/mock_data.py` -- ayni
  `as_of_date` icin her zaman ayni sayilari ureten deterministik sahte veri.
  Gercek piyasa verisi DEGILDIR, yalnizca gelistirme/test icindir.
- **`live`**: `core/live_data.py` -- [borsapy](https://github.com/saidsurucu/borsapy)
  kutuphanesi uzerinden Is Yatirim + doviz.com kaynakli **GERCEK, canli** veri.
  Resmi KAP REST API kurumsal sozlesme gerektirdigi ve bunu bu ortamda
  edinmek mumkun olmadigi icin borsapy, arastirma sonucu bulunan en genis
  kapsamli ucretsiz alternatif olarak secildi (807 sirketlik tam BIST
  evrenini, fiyat/hacim/bilanco/gelir tablosu/nakit akis/temettu/KAP
  bildirim basliklarini ve 2Y devlet tahvili getirisini kapsiyor).

```bash
export BIST_DATA_MODE=live
python run.py --as-of-date $(date +%F)
```

Bu modda **evrende hicbir hardcoded ticker yoktur**: `core/live_data.py::live_universe()`
her kosuda `bp.companies()` ile TUM BIST'i (~800 sirket) dinamik olarak ceker;
tarama, universe_filters (min_volume/min_listing_days/tedbir) ve peer-group
mantigi bu tam evren uzerinde calisir. "Giris fiyati" (`entry_price`) satirdaki
en son gercek kapanis fiyatidir, "Hedef fiyat" ise `core/targets.py`'nin KENDI
kesitsel/peer-relative modelinden (analist konsensusu DEGIL, spec'in
gerektirdigi sekilde kendi hesaplanan degerleme) turetilir.

**Live modda gercek olan alanlar:** fiyat/OHLCV (`Ticker.history`), F/K, PD/DD,
piyasa degeri, halka aciklik orani, yabanci payi (`fast_info`), bilanco/gelir
tablosu/nakit akis kalemleri (Piotroski 9 kriteri ve Sloan tahakkuk orani
GERCEK, 2 donem karsilastirmali hesaplanir), temettu gecmisi, KAP bildirim
basliklari (kural-tabanli/regex siniflandirici ile kategorize edilir, LLM
DEGIL), 2 yillik gosterge tahvil getirisi (hurdle_engine'in tek sert-gecit
girdisi), USD/TRY spot, XU100 seviyesi.

**Live modda GERCEK KAYNAGI OLMADIGI ICIN uydurulmayan, `None` birakilan
alanlar** (ilgili `core/*.py` modulleri bunlari None-guard ile ele alir, sahte
sayi uretilmez): yatirimci sayisi ve retail/kurumsal kirilimi (MKK/TSPB
kaynakli, ucretsiz API yok), tedbir/VBTS listesi, TCMB anket bazli TUFE
yil-sonu beklentisi ve USD/TRY 12 aylik beklentisi, acik satis yasagi durumu,
yillik IPO adedi, GYO/holding NAV degeri, banka/sigorta rasyolari (roa/nim/
npl_ratio/car/combined_ratio -- bkz. asagidaki sablon sinirlamasi). Bu, projenin
"asla uydurma sayi yok" ilkesiyle bilincli bir tercihtir.

**Bilinen sablon sinirlamasi:** Is Yatirim'in bilanco/gelir tablosu endpoint'i
banka/sigorta/finansal kiralama gibi BDDK-tipi konsolide sablonlari
desteklemiyor (canli testte GARAN icin `DataNotAvailableError`). Bu tickerlar
icin Piotroski/Sloan hesaplanamaz; `reporting_basis='unknown'` olur ve
`basis_guard.is_scorable()` bunlari otomatik eler -- zaten var olan bir
guvenlik mekanizmasi (bkz. `UNKNOWN_RATIO_HALT_THRESHOLD=0.30`).

Butun skorlama/filtre/rapor mantigi (`core/*.py`) her iki modda da AYNI
kod yolundan gecer; degisen tek sey `bist_mcp/server.py`, `kap_web_mcp/server.py`,
`macro_mcp/server.py` icindeki veri kaynagi secimidir (imzalar ve donus
semalari sabit).

## Kurulum

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # SMTP bilgilerinizi doldurun (opsiyonel)
```

## Calistirma

Tek seferlik bir kosu:

```bash
python run.py --as-of-date 2026-09-10
```

`--as-of-date` verilmezse bugunun tarihi kullanilir. SMTP degiskenleri
(`.env`) doldurulmadiysa e-posta gonderilmez, HTML rapor ve payload.json
`data/reports/` altina yazilir.

Dashboard (salt-okunur):

```bash
streamlit run dashboard.py
```

Zamanlamak icin (spec: 18:30 Europe/Istanbul, cron):

```cron
30 18 * * * cd /path/to/bist_project && .venv/bin/python run.py >> logs/run.log 2>&1
```

## Testler

```bash
pytest tests/ -v
```

92 test, spec'in `testing.required` listesindeki her maddeyi kapsar (basis_guard,
hurdle, piotroski, sloan cross-sectional, beta hurdle bilgi-alani kontrolu,
event calendar tahmin-yasagi, regime_taxonomy statik izolasyon taramasi,
invalidation monitor, validation_gate/banned_claims, idempotency, dashboard
salt-okunurluk, vb.)

## Mimari

```
bist_mcp/, kap_web_mcp/, macro_mcp/   MCP sunuculari (su an mock veri)
core/                                  deterministik hesap motorlari (tek gercek kaynak)
report/                                Jinja2 sablon + validation_gate
skills/                                yontem paketleri (ince CLI sarmalayicilar)
config/                                weights.yaml, equity_risk_premium.yaml, ... (DENENMEMIS varsayimlar)
run.py                                 gunluk orkestratör (execution_order'i uygular)
dashboard.py                           salt-okunur Streamlit goruntuleme
data/bist_history.db                   SQLite (spec: database_schema)
```

`run.py`, spec'in `architecture.execution_order` listesini birebir uygular:
regime_monitor → regime_taxonomy → universe → basis_guard → ranking →
earnings_quality_sloan → catalysts → event_calendar_engine → ownership_quality
→ target_price_engine → hurdle_engine → beta_adjusted_hurdle →
dividend_sustainability_engine → optional_valuation_addon → concentration_check
→ correlation_diagnostic → decision_diff_engine → payload → thesis_card →
validate → dispatch → evaluate_past_predictions → thesis_invalidation_monitor.

## Kritik tasarim kurallari (kodda uygulanir, testlerle korunur)

- **Sabit esik yok**: `core/ranking.py` yalnizca esler grubu ici kesitsel
  persentil/z-skor kullanir; hicbir yerde sabit F/K, PD/DD, FD/FAVOK esigi yoktur.
- **regime_taxonomy → scoring.py izolasyonu**: `core/regime_taxonomy.py`
  etiketleri yalnizca raporlamada gorunur, `core/scoring.py`'ye hicbir
  import/veri akisi yoktur (`tests/test_regime_taxonomy_static.py`).
- **validation_gate**: `report/validate.py`, uretilen HTML'deki her sayisal
  degerin `core/payload.py::build_report_payload` ciktisinda bulunmasini
  zorunlu kilar; aksi halde gonderim iptal edilir.
- **priors_are_disclosed**: `config/weights.yaml`, `config/equity_risk_premium.yaml`
  ve rapor altbilgisi, tum agirlik/esiklerin DENENMEMIS baslangic varsayimi
  oldugunu acikca belirtir.
- **evaluate_past_predictions bir backtest degildir**: `core/evaluate.py` ve
  rapor, bunu her zaman canli takip olarak etiketler; `banned_claims` listesi
  (`kanitlanmis edge`, `istatistiksel olarak anlamli`, ...) hem kod hem
  validation_gate tarafindan taranir.
- **dashboard.py salt-okunur**: yalnizca `core.db.get_connection(read_only=True)`
  kullanir, hicbir INSERT/UPDATE/DELETE icermez.

## Bilinen sinirlamalar

- `broker_concentration_guard` spec'te `deferred_pending_data_source` olarak
  isaretlendi (veri kaynagi yok) — uygulanmadi.
- MCP sunuculari (`bist_mcp`, `kap_web_mcp`, `macro_mcp`) `BIST_DATA_MODE`'a
  gore mock veya live veri dondurur; `mcp` paketi kuruluysa
  `python -m bist_mcp.server` gibi bagimsiz MCP sunuculari olarak da
  calistirilabilirler (Claude Desktop / baska bir MCP istemcisiyle).
- `XU100` endeks getirisi `core/evaluate.py` icinde su an yer tutucu (0.0)
  olarak birakildi; gercek entegrasyonda `bp.Index("XU100").history(...)`
  ile gunluk kapanis serisi eklenmeli.
- Live modda yatirimci sayisi/retail-kurumsal kirilimi, TCMB anket bazli
  makro beklentiler, acik satis yasagi durumu, tedbir/VBTS listesi ve
  banka/sigorta rasyolari icin ucretsiz, guvenilir bir kaynak dogrulanamadi
  (bkz. yukaridaki "Veri katmani" bolumu) -- bu alanlar `None` birakilir.
- Banka/sigorta/finansal kiralama sirketleri icin Is Yatirim'in bilanco
  endpoint'i (borsapy uzerinden) veri dondurmuyor -- bu tickerlar
  `reporting_basis='unknown'` ile Piotroski/Sloan'dan otomatik elenir.
- `core/live_data.py`'nin listing_days/avg_volume_tl_20d hesaplari ve KAP
  kategorizasyon regex'leri makul varsayimlar/proxy'lerdir, resmi bir
  referansla dogrulanmamistir; ilk canli kosularda `data/reports/*_payload.json`
  uzerinden gozden gecirilmesi onerilir.
