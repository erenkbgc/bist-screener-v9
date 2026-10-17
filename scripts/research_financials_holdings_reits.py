#!/usr/bin/env python3
"""Sektore ozel degerleme modelleri: Bankalar/Finansallar, Holdingler ve GYO'lar
(docs/research/financials_holdings_reits_preregistration.md).

Bolumler:
  - S1: Bankalar (13 hisse, UFRS) ve Tum Finansallar (52 hisse, UFRS/UFRS_K/UFRS_B/XI_29/XI_29K)
        icin B0_bm, B1_bm_roe ve B2_pb_roe_resid modelleri.
  - S2: Holdingler (52 hisse) icin H0_value_sn, H1_bm_ep_roe ve H2_backing_nav modelleri.
  - S3: GYO'lar (62 hisse) icin G0_value_sn, G1_nav_ffo ve G2_letdin_sirmans_resid modelleri.
  - S4: Maliyetli portfoy simulasyonu (1M TL, baz maliyet, ertesi gun kapanisi):
        P0 (mevcut R0), P1 (Holding=H1, GYO=G1) ve P2 (Finansal dilim dahil) vs EW net ve BIST 100 TR.

    python scripts/research_financials_holdings_reits.py
"""
from __future__ import annotations

import json
import pickle
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import factor_backtest as fb  # noqa: E402
from core import pit_panel  # noqa: E402
from core import portfolio_backtest as pb  # noqa: E402
from diagnose_crashed_picks import month_end  # noqa: E402
from research_long_term import load as load_nonfin_c1  # noqa: E402
from research_portfolio_backtest import (  # noqa: E402
    CAPITAL_REF,
    RESEARCH,
    SPLIT,
    TOP,
    attach_benchmarks,
    daily_frame,
    stats,
)

RAW_NONFIN = RESEARCH / "raw"
RAW_FIN = RESEARCH / "raw_fin"
FIN_RAW_VERSION = 1

FIN_BS_ITEMS = {
    "total_assets": ("TOPLAM VARLIKLAR", "AKTİF TOPLAMI"),
    "equity_parent": ("Ana Ortaklığa Ait Özkaynaklar",),
    "equity": ("Özkaynaklar", "XVI. ÖZKAYNAKLAR", "ÖZKAYNAK", "Özsermaye Toplamı"),
    "paid_in": (
        "Ödenmiş Sermaye",
        "16.1 Ödenmiş Sermaye",
        "14.1 Ödenmiş Sermaye",
        "13.1 Ödenmiş Sermaye",
        "A- Ödenmiş Sermaye",
        "1- (Nominal) Sermaye",
    ),
    "cash": ("Nakit ve Nakit Benzerleri", "I. NAKİT DEĞERLER VE MERKEZ BANKASI"),
    "fin_debt": ("Finansal Borçlar", "III. ALINAN KREDİLER"),
}
FIN_INC_ITEMS = {
    "revenue": (
        "Satış Gelirleri",
        "VIII. FAALİYET GELİRLERİ/GİDERLERİ TOPLAMI (III+IV+V+VI+VII)",
    ),
    "gross_profit": ("BRÜT KAR (ZARAR)", "III. NET FAİZ GELİRİ/GİDERİ (I - II)", "III. NET KAR PAYI GELİRİ/GİDERİ (I-II)"),
    "op_profit": (
        "FAALİYET KARI (ZARARI)",
        "Net Faaliyet Kar/Zararı",
        "XI. NET FAALİYET KARI/ZARARI (VIII-IX-X)",
    ),
    "ni_parent": ("Ana Ortaklık Payları", "23.1 Grubun Karı/Zararı"),
    "net_income": (
        "DÖNEM KARI (ZARARI)",
        "XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)",
        "XVIII. NET DÖNEM KARI/ZARARI (XVII+XXII)",
        "NET DÖNEM KARI (ZARARI)",
        "N- Dönem Net Karı veya Zararı",
        "3- Dönem Net Kar veya Zararı",
        "16.4.2 Dönem Net Kar/Zararı",
        "14.4.2 Dönem Net Kar/Zararı",
        "13.4.2 Dönem Net Kâr veya Zararı",
        "F-Dönem Net Karı",
    ),
}

EXTRA_BS_ITEMS = {
    "inv_property": ("Yatırım Amaçlı Gayrimenkuller",),
    "inventories": ("Stoklar",),
    "fin_investments": ("Finansal Yatırımlar",),
    "eq_investments": ("Özkaynak Yöntemiyle Değerlenen Yatırımlar",),
    "intangibles": ("Maddi Olmayan Duran Varlıklar",),
    "goodwill": ("Şerefiye",),
    "fin_sector_liab": ("Finans Sektörü Faaliyetlerinden Borçlar",),
}
EXTRA_SUM_DUPES = {"inventories", "fin_investments", "fin_sector_liab"}

SECTOR_TEMPLATE_ORDER = {
    "Bankacılık": ("UFRS", "UFRS_K"),
    "Sigorta": ("UFRS", "UFRS_K"),
    "Emeklilik": ("UFRS", "UFRS_K"),
    "Varlık Yönetimi": ("UFRS_B", "UFRS", "XI_29"),
    "Faktoring": ("XI_29K", "XI_29", "UFRS"),
    "Finansal Kiralama": ("XI_29K", "XI_29", "UFRS"),
    "Tasarruf Finansman": ("XI_29K", "XI_29", "UFRS"),
    "Aracı Kurum": ("XI_29", "XI_29K", "UFRS"),
    "Menkul Kıymet Yat. Ort.": ("XI_29", "XI_29K", "UFRS"),
}


def nw(s: pd.Series, lags: int = 6, scale: float = 1200.0) -> dict:
    m, t, n = fb.newey_west_t(s, lags)
    return {
        "ann_pct": round(scale * m, 2) if np.isfinite(m) else None,
        "raw_mean": round(float(m), 4) if np.isfinite(m) else None,
        "t": round(float(t), 2) if np.isfinite(t) else None,
        "months": int(n),
    }


def cross_sectional_residual(df: pd.DataFrame, y_col: str, x_cols: list[str],
                             group_col: str | None = None, min_n: int = 6) -> pd.Series:
    """Her ay (ve varsa sektor grubu) icinde y_col ~ 1 + x_cols EKK artigini (e_i) dondurur."""
    out = pd.Series(np.nan, index=df.index, dtype=float)
    keys = ["date", group_col] if group_col else ["date"]
    for _, g in df.groupby(keys):
        sub = g[[y_col, *x_cols]].dropna()
        if len(sub) < max(min_n, len(x_cols) + 2):
            continue
        y = sub[y_col].to_numpy(dtype=float)
        X = np.column_stack([np.ones(len(sub)), sub[x_cols].to_numpy(dtype=float)])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        out.loc[sub.index] = fb.winsorize_z(pd.Series(resid, index=sub.index))
    return out


def fetch_financial_table_any(ticker: str, sector: str, last_n: int = 60) -> pd.DataFrame | None:
    """Is Yatirim'dan finansal kurulusun tum satirlarini (statement_type=None) ceker."""
    from borsapy._providers.isyatirim import get_isyatirim_provider

    prov = get_isyatirim_provider()
    periods = prov._get_periods(datetime.now().year, True, count=last_n)
    step = prov._MAX_PERIODS_PER_CALL
    groups = SECTOR_TEMPLATE_ORDER.get(sector, ("UFRS", "XI_29", "XI_29K", "UFRS_B", "UFRS_K"))
    for grp in groups:
        batches = []
        for i in range(0, len(periods), step):
            try:
                b = prov._fetch_financial_table(
                    symbol=ticker,
                    financial_group=grp,
                    periods=periods[i:i + step],
                    quarterly=True,
                    statement_type=None,
                )
                if b is not None and not b.empty:
                    batches.append(b)
            except Exception:  # noqa: BLE001
                continue
        df = pit_panel.merge_statement_batches(batches)
        if not df.empty:
            return df[sorted(df.columns, key=prov._period_sort_key, reverse=True)]
    return None


def fin_statements_long(ticker: str, tbl: pd.DataFrame | None) -> pd.DataFrame:
    """Finansal kurulus birlesik tablosundan (ticker, period, item, value) uretir."""
    if tbl is None or tbl.empty:
        return pd.DataFrame()
    out = []
    for items in (FIN_BS_ITEMS, FIN_INC_ITEMS):
        for item, labels in items.items():
            s = pit_panel._pick(tbl, labels, item in pit_panel.SUM_DUPLICATES)
            if s is None:
                continue
            for period, v in s.items():
                if v is not None and np.isfinite(v):
                    out.append({"ticker": ticker, "period": str(period), "item": item, "value": float(v)})
    return pd.DataFrame(out)


def fetch_fin_raw(ticker: str, sector: str, refresh: bool = False) -> dict:
    RAW_FIN.mkdir(parents=True, exist_ok=True)
    path = RAW_FIN / f"{ticker}.pkl"
    cached = pickle.loads(path.read_bytes()) if path.exists() and not refresh else None
    if (cached is not None and cached.get("version") == FIN_RAW_VERSION
            and (cached.get("tbl") is None or (cached.get("px_raw") is not None and cached.get("px_adj") is not None))):
        return cached
    import borsapy as bp

    t = bp.Ticker(ticker)

    def safe(fn, **kw):
        for _ in range(2):
            try:
                res = fn(**kw)
                if res is not None:
                    return res
            except Exception:  # noqa: BLE001
                continue
        return None

    raw = cached or {"sector": sector, "version": FIN_RAW_VERSION}
    if raw.get("px_raw") is None:
        raw["px_raw"] = safe(t.history, period="max", adjust=False)
    if raw.get("px_adj") is None:
        raw["px_adj"] = safe(t.history, period="max", adjust=True)
    if "splits" not in raw or raw.get("splits") is None:
        raw["splits"] = safe(lambda: t.splits)
    if raw.get("tbl") is None or refresh:
        raw["tbl"] = fetch_financial_table_any(ticker, sector, last_n=60)
    raw["version"] = FIN_RAW_VERSION
    path.write_bytes(pickle.dumps(raw))
    return raw


def build_financials_panel(sectors: dict[str, str], refresh: bool = False) -> pd.DataFrame:
    """53 finansal hisse icin nokta-zamanli C1 aylik faktor panelini kurar/yukler."""
    cache_pq = RESEARCH / "financials_factors_monthly.parquet"
    if cache_pq.exists() and not refresh:
        df = pd.read_parquet(cache_pq)
        if {"AKBNK", "ALBRK", "GARAN", "ISCTR"}.issubset(set(df["ticker"])):
            df["date"] = month_end(df["date"])
            return df

    fin_tickers = sorted((t, s) for t, s in sectors.items() if s in pit_panel.FINANCIAL_SECTORS)
    longs, pxs, evs = [], [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_fin_raw, tk, sec, refresh): (tk, sec) for tk, sec in fin_tickers}
        for fut in as_completed(futs):
            tk, _ = futs[fut]
            raw = fut.result()
            longs.append(fin_statements_long(tk, raw.get("tbl")))
            pxs.append(pit_panel.monthly_prices(tk, raw.get("px_raw"), raw.get("px_adj")))
            evs.append(pit_panel.split_events(tk, raw.get("splits")))

    long_df = pd.concat([x for x in longs if not x.empty], ignore_index=True)
    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    cpi = pit_panel.cpi_index(macro["cpi_mom"])
    q = pit_panel.quarterly_table(long_df, cpi=cpi)
    archive = RESEARCH / "kap_archive.parquet"
    if archive.exists():
        q = pit_panel.apply_report_dates(q, pit_panel.kap_report_dates(pd.read_parquet(archive)))
    px = pd.concat([x for x in pxs if not x.empty], ignore_index=True)
    ev = pd.concat([x for x in evs if not x.empty], ignore_index=True) if any(not x.empty for x in evs) else pd.DataFrame()
    factors = pit_panel.build_monthly_factors(q, px, ev, sectors)
    factors["date"] = month_end(factors["date"])
    market_m = pit_panel.monthly_market(pd.read_parquet(RESEARCH / "fx.parquet"))
    factors = pit_panel.add_usd_returns(factors, market_m)
    factors.to_parquet(cache_pq, index=False)
    return factors


def extract_holding_reit_balance_sheet(tickers: list[str]) -> pd.DataFrame:
    """Holding ve GYO hisseleri icin raw/*.pkl bilancodan ek varlik kalemlerini cikarir."""
    rows = []
    for tk in tickers:
        p = RAW_NONFIN / f"{tk}.pkl"
        if not p.exists():
            continue
        raw = pickle.loads(p.read_bytes())
        bs = raw.get("bs")
        if bs is None or bs.empty:
            continue
        per_map: dict[str, dict[str, float]] = {}
        for item, labels in {**pit_panel.BS_ITEMS, **EXTRA_BS_ITEMS}.items():
            s = pit_panel._pick(bs, labels, item in (pit_panel.SUM_DUPLICATES | EXTRA_SUM_DUPES))
            if s is None:
                continue
            for period, v in s.items():
                if v is not None and np.isfinite(v):
                    per_map.setdefault(str(period), {})[item] = float(v)
        for period, vals in per_map.items():
            rows.append({"ticker": tk, "stmt_period": period, **vals})
    return pd.DataFrame(rows)


def compute_bank_and_financial_scores(fin_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """S1a (Bankalar, 13 hisse) ve S1b (Tum Finansallar, likit %70) skorlarini uretir."""
    banks = fin_df[fin_df["sector"] == "Bankacılık"].copy()
    for c in ("bm", "ep", "roe"):
        banks[f"{c}_z"] = banks.groupby("date")[c].transform(fb.winsorize_z)
    banks["B0_bm"] = banks["bm_z"]
    banks["B1_bm_roe"] = banks[["bm_z", "ep_z", "roe_z"]].mean(axis=1)
    banks["B2_pb_roe_resid"] = cross_sectional_residual(banks, "bm_z", ["roe_z"], min_n=5)

    all_fin = fb.prepare(fin_df, ["bm", "ep", "roe"], liq_drop_pct=0.30, min_names=10)
    for c in ("bm_z", "ep_z", "roe_z"):
        all_fin[f"{c}_sn"] = fb.sector_neutralize(all_fin, c, min_n=3)
    all_fin["F0_bm_sn"] = all_fin["bm_z_sn"]
    all_fin["F1_bm_roe_sn"] = all_fin[["bm_z_sn", "ep_z_sn", "roe_z_sn"]].mean(axis=1)
    all_fin["F2_pb_roe_resid"] = cross_sectional_residual(all_fin, "bm_z_sn", ["roe_z_sn"], min_n=6)
    return banks, all_fin


def compute_holding_scores(hold_df: pd.DataFrame) -> pd.DataFrame:
    """S2 (Holdingler): H0_value_sn, H1_bm_ep_roe, H2_backing_nav skorlarini uretir."""
    h = hold_df.copy()
    eq = h["equity_parent"].where(h["equity_parent"].notna(), h.get("equity"))
    intang = h.get("intangibles", pd.Series(0.0, index=h.index)).fillna(0.0)
    gw = h.get("goodwill", pd.Series(0.0, index=h.index)).fillna(0.0)
    h["tangible_bm"] = ((eq - intang - gw) / h["mcap"]).where(h["mcap"] > 0)

    cash = h.get("cash", pd.Series(0.0, index=h.index)).fillna(0.0)
    fin_inv = h.get("fin_investments", pd.Series(0.0, index=h.index)).fillna(0.0)
    eq_inv = h.get("eq_investments", pd.Series(0.0, index=h.index)).fillna(0.0)
    fdebt = h.get("fin_debt", pd.Series(0.0, index=h.index)).fillna(0.0)
    h["fin_backing"] = ((cash + fin_inv + eq_inv - fdebt) / h["mcap"]).where(h["mcap"] > 0)

    for col in ("bm", "ep", "sp", "ey", "roe", "tangible_bm", "fin_backing"):
        h[f"{col}_hz"] = h.groupby("date")[col].transform(fb.winsorize_z)
    h["H0_value_sn"] = h[["bm_hz", "ep_hz", "sp_hz", "ey_hz"]].mean(axis=1)
    h["H1_bm_ep_roe"] = h[["bm_hz", "ep_hz", "roe_hz"]].mean(axis=1)
    h["H2_backing_nav"] = h[["tangible_bm_hz", "fin_backing_hz", "ep_hz"]].mean(axis=1)
    return h


def compute_reit_scores(reit_df: pd.DataFrame, q_ext: pd.DataFrame | None = None) -> pd.DataFrame:
    """S3 (GYO'lar): G0_value_sn, G1_nav_ffo, G2_letdin_sirmans_resid skorlarini uretir."""
    g = reit_df.copy()
    if q_ext is not None and "ttm_op_profit" not in g.columns:
        cols = [c for c in ("ticker", "period", "ttm_op_profit", "ttm_ebit") if c in q_ext.columns]
        g = g.merge(q_ext[cols].rename(columns={"period": "stmt_period"}), on=["ticker", "stmt_period"], how="left")

    inv_prop = g.get("inv_property", pd.Series(0.0, index=g.index)).fillna(0.0)
    inv_stok = g.get("inventories", pd.Series(0.0, index=g.index)).fillna(0.0)
    cash = g.get("cash", pd.Series(0.0, index=g.index)).fillna(0.0)
    fdebt = g.get("fin_debt", pd.Series(0.0, index=g.index)).fillna(0.0)
    g["prop_nav"] = ((inv_prop + inv_stok + cash - fdebt) / g["mcap"]).where(g["mcap"] > 0)

    op = g.get("ttm_op_profit")
    if op is None:
        op = g.get("ey") * g["mcap"]
    g["op_ep"] = (op / g["mcap"]).where(g["mcap"] > 0)
    ta = g.get("total_assets")
    g["lev"] = (fdebt / ta).where(ta > 0)

    for col in ("bm", "ep", "sp", "ey", "roe", "prop_nav", "op_ep", "lev", "size"):
        if col in g.columns:
            g[f"{col}_gz"] = g.groupby("date")[col].transform(fb.winsorize_z)
    g["G0_value_sn"] = g[["bm_gz", "ep_gz", "sp_gz", "ey_gz"]].mean(axis=1)
    g["G1_nav_ffo"] = g[["bm_gz", "prop_nav_gz", "op_ep_gz"]].mean(axis=1)
    g["G2_letdin_sirmans_resid"] = cross_sectional_residual(
        g, "bm_gz", ["roe_gz", "lev_gz", "size_gz"], min_n=8
    )
    return g


def evaluate_sector_models(df: pd.DataFrame, cols: list[str], base_col: str,
                           top_pct: float = 0.20, min_names: int = 8) -> dict:
    """Sektor icinde Rank-IC ve ust %20 (veya en az 2 hisse) - Sektor EW aktif getiri analizi."""
    out: dict[str, dict] = {}
    spreads: dict[str, pd.Series] = {}
    ics: dict[str, pd.Series] = {}

    for col in cols:
        ic_rows, sp_rows = [], []
        for dt, g in df[["date", "ticker", col, "fwd_ret_1m"]].dropna().groupby("date"):
            if len(g) < min_names:
                continue
            ic_val = g[col].corr(g["fwd_ret_1m"], method="spearman")
            if np.isfinite(ic_val):
                ic_rows.append((dt, float(ic_val)))
            k = max(2, int(round(len(g) * top_pct)))
            top = g.nlargest(k, col)
            sp_rows.append((dt, float(top["fwd_ret_1m"].mean() - g["fwd_ret_1m"].mean())))
        ics[col] = pd.Series(dict(ic_rows)).sort_index() if ic_rows else pd.Series(dtype=float)
        spreads[col] = pd.Series(dict(sp_rows)).sort_index() if sp_rows else pd.Series(dtype=float)

    for col in cols:
        out[col] = {}
        for wname, wfn in (("full", lambda idx: idx == idx),
                           ("discovery", lambda idx: idx < SPLIT),
                           ("holdout", lambda idx: idx >= SPLIT)):
            sub_ic = ics[col][wfn(ics[col].index)]
            sub_sp = spreads[col][wfn(spreads[col].index)]
            entry = {
                "rank_ic": nw(sub_ic, scale=1.0),
                "top_minus_sector_ew": nw(sub_sp, scale=1200.0),
            }
            if col != base_col and not spreads[base_col].empty:
                d_sp = (spreads[col] - spreads[base_col]).dropna()
                entry["diff_vs_base"] = nw(d_sp[wfn(d_sp.index)], scale=1200.0)
            out[col][wname] = entry
    return out


def load_daily_any(tk: str) -> pd.DataFrame | None:
    """Hem raw/ hem raw_fin/ altindaki gunluk fiyatlari yukler."""
    for folder in (RAW_NONFIN, RAW_FIN):
        p = folder / f"{tk}.pkl"
        if p.exists():
            d = pickle.loads(p.read_bytes())
            df = daily_frame(d.get("px_adj"), d.get("px_raw"))
            if df is not None:
                return df
    return None


def main() -> None:
    sector_rows = json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))
    sectors = {r["ticker"]: r["sektor"] for r in sector_rows}

    # 1. Finansal paneli insa et / yukle (S1)
    fin_df = build_financials_panel(sectors)
    banks_df, all_fin_df = compute_bank_and_financial_scores(fin_df)
    s1_banks = evaluate_sector_models(
        banks_df, ["B0_bm", "B1_bm_roe", "B2_pb_roe_resid"], "B0_bm", top_pct=0.25, min_names=6
    )
    s1_all_fin = evaluate_sector_models(
        all_fin_df, ["F0_bm_sn", "F1_bm_roe_sn", "F2_pb_roe_resid"], "F0_bm_sn", top_pct=0.20, min_names=10
    )

    # 2. Holding (S2) ve GYO (S3) modellerini hesapla
    nonfin_df = load_nonfin_c1()
    hr_tickers = sorted(nonfin_df.loc[nonfin_df["sector"].isin(["Holding", "Gayrimenkul"]), "ticker"].unique())
    extra_bs = extract_holding_reit_balance_sheet(hr_tickers)
    q_ext = pd.read_parquet(RESEARCH / "quarterly_ext.parquet")

    hold_sub = nonfin_df[nonfin_df["sector"] == "Holding"].merge(
        extra_bs, on=["ticker", "stmt_period"], how="left"
    )
    hold_scored = compute_holding_scores(hold_sub)
    s2_holdings = evaluate_sector_models(
        hold_scored, ["H0_value_sn", "H1_bm_ep_roe", "H2_backing_nav"], "H0_value_sn", top_pct=0.20, min_names=8
    )

    reit_sub = nonfin_df[nonfin_df["sector"] == "Gayrimenkul"].merge(
        extra_bs, on=["ticker", "stmt_period"], how="left"
    )
    reit_scored = compute_reit_scores(reit_sub, q_ext=q_ext)
    s3_reits = evaluate_sector_models(
        reit_scored, ["G0_value_sn", "G1_nav_ffo", "G2_letdin_sirmans_resid"], "G0_value_sn", top_pct=0.20, min_names=8
    )

    # 3. Maliyetli portfoy simulasyonu (S4: P0 vs P1 vs P2, EW net ve BIST 100 TR karsisinda)
    h1_map = hold_scored.set_index(["date", "ticker"])["H1_bm_ep_roe"]
    g1_map = reit_scored.set_index(["date", "ticker"])["G1_nav_ffo"]

    nonfin_p = nonfin_df[nonfin_df["value_sn_z"].notna()].copy()
    nonfin_p["score_P1"] = nonfin_p["value_sn_z"]
    idx_nf = nonfin_p.set_index(["date", "ticker"]).index
    mask_h = nonfin_p["sector"].to_numpy() == "Holding"
    mask_g = nonfin_p["sector"].to_numpy() == "Gayrimenkul"
    nonfin_p.loc[mask_h, "score_P1"] = h1_map.reindex(idx_nf[mask_h]).to_numpy()
    nonfin_p.loc[mask_g, "score_P1"] = g1_map.reindex(idx_nf[mask_g]).to_numpy()

    sel: dict[str, dict[pd.Timestamp, list[str]]] = {
        "P0_nonfin_baseline": {},
        "P1_nonfin_sector_specialized": {},
        "P2_all_bist_with_financials": {},
        "EW_nonfin": {},
    }
    fin_by_dt = {t: g for t, g in all_fin_df[all_fin_df["F1_bm_roe_sn"].notna()].groupby("date")}
    for t, g in nonfin_p.groupby("date"):
        sel["EW_nonfin"][t] = sorted(g["ticker"])
        r0 = g["value_sn_z"].rank(ascending=False, pct=True)
        p0_list = sorted(g.loc[r0 <= TOP, "ticker"])
        sel["P0_nonfin_baseline"][t] = p0_list

        g1 = g[g["score_P1"].notna()]
        r1 = g1["score_P1"].rank(ascending=False, pct=True)
        sel["P1_nonfin_sector_specialized"][t] = sorted(g1.loc[r1 <= TOP, "ticker"])

        fg = fin_by_dt.get(t)
        if fg is not None and len(fg) >= 5:
            rf = fg["F1_bm_roe_sn"].rank(ascending=False, pct=True)
            fin_picks = sorted(fg.loc[rf <= TOP, "ticker"])
            sel["P2_all_bist_with_financials"][t] = sorted(set(p0_list) | set(fin_picks))
        else:
            sel["P2_all_bist_with_financials"][t] = p0_list

    fx = pd.read_parquet(RESEARCH / "fx.parquet")
    fx["date"] = pd.to_datetime(fx["date"]).dt.normalize()
    fx = fx.set_index("date").sort_index()
    days = fx.index
    months = sorted(nonfin_p["date"].unique())
    d0_of = {t: days[days.searchsorted(t, side="right") - 1] for t in months}

    tickers = sorted({tk for m in sel.values() for lst in m.values() for tk in lst})
    frames = {tk: load_daily_any(tk) for tk in tickers}
    frames = {tk: f for tk, f in frames.items() if f is not None}
    mat = {k: pd.DataFrame({tk: f[c] for tk, f in frames.items()}).reindex(days)
           for k, c in (("close", "Close"), ("open", "Open"), ("adv", "adv"), ("sigma", "sigma"))}
    mat["adv"], mat["sigma"] = mat["adv"].ffill(), mat["sigma"].ffill()

    macro = pd.read_parquet(RESEARCH / "macro_monthly.parquet")
    macro.index = pd.to_datetime(macro.index).to_period("M")
    rf_daily = pb.policy_rf_daily(macro["policy"], days)
    cpi_idx = (1 + macro["cpi_mom"].fillna(0) / 100).cumprod()
    ref = cpi_idx[CAPITAL_REF.to_period("M")]
    cpi_rel = {t: float(cpi_idx[t.to_period("M")] / ref) for t in months}
    cap = {t: 1e6 * cpi_rel[t] for t in months}
    universe_liq = {t: np.sort(g["tlvol60"].to_numpy()) for t, g in nonfin_p.groupby("date")}
    bench = nonfin_p.groupby("date")[["fwd_ret_1m", "fwd_ret_1m_usd"]].mean()
    mkt = pb.Market(close=mat["close"], open=mat["open"], adv=mat["adv"], sigma=mat["sigma"], rf_daily=rf_daily)
    ctx = {"months": months, "d0_of": d0_of, "fx": fx, "rf_daily": rf_daily, "cpi_idx": cpi_idx,
           "bench": bench, "cpi_rel": cpi_rel, "universe_liq": universe_liq}

    tr_idx = pd.read_parquet(RESEARCH / "tr_indices.parquet")
    if "date" in tr_idx.columns:
        tr_idx["date"] = pd.to_datetime(tr_idx["date"]).dt.normalize()
        tr_idx = tr_idx.set_index("date")
    else:
        tr_idx.index = pd.to_datetime(tr_idx.index).normalize()
    tr_idx = tr_idx.sort_index()
    xu100_tr_m = {}
    for i, t in enumerate(months[:-1]):
        d_a, d_b = d0_of[t], d0_of[months[i + 1]]
        sub_tr = tr_idx["xu100_tr"].loc[:d_b].dropna()
        sub_a = tr_idx["xu100_tr"].loc[:d_a].dropna()
        if not sub_tr.empty and not sub_a.empty and (d_a - sub_a.index[-1]).days <= 10:
            xu100_tr_m[t] = float(sub_tr.iloc[-1] / sub_a.iloc[-1] - 1.0)
    xu100_tr_s = pd.Series(xu100_tr_m)

    costs = pb.Costs()
    ew_sim = pb.simulate(sel["EW_nonfin"], months, d0_of, mkt, universe_liq, cap, costs=costs).set_index("date")
    sims = {}
    for pname in ("P0_nonfin_baseline", "P1_nonfin_sector_specialized", "P2_all_bist_with_financials"):
        p = attach_benchmarks(pb.simulate(sel[pname], months, d0_of, mkt, universe_liq, cap, costs=costs), ctx)
        p = p.set_index("date")
        p["ew_net"] = ew_sim["port"].reindex(p.index)
        p["active_ew_net"] = p["port"] - p["ew_net"]
        p["xu100_tr"] = xu100_tr_s.reindex(p.index)
        p["active_xu100_tr"] = p["port"] - p["xu100_tr"]
        sims[pname] = p

    s4_portfolios = {}
    p0 = sims["P0_nonfin_baseline"]
    for pname, p in sims.items():
        s4_portfolios[pname] = {}
        for wname, wfn in (("discovery", lambda idx: idx < SPLIT),
                           ("holdout", lambda idx: idx >= SPLIT)):
            sub = p[wfn(p.index)].reset_index()
            st = stats(sub)
            entry = {
                "vs_ew_net": nw(p.loc[wfn(p.index), "active_ew_net"]),
                "vs_xu100_tr": nw(p.loc[wfn(p.index), "active_xu100_tr"].dropna()),
                "vs_xu100_price_ann_pct": st.get("active_xu100_ann_pct"),
                "cagr_tl_pct": st.get("cagr_tl_pct"),
                "cagr_usd_pct": st.get("cagr_usd_pct"),
                "max_dd_usd_pct": st.get("max_dd_usd_pct"),
                "turnover_pct": st.get("turnover_pct"),
                "cost_ann_pct": st.get("cost_ann_pct"),
                "avg_names": st.get("avg_names"),
            }
            if pname != "P0_nonfin_baseline":
                d_s = (p["port"] - p0["port"]).loc[wfn(p.index)]
                entry["diff_vs_P0"] = nw(d_s)
            s4_portfolios[pname][wname] = entry

    result = {
        "as_of": date.today().isoformat(),
        "financial_panel_coverage": {
            "n_tickers": int(fin_df["ticker"].nunique()),
            "n_rows": int(len(fin_df)),
            "sectors": fin_df.groupby("sector")["ticker"].nunique().to_dict(),
        },
        "S1a_banks_descriptive": s1_banks,
        "S1b_all_financials_liquid": s1_all_fin,
        "S2_holdings": s2_holdings,
        "S3_reits": s3_reits,
        "S4_portfolio_simulations": s4_portfolios,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    out = ROOT / "data" / "reports" / f"research_financials_holdings_reits_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
