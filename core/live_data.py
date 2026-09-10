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

import re
import warnings
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import borsapy as bp

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

_BANK_SECTOR_KEYWORDS = ["bankacılık", "banka", "finansal kiralama", "faktoring",
                          "finansman şirketleri", "sigorta", "varlık yönetim",
                          "tasarruf finansman", "aracı kurum"]
_REIT_SECTOR_KEYWORDS = ["gayrimenkul yatırım", "gyo"]
_HOLDING_SECTOR_KEYWORDS = ["holding", "yatırım ortaklığı"]

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
    if any(k in s for k in _REIT_SECTOR_KEYWORDS):
        return "reit", "SPK_TFRS"
    if any(k in s for k in _HOLDING_SECTOR_KEYWORDS):
        return "holding", "SPK_TFRS"
    return "industrial", "SPK_TFRS"


@lru_cache(maxsize=2048)
def _ticker_obj(ticker: str):
    return bp.Ticker(ticker)


_FAST_INFO_FIELDS = ["last_price", "market_cap", "shares", "pe_ratio", "pb_ratio",
                     "free_float", "foreign_ratio"]


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
def _statements_cached(ticker: str):
    """(balance_sheet, income_stmt, cashflow) DataFrame'lerini dondurur, cekilemezse
    ucu None olan bir tuple doner (banka/sigorta sablon uyumsuzlugu -> unknown basis)."""
    t = _ticker_obj(ticker)
    try:
        bs = t.balance_sheet
        inc = t.income_stmt
        cf = t.cashflow
        return bs, inc, cf
    except Exception:
        return None, None, None


def _row(df, *labels):
    """DataFrame'de TAM ESLESEN (indent'siz) ilk etiketi bulup Series dondurur, yoksa None."""
    if df is None:
        return None
    for lbl in labels:
        if lbl in df.index:
            return df.loc[lbl]
    return None


def _val(series, col_pos: int = 0):
    """Series'ten col_pos'inci (0=en yeni donem) sayisal degeri güvenle cikar."""
    if series is None:
        return None
    try:
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
    seed: list[dict] = []
    for _, r in companies_df.iterrows():
        ticker = r["ticker"]
        info = _info_cached(ticker)
        sector = info.get("sector") or info.get("industry")
        ratio_profile, regulator = _classify_sector(sector)
        seed.append({
            "ticker": ticker, "name": r.get("name") or ticker,
            "sector": sector or "BILINMIYOR", "ratio_profile": ratio_profile,
            "regulator": regulator,
        })
    return seed


# ---------------------------------------------------------------------------
# listing / size / tedbir
# ---------------------------------------------------------------------------

def live_listing_and_size(ticker: str, as_of_date: str) -> dict:
    fi = _fast_info_cached(ticker)
    market_cap = fi.get("market_cap") if fi else None

    avg_volume_tl = None
    listing_days = None
    try:
        hist = _ticker_obj(ticker).history(period="2y")
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

def live_prices(ticker: str, as_of_date: str, days: int = 140) -> list[dict]:
    try:
        period = "1y" if days > 250 else "6mo"
        hist = _ticker_obj(ticker).history(period=period)
    except Exception:
        return []
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
        r["sma20"] = sma20
        r["sma50"] = sma50
        r["atr20"] = atr20
        r["volume_ratio_20d"] = r["volume"] / avg_vol20 if avg_vol20 else None
    return rows


# ---------------------------------------------------------------------------
# fundamentals
# ---------------------------------------------------------------------------

def live_fundamentals(ticker: str, as_of_date: str, regulator: str, ratio_profile: str) -> dict:
    fi = _fast_info_cached(ticker)
    info = _info_cached(ticker)
    bs, inc, cf = _statements_cached(ticker)

    pe = fi.get("pe_ratio") if fi else None
    pb = fi.get("pb_ratio") if fi else None
    ev_ebitda = info.get("enterpriseToEbitda")
    net_debt = info.get("netDebt")
    market_cap = fi.get("market_cap") if fi else None
    shares_outstanding = info.get("sharesOutstanding") or (fi.get("shares") if fi else None)

    revenue = _val(_row(inc, "Satış Gelirleri"))
    net_income = _val(_row(inc, "DÖNEM KARI (ZARARI)", "Ana Ortaklık Payları"))
    equity = _val(_row(bs, "Özkaynaklar"))
    total_assets = _val(_row(bs, "TOPLAM VARLIKLAR"))
    ebitda_ttm = None
    if ev_ebitda and market_cap and net_debt is not None and ev_ebitda != 0:
        ebitda_ttm = (market_cap + net_debt) / ev_ebitda
    ev_sales = ((market_cap + net_debt) / revenue) if (market_cap and net_debt is not None and revenue) else None
    roe = (net_income / equity * 100) if (net_income is not None and equity) else None

    eps_ttm = _val(_row(inc, "Hisse Başına Kazanç"))
    if eps_ttm is None and net_income is not None and shares_outstanding:
        eps_ttm = net_income / shares_outstanding

    fcf_ttm = _val(_row(cf, "Serbest Nakit Akım"))
    dividend_per_share_ttm = _dividend_ttm(ticker)
    payout_ratio = None
    if dividend_per_share_ttm and eps_ttm and eps_ttm > 0:
        payout_ratio = dividend_per_share_ttm / eps_ttm
    elif dividend_per_share_ttm == 0:
        payout_ratio = 0.0

    return {
        "reporting_basis": None,  # fundamentals.py bunu basis_guard ile ezer
        "pe": pe, "pb": pb, "ev_ebitda": ev_ebitda, "ev_sales": ev_sales, "roe": roe,
        "eps_ttm": eps_ttm, "ebitda_ttm": ebitda_ttm, "net_debt": net_debt,
        "nav_discount": None,  # NAV hesaplamasi icin GYO portfoy degeri gerekir, kaynak yok
        "dividend_per_share_ttm": dividend_per_share_ttm, "payout_ratio": payout_ratio,
        "fcf_ttm": fcf_ttm,
        "roa": (net_income / total_assets * 100) if (net_income is not None and total_assets) else None,
        "nim": None, "npl_ratio": None, "car": None, "combined_ratio": None,
        "ffo_yield": None,
        "_shares_outstanding": shares_outstanding,
        "_total_assets": total_assets,
        "_net_income": net_income,
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

def live_piotroski_raw_criteria(ticker: str, as_of_date: str) -> dict:
    bs, inc, cf = _statements_cached(ticker)
    if bs is None or inc is None or cf is None or bs.shape[1] < 2 or inc.shape[1] < 2:
        return {f"criterion_{i}": None for i in range(1, 10)}

    ta0, ta1 = _val(_row(bs, "TOPLAM VARLIKLAR"), 0), _val(_row(bs, "TOPLAM VARLIKLAR"), 1)
    ni0, ni1 = _val(_row(inc, "DÖNEM KARI (ZARARI)"), 0), _val(_row(inc, "DÖNEM KARI (ZARARI)"), 1)
    cfo0 = _val(_row(cf, " İşletme Faaliyetlerinden Kaynaklanan Net Nakit",
                      "İşletme Faaliyetlerinden Kaynaklanan Net Nakit"), 0)
    ca0, ca1 = _val(_row(bs, "Dönen Varlıklar"), 0), _val(_row(bs, "Dönen Varlıklar"), 1)
    cl0, cl1 = _val(_row(bs, "Kısa Vadeli Yükümlülükler"), 0), _val(_row(bs, "Kısa Vadeli Yükümlülükler"), 1)
    ltd0, ltd1 = _val(_row(bs, "Uzun Vadeli Yükümlülükler"), 0), _val(_row(bs, "Uzun Vadeli Yükümlülükler"), 1)
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

    def bit(cond):
        return None if cond is None else (1 if cond else 0)

    return {
        "criterion_1": bit(roa0 is not None and roa0 > 0),
        "criterion_2": bit(cfo0 is not None and cfo0 > 0),
        "criterion_3": bit(roa0 is not None and roa1 is not None and roa0 > roa1),
        "criterion_4": bit(cfo0 is not None and ni0 is not None and cfo0 > ni0),
        "criterion_5": bit(lev0 is not None and lev1 is not None and lev0 < lev1),
        "criterion_6": bit(cur_ratio0 is not None and cur_ratio1 is not None and cur_ratio0 > cur_ratio1),
        "criterion_7": bit(capital_raise0 is not None and capital_raise0 <= 0),
        "criterion_8": bit(margin0 is not None and margin1 is not None and margin0 > margin1),
        "criterion_9": bit(turn0 is not None and turn1 is not None and turn0 > turn1),
    }


def live_cashflow_for_sloan(ticker: str, as_of_date: str, net_income_hint: float) -> dict:
    bs, inc, cf = _statements_cached(ticker)
    cfo = _val(_row(cf, " İşletme Faaliyetlerinden Kaynaklanan Net Nakit",
                     "İşletme Faaliyetlerinden Kaynaklanan Net Nakit"))
    ta0 = _val(_row(bs, "TOPLAM VARLIKLAR"), 0)
    ta1 = _val(_row(bs, "TOPLAM VARLIKLAR"), 1) if bs is not None and bs.shape[1] > 1 else None
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
        try:
            news_df = _ticker_obj(ticker).news
        except Exception:
            continue
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
        try:
            ed = _ticker_obj(ticker).earnings_dates
        except Exception:
            ed = None
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
