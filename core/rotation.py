"""Aylik rotasyon listesi: AL / TUT / SAT (docs/research/exit_rules_preregistration.md).

On-kayitli satis testinde hicbir tampon, stop veya tez bozulmasi kurali gecmedi;
gecerli kural R0: uzun vade evreninde degerleme z'sine (value_sn) gore ust %20
tutulur, ust %20'den cikan satilir. Ay basina bir dengeleme yapilir: ayin ilk
kosusu listeyi kaydeder, ayni ay icindeki sonraki kosular ayni listeyi gosterir.

Evren: degerleme z'si hesaplanabilen uzun vade adaylari (karantina ve akran
yetersizligi haric). Hedef fiyat, hurdle ve Piotroski kapilari bu listeyi
ETKILEMEZ: test edilen kural bu kapilari icermiyordu.
"""
from __future__ import annotations

from core import db

TOP_PCT = 0.20


def _eligible(candidates: list[dict]) -> list[dict]:
    return [c for c in candidates
            if c.get("bucket") == "long_term"
            and c.get("candidate_state") != "QUARANTINE"
            and c.get("confidence") != "insufficient_peers"
            and c.get("valuation_z") is not None]


def select_top(candidates: list[dict]) -> list[dict]:
    pool = sorted(_eligible(candidates), key=lambda c: -c["valuation_z"])
    if not pool:
        return []
    n_top = max(1, round(len(pool) * TOP_PCT))
    return [{"ticker": c["ticker"], "valuation_z": c["valuation_z"],
             "rank_pct": round((i + 1) / len(pool), 4)} for i, c in enumerate(pool[:n_top])]


def _holdings(rebalance_date: str) -> list[dict]:
    rows = db.query("SELECT ticker, valuation_z, rank_pct FROM rotation_holdings WHERE rebalance_date=? "
                    "ORDER BY rank_pct", (rebalance_date,))
    return [dict(r) for r in rows]


def monthly_rotation(as_of_date: str, candidates: list[dict]) -> dict:
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
        if current:
            db.executemany(
                "INSERT OR REPLACE INTO rotation_holdings (rebalance_date, ticker, valuation_z, rank_pct) "
                "VALUES (?, ?, ?, ?)",
                [(as_of_date, h["ticker"], h["valuation_z"], h["rank_pct"]) for h in current])
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
    }
