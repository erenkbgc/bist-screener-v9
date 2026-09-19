"""core/data_quality.py: BIST Data Quality & Survivorship Bias Module.

v13 Roadmap P0-4:
1. Delist / iflas eden hisselerin arsivlenmesi (Survivorship Bias onleme).
2. Fiyat duzeltmeleri: temettu, bedelsiz, sermaye artirimi (Adjusted Price Engine).
3. Veri dogrulama: fiyat sicramalari, eksik gunler, sifir hacim, hatali degerler (Data Quality Audit).
4. Alternatif kaynak entegrasyonu ve resilience.
Cikti: data_quality_report, duzeltilmis fiyat serisi (adjusted_prices), delisted_stocks.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core import db

logger = logging.getLogger(__name__)


def _live_enabled() -> bool:
    return os.environ.get("BIST_DATA_MODE", "mock").strip().lower() == "live"

# =====================================================================
# 1. SURVIVORSHIP BIAS & DELISTED STOCKS ARCHIVE
# =====================================================================

HISTORICAL_DELISTED_STOCKS = [
    {
        "ticker": "ASYAB",
        "company_name": "Asya Katılım Bankası A.Ş.",
        "delist_date": "2016-07-22",
        "delist_reason": "bankruptcy",
        "last_price": 0.69,
        "terminal_recovery_pct": 0.0,
        "sector": "XBANK",
        "notes": "Faaliyet izni kaldırıldı, TMSF tasfiye sürecine alındı, borsa kotundan çıkarıldı.",
    },
    {
        "ticker": "GENYH",
        "company_name": "Gen Yatırım Holding A.Ş.",
        "delist_date": "2017-05-12",
        "delist_reason": "bankruptcy",
        "last_price": 0.44,
        "terminal_recovery_pct": 0.0,
        "sector": "XHOLD",
        "notes": "İflas kararı ve SPK/BIST kottan çıkarma.",
    },
    {
        "ticker": "MEMS",
        "company_name": "Mensa Sınai Ticari ve Mali Yatırımlar A.Ş.",
        "delist_date": "2020-04-14",
        "delist_reason": "regulatory_expulsion",
        "last_price": 0.14,
        "terminal_recovery_pct": 0.0,
        "sector": "XTEKS",
        "notes": "Kotasyon yönergesi uyarınca sürekli işlem görmekten men / kottan çıkarma.",
    },
    {
        "ticker": "ESEM",
        "company_name": "Esem Spor Giyim Sanayi ve Ticaret A.Ş.",
        "delist_date": "2021-06-25",
        "delist_reason": "regulatory_expulsion",
        "last_price": 0.38,
        "terminal_recovery_pct": 0.0,
        "sector": "XTEKS",
        "notes": "Üretim faaliyetinin durması ve finansal yükümlülükler nedeniyle kottan çıkarıldı.",
    },
    {
        "ticker": "MANGO",
        "company_name": "Mango Gıda Sanayi ve Ticaret A.Ş.",
        "delist_date": "2015-11-20",
        "delist_reason": "bankruptcy",
        "last_price": 0.22,
        "terminal_recovery_pct": 0.0,
        "sector": "XGIDA",
        "notes": "İflas açılması ve Borsa kotundan resen çıkarma.",
    },
    {
        "ticker": "ARTI",
        "company_name": "Artı Yatırım Holding A.Ş.",
        "delist_date": "2021-08-13",
        "delist_reason": "regulatory_expulsion",
        "last_price": 1.15,
        "terminal_recovery_pct": 0.0,
        "sector": "XHOLD",
        "notes": "Sermaye kaybı ve faaliyetlerini sürdürememe gerekçesiyle kottan çıkarma.",
    },
    {
        "ticker": "MEKPET",
        "company_name": "Meka Petrol Dağıtım A.Ş.",
        "delist_date": "2014-04-01",
        "delist_reason": "bankruptcy",
        "last_price": 0.31,
        "terminal_recovery_pct": 0.0,
        "sector": "XKMYA",
        "notes": "İflas ve tasfiye.",
    },
    {
        "ticker": "UKIM",
        "company_name": "Uki Uluslararası Konfeksiyon İmalat ve Ticaret A.Ş.",
        "delist_date": "2013-09-06",
        "delist_reason": "bankruptcy",
        "last_price": 0.18,
        "terminal_recovery_pct": 0.0,
        "sector": "XTEKS",
        "notes": "İflas kararı kesinleşti.",
    },
    {
        "ticker": "BISAS",
        "company_name": "Bisaş Tekstil Sanayi ve Ticaret A.Ş.",
        "delist_date": "2017-12-08",
        "delist_reason": "regulatory_expulsion",
        "last_price": 0.52,
        "terminal_recovery_pct": 0.0,
        "sector": "XTEKS",
        "notes": "Finansman yapısının bozulması ve kottan çıkarma.",
    },
    {
        "ticker": "RANLO",
        "company_name": "Ran Lojistik Hizmetleri A.Ş.",
        "delist_date": "2015-05-29",
        "delist_reason": "bankruptcy",
        "last_price": 0.28,
        "terminal_recovery_pct": 0.0,
        "sector": "XULAS",
        "notes": "İflas.",
    },
    {
        "ticker": "TRANST",
        "company_name": "Transtürk Holding A.Ş.",
        "delist_date": "2019-11-29",
        "delist_reason": "regulatory_expulsion",
        "last_price": 0.35,
        "terminal_recovery_pct": 0.0,
        "sector": "XHOLD",
        "notes": "Kotasyon kriterlerini sağlayamama sebebiyle kottan çıkarma.",
    },
    {
        "ticker": "DENIZ",
        "company_name": "Denizbank A.Ş.",
        "delist_date": "2019-11-14",
        "delist_reason": "squeeze_out",
        "last_price": 15.60,
        "terminal_recovery_pct": 100.0,
        "sector": "XBANK",
        "notes": "Emirates NBD devri sonrası ortaklıktan çıkarma hakkı kullanımı ile borsa kotundan çıkış.",
    },
    {
        "ticker": "TEB",
        "company_name": "Türk Ekonomi Bankası A.Ş.",
        "delist_date": "2014-11-14",
        "delist_reason": "voluntary",
        "last_price": 2.18,
        "terminal_recovery_pct": 100.0,
        "sector": "XBANK",
        "notes": "Hakim ortak BNP Paribas çağrısı sonrası gönüllü borsa kotundan çıkış.",
    },
    {
        "ticker": "MUTLU",
        "company_name": "Mutlu Akü ve Malzemeleri Sanayii A.Ş.",
        "delist_date": "2015-09-15",
        "delist_reason": "squeeze_out",
        "last_price": 8.35,
        "terminal_recovery_pct": 100.0,
        "sector": "XUSIN",
        "notes": "Hakim ortak Metair Investments tarafından ortaklıktan çıkarma hakkı kullanımı.",
    },
]


def seed_delisted_stocks() -> int:
    """Delist olmus hisse arsivini veritabanina yukler."""
    conn = db.get_connection()
    try:
        inserted = 0
        for stock in HISTORICAL_DELISTED_STOCKS:
            cur = conn.execute(
                """INSERT INTO delisted_stocks
                   (ticker, company_name, delist_date, delist_reason, last_price, terminal_recovery_pct, sector, notes)
                   VALUES (:ticker, :company_name, :delist_date, :delist_reason, :last_price, :terminal_recovery_pct, :sector, :notes)
                   ON CONFLICT(ticker) DO UPDATE SET
                     delist_date=excluded.delist_date,
                     delist_reason=excluded.delist_reason,
                     last_price=excluded.last_price,
                     terminal_recovery_pct=excluded.terminal_recovery_pct,
                     notes=excluded.notes""",
                stock,
            )
            inserted += cur.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()


def get_delisted_stocks() -> list[dict]:
    """Arsivlenmis delist hisseleri dondurur."""
    rows = db.query("SELECT * FROM delisted_stocks ORDER BY delist_date DESC")
    if not rows:
        seed_delisted_stocks()
        rows = db.query("SELECT * FROM delisted_stocks ORDER BY delist_date DESC")
    return [dict(r) for r in rows]


def get_delist_info(ticker: str) -> dict | None:
    """Belirli bir hissenin delist bilgilerini dondurur (varsa)."""
    rows = db.query("SELECT * FROM delisted_stocks WHERE ticker = ?", (ticker.upper(),))
    if rows:
        return dict(rows[0])
    # Memory seed fallback
    for item in HISTORICAL_DELISTED_STOCKS:
        if item["ticker"] == ticker.upper():
            return dict(item)
    return None


def is_delisted(ticker: str, as_of_date: str | None = None) -> bool:
    """Hissenin as_of_date tarihi itibariyle delist olup olmadigini kontrol eder."""
    info = get_delist_info(ticker)
    if not info:
        return False
    if as_of_date is None:
        return True
    return info["delist_date"] <= as_of_date


# delisted_stocks.sector'da saklanan BIST sektor kodlarindan ratio_profile/supersector
# turetir (core/universe.py'deki canli evren siniflandirmasiyla tutarli).
_DELISTED_SECTOR_RATIO_PROFILE = {
    "XBANK": "bank",
    "XSGRT": "insurance",
    "XHOLD": "holding",
    "XGMYO": "reit",
}
_DELISTED_SECTOR_SUPERSECTOR = {
    "XBANK": "XUMAL", "XFINK": "XUMAL", "XSGRT": "XUMAL", "XHOLD": "XUMAL",
    "XYORT": "XUMAL", "XGMYO": "XUMAL", "XILTM": "XUTEK", "XBLSM": "XUTEK",
}


def get_survivorship_free_universe(
    as_of_date: str,
    active_universe: list[dict] | None = None,
) -> list[dict]:
    """Gecmis bir tarihteki BIST evrenini survivorship bias olmadan olusturur.
    
    O tarihte islem goren ancak bugun delist olmus sirketleri de listeye ekler.
    """
    universe = list(active_universe or [])
    active_tickers = {x["ticker"] for x in universe}
    
    delisted = get_delisted_stocks()
    for d in delisted:
        # Eger sirket as_of_date tarihinde henuz delist OLMAMISSA, o tarihteki evrende yer almaliydi!
        if d["delist_date"] > as_of_date and d["ticker"] not in active_tickers:
            universe.append({
                "ticker": d["ticker"],
                "name": d["company_name"],
                "sector": d["sector"],
                "supersector": _DELISTED_SECTOR_SUPERSECTOR.get(d["sector"], "XUSIN"),
                "ratio_profile": _DELISTED_SECTOR_RATIO_PROFILE.get(d["sector"], "industrial"),
                "regulator": "SPK",
                "is_delisted": False,
                "delisted_future_date": d["delist_date"],
                "delist_reason": d["delist_reason"],
            })
        elif d["delist_date"] <= as_of_date and d["ticker"] in active_tickers:
            # Bugunku listede ama o tarihte zaten delist ise cikarilmasi gerekir
            universe = [x for x in universe if x["ticker"] != d["ticker"]]

    return universe


# =====================================================================
# 2. CORPORATE ACTIONS & PRICE ADJUSTMENT ENGINE
# =====================================================================

@dataclass
class CorporateAction:
    ticker: str
    action_date: str
    action_type: str  # 'dividend', 'bonus_issue' (bedelsiz), 'rights_issue' (bedelli), 'split'
    ratio_or_amount: float
    split_factor: float = 1.0
    dividend_amount: float = 0.0
    source: str = "live"


def save_corporate_actions(actions: list[dict]) -> None:
    """Kurumsal aksiyonlari veritabanina kaydeder."""
    if not actions:
        return
    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO corporate_actions
               (ticker, action_date, action_type, ratio_or_amount, split_factor, dividend_amount, source)
               VALUES (:ticker, :action_date, :action_type, :ratio_or_amount, :split_factor, :dividend_amount, :source)
               ON CONFLICT(ticker, action_date, action_type) DO UPDATE SET
                 ratio_or_amount=excluded.ratio_or_amount,
                 split_factor=excluded.split_factor,
                 dividend_amount=excluded.dividend_amount,
                 source=excluded.source""",
            actions,
        )
        conn.commit()
    finally:
        conn.close()


def get_corporate_actions_from_db(ticker: str) -> list[dict]:
    """DB'de kayitli kurumsal aksiyonlari getirir."""
    rows = db.query(
        "SELECT * FROM corporate_actions WHERE ticker = ? ORDER BY action_date ASC",
        (ticker.upper(),),
    )
    return [dict(r) for r in rows]


def fetch_corporate_actions(ticker: str, as_of_date: str | None = None) -> list[dict]:
    """Hisseye ait kurumsal aksiyonlari (temettu, bedelsiz, bedelli) ceker."""
    ticker = ticker.upper()
    actions: list[dict] = []

    # 1. DB oncelikli kontrol
    cached = get_corporate_actions_from_db(ticker)
    if cached:
        if as_of_date:
            return [a for a in cached if a["action_date"] <= as_of_date]
        return cached

    # 2. Canli veri cekimi (borsapy uzerinden) -- yalnizca BIST_DATA_MODE=live iken
    if not _live_enabled():
        return []

    try:
        import borsapy as bp
        t = bp.Ticker(ticker)

        # Temettuler
        try:
            divs = t.dividends
            if divs is not None and not divs.empty:
                for idx, row in divs.iterrows():
                    d_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                    amount = float(row.get("Amount", 0.0) or row.get("NetRate", 0.0) or 0.0)
                    if amount > 0:
                        actions.append({
                            "ticker": ticker,
                            "action_date": d_str,
                            "action_type": "dividend",
                            "ratio_or_amount": amount,
                            "split_factor": 1.0,
                            "dividend_amount": amount,
                            "source": "borsapy_dividends",
                        })
        except Exception as e:
            logger.debug("Dividends fetch error for %s: %s", ticker, e)

        # Bolunmeler & Bedelsizler (splits)
        try:
            splits_df = t.splits
            if splits_df is not None and not splits_df.empty:
                for idx, row in splits_df.iterrows():
                    d_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                    bonus_cap = float(row.get("BonusFromCapital", 0.0) or 0.0)
                    bonus_div = float(row.get("BonusFromDividend", 0.0) or 0.0)
                    rights = float(row.get("RightsIssue", 0.0) or 0.0)
                    total_bonus = bonus_cap + bonus_div
                    if total_bonus > 0:
                        # %100 bedelsiz -> 1 paya karsilik 1 yeni pay, split factor = (100 + bonus) / 100 = 2.0
                        split_factor = 1.0 + (total_bonus / 100.0)
                        actions.append({
                            "ticker": ticker,
                            "action_date": d_str,
                            "action_type": "bonus_issue",
                            "ratio_or_amount": total_bonus,
                            "split_factor": split_factor,
                            "dividend_amount": 0.0,
                            "source": "borsapy_splits",
                        })
                    elif rights > 0:
                        split_factor = 1.0 + (rights / 100.0)
                        actions.append({
                            "ticker": ticker,
                            "action_date": d_str,
                            "action_type": "rights_issue",
                            "ratio_or_amount": rights,
                            "split_factor": split_factor,
                            "dividend_amount": 0.0,
                            "source": "borsapy_splits",
                        })
        except Exception as e:
            logger.debug("Splits fetch error for %s: %s", ticker, e)

        if actions:
            save_corporate_actions(actions)

    except Exception as e:
        logger.debug("borsapy actions error for %s: %s", ticker, e)

    if as_of_date:
        actions = [a for a in actions if a["action_date"] <= as_of_date]

    return sorted(actions, key=lambda x: x["action_date"])


def adjust_price_series(
    price_rows: list[dict],
    corporate_actions: list[dict] | None = None,
) -> list[dict]:
    """Ham OHLCV fiyat serisini kurumsal aksiyonlara gore geriye donuk duzeltir (CRSP Standart).
    
    - Bedelsiz / Bolunme (split_factor = S):
      Aksiyon tarihinden ONCEKI tum fiyatlar S'ye bolunur, hacim S ile carpilir.
    - Nakit Temettu (D):
      Aksiyondan hemen onceki kapanis fiyati P_cum olmak uzere:
      f = (P_cum - D) / P_cum (P_cum > D kosuluyla).
      Aksiyon tarihinden ONCEKI tum fiyatlar f ile carpilir.
    """
    if not price_rows:
        return []

    # Kronolojik sira garanti
    sorted_rows = sorted(price_rows, key=lambda x: x["date"])
    
    # Kopyalarini cikarip ham alanlari koru
    adjusted = []
    for r in sorted_rows:
        row_copy = dict(r)
        raw_close = float(r["close"])
        row_copy["raw_close"] = raw_close
        row_copy["adj_open"] = float(r["open"])
        row_copy["adj_high"] = float(r["high"])
        row_copy["adj_low"] = float(r["low"])
        row_copy["adj_close"] = raw_close
        row_copy["adj_volume"] = float(r.get("volume", 0.0))
        row_copy["adjustment_factor"] = 1.0
        adjusted.append(row_copy)

    if not corporate_actions:
        return adjusted

    # Aksiyonlari kronolojik uygula
    sorted_actions = sorted(corporate_actions, key=lambda x: x["action_date"])

    for action in sorted_actions:
        a_date = action["action_date"]
        split_factor = float(action.get("split_factor", 1.0))
        div_amount = float(action.get("dividend_amount", 0.0))

        # Bolunme / Bedelsiz duzeltmesi
        if split_factor > 1.0:
            for r in adjusted:
                if r["date"] < a_date:
                    r["adj_open"] = round(r["adj_open"] / split_factor, 4)
                    r["adj_high"] = round(r["adj_high"] / split_factor, 4)
                    r["adj_low"] = round(r["adj_low"] / split_factor, 4)
                    r["adj_close"] = round(r["adj_close"] / split_factor, 4)
                    r["adj_volume"] = round(r["adj_volume"] * split_factor, 1)
                    r["adjustment_factor"] = round(r["adj_close"] / r["raw_close"], 6) if r["raw_close"] else 1.0

        # Temettu duzeltmesi
        if div_amount > 0.0:
            # Aksiyon gununden hemen onceki kapanis
            prior_rows = [r for r in adjusted if r["date"] < a_date]
            if prior_rows:
                p_cum = prior_rows[-1]["adj_close"]
                if p_cum > div_amount:
                    div_factor = (p_cum - div_amount) / p_cum
                    for r in prior_rows:
                        r["adj_open"] = round(r["adj_open"] * div_factor, 4)
                        r["adj_high"] = round(r["adj_high"] * div_factor, 4)
                        r["adj_low"] = round(r["adj_low"] * div_factor, 4)
                        r["adj_close"] = round(r["adj_close"] * div_factor, 4)
                        r["adjustment_factor"] = round(r["adj_close"] / r["raw_close"], 6) if r["raw_close"] else 1.0

    return adjusted


def save_adjusted_prices(adjusted_rows: list[dict]) -> None:
    """Duzeltilmis fiyat serilerini adjusted_prices tablosuna yazar."""
    if not adjusted_rows:
        return
    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO adjusted_prices
               (date, ticker, adj_open, adj_high, adj_low, adj_close, adj_volume, adjustment_factor, raw_close)
               VALUES (:date, :ticker, :adj_open, :adj_high, :adj_low, :adj_close, :adj_volume, :adjustment_factor, :raw_close)
               ON CONFLICT(date, ticker) DO UPDATE SET
                 adj_open=excluded.adj_open,
                 adj_high=excluded.adj_high,
                 adj_low=excluded.adj_low,
                 adj_close=excluded.adj_close,
                 adj_volume=excluded.adj_volume,
                 adjustment_factor=excluded.adjustment_factor,
                 raw_close=excluded.raw_close""",
            adjusted_rows,
        )
        conn.commit()
    finally:
        conn.close()


# =====================================================================
# 3. DATA QUALITY AUDITOR
# =====================================================================

@dataclass
class SuspiciousJump:
    date: str
    return_pct: float
    prev_close: float
    close: float
    explained_by_action: bool
    details: str


@dataclass
class DataQualityReport:
    ticker: str
    as_of_date: str
    total_bars: int
    date_range: tuple[str, str] | None
    quality_score: float  # 0 to 100
    is_clean: bool
    missing_days_count: int
    suspicious_jumps_count: int
    zero_volume_count: int
    stale_price_streaks_count: int
    delist_status: str  # 'active', 'delisted', 'suspended'
    issues: list[str]
    corporate_actions_applied: list[dict]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_ticker_data_quality(
    ticker: str,
    price_rows: list[dict],
    as_of_date: str | None = None,
    corporate_actions: list[dict] | None = None,
) -> DataQualityReport:
    """Bir hissenin fiyat serisini veri kalitesi ve anomali acisindan denetler."""
    ticker = ticker.upper()
    if as_of_date is None and price_rows:
        as_of_date = max(r["date"] for r in price_rows)
    elif as_of_date is None:
        as_of_date = date.today().isoformat()

    issues: list[str] = []
    suspicious_jumps: list[SuspiciousJump] = []
    zero_volume_days = 0
    zero_vol_streak = 0
    max_zero_vol_streak = 0
    stale_streak = 0
    max_stale_streak = 0
    missing_days_count = 0
    invalid_bar_count = 0

    if not price_rows:
        delist_info = get_delist_info(ticker)
        delist_status = "delisted" if delist_info else "no_data"
        issues.append(f"Hisse {ticker} icin hic fiyat verisi bulunamadi.")
        return DataQualityReport(
            ticker=ticker,
            as_of_date=as_of_date,
            total_bars=0,
            date_range=None,
            quality_score=0.0,
            is_clean=False,
            missing_days_count=0,
            suspicious_jumps_count=0,
            zero_volume_count=0,
            stale_price_streaks_count=0,
            delist_status=delist_status,
            issues=issues,
            corporate_actions_applied=[],
        )

    # Kronolojik sirala
    sorted_rows = sorted(price_rows, key=lambda x: x["date"])
    date_range = (sorted_rows[0]["date"], sorted_rows[-1]["date"])

    # Delist kontrolu
    delist_info = get_delist_info(ticker)
    if delist_info:
        if delist_info["delist_date"] <= as_of_date:
            delist_status = "delisted"
            issues.append(
                f"Hisse {delist_info['delist_date']} tarihinde kottan cikarildi "
                f"({delist_info['delist_reason']}). Kurtarma orani: %{delist_info['terminal_recovery_pct']}."
            )
        else:
            delist_status = "active_pre_delist"
    else:
        delist_status = "active"

    # Kurumsal aksiyonlar
    actions = corporate_actions if corporate_actions is not None else fetch_corporate_actions(ticker, as_of_date)
    action_dates = {a["action_date"] for a in actions}

    # Fiyat serisi denetimi
    for i, r in enumerate(sorted_rows):
        o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
        v = float(r.get("volume", 0.0) or 0.0)
        curr_date = r["date"]

        # 1. Sanity Kontrolleri (Negative / Inverted prices)
        bar_invalid = False
        if c <= 0 or o <= 0 or h <= 0 or l <= 0:
            issues.append(f"{curr_date}: Gecersiz sifir veya negatif fiyat (O:{o}, H:{h}, L:{l}, C:{c}).")
            bar_invalid = True
        if h < l:
            issues.append(f"{curr_date}: High ({h}) Low'dan ({l}) kucuk.")
            bar_invalid = True
        if c > h or c < l:
            issues.append(f"{curr_date}: Close ({c}) [Low, High] araligi disinda.")
            bar_invalid = True
        if bar_invalid:
            invalid_bar_count += 1

        # 2. Sifir Hacim
        if v == 0.0:
            zero_volume_days += 1
            zero_vol_streak += 1
            max_zero_vol_streak = max(max_zero_vol_streak, zero_vol_streak)
        else:
            zero_vol_streak = 0

        # 3. Durgun / Flat Fiyatlar (H == L == C)
        if h == l == c and i > 0 and c == float(sorted_rows[i - 1]["close"]):
            stale_streak += 1
            max_stale_streak = max(max_stale_streak, stale_streak)
        else:
            stale_streak = 0

        # 4. Fiyat Sicramasi / Circuit Breaker Denetimi
        if i > 0:
            prev_close = float(sorted_rows[i - 1]["close"])
            if prev_close > 0:
                ret_pct = (c / prev_close - 1.0) * 100.0
                # BIST marj tavan/taban degeri genel olarak %10'dur (tolerans %10.5)
                if abs(ret_pct) > 10.5:
                    explained = curr_date in action_dates
                    details = "Kurumsal aksiyon (bedelsiz/temettu) ile aciklandi." if explained else "BIST marj disi supheli sicrama!"
                    suspicious_jumps.append(
                        SuspiciousJump(
                            date=curr_date,
                            return_pct=round(ret_pct, 2),
                            prev_close=prev_close,
                            close=c,
                            explained_by_action=explained,
                            details=details,
                        )
                    )
                    if not explained:
                        issues.append(f"{curr_date}: %{ret_pct:.1f} oraninda aciklanamayan sert fiyat sicramasi.")

            # 5. Eksik Islem Gunleri (Takvim boslugu)
            d_prev = datetime.strptime(sorted_rows[i - 1]["date"], "%Y-%m-%d").date()
            d_curr = datetime.strptime(curr_date, "%Y-%m-%d").date()
            gap_days = (d_curr - d_prev).days
            # Hafta sonu haric 4 gunu asan bosluklar (bayram tatili harici supheli)
            if gap_days > 4:
                missing_days_count += (gap_days - 3)

    if max_zero_vol_streak >= 3:
        issues.append(f"{max_zero_vol_streak} gun art arda 0 hacim tespit edildi (likidite/tahta kapali riski).")
    if max_stale_streak >= 5:
        issues.append(f"{max_stale_streak} gun art arda degismeyen sabit fiyat (tahta askida).")
    if missing_days_count > 10:
        issues.append(f"Toplam {missing_days_count} gunluk takvim eksigi tespit edildi.")

    # Skorlama (100 uzerinden)
    score = 100.0
    unexplained_jumps = [j for j in suspicious_jumps if not j.explained_by_action]
    score -= len(unexplained_jumps) * 15.0
    score -= min(40.0, invalid_bar_count * 20.0)
    if max_zero_vol_streak >= 3:
        score -= min(30.0, max_zero_vol_streak * 5.0)
    if max_stale_streak >= 5:
        score -= min(25.0, max_stale_streak * 4.0)
    if missing_days_count > 0:
        score -= min(20.0, missing_days_count * 1.0)
    if delist_status == "delisted":
        score -= 20.0

    quality_score = max(0.0, min(100.0, round(score, 1)))
    is_clean = (quality_score >= 75.0) and (len(unexplained_jumps) == 0) and (invalid_bar_count == 0)

    report = DataQualityReport(
        ticker=ticker,
        as_of_date=as_of_date,
        total_bars=len(sorted_rows),
        date_range=date_range,
        quality_score=quality_score,
        is_clean=is_clean,
        missing_days_count=missing_days_count,
        suspicious_jumps_count=len(suspicious_jumps),
        zero_volume_count=zero_volume_days,
        stale_price_streaks_count=max_stale_streak,
        delist_status=delist_status,
        issues=issues,
        corporate_actions_applied=actions,
    )

    # Raporu DB'ye kaydet
    _save_data_quality_report(report)

    return report


def _save_data_quality_report(rep: DataQualityReport) -> None:
    """Veri kalitesi raporunu DB'ye yazar."""
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO data_quality_reports
               (as_of_date, ticker, quality_score, is_clean, total_bars, missing_days_count,
                suspicious_jumps_count, zero_volume_count, delist_status, issues_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(as_of_date, ticker) DO UPDATE SET
                 quality_score=excluded.quality_score,
                 is_clean=excluded.is_clean,
                 total_bars=excluded.total_bars,
                 missing_days_count=excluded.missing_days_count,
                 suspicious_jumps_count=excluded.suspicious_jumps_count,
                 zero_volume_count=excluded.zero_volume_count,
                 delist_status=excluded.delist_status,
                 issues_json=excluded.issues_json,
                 created_at=excluded.created_at""",
            (
                rep.as_of_date,
                rep.ticker,
                rep.quality_score,
                1 if rep.is_clean else 0,
                rep.total_bars,
                rep.missing_days_count,
                rep.suspicious_jumps_count,
                rep.zero_volume_count,
                rep.delist_status,
                json.dumps(rep.issues, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_data_quality_report(ticker: str, as_of_date: str) -> dict | None:
    """Kayitli veri kalitesi raporunu sorgular."""
    rows = db.query(
        "SELECT * FROM data_quality_reports WHERE as_of_date = ? AND ticker = ?",
        (as_of_date, ticker.upper()),
    )
    if rows:
        res = dict(rows[0])
        res["issues"] = json.loads(res.get("issues_json") or "[]")
        return res
    return None
