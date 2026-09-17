"""Gercek veri katmani: borsapy (Is Yatirim + doviz.com kaynakli) uzerinden
CANLI BIST verisi ceker.

NEDEN borsapy: Resmi KAP REST API kurumsal sozlesme gerektiriyor; borsapy
(https://github.com/saidsurucu/borsapy) BIST'in NEREDEYSE TUMUNU (807 sirket,
bkz. companies()) Is Yatirim'in kamuya acik web servislerinden yfinance-benzeri
bir arayuzle ceken, aktif bakimi yapilan (PyPI) bir kutuphanedir. 2Y devlet
tahvili getirisi icin doviz.com saglayicisini kullanir.

Bu dosya core/mock_data.py ile AYNI "sekli" (donen dict/list alanlari) uretir;
bist_mcp/kap_web_mcp/macro_mcp sunuculari BIST_DATA_MODE=live oldugunda
core/mock_data.py yerine buradaki fonksiyonlari cagirir. Boylece core/*
skorlama motorlarinin hicbiri degismez (imza ve semalar sabit kalir).

DURUSTLUK KURALI (bu projenin genel ilkesiyle uyumlu): borsapy/Is Yatirim'in
UCRETSIZ olarak sunmadigi alanlar (yatirimci sayisi/retail-kurumsal kirilimi,
TCMB anket bazli TUFE yil-sonu beklentisi, USD/TRY 12 aylik beklenti, acik
satis yasagi durumu, VBTS sayaci, yillik IPO adedi) SESSIZCE UYDURULMAZ;
None + acik bir yorum olarak birakilir, ilgili core/ modulleri bu None'lari
guvenli sekilde ele alacak sekilde ayrica None-guard edilmistir (bkz.
core/ownership.py, core/hurdle.py, core/regime.py).

BILINEN SINIRLAMA: Is Yatirim'in "Finansal Tablolar" endpoint'i bankalar/
sigorta/finansal kiralama gibi BDDK-tipi konsolide sablonlari desteklemiyor
(canli test: GARAN icin DataNotAvailableError). Bu tickerlar icin bilanco/
gelir tablosu/nakit akis cekilemez -> reporting_basis='unknown' olarak
isaretlenir ve basis_guard.is_scorable() bunlari otomatik eler (bu zaten
var olan, tasarlanmis bir guvenlik mekanizmasidir: core/basis_guard.py
UNKNOWN_RATIO_HALT_THRESHOLD=0.30 ustunde kalirsa kosu zaten durur).
"""
from __future__ import annotations

import json
import re
import socket
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from statistics import pstdev

import borsapy as bp

# borsapy'nin altindaki HTTP cagrilarinin HICBIRINDE acik bir `timeout=`
# yok (2026-09-13 olcumu: tek bir istek, saglayici rate-limit/throttle
# uyguladiginda SONSUZA KADAR askida kalabiliyor -- 1 ticker'lik bir kosu
# bile 17+ dakika hicbir DB yazisi olmadan takili kaldi, GitHub Actions
# job'unun timeout-minutes:350 sinirina kadar hic bitmeyebilirdi). Global
# socket zaman asimi, ucuncu taraf kutuphaneye dokunmadan TUM canli agsal
# cagrilari sinirlar -- takilan istek artik `socket.timeout` firlatir,
# ilgili try/except Exception bloklari (live_macro_snapshot vb.) bunu zaten
# yakalayip None/varsayilana duser (durustluk kurali ile tutarli).
socket.setdefaulttimeout(25)

# Butun canli fonksiyonlar tek tek, sirali (I/O-bound) ag cagrilari yapar.
# ~800 tickerlik tam evrende bu, ticker basina saniyeler suren gecikmeyi
# CARPARAK biriktirir (olcum: sirali ~9sn/ticker sadece ag katmani -> tam
# evren ~2 saat, run.py'nin DB yazma/skorlama katmaniyla birlikte ~8 saat).
#
# ONEMLI OLCUM SONUCU: yuksek concurrency (12) FAYDA SAGLAMADI -- TradingView
# saglayicisi (fast_info'nun kaynagi) es zamanli istek sayisi arttikca
# THROTTLE ediyor (4 es zamanli istekte tek istek suresi 5sn'den 11-23sn'ye
# cikti). 12 worker'la 40 tickerlik test, 15 tickerlik sirali testten (9dk)
# DAHA UZUN surdu. 4 worker'da net kazanc olculdu (~2.5x). Bu yuzden
# PREFETCH_MAX_WORKERS BILINCLI OLARAK DUSUK tutuluyor -- "daha fazla worker
# = daha hizli" varsayimi bu saglayicilar icin GECERSIZ.
PREFETCH_MAX_WORKERS = 4

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

_BANK_SECTOR_KEYWORDS = ["bankacılık", "banka", "finansal kiralama", "faktoring",
                          "finansman şirketleri", "varlık yönetim",
                          "tasarruf finansman", "aracı kurum"]
_INSURANCE_SECTOR_KEYWORDS = ["sigorta", "emeklilik"]
_REIT_SECTOR_KEYWORDS = ["gayrimenkul", "gyo"]
_HOLDING_SECTOR_KEYWORDS = ["holding", "yatırım ortaklığı", "yat. ort."]

# financial_institution_data_source: Is Yatirim'in "Finansal Tablolar" endpoint'i
# XI_29 (sanayi) sablonunun yani sira bir de "UFRS" (BDDK-tipi konsolide,
# banka/sigorta/finansal kiralama) sablonu sunuyor -- borsapy'nin
# get_balance_sheet/get_income_stmt/get_cashflow fonksiyonlarina
# financial_group="UFRS" verilerek erisiliyor (canli test: 2026-09-17, AKBNK
# ve ANHYT icin dogrulandi). ratio_profile='bank'/'insurance' disinda (industrial/
# holding/reit) financial_group=None birakilir (varsayilan XI_29).
_UFRS_RATIO_PROFILES = frozenset({"bank", "insurance"})


def _financial_group_for_profile(ratio_profile: str | None) -> str | None:
    return "UFRS" if ratio_profile in _UFRS_RATIO_PROFILES else None

# fintables.com'dan elle dogrulanmis ticker->sektor eslemesi (borsapy'nin
# `info.sector` alani sik sik eksik/BILINMIYOR donuyor ya da tutarsiz bir
# Ingilizce/karisik taksonomi kullaniyor). Mevcutsa bu, borsapy'nin sektor
# alanindan ONCELIKLIDIR; kapsamadigi ticker'lar icin borsapy'ye dusulur.
_SEKTOR_MAP_PATH = Path(__file__).resolve().parent.parent / "config" / "fintables_ticker_sektor.json"


@lru_cache(maxsize=1)
def _fintables_sector_map() -> dict[str, str]:
    try:
        with open(_SEKTOR_MAP_PATH, encoding="utf-8") as f:
            rows = json.load(f)
        return {r["ticker"]: r["sektor"] for r in rows}
    except Exception:
        return {}

# TCMB politika faizi icin makul aralik (plausibility guard). borsapy'nin
# policy_rate() saglayicisi bazen yanlis/eski bir hucre donduruyor (canli
# testte 7.0 gibi gercekci olmayan bir deger gozlemlendi); bu aralik disindaki
# degerler kullanilmaz, None birakilir.
_POLICY_RATE_PLAUSIBLE_RANGE = (15.0, 75.0)


def _classify_sector(sector_text: str | None) -> tuple[str, str]:
    """(ratio_profile, regulator) dondurur. sector_text Is Yatirim'in NACE benzeri
    Turkce sektor adi (orn. 'ULAŞTIRMA VE DEPOLAMA', 'BANKACILIK')."""
    s = (sector_text or "").strip().lower()
    if any(k in s for k in _BANK_SECTOR_KEYWORDS):
        return "bank", "BDDK"
    if any(k in s for k in _INSURANCE_SECTOR_KEYWORDS):
        return "insurance", "BDDK"
    if any(k in s for k in _REIT_SECTOR_KEYWORDS):
        return "reit", "SPK_TFRS"
    if any(k in s for k in _HOLDING_SECTOR_KEYWORDS):
        return "holding", "SPK_TFRS"
    return "industrial", "SPK_TFRS"


@lru_cache(maxsize=2048)
def _ticker_obj(ticker: str):
    return bp.Ticker(ticker)


_FAST_INFO_FIELDS = ["last_price", "market_cap", "shares", "pe_ratio", "pb_ratio",
                     "free_float", "foreign_ratio", "bid", "ask"]


@lru_cache(maxsize=2048)
def _fast_info_cached(ticker: str) -> dict | None:
    """FastInfo, ilk ozellik erisiminde (lazy __getattr__) agsal cagri yapan bir
    proxy'dir -- tek bir alana erismek TUM veriyi tetikler ve hata da o anda
    firlar. Bu yuzden burada TEK bir try/except icinde duz bir dict'e
    donusturulur (islemi asagidaki tuketici fonksiyonlarda tekrar tekrar
    try/except ile sarmalamaktan kacinmak icin); tamami veya hicbiri.
    Kotasyonu olmayan/askidaki semboller (orn. ADLVY) icin None doner."""
    try:
        fi = _ticker_obj(ticker).fast_info
        return {f: getattr(fi, f, None) for f in _FAST_INFO_FIELDS}
    except Exception:
        return None


@lru_cache(maxsize=2048)
def _info_cached(ticker: str):
    try:
        return dict(_ticker_obj(ticker).info)
    except Exception:
        return {}


@lru_cache(maxsize=2048)
def _dividends_cached(ticker: str):
    try:
        return _ticker_obj(ticker).dividends
    except Exception:
        return None


@lru_cache(maxsize=2048)
def _history_cached(ticker: str, period: str = "2y"):
    """live_listing_and_size VE live_prices AYNI 2 yillik fiyat gecmisini
    kullanir -- tek bir cache anahtari altinda paylasilarak ticker basina
    fazladan bir ag cagrisi onlenir (bkz. prefetch_all).

    KRITIK: borsapy.Ticker.history()'nin VARSAYILANI adjust=True (bonus/bedelsiz
    pay ihraci gibi olaylar icin GERIYE DONUK SPLIT-DUZELTMELI kapanis fiyati
    dondurur). fast_info.last_price ISE HER ZAMAN HAM/guncel piyasa fiyatidir.
    Sik bedelsiz cikaran hisselerde (orn. ASELS) bu ikisi %20-40 gibi buyuk
    bir farka yol acar -- canli fiyat "supheli sapma" sanilip yanlislikla
    reddedilir ve SMA20/ATR20/entry_price gibi TUM turevler de gercek piyasa
    olceginden kopuk (dusuk) cikar (canli test: ASELS ~394 TRY iken adjust=True
    gecmis kapanisi ~289 TRY donduruyordu). adjust=False ile HAM (duzeltmesiz)
    fiyat istenir -- boylece gecmis seri fast_info.last_price ile AYNI olcekte
    kalir."""
    try:
        return _ticker_obj(ticker).history(period=period, adjust=False)
    except Exception:
        return None


@lru_cache(maxsize=2048)
def _news_cached(ticker: str):
    try:
        return _ticker_obj(ticker).news
    except Exception:
        return None


@lru_cache(maxsize=2048)
def _earnings_dates_cached(ticker: str):
    try:
        return _ticker_obj(ticker).earnings_dates
    except Exception:
        return None


@lru_cache(maxsize=2048)
def _statements_cached(ticker: str, financial_group: str | None = None):
    """(balance_sheet, income_stmt, cashflow) DataFrame'lerini dondurur.

    financial_group=None -> XI_29 (sanayi, varsayilan). financial_group="UFRS"
    -> banka/sigorta/finansal kiralama sablonu (bkz. _financial_group_for_profile).

    Her tablo AYRI try/except icinde cekilir: banka/sigorta icin nakit akis
    tablosu Is Yatirim'de HIC mevcut degil (canli test: 2026-09-17, AKBNK/ANHYT
    icin DataNotAvailableError) ama bilanco/gelir tablosu mevcuttur -- tek bir
    ortak try/except kullanilsaydi cf'nin basarisiz olmasi bs/inc'in de
    (basariyla cekilebilecekken) atilmasina yol acardi.

    financial_group="UFRS" ile FALLBACK: _classify_sector'un 'bank' profiline
    soktugu her ticker gercekte UFRS sablonu KULLANMIYOR -- canli test
    (2026-09-17) araci kurumlarin (ISMEN, GEDIK -- 'aracı kurum' anahtar
    kelimesiyle 'bank' profiline giriyor) UFRS'de DataNotAvailableError
    verdigini ama XI_29 (sanayi) sablonunda basariyla cekildigini gosterdi.
    UFRS'nin UCU (bs VE inc) tamamen bos donerse XI_29 ile bir kez daha
    denenir -- boylece sektor siniflandirmasi banka/aracı kurum ayrimini tam
    yapamasa bile veri kaybi olmaz."""
    t = _ticker_obj(ticker)

    def fetch(fg):
        def _f(fn_name: str):
            try:
                return getattr(t, f"get_{fn_name}")(financial_group=fg)
            except Exception:
                return None
        return _f("balance_sheet"), _f("income_stmt"), _f("cashflow")

    bs, inc, cf = fetch(financial_group)
    if bs is None and inc is None and financial_group is not None:
        bs, inc, cf = fetch(None)
    return bs, inc, cf


def _row(df, *labels):
    """DataFrame'de (bosluk-toleransli) ilk eslesen etiketi bulup Series dondurur, yoksa None.

    UFRS (banka/sigorta) sablonlari ayni satiri XI_29'dan (sanayi) FARKLI bir
    etiketle ve bazen baslangicta/sonunda fazladan bosluk ile donduruyor (orn.
    ' AKTİF TOPLAMI' vs 'AKTİF TOPLAMI') -- strip() ile normalize edilmezse
    bu satirlar sessizce None donerdi."""
    if df is None:
        return None
    stripped_index = {str(idx).strip(): idx for idx in df.index}
    for lbl in labels:
        if lbl in stripped_index:
            return df.loc[stripped_index[lbl]]
    return None


def _val(series, col_pos: int = 0):
    """Series veya DataFrame'den col_pos'inci (0=en yeni donem) sayisal degeri guvenle cikar.
    Eger etiket birden fazla satirda tekrarlanmissa (orn. kisa ve uzun vadeli Stoklar/Borclar),
    o doneme ait tum satirlari toplar."""
    if series is None:
        return None
    try:
        if hasattr(series, "ndim") and series.ndim == 2:
            col_vals = series.iloc[:, col_pos].dropna()
            val = float(col_vals.sum())
            return val if val == val else None
        v = series.iloc[col_pos]
        v = float(v)
        return v if v == v else None  # NaN kontrolu
    except Exception:
        return None


# ---------------------------------------------------------------------------
# universe
# ---------------------------------------------------------------------------

def live_universe(limit: int | None = None) -> list[dict]:
    """companies() ile TUM BIST evrenini ceker (807 sirket, hardcoded liste DEGIL).

    Sektor/regulator siniflandirmasi icin her ticker'a bir 'info' cagrisi gerekir;
    bu maliyetlidir (~800 istek) ama gunluk bir toplu is (cron 18:30) icin kabul
    edilebilir (~0.05-0.2sn/istek). `limit` yalnizca gelistirme/hizli-test icin:
    verilirse per-ticker siniflandirma dongusune GIRMEDEN ONCE listeyi kirpar
    (yoksa limit'in hicbir performans faydasi olmazdi).
    """
    companies_df = bp.companies()
    if limit:
        companies_df = companies_df.head(int(limit))
    tickers = companies_df["ticker"].tolist()

    # `info` cekimi (807 ag cagrisina kadar) buradaki tek maliyetli adim;
    # sirali degil PREFETCH_MAX_WORKERS kadar paralel yapilir.
    with ThreadPoolExecutor(max_workers=PREFETCH_MAX_WORKERS) as pool:
        list(pool.map(_info_cached, tickers))

    seed: list[dict] = []
    for _, r in companies_df.iterrows():
        ticker = r["ticker"]
        info = _info_cached(ticker)  # yukarida zaten cache'lendi, ag cagrisi yok
        sector = _fintables_sector_map().get(ticker) or info.get("sector") or info.get("industry")
        ratio_profile, regulator = _classify_sector(sector)
        seed.append({
            "ticker": ticker, "name": r.get("name") or ticker,
            "sector": sector or "BILINMIYOR", "ratio_profile": ratio_profile,
            "regulator": regulator,
        })
    return seed


def prefetch_all(universe_rows: list[dict]) -> None:
    """Evrenin geri kalan tum canli fonksiyonlarinin ihtiyac duydugu ag
    cagrilarini (fast_info, statements, dividends, 2y history, news,
    earnings_dates) PARALEL olarak onceden cache'ler. run.py, universe
    build'den sonra (eligible tickers belli olunca) bunu bir kez cagirir;
    ardindan gelen tum sirali per-ticker dongulari (fundamentals, piotroski,
    sloan, catalysts, prices, ownership, dividend_sustainability...) sadece
    lru_cache'ten okur, yeni ag cagrisi yapmaz.

    universe_rows: ticker basina 'ratio_profile' de tasir -- _statements_cached
    banka/sigorta icin dogru financial_group="UFRS" ile onceden cache'lenmezse,
    sonraki live_fundamentals/live_piotroski_raw_criteria cagrilari CACHE MISS
    yasar ve sirali/ekstra ag cagrisina duser (bkz. financial_institution_data_source)."""
    tickers = [u["ticker"] for u in universe_rows]
    fns = [_fast_info_cached, _info_cached, _dividends_cached,
           _news_cached, _earnings_dates_cached]
    with ThreadPoolExecutor(max_workers=PREFETCH_MAX_WORKERS) as pool:
        futures = []
        for fn in fns:
            futures.extend(pool.submit(fn, t) for t in tickers)
        futures.extend(pool.submit(_statements_cached, u["ticker"],
                                    _financial_group_for_profile(u.get("ratio_profile")))
                        for u in universe_rows)
        futures.extend(pool.submit(_history_cached, t, "2y") for t in tickers)
        for f in futures:
            f.result()  # istisnalar zaten fonksiyon icinde yutuluyor, sadece bekle


# ---------------------------------------------------------------------------
# listing / size / tedbir
# ---------------------------------------------------------------------------

def live_listing_and_size(ticker: str, as_of_date: str) -> dict:
    fi = _fast_info_cached(ticker)
    market_cap = fi.get("market_cap") if fi else None

    avg_volume_tl = None
    listing_days = None
    try:
        hist = _history_cached(ticker, "2y")
        if hist is not None and not hist.empty:
            first_date = hist.index[0].date()
            as_of = datetime.strptime(as_of_date, "%Y-%m-%d").date()
            listing_days = max((as_of - first_date).days, 1)
            # 2y'lik gecmis > 400 gun ise sirket muhtemelen ondan da eski
            # listelenmis; sadece "yeterince eski" ayrimi icin bu proxy yeterli
            # (spec MIN_LISTING_DAYS=90 esigini gecmek icin).
            tail20 = hist.tail(20)
            if not tail20.empty:
                avg_volume_tl = float((tail20["Close"] * tail20["Volume"]).mean())
    except Exception:
        pass

    return {
        "listing_days": listing_days if listing_days is not None else 9999,
        "market_cap": market_cap,
        "avg_volume_tl_20d": avg_volume_tl,
    }


def live_tedbir_level(ticker: str, as_of_date: str) -> dict:
    # Tedbir/VBTS listesi (Borsa Istanbul "Volatilite Bazli Tedbir Sistemi")
    # ucretsiz, yapilandirilmis bir API ile borsapy uzerinden erisilebilir
    # DEGIL. Gercek entegrasyon icin bkz. README "Bilinen sinirlamalar".
    return {"ticker": ticker, "tedbir_level": 0}


# ---------------------------------------------------------------------------
# prices
# ---------------------------------------------------------------------------

_LAST_PRICE_MAX_DEVIATION_PCT = 20.0  # son kapanistan bu orandan fazla sapan last_price supheli sayilir
_VWAP_FALLBACK_WINDOW = 3  # last_price guvenilmezse son N gunun hacim-agirlikli ortalamasina dus


def live_bid_ask(ticker: str) -> dict:
    """v10 roadmap: transaction_cost_model girdisi. fast_info bid/ask
    borsapy'de desteklenmiyorsa (veya kotasyon yoksa) sessizce None doner --
    core/hurdle.py::bid_ask_spread_bps bu durumda net_* alanlarini None birakir."""
    fi = _fast_info_cached(ticker)
    return {"bid": fi.get("bid") if fi else None, "ask": fi.get("ask") if fi else None}


def live_current_price(ticker: str, price_rows: list[dict]) -> dict:
    """"Anlik" fiyati mumkun oldugunca gercege yakin dondurur.

    Sira: (1) borsapy fast_info.last_price (gercek zamanli son islem fiyati);
    bu deger yoksa/sifir-negatifse/son gunun hacmi 0 ise (islem gormeyen/askidaki
    sembol belirtisi) ya da son kapanistan mantiksiz uzaksa (>%20, muhtemelen
    hatali/gecikmis veri) GUVENILMEZ sayilir. (2) Bu durumda son
    _VWAP_FALLBACK_WINDOW gunun hacim-agirlikli ortalama fiyatina (VWAP) dusulur
    -- bu, son islem fiyati yerine "piyasanin gercekte hangi fiyat seviyelerinde
    islem gordugunu" hacimle agirliklandirarak yansitan daha saglam bir vekildir.
    (3) O da hesaplanamazsa son kapanis fiyati kullanilir. Hicbiri yoksa None."""
    fi = _fast_info_cached(ticker)
    last_price = fi.get("last_price") if fi else None
    last_close = price_rows[-1]["close"] if price_rows else None
    last_volume = price_rows[-1]["volume"] if price_rows else None

    if last_price is not None and last_price > 0 and last_volume:
        deviation_ok = True
        if last_close:
            deviation_ok = abs(last_price - last_close) / last_close * 100 <= _LAST_PRICE_MAX_DEVIATION_PCT
        if deviation_ok:
            return {"price": float(last_price), "source": "live"}

    recent = [r for r in price_rows[-_VWAP_FALLBACK_WINDOW:] if r.get("volume")]
    total_volume = sum(r["volume"] for r in recent)
    if total_volume:
        vwap = sum(r["close"] * r["volume"] for r in recent) / total_volume
        return {"price": vwap, "source": "vwap_fallback"}

    if last_close is not None:
        return {"price": last_close, "source": "last_close"}
    return {"price": None, "source": None}


def live_prices(ticker: str, as_of_date: str, days: int = 140) -> list[dict]:
    # live_listing_and_size ile AYNI 2 yillik gecmisi paylasir (_history_cached);
    # 140 gunluk istek bunun icine rahatca siger, ayri bir ag cagrisi gerekmez.
    hist = _history_cached(ticker, "2y")
    if hist is None or hist.empty:
        return []

    as_of = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    rows = []
    for idx, r in hist.iterrows():
        d = idx.date()
        if d > as_of:
            continue
        rows.append({
            "date": d.isoformat(), "ticker": ticker,
            "open": float(r["Open"]), "high": float(r["High"]),
            "low": float(r["Low"]), "close": float(r["Close"]),
            "volume": float(r["Volume"]) if r["Volume"] == r["Volume"] else 0.0,
        })
    rows = rows[-days:]

    for i, r in enumerate(rows):
        window20 = rows[max(0, i - 19):i + 1]
        window50 = rows[max(0, i - 49):i + 1]
        sma20 = sum(x["close"] for x in window20) / len(window20)
        sma50 = sum(x["close"] for x in window50) / len(window50)
        trs = []
        for j in range(max(1, i - 19), i + 1):
            prev_close = rows[j - 1]["close"]
            tr = max(rows[j]["high"] - rows[j]["low"],
                     abs(rows[j]["high"] - prev_close),
                     abs(rows[j]["low"] - prev_close))
            trs.append(tr)
        atr20 = sum(trs) / len(trs) if trs else 0.0
        vol20 = [x["volume"] for x in window20]
        avg_vol20 = sum(vol20) / len(vol20)
        window60 = rows[max(0, i - 59):i + 1]
        daily_returns60 = [window60[k]["close"] / window60[k - 1]["close"] - 1
                            for k in range(1, len(window60)) if window60[k - 1]["close"]]
        # az sayida gozlemle stdev anlamsiz gurultu uretir; en az 30 gozlem sartiyla
        # hesaplanir, aksi halde None (uydurma/duyarsiz bir deger uretilmez).
        volatility_60d = pstdev(daily_returns60) if len(daily_returns60) >= 30 else None
        r["sma20"] = sma20
        r["sma50"] = sma50
        r["atr20"] = atr20
        r["volume_ratio_20d"] = r["volume"] / avg_vol20 if avg_vol20 else None
        r["volatility_60d"] = volatility_60d
    return rows


# ---------------------------------------------------------------------------
# fundamentals
# ---------------------------------------------------------------------------

def live_fundamentals(ticker: str, as_of_date: str, regulator: str, ratio_profile: str) -> dict:
    fi = _fast_info_cached(ticker)
    info = _info_cached(ticker)
    bs, inc, cf = _statements_cached(ticker, _financial_group_for_profile(ratio_profile))

    pe = fi.get("pe_ratio") if fi else None
    pb = fi.get("pb_ratio") if fi else None
    ev_ebitda = info.get("enterpriseToEbitda")
    net_debt = info.get("netDebt")
    market_cap = fi.get("market_cap") if fi else None
    shares_outstanding = info.get("sharesOutstanding") or (fi.get("shares") if fi else None)

    # "Satış Gelirleri"/"BRÜT KAR" (XI_29/sanayi) UFRS banka/sigorta sablonunda
    # YOK -- revenue/gross-profit kavramlari bu sektorler icin anlamli degil,
    # bu yuzden banka/sigorta icin bilinçli olarak None kalir (uydurulmaz).
    revenue = _val(_row(inc, "Satış Gelirleri"))
    net_income = _val(_row(inc, "DÖNEM KARI (ZARARI)", "Ana Ortaklık Payları",
                            "23.1 Grubun Karı/Zararı", "XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)",
                            "3- Dönem Net Kar veya Zararı"))
    equity = _val(_row(bs, "Özkaynaklar", "XVI. ÖZKAYNAKLAR", "Özsermaye Toplamı"))
    total_assets = _val(_row(bs, "TOPLAM VARLIKLAR", "AKTİF TOPLAMI"))
    ebitda_ttm = None
    if ev_ebitda and market_cap and net_debt is not None and ev_ebitda != 0:
        ebitda_ttm = (market_cap + net_debt) / ev_ebitda
    ev_sales = ((market_cap + net_debt) / revenue) if (market_cap and net_debt is not None and revenue) else None
    roe = (net_income / equity * 100) if (net_income is not None and equity) else None

    # OLCUM SONUCU (2026-09-13): "Hisse Basina Kazanc" tablo satiri, sirketin
    # gecmiste yaptigi bedelsiz sermaye artisi/bolunme sonrasi GUNCEL pay
    # sayisina gore duzeltilmemis (split-adjusted degil) -- oysa
    # shares_outstanding (fast_info) GUNCEL/duzeltilmis pay sayisidir. Bu
    # tutarsizlik ASELS'te eps_ttm'i ~100x, AYEN'de ~8x sisirdi (net_income/
    # shares_outstanding ile karsilastirmali olculdu), ve core/targets.py'nin
    # P/E bacagini (leg1) EV/EBITDA bacagiyla (leg2, zaten shares_outstanding
    # kullanir) TUTARSIZ bir pay-sayisi bazina oturttu -> hedef fiyatlar
    # gercek disi sekilde sisti (orn. ASELS icin ~22x). Bu yuzden GUNCEL pay
    # sayisina gore hesaplanan net_income/shares_outstanding BIRINCIL kaynak;
    # ham tablo satiri yalnizca net_income/shares_outstanding hesaplanamazsa
    # (biri eksikse) yedek olarak kullanilir.
    if net_income is not None and shares_outstanding:
        eps_ttm = net_income / shares_outstanding
    else:
        eps_ttm = _val(_row(inc, "Hisse Başına Kazanç"))

    fcf_ttm = _val(_row(cf, "Serbest Nakit Akım"))
    # valuation_engine_v2_dcf_addon.inputs.wacc: borclanma maliyeti proxy'si icin.
    # "(Esas Faaliyet Disi) Finansal Giderler (-)" saf faiz gideri degil (FX
    # zarari da icerebilir) ama gelir tablosunda mevcut EN YAKIN satir; canli
    # THYAO verisiyle dogrulandi (2026-09-16).
    financial_expenses_ttm = _val(_row(inc, "(Esas Faaliyet Dışı) Finansal Giderler (-)"))
    if financial_expenses_ttm is not None:
        financial_expenses_ttm = abs(financial_expenses_ttm)
    dividend_per_share_ttm = _dividend_ttm(ticker)
    payout_ratio = None
    if dividend_per_share_ttm and eps_ttm and eps_ttm > 0:
        payout_ratio = dividend_per_share_ttm / eps_ttm
    elif dividend_per_share_ttm == 0:
        payout_ratio = 0.0

    # valuation_triangle (v13 roadmap P0-3): GYO portfoy degeri ve Holding net aktif degeri (NAV)
    nav_discount = None
    nav_per_share = None
    portfolio_val = None
    if ratio_profile == "reit" and bs is not None:
        inv_prop = _val(_row(bs, "Yatırım Amaçlı Gayrimenkuller"))
        inventories = _val(_row(bs, "Stoklar"))
        tangible = _val(_row(bs, "Maddi Duran Varlıklar"))
        portfolio_val = (inv_prop or 0.0) + (inventories or 0.0) + (tangible or 0.0)
        if portfolio_val <= 0 and total_assets:
            portfolio_val = total_assets
        if portfolio_val > 0:
            effective_net_debt = net_debt if net_debt is not None else 0.0
            nav = portfolio_val - effective_net_debt
            if shares_outstanding and shares_outstanding > 0:
                nav_per_share = nav / shares_outstanding
            if market_cap and market_cap > 0 and nav > 0:
                nav_discount = (nav - market_cap) / nav
    elif ratio_profile == "holding" and equity and market_cap and market_cap > 0 and equity > 0:
        nav_discount = (equity - market_cap) / equity
        if shares_outstanding and shares_outstanding > 0:
            nav_per_share = equity / shares_outstanding

    # dead_hard_filters_repair (v12 T0-2): modul basligi (yukarida) zaten "mali
    # tablo cekilemeyen ticker'lar reporting_basis='unknown' olarak isaretlenir"
    # diyordu ama bu HICBIR ZAMAN gerceklesmiyordu -- fundamentals.py asagidaki
    # None'u SADECE regulator'e gore (BDDK->nominal, SPK_TFRS->adjusted)
    # eziyordu, gercekten veri gelip gelmedigine hic bakmadan. Sonuc: basis_guard'in
    # %30 halt kapisi ve reporting_basis!='unknown' hard filter'i olu kaliyordu
    # (canli kanit: 1606/1606 fundamentals satiri 'adjusted', 2026-09-17). bs VE
    # inc'in IKISI de None ise (financial_group fallback'i dahil hicbir sablonda
    # veri yok -- bkz. _statements_cached) fundamentals.py'ye "unknown" sinyali
    # gonderilir; bu, regulator eslemesini KASITLI olarak ezer.
    reporting_basis = "unknown" if (bs is None and inc is None) else None
    return {
        "reporting_basis": reporting_basis,  # None ise fundamentals.py basis_guard ile doldurur
        "pe": pe, "pb": pb, "ev_ebitda": ev_ebitda, "ev_sales": ev_sales, "roe": roe,
        "eps_ttm": eps_ttm, "ebitda_ttm": ebitda_ttm, "net_debt": net_debt,
        "nav_discount": nav_discount,
        "dividend_per_share_ttm": dividend_per_share_ttm, "payout_ratio": payout_ratio,
        "fcf_ttm": fcf_ttm,
        "roa": (net_income / total_assets * 100) if (net_income is not None and total_assets) else None,
        "nim": None, "npl_ratio": None, "car": None, "combined_ratio": None,
        "ffo_yield": None,
        "_shares_outstanding": shares_outstanding,
        "_total_assets": total_assets,
        "_net_income": net_income,
        "_financial_expenses_ttm": financial_expenses_ttm,
        "_nav_per_share": nav_per_share,
        "_portfolio_value": portfolio_val,
    }


def _dividend_ttm(ticker: str) -> float:
    divs = _dividends_cached(ticker)
    if divs is None or divs.empty or "Amount" not in divs.columns:
        return 0.0
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=370)
    recent = [float(a) for d, a in zip(divs.index, divs["Amount"]) if d.date() >= cutoff]
    return sum(recent) if recent else 0.0


# ---------------------------------------------------------------------------
# piotroski (gercek 9 kriter, 2 donem karsilastirmali)
# ---------------------------------------------------------------------------

def live_piotroski_raw_criteria(ticker: str, as_of_date: str, ratio_profile: str | None = None) -> dict:
    bs, inc, cf = _statements_cached(ticker, _financial_group_for_profile(ratio_profile))
    # NOT cf is None DEGIL: banka/sigorta (UFRS) icin nakit akis tablosu Is
    # Yatirim'de hic mevcut degil (bkz. _statements_cached), ama bilanco/gelir
    # tablosu MEVCUT olabilir -- cf'yi de sarta baglamak bu tickerlari
    # gereksiz yere TAMAMEN (9/9 None) elerdi; asagidaki kriterler zaten
    # cfo'nun None kalmasiyla (2, 4, 7) dogal olarak hesaplanamaz sayilir.
    if bs is None or inc is None or bs.shape[1] < 2 or inc.shape[1] < 2:
        return {f"criterion_{i}": None for i in range(1, 10)}

    ta0, ta1 = (_val(_row(bs, "TOPLAM VARLIKLAR", "AKTİF TOPLAMI"), 0),
                _val(_row(bs, "TOPLAM VARLIKLAR", "AKTİF TOPLAMI"), 1))
    _ni_labels = ("DÖNEM KARI (ZARARI)", "23.1 Grubun Karı/Zararı",
                  "XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)", "3- Dönem Net Kar veya Zararı")
    ni0, ni1 = _val(_row(inc, *_ni_labels), 0), _val(_row(inc, *_ni_labels), 1)
    cfo0 = _val(_row(cf, " İşletme Faaliyetlerinden Kaynaklanan Net Nakit",
                      "İşletme Faaliyetlerinden Kaynaklanan Net Nakit"), 0)
    # Sigorta (UFRS) sablonu cari/duran varlik ayrimini industrial'den FARKLI
    # etiketlerle ama AYNI kavramla tutuyor (banka sablonunda bu ayrim yok --
    # asagidaki etiketler bulunamaz, criterion_6 dogal olarak None kalir).
    _ca_labels = ("Dönen Varlıklar", "I- Cari Varlıklar Toplamı")
    _cl_labels = ("Kısa Vadeli Yükümlülükler", "III - Kısa Vadeli Yükümlülükler Toplamı")
    _ltd_labels = ("Uzun Vadeli Yükümlülükler", "IV- Uzun Vadeli Yükümlülükler Toplamı")
    ca0, ca1 = _val(_row(bs, *_ca_labels), 0), _val(_row(bs, *_ca_labels), 1)
    cl0, cl1 = _val(_row(bs, *_cl_labels), 0), _val(_row(bs, *_cl_labels), 1)
    ltd0, ltd1 = _val(_row(bs, *_ltd_labels), 0), _val(_row(bs, *_ltd_labels), 1)
    gp0, gp1 = _val(_row(inc, "BRÜT KAR (ZARAR)"), 0), _val(_row(inc, "BRÜT KAR (ZARAR)"), 1)
    rev0, rev1 = _val(_row(inc, "Satış Gelirleri"), 0), _val(_row(inc, "Satış Gelirleri"), 1)
    capital_raise0 = _val(_row(cf, "Sermaye Artırımı"), 0)

    def safe_div(a, b):
        return (a / b) if (a is not None and b) else None

    roa0 = safe_div(ni0, ta0)
    roa1 = safe_div(ni1, ta1)
    cur_ratio0 = safe_div(ca0, cl0)
    cur_ratio1 = safe_div(ca1, cl1)
    lev0 = safe_div(ltd0, ta0)
    lev1 = safe_div(ltd1, ta1)
    margin0 = safe_div(gp0, rev0)
    margin1 = safe_div(gp1, rev1)
    turn0 = safe_div(rev0, ta0)
    turn1 = safe_div(rev1, ta1)

    def bit(cmp, *vals):
        """cmp(*vals) sonucunu 0/1'e cevirir; vals'tan biri None ise (banka/sigorta
        sablonunda o satirin hic olmadigi durum dahil) None doner -- 'hesaplanamiyor'
        ile 'kriter karsilanmadi' (0) birbirine KARISTIRILMAZ (bkz. core/piotroski.py
        criteria_computable). ONEMLI: eskiden bu Python'un 'and' kisa devresine
        dayaniyordu (orn. 'roa0 is not None and roa0 > 0') -- roa0 None oldugunda
        bu ifade False (0) donuyordu, None DEGIL; yani "hesaplanamiyor" durumu
        sessizce "kriter karsilanmadi" sayiliyordu. Banka/sigorta gibi bazi
        kriterlerin YAPISAL olarak hesaplanamadigi (current ratio/margin/turnover/
        capital raise gibi kavramlarin bile var olmadigi) durumlarda bu fark
        onemli hale geliyor -- bu yuzden acikca None-guard edildi."""
        if any(v is None for v in vals):
            return None
        return 1 if cmp(*vals) else 0

    return {
        "criterion_1": bit(lambda r: r > 0, roa0),
        "criterion_2": bit(lambda c: c > 0, cfo0),
        "criterion_3": bit(lambda a, b: a > b, roa0, roa1),
        "criterion_4": bit(lambda c, n: c > n, cfo0, ni0),
        "criterion_5": bit(lambda a, b: a < b, lev0, lev1),
        "criterion_6": bit(lambda a, b: a > b, cur_ratio0, cur_ratio1),
        "criterion_7": bit(lambda c: c <= 0, capital_raise0),
        "criterion_8": bit(lambda a, b: a > b, margin0, margin1),
        # inflation_basis_truthful_labeling (v12 T0-3):
        # Is Yatirim beslemesi nominal/tarihi maliyetli oldugundan, yuksek enflasyonda
        # hasilat nominal siserken aktifler tarihi maliyetle kalir. Aktif devir hizi
        # (turn0 > turn1) mekanik olarak siser ve neredeyse tum sirketlere bedava puan verir;
        # bu nedenle nominal beslemede criterion_9 hesaplanamaz (None) kabul edilir.
        "criterion_9": None,
    }


def live_cashflow_for_sloan(ticker: str, as_of_date: str, net_income_hint: float,
                             ratio_profile: str | None = None) -> dict:
    bs, inc, cf = _statements_cached(ticker, _financial_group_for_profile(ratio_profile))
    # Banka/sigorta (UFRS) icin cf HER ZAMAN None -> cfo None kalir (bkz.
    # _statements_cached); sloan.py bunu "not_computable" olarak ele alir,
    # None ile aritmetik islem YAPMAZ.
    cfo = _val(_row(cf, " İşletme Faaliyetlerinden Kaynaklanan Net Nakit",
                     "İşletme Faaliyetlerinden Kaynaklanan Net Nakit"))
    _ta_labels = ("TOPLAM VARLIKLAR", "AKTİF TOPLAMI")
    ta0 = _val(_row(bs, *_ta_labels), 0)
    ta1 = _val(_row(bs, *_ta_labels), 1) if bs is not None and bs.shape[1] > 1 else None
    avg_assets = None
    if ta0 is not None:
        avg_assets = (ta0 + ta1) / 2 if ta1 is not None else ta0
    return {"operating_cashflow_ttm": cfo, "average_total_assets": avg_assets}


# ---------------------------------------------------------------------------
# dividend history / ownership
# ---------------------------------------------------------------------------

def live_dividend_history(ticker: str, as_of_date: str) -> dict:
    divs = _dividends_cached(ticker)
    if divs is None or divs.empty:
        return {"dividend_streak_years": 0, "payout_ratio_trend_3p": "stabil"}

    years_paid = sorted({d.year for d in divs.index}, reverse=True)
    as_of_year = datetime.strptime(as_of_date, "%Y-%m-%d").year
    streak = 0
    y = as_of_year - 1  # bu yilki temettu henuz aciklanmamis olabilir, gecen yildan say
    for yr in years_paid:
        if yr == y:
            streak += 1
            y -= 1
        elif yr > y:
            continue
        else:
            break
    return {"dividend_streak_years": streak, "payout_ratio_trend_3p": "stabil"}


def live_ownership(ticker: str, as_of_date: str) -> dict:
    fi = _fast_info_cached(ticker)
    free_float_pct = fi.get("free_float") if fi else None
    foreign_pct = fi.get("foreign_ratio") if fi else None
    # MKK/TSPB kaynakli yatirimci sayisi ve retail/kurumsal kirilimi ucretsiz,
    # yapilandirilmis bir API ile erisilebilir degil -> durustce None birakilir.
    # core/ownership.py bu alanlari None-guard ile ele alir.
    return {
        "investor_count": None, "investor_count_change_1m": None,
        "retail_pct": None, "institutional_pct": None,
        "free_float_pct": free_float_pct, "foreign_pct": foreign_pct,
    }


# ---------------------------------------------------------------------------
# KAP disclosures (gercek, kural-tabanli kategorizasyon)
# ---------------------------------------------------------------------------

_CATEGORY_RULES: list[tuple[str, str, re.Pattern]] = [
    ("financial_report", "positive", re.compile(r"finansal rapor|bilanço|mali tablo", re.I)),
    ("share_buyback", "positive", re.compile(r"pay geri al|geri alım", re.I)),
    ("bonus_issue", "positive", re.compile(r"bedelsiz", re.I)),
    ("rights_issue", "neutral", re.compile(r"bedelli|sermaye artır", re.I)),
    ("insider_buy", "positive", re.compile(r"pay alım.*(yönetici|ilişkili)|(yönetici|ilişkili).*pay alım", re.I)),
    ("insider_sell", "negative", re.compile(r"pay satış.*(yönetici|ilişkili)|(yönetici|ilişkili).*pay satış", re.I)),
    ("vbts_measure_applied", "negative", re.compile(r"tedbir|vbts", re.I)),
    ("secondary_offering", "neutral", re.compile(r"halka arz|ikincil", re.I)),
    ("management_change", "neutral", re.compile(r"yönetim kurulu|genel müdür", re.I)),
    ("new_business_or_tender", "positive", re.compile(r"ihale|sözleşme|anlaşma|yatırım", re.I)),
]
_DEFAULT_CATEGORY = "material_event_other"


def _categorize_kap_title(title: str) -> tuple[str, str]:
    """KURAL TABANLI (regex/anahtar kelime), LLM DEGIL: no_free_text_interpretation_of_kap."""
    for category, sign, pattern in _CATEGORY_RULES:
        if pattern.search(title or ""):
            return category, sign
    return _DEFAULT_CATEGORY, "neutral"


def live_kap_disclosures(tickers: list[str], as_of_date: str, lookback_days: int = 14) -> list[dict]:
    as_of = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    cutoff = as_of - timedelta(days=lookback_days)
    rows: list[dict] = []
    for ticker in tickers:
        news_df = _news_cached(ticker)
        if news_df is None or news_df.empty:
            continue
        for i, r in news_df.iterrows():
            try:
                published_dt = datetime.strptime(r["Date"], "%d.%m.%Y %H:%M:%S").date()
            except Exception:
                continue
            if published_dt < cutoff or published_dt > as_of:
                continue
            title = str(r.get("Title") or "")
            category, sign = _categorize_kap_title(title)
            rows.append({
                "ticker": ticker,
                "disclosure_id": f"{ticker}-{published_dt.isoformat()}-{i}",
                "category": category,
                "title": category,  # gercek serbest metin LLM'e gitmez, yalnizca kategori tasinir
                "summary": "Kural-tabanli (regex) siniflandirici ile deterministik kategoriye indirgendi.",
                "impact_sign": sign if sign in ("positive", "negative") else "positive",
                "url": r.get("URL") or "",
                "published_at": published_dt.isoformat(),
                "available_at": published_dt.isoformat(),
                "effective_at": published_dt.isoformat(),
            })
    return rows


def live_upcoming_events(tickers: list[str], as_of_date: str) -> list[dict]:
    events: list[dict] = []
    for ticker in tickers:
        ed = _earnings_dates_cached(ticker)
        if ed is None or ed.empty:
            continue
        for dt_idx in ed.index:
            try:
                d = dt_idx.date()
            except Exception:
                continue
            if d.isoformat() <= as_of_date:
                continue
            events.append({
                "ticker": ticker, "event_type": "bilanco_aciklama_tarihi",
                "event_date": d.isoformat(),
                "source": "Is Yatirim finansal takvim (KAP kaynakli)",
                "coverage_note": "resmi",
            })
    return events


# ---------------------------------------------------------------------------
# macro
# ---------------------------------------------------------------------------

def live_index_return_pct(index_name: str, start_date: str, end_date: str) -> float | None:
    """start_date -> end_date arasi endeks (ör. XU100) getirisini (%) dondurur;
    evaluate_past_predictions'in excess_vs_index_pct hesabinda kullanilir
    (v10 roadmap: xu100_benchmark_integration -- eskiden 0.0 sabit yer tutucu).

    point_in_time: start_date/end_date TAM o gunku islem gunu olmayabilir
    (hafta sonu/tatil) -- bu yuzden her iki tarih icin de "o tarihe kadarki
    (dahil) EN SON kapanis" alinir, ileriye bakis (look-ahead) yapilmaz.
    Herhangi bir nedenle veri cekilemezse (agsal hata, bos seri) UYDURULMAZ,
    None doner -- cagiran taraf (core/evaluate.py) bu durumda o satiri
    ATLAR (bir sonraki kosuda tekrar denenir), sahte 0.0 yazmaz."""
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        # start_dt tam bir islem gunune denk gelmeyebilir diye birkac gunluk
        # tampon ile geriden cekiyoruz (yine de yalnizca <= start_dt kullanilacak).
        fetch_start = start_dt - timedelta(days=10)
        hist = bp.Index(index_name).history(start=fetch_start.isoformat(), end=end_dt.isoformat())
        if hist is None or hist.empty:
            return None
        closes = [(idx.date(), float(row["Close"])) for idx, row in hist.iterrows()]
        closes.sort(key=lambda x: x[0])
        start_candidates = [c for d, c in closes if d <= start_dt]
        end_candidates = [c for d, c in closes if d <= end_dt]
        if not start_candidates or not end_candidates:
            return None
        start_close, end_close = start_candidates[-1], end_candidates[-1]
        if not start_close:
            return None
        return (end_close - start_close) / start_close * 100
    except Exception:
        return None


def live_macro_snapshot(as_of_date: str) -> dict:
    result: dict = {
        "policy_rate_pct": None, "bond_2y_pct": None, "bond_10y_pct": None,
        "cpi_yoy_pct": None, "cpi_yearend_expectation_pct": None,
        "usdtry_spot": None, "usdtry_12m_expectation": None,
        "xu100_level": None, "xu100_pe": None, "foreign_ownership_pct": None,
        "short_selling_ban_active": False, "individual_investor_count_millions": None,
        "ytd_ipo_count": None, "vbts_stock_count": None,
    }
    try:
        tp = bp.bond.get_tahvil_provider()
        b2 = tp.get_bond("2Y")
        b10 = tp.get_bond("10Y")
        result["bond_2y_pct"] = b2.get("yield")
        result["bond_10y_pct"] = b10.get("yield")
    except Exception:
        pass
    try:
        pr = bp.policy_rate()
        if pr is not None and _POLICY_RATE_PLAUSIBLE_RANGE[0] <= pr <= _POLICY_RATE_PLAUSIBLE_RANGE[1]:
            result["policy_rate_pct"] = pr
    except Exception:
        pass
    try:
        result["usdtry_spot"] = bp.FX("USD").current.get("last")
    except Exception:
        pass
    try:
        result["xu100_level"] = bp.Index("XU100").info.get("last")
    except Exception:
        pass
    # cpi_yoy_pct, cpi_yearend_expectation_pct, usdtry_12m_expectation,
    # short_selling_ban_active, individual_investor_count_millions,
    # ytd_ipo_count, vbts_stock_count, foreign_ownership_pct, xu100_pe:
    # ucretsiz, guvenilir, tek-noktadan bir kaynak dogrulanamadi (TCMB EVDS
    # anket serileri incelenmeyi bekliyor, bkz. README "Bilinen sinirlamalar").
    # Durustce None/varsayilan birakilir; core/hurdle.py ve core/regime.py bu
    # alanlar icin None-guard icerir.
    return result
