"""Aylik rotasyon listesi: AL / TUT / SAT (docs/research/exit_rules_preregistration.md).

On-kayitli satis testinde hicbir tampon, stop veya tez bozulmasi kurali gecmedi;
gecerli kural R0: uzun vade evreninde degerleme z'sine (value_sn) gore ust %20
tutulur, ust %20'den cikan satilir. Ay basina bir dengeleme yapilir: ayin ilk
kosusu listeyi kaydeder, ayni ay icindeki sonraki kosular ayni listeyi gosterir.

Evren: degerleme z'si hesaplanabilen uzun vade adaylari (karantina ve akran
yetersizligi haric). Finansal sirketler (banka, sigorta, faktoring, leasing,
araci kurum, MKYO...) haric: test edilen panel bunlari icermiyordu
(core/pit_panel.FINANCIAL_SECTORS); bilancolari satis/FAVOK tasimiyor. Hedef fiyat, hurdle ve Piotroski kapilari bu listeyi
ETKILEMEZ: test edilen kural bu kapilari icermiyordu.

Likidite: test edilen panel her ay 60 gunluk medyan TL hacmine gore en az likit
%30'u atiyordu (core/factor_backtest.prepare, liq_drop_pct=0.3). Canli evrenin
10M TL tabani bundan gevsek; 2026-10-10 kosusunda ust %20'nin ~1/3'u test
edilmemis likidite diliminden geliyordu. Ayni kesim burada da uygulanir; 60g
medyani hesaplanamayan (<40 bar) hisse, panelde oldugu gibi disarida kalir.
"""
from __future__ import annotations

from bisect import bisect_right
from statistics import median

from core import db, forward_record
from core.ranking import value_sn_ratios
from core.pit_panel import FINANCIAL_SECTORS

TOP_PCT = 0.20
LIQ_DROP_PCT = 0.30      # core/factor_backtest.prepare ile ayni
LIQ_WINDOW, LIQ_MIN_BARS = 60, 40  # core/pit_panel: rolling(60, min_periods=40).median()
SMALL_THIRD = 100 / 3    # bilgi notu: havuzun alt ucte birlik piyasa degeri / likidite dilimi
# docs/research/portfolio_backtest_preregistration.md (PR #43), 1M TL, base maliyet:
# kucuk/az likit hisseleri cikaran filtrelerin olculen getiri maliyeti (yillik %).
F1_SMALL_CAP_COST_PCT = 8.83   # kesif, piyasa degeri alt %30 haric
F2_LIQUIDITY_COST_PCT = 3.75   # holdout, likidite kesimi %50


def tl_volume_median_60(bars: list[dict]) -> float | None:
    """Son 60 bardaki gunluk TL hacminin (kapanis x adet) medyani; panelin tlvol60 tanimi."""
    vals = [b["close"] * b["volume"] for b in bars[-LIQ_WINDOW:]
            if b.get("close") and b.get("volume") is not None]
    return median(vals) if len(vals) >= LIQ_MIN_BARS else None


def is_financial(candidate: dict) -> bool:
    return candidate.get("sector") in FINANCIAL_SECTORS


def _eligible(candidates: list[dict], financial: bool = False) -> list[dict]:
    return [c for c in candidates
            if c.get("bucket") == "long_term"
            and is_financial(c) == financial
            and c.get("candidate_state") != "QUARANTINE"
            and c.get("confidence") != "insufficient_peers"
            and c.get("valuation_z") is not None]


def _liquidity_cut(candidates: list[dict]) -> tuple[dict[str, float], float | None]:
    """Finansal olmayan uzun vade adaylarinin 60g medyan TL hacmi ve alt %30 kesim degeri."""
    liq = {c["ticker"]: c["tl_vol_med60"] for c in candidates
           if c.get("bucket") == "long_term" and not is_financial(c)
           and c.get("tl_vol_med60") is not None and c["tl_vol_med60"] > 0}
    if not liq:
        return liq, None
    vals = sorted(liq.values())
    # pandas Series.quantile (lineer) ile ayni kesim
    pos = LIQ_DROP_PCT * (len(vals) - 1)
    lo = int(pos)
    return liq, vals[lo] + (vals[min(lo + 1, len(vals) - 1)] - vals[lo]) * (pos - lo)


def _liquid_tickers(candidates: list[dict]) -> set[str]:
    """Finansal olmayan uzun vade adaylari icinde 60g medyan TL hacmine gore alt %30'u atar."""
    liq, cut = _liquidity_cut(candidates)
    return {t for t, v in liq.items() if v >= cut} if cut is not None else set()


def _percentiles(values: dict[str, float]) -> dict[str, float]:
    """Her degerin havuzdaki yuzdeligi (0-100, kendisi dahil <= olanlarin payi)."""
    vals = sorted(values.values())
    return {t: round(100 * bisect_right(vals, v) / len(vals), 1) for t, v in values.items()}


def ranking_pool(candidates: list[dict]) -> list[dict]:
    """Siralanan evren: finansal olmayan, uygun, likidite kesimini gecen adaylar (z'ye gore azalan)."""
    liquid = _liquid_tickers(candidates)
    return sorted((c for c in _eligible(candidates) if c["ticker"] in liquid), key=lambda c: -c["valuation_z"])


def select_top(candidates: list[dict]) -> list[dict]:
    pool = ranking_pool(candidates)
    if not pool:
        return []
    # Bilgi: secilen hissenin piyasa degeri ve likiditesi, finansal olmayan uzun vade
    # adaylari icinde kacinci yuzdelikte (karari ETKILEMEZ; F1/F2 filtreleri testte gecmedi).
    base = [c for c in candidates if c.get("bucket") == "long_term" and not is_financial(c)]
    mcap_pct = _percentiles({c["ticker"]: c["market_cap"] for c in base if c.get("market_cap")})
    liq_pct = _percentiles({c["ticker"]: c["tl_vol_med60"] for c in base if c.get("tl_vol_med60")})
    n_top = max(1, round(len(pool) * TOP_PCT))
    return [{"ticker": c["ticker"], "valuation_z": c["valuation_z"],
             "rank_pct": round((i + 1) / len(pool), 4),
             "market_cap": c.get("market_cap"), "mcap_pct": mcap_pct.get(c["ticker"]),
             "liq_pct": liq_pct.get(c["ticker"])} for i, c in enumerate(pool[:n_top])]


def small_or_illiquid(holdings: list[dict]) -> dict:
    """Piyasa degeri veya likiditesi havuzun alt ucte birinde olan tutulan hisseler (bilgi)."""
    names = [{"ticker": h["ticker"], "market_cap_mn": round(h["market_cap"] / 1e6),
              "mcap_pct": h["mcap_pct"], "liq_pct": h["liq_pct"]}
             for h in holdings
             if h.get("market_cap") and h.get("mcap_pct") is not None and h.get("liq_pct") is not None
             and (h["mcap_pct"] < SMALL_THIRD or h["liq_pct"] < SMALL_THIRD)]
    return {"names": sorted(names, key=lambda n: n["market_cap_mn"]), "n": len(names),
            "n_holdings": len(holdings),
            "f1_cost_pct": F1_SMALL_CAP_COST_PCT, "f2_cost_pct": F2_LIQUIDITY_COST_PCT}


def untested_financials(candidates: list[dict]) -> list[dict]:
    """Finansallar icinde degerleme z'sine gore ust %20: YALNIZCA bilgi amacli.
    Bu kural finansallarda test edilmedi; AL/TUT listesine girmez."""
    pool = sorted(_eligible(candidates, financial=True), key=lambda c: -c["valuation_z"])
    if not pool:
        return []
    n_top = max(1, round(len(pool) * TOP_PCT))
    return [{"ticker": c["ticker"], "sector": c.get("sector")} for c in pool[:n_top]]


def decision_details(candidates: list[dict], health: dict | None = None) -> dict:
    """Ileriye donuk kayit icin karar anindaki durum: tum siralama evreni (oranlar,
    likidite, fiyat ve finansal tablo tarihleri), evren sayimlari ve veri sagligi."""
    pool = ranking_pool(candidates)
    _, cut = _liquidity_cut(candidates)
    ranking = []
    for i, c in enumerate(pool):
        fnd = c.get("_raw_fundamentals") or {}
        vi = c.get("value_inputs") or {}
        ranking.append({
            "rank": i + 1, "ticker": c["ticker"], "valuation_z": c["valuation_z"],
            "valid_metric_count": c.get("valid_metric_count"), **value_sn_ratios(c),
            "tl_vol_med60": c.get("tl_vol_med60"), "market_cap": c.get("market_cap"),
            "close": c.get("current_price"), "price_date": c.get("price_date"),
            # Kullanilan ceyrek ve ONUN KAP yayini (value_inputs); value_inputs yoksa (mock) bos
            "statement_period": vi.get("stmt_period"), "statement_period_end": vi.get("stmt_period_end"),
            "kap_published_at": vi.get("kap_published_at"), "kap_available_at": vi.get("kap_available_at"),
            "value_source": vi.get("source"), "ttm_unit": vi.get("ttm_unit"), "observed_at": vi.get("observed_at"),
            "inputs": vi.get("inputs"),
            # Temel veri katmaninin kendi donemi (hard filter'in point_in_time kontrolu)
            "fundamentals_period_end": fnd.get("period_end"), "fundamentals_pit_source": fnd.get("pit_source"),
        })
    long_term = [c for c in candidates if c.get("bucket") == "long_term" and not is_financial(c)]
    price_dates = [r["price_date"] for r in ranking if r["price_date"]]
    return {
        "ranking": ranking,
        "counts": {"long_term_nonfinancial": len(long_term), "eligible": len(_eligible(candidates)),
                   "pool": len(pool)},
        "liq_cut_tl": cut,
        "price_date_max": max(price_dates, default=None),
        "price_date_min": min(price_dates, default=None),
        "health": ({"status": health.get("status"), "issues": health.get("issues"),
                    "config_hash": health.get("config_hash")} if health else None),
    }


def holding_checks(candidates: list[dict], holdings: list[dict]) -> list[dict]:
    """Tutulan her hisse icin tek hisse kontrol satiri (plan_2026-10-21 P2-4). YALNIZCA
    bilgi: sepet kuralinin kaniti tek hisseye tasinmaz; esikler test edilmedi."""
    by_ticker = {c["ticker"]: c for c in candidates}
    rows = []
    for h in holdings:
        c = by_ticker.get(h["ticker"], {})
        vi = c.get("value_inputs") or {}
        rows.append({
            "ticker": h["ticker"], "sector": c.get("sector"),
            "statement_period": vi.get("stmt_period"), "kap_published_at": vi.get("kap_published_at"),
            "price_date": c.get("price_date"), "valid_metric_count": c.get("valid_metric_count"),
            "loss_flag": c.get("loss_flag"), "sloan_flag": c.get("sloan_flag"), "fcf_yield": c.get("fcf_yield"),
            "net_debt_ebitda": c.get("net_debt_ebitda"), "distress_flag": c.get("distress_flag"),
            "piotroski_normalized_score": c.get("piotroski_normalized_score"),
            "value_trap_risk": c.get("value_trap_risk"),
            "drawdown_from_5y_peak_pct": c.get("drawdown_from_5y_peak_pct"),
            "max_drawdown_5y_pct": c.get("max_drawdown_5y_pct"), "volatility_60d": c.get("volatility_60d"),
            "risk_flags": c.get("risk_flags") or [], "unknown_checks": c.get("unknown_checks") or [],
            "in_today_candidates": bool(c),
        })
    return rows


def _holdings(rebalance_date: str) -> list[dict]:
    rows = db.query("SELECT ticker, valuation_z, rank_pct, market_cap, mcap_pct, liq_pct "
                    "FROM rotation_holdings WHERE rebalance_date=? "
                    "ORDER BY rank_pct", (rebalance_date,))
    return [dict(r) for r in rows]


def monthly_rotation(as_of_date: str, candidates: list[dict], health: dict | None = None) -> dict:
    month = as_of_date[:7]
    rows = db.query("SELECT DISTINCT rebalance_date FROM rotation_holdings WHERE rebalance_date <= ? "
                    "ORDER BY rebalance_date DESC LIMIT 2", (as_of_date,))
    dates = [r["rebalance_date"] for r in rows]
    if dates and dates[0][:7] == month:
        current_date, prev_date = dates[0], (dates[1] if len(dates) > 1 else None)
        current = _holdings(current_date)
    else:
        current = select_top(candidates)
        current_date, prev_date = as_of_date, (dates[0] if dates else None)
        details = decision_details(candidates, health)
        if current:
            forward_record.append_decision(as_of_date, [h["ticker"] for h in current],
                                           [r["ticker"] for r in details["ranking"]], details=details)
            db.executemany(
                "INSERT OR REPLACE INTO rotation_holdings (rebalance_date, ticker, valuation_z, rank_pct, "
                "market_cap, mcap_pct, liq_pct) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(as_of_date, h["ticker"], h["valuation_z"], h["rank_pct"], h.get("market_cap"),
                  h.get("mcap_pct"), h.get("liq_pct")) for h in current])
        else:
            forward_record.append_no_decision(as_of_date, "empty_pool", details=details)
    prev = {h["ticker"] for h in _holdings(prev_date)} if prev_date else set()
    cur = {h["ticker"] for h in current}
    return {
        "rebalance_date": current_date,
        "previous_rebalance_date": prev_date,
        "buy": [h for h in current if h["ticker"] not in prev],
        "hold": [h for h in current if h["ticker"] in prev],
        "sell": sorted(prev - cur),
        "n_holdings": len(current),
        "top_pct": TOP_PCT * 100,
        "untested_financials": untested_financials(candidates),
        "size_liquidity": small_or_illiquid(current),
        "checks": holding_checks(candidates, current),
    }
