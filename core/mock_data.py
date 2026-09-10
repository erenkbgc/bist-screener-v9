"""Gelistirme/test amacli deterministik mock veri saglayicisi.

NEDEN VAR: Gercek KAP REST API kurumsal sozlesme gerektiriyor, resmi BIST
aracı kurum bazli veri seti sahsi kullanimda erisilebilir degil (bkz.
bist_screener_v9_prompt.json -> mcp_servers.kap-web.description ve
deferred_pending_data_source). Bu modul, bist_mcp/kap_web_mcp/macro_mcp
sunuculariyla ayni fonksiyon imzasini tasiyan, ayni as_of_date icin HER ZAMAN
AYNI degerleri ureten (random.Random(seed)) sahte bir veri katmanidir.

Gercek veri kaynagi baglanacagi zaman yalnizca bu modulun cagrildigi yerler
(bist_mcp/server.py, kap_web_mcp/server.py, macro_mcp/server.py) degistirilir;
core/ altindaki hesap motorlarinin hicbiri bu dosyaya dogrudan bagli degildir.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta

# Gercek BIST sirketlerinden secilmis, sektor cesitliligi olan kucuk bir evren.
# (Bu bir "hardcoded ticker" skorlama girdisi degildir; yalnizca mock veri
# uretmek icin bir isim listesidir. execution_rules.no_hardcoded_tickers,
# core/ranking.py ve core/scoring.py gibi skorlama kodunun hicbir yerinde
# sembol referansi olmamasi anlamina gelir, mock veri kaynaginin evren
# listesine degil.)
_UNIVERSE = [
    ("THYAO", "Turk Hava Yollari", "XULAS", "industrial", "SPK_TFRS"),
    ("ASELS", "Aselsan", "XMANA", "industrial", "SPK_TFRS"),
    ("BIMAS", "BIM Magazalar", "XTCRT", "industrial", "SPK_TFRS"),
    ("EREGL", "Eregli Demir Celik", "XMADN", "industrial", "SPK_TFRS"),
    ("TUPRS", "Tupras", "XKMYA", "industrial", "SPK_TFRS"),
    ("AKBNK", "Akbank", "XBANK", "bank", "BDDK"),
    ("GARAN", "Garanti BBVA", "XBANK", "bank", "BDDK"),
    ("ISCTR", "Is Bankasi C", "XBANK", "bank", "BDDK"),
    ("YKBNK", "Yapi Kredi", "XBANK", "bank", "BDDK"),
    ("SAHOL", "Sabanci Holding", "XHOLD", "holding", "SPK_TFRS"),
    ("KCHOL", "Koc Holding", "XHOLD", "holding", "SPK_TFRS"),
    ("SISE", "Sise Cam", "XKMYA", "industrial", "SPK_TFRS"),
    ("PETKM", "Petkim", "XKMYA", "industrial", "SPK_TFRS"),
    ("TOASO", "Tofas", "XMANA", "industrial", "SPK_TFRS"),
    ("FROTO", "Ford Otosan", "XMANA", "industrial", "SPK_TFRS"),
    ("ARCLK", "Arcelik", "XMESY", "industrial", "SPK_TFRS"),
    ("TCELL", "Turkcell", "XILTM", "industrial", "SPK_TFRS"),
    ("VESTL", "Vestel", "XMESY", "industrial", "SPK_TFRS"),
    ("KOZAL", "Koza Altin", "XMADN", "industrial", "SPK_TFRS"),
    ("ENJSA", "Enerjisa", "XELKT", "industrial", "SPK_TFRS"),
    ("AEFES", "Anadolu Efes", "XGIDA", "industrial", "SPK_TFRS"),
    ("ULKER", "Ulker Biskuvi", "XGIDA", "industrial", "SPK_TFRS"),
    ("MGROS", "Migros", "XTCRT", "industrial", "SPK_TFRS"),
    ("HALKB", "Halkbank", "XBANK", "bank", "BDDK"),
    ("VAKBN", "Vakifbank", "XBANK", "bank", "BDDK"),
    ("TAVHL", "TAV Havalimanlari", "XTRZM", "industrial", "SPK_TFRS"),
    ("PGSUS", "Pegasus", "XULAS", "industrial", "SPK_TFRS"),
    ("DOAS", "Dogus Otomotiv", "XTCRT", "industrial", "SPK_TFRS"),
    ("EKGYO", "Emlak Konut GYO", "XGMYO", "reit", "SPK_TFRS"),
    ("KLGYO", "Kiler GYO", "XGMYO", "reit", "SPK_TFRS"),
    ("ANSGR", "Anadolu Sigorta", "XSGRT", "insurance", "SPK_TFRS"),
    ("TURSG", "Turkiye Sigorta", "XSGRT", "insurance", "SPK_TFRS"),
    ("ALARK", "Alarko Holding", "XHOLD", "holding", "SPK_TFRS"),
    ("OTKAR", "Otokar", "XMANA", "industrial", "SPK_TFRS"),
    ("KRDMD", "Kardemir D", "XMADN", "industrial", "SPK_TFRS"),
    ("SASA", "Sasa Polyester", "XKMYA", "industrial", "SPK_TFRS"),
    ("CIMSA", "Cimsa", "XTAST", "industrial", "SPK_TFRS"),
    ("AKSA", "Aksa Akrilik", "XTEKS", "industrial", "SPK_TFRS"),
    ("TSKB", "TSKB", "XFINK", "bank", "BDDK"),
    ("ISMEN", "Is Yatirim Menkul", "XHOLD", "holding", "SPK_TFRS"),
    ("SOKM", "Sok Marketler", "XTCRT", "industrial", "SPK_TFRS"),
]


def universe_seed() -> list[dict]:
    return [
        {"ticker": t, "name": n, "sector": sec, "ratio_profile": rp, "regulator": reg}
        for t, n, sec, rp, reg in _UNIVERSE
    ]


def _seed_int(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:12], 16)


def _rng(ticker: str, as_of_date: str, salt: str = "") -> random.Random:
    return random.Random(_seed_int(ticker, as_of_date, salt))


def mock_listing_days(ticker: str, as_of_date: str) -> int:
    rng = _rng(ticker, "static", "listing")
    # cogu sirket eski, birkacini yeni IPO gibi davranmasi icin dagit
    base = rng.choice([120, 400, 900, 1800, 3600, 40, 75])
    return base


def mock_tedbir_level(ticker: str, as_of_date: str) -> int:
    rng = _rng(ticker, as_of_date, "tedbir")
    # coğunlukla 0, nadiren tedbir
    return rng.choices([0, 1, 2, 3], weights=[80, 12, 6, 2])[0]


def mock_market_cap_and_volume(ticker: str, as_of_date: str) -> tuple[float, float]:
    rng = _rng(ticker, as_of_date, "size")
    market_cap = rng.uniform(2e9, 400e9)
    avg_volume_tl = rng.uniform(3e6, 900e6)
    return market_cap, avg_volume_tl


def mock_prices(ticker: str, as_of_date: str, days: int = 140) -> list[dict]:
    rng = _rng(ticker, as_of_date, "prices")
    end = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    price = rng.uniform(10, 400)
    rows = []
    drift = rng.uniform(-0.0015, 0.0025)
    vol = rng.uniform(0.012, 0.035)
    closes = []
    d = end - timedelta(days=days)
    cur = d
    while cur <= end:
        if cur.weekday() < 5:
            ret = rng.gauss(drift, vol)
            price = max(0.5, price * (1 + ret))
            o = price * (1 + rng.uniform(-0.005, 0.005))
            h = max(o, price) * (1 + rng.uniform(0, 0.01))
            l = min(o, price) * (1 - rng.uniform(0, 0.01))
            volu = max(1000, rng.uniform(0.5, 1.8) * 1_000_000)
            rows.append({"date": cur.isoformat(), "ticker": ticker, "open": o, "high": h,
                         "low": l, "close": price, "volume": volu})
            closes.append(price)
        cur += timedelta(days=1)
    # basit ATR20 / SMA20 / SMA50 / volume_ratio_20d hesapla
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


def mock_fundamentals(ticker: str, as_of_date: str, regulator: str, ratio_profile: str) -> dict:
    rng = _rng(ticker, as_of_date, "fundamentals")
    reporting_basis = "adjusted" if regulator == "SPK_TFRS" else "nominal"
    eps = rng.uniform(0.5, 40)
    pe = rng.uniform(3, 45)
    pb = rng.uniform(0.4, 8)
    ev_ebitda = rng.uniform(2, 20)
    ev_sales = rng.uniform(0.3, 6)
    roe = rng.uniform(-15, 55)
    ebitda_ttm = rng.uniform(1e8, 5e10)
    net_debt = rng.uniform(-2e10, 3e10)
    dividend_streak_hint = rng.random()
    dividend_per_share = round(eps * rng.uniform(0, 0.6), 4) if dividend_streak_hint > 0.35 else 0.0
    payout_ratio = (dividend_per_share / eps) if eps else 0.0
    fcf_ttm = rng.uniform(-5e9, 3e10)
    return {
        "reporting_basis": reporting_basis,
        "pe": pe, "pb": pb, "ev_ebitda": ev_ebitda, "ev_sales": ev_sales, "roe": roe,
        "eps_ttm": eps, "ebitda_ttm": ebitda_ttm, "net_debt": net_debt,
        "nav_discount": rng.uniform(-0.4, 0.4),
        "dividend_per_share_ttm": dividend_per_share, "payout_ratio": payout_ratio,
        "fcf_ttm": fcf_ttm,
        # bank/insurance icin ek metrikler
        "roa": rng.uniform(0.5, 4.0), "nim": rng.uniform(2.0, 8.0),
        "npl_ratio": rng.uniform(1.0, 8.0), "car": rng.uniform(12.0, 22.0),
        "combined_ratio": rng.uniform(85, 115),
        "ffo_yield": rng.uniform(2, 12),
    }


def mock_piotroski_inputs(ticker: str, as_of_date: str) -> dict:
    rng = _rng(ticker, as_of_date, "piotroski")
    return {f"criterion_{i}": rng.choice([0, 1]) for i in range(1, 10)}


def mock_cashflow_for_sloan(ticker: str, as_of_date: str, net_income_hint: float) -> dict:
    rng = _rng(ticker, as_of_date, "sloan")
    operating_cashflow = net_income_hint * rng.uniform(0.5, 1.6)
    average_total_assets = abs(net_income_hint) * rng.uniform(8, 25) + 1e6
    return {"operating_cashflow_ttm": operating_cashflow, "average_total_assets": average_total_assets}


def mock_dividend_history(ticker: str, as_of_date: str) -> dict:
    rng = _rng(ticker, as_of_date, "dividend_hist")
    streak = rng.choices([0, 1, 2, 3, 4, 5], weights=[30, 10, 10, 10, 15, 25])[0]
    payout_trend = rng.choice(["artiyor", "azaliyor", "stabil"])
    return {"dividend_streak_years": streak, "payout_ratio_trend_3p": payout_trend}


def mock_ownership(ticker: str, as_of_date: str) -> dict:
    rng = _rng(ticker, as_of_date, "ownership")
    retail_pct = rng.uniform(10, 95)
    return {
        "investor_count": rng.randint(500, 900000),
        "investor_count_change_1m": rng.uniform(-10, 80),
        "retail_pct": retail_pct,
        "institutional_pct": max(0.0, 100 - retail_pct - rng.uniform(0, 10)),
        "free_float_pct": rng.uniform(8, 75),
        "foreign_pct": rng.uniform(2, 40),
    }


_KAP_CATEGORIES = [
    "financial_report", "new_business_or_tender", "share_buyback", "rights_issue",
    "bonus_issue", "insider_buy", "insider_sell", "vbts_measure_applied",
    "vbts_measure_expiring", "secondary_offering", "management_change", "material_event_other",
]


def mock_kap_disclosures(ticker: str, as_of_date: str, lookback_days: int) -> list[dict]:
    """KAP bildirimlerini ONCEDEN KATEGORIZE EDILMIS olarak dondurur.

    no_free_text_interpretation_of_kap kuralina uygun: LLM'e serbest metin
    verilmez, bildirim burada zaten deterministik bir kategoriye indirgenmis
    olarak gelir (gercek entegrasyonda bu adim kap_web_mcp icinde bir
    kural/regex tabanli siniflandirici olur, LLM degil).
    """
    rng = _rng(ticker, as_of_date, "kap")
    n = rng.choices([0, 1, 2, 3], weights=[40, 30, 20, 10])[0]
    end = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    rows = []
    for i in range(n):
        cat = rng.choice(_KAP_CATEGORIES)
        days_ago = rng.randint(0, lookback_days - 1)
        published = end - timedelta(days=days_ago)
        sign = "positive" if rng.random() > 0.5 else "negative"
        rows.append({
            "ticker": ticker,
            "disclosure_id": f"{ticker}-{published.isoformat()}-{i}",
            "category": cat,
            "title": f"{ticker} KAP bildirimi ({cat})",
            "summary": "Kategoriye deterministik olarak indirgenmis ozet (mock).",
            "impact_sign": sign,
            "url": f"https://www.kap.org.tr/tr/mock/{ticker}/{i}",
            "published_at": published.isoformat(),
            "available_at": published.isoformat(),
            "effective_at": published.isoformat(),
        })
    return rows


def mock_upcoming_events(ticker: str, as_of_date: str) -> list[dict]:
    rng = _rng(ticker, as_of_date, "events")
    end = datetime.strptime(as_of_date, "%Y-%m-%d").date()
    events = []
    if rng.random() > 0.6:
        events.append({
            "ticker": ticker, "event_type": "bist_index_rebalance",
            "event_date": (end + timedelta(days=rng.randint(5, 60))).isoformat(),
            "source": "Borsa Istanbul endeks revizyon takvimi", "coverage_note": "yuksek",
        })
    if rng.random() > 0.5:
        events.append({
            "ticker": ticker, "event_type": "viop_expiry",
            "event_date": (end + timedelta(days=rng.choice([3, 31, 59]))).isoformat(),
            "source": "VIOP sabit vade takvimi", "coverage_note": "yuksek",
        })
    if rng.random() > 0.85:
        events.append({
            "ticker": ticker, "event_type": "genel_kurul_temettu_kesim",
            "event_date": (end + timedelta(days=rng.randint(10, 90))).isoformat(),
            "source": "KAP genel kurul ilani", "coverage_note": "yalnizca KAP'ta resmen aciklanmissa",
        })
    # bilanco_aciklama_tarihi: kural geregi yalnizca sirket acikca ilan etmisse doldurulur.
    # Mock veri de bu kisiti ciddiye alir: cogunlukla BOS doner.
    if rng.random() > 0.92:
        events.append({
            "ticker": ticker, "event_type": "bilanco_aciklama_tarihi",
            "event_date": (end + timedelta(days=rng.randint(20, 45))).isoformat(),
            "source": "KAP (sirket tarafindan resmen ilan edildi)", "coverage_note": "dusuk",
        })
    return events


def mock_macro_snapshot(as_of_date: str) -> dict:
    rng = _rng("MACRO", as_of_date, "macro")
    base = {
        "policy_rate_pct": 37.0, "bond_2y_pct": 39.6, "bond_10y_pct": 34.2, "cpi_yoy_pct": 31.5,
        "cpi_yearend_expectation_pct": 29.4, "usdtry_spot": 48.4, "usdtry_12m_expectation": 57.4,
        "xu100_level": 14000.0, "xu100_pe": 13.6, "foreign_ownership_pct": 32.6,
        "short_selling_ban_active": True, "individual_investor_count_millions": 6.76,
        "ytd_ipo_count": 26,
    }
    jitter_days = (datetime.strptime(as_of_date, "%Y-%m-%d").date() - date(2026, 9, 8)).days
    drift = jitter_days * rng.uniform(-0.02, 0.03)
    base["usdtry_spot"] = round(base["usdtry_spot"] * (1 + drift / 100), 4)
    base["xu100_level"] = round(base["xu100_level"] * (1 + rng.uniform(-0.01, 0.015) * max(1, abs(jitter_days))), 2)
    base["vbts_stock_count"] = rng.randint(0, 25)
    return base
