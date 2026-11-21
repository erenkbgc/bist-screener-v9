#!/usr/bin/env python3
"""Nokta-zamanli arastirma panelini kurar (data/research/, git'e girmez).

    python scripts/build_pit_panel.py                 # tum finansal-disi evren (eksik hamlar cekilir)
    python scripts/build_pit_panel.py --rebuild       # agsiz: yalniz data/research/raw/*.pkl'den yeniden kur
    python scripts/build_pit_panel.py --tickers THYAO,ASELS,BIMAS
    python scripts/build_pit_panel.py --refresh       # ham onbellegi yenile

Varsayilan nokta-zamanli tanim (docs/research/first_published_panel.md, market_cap_source.md):
  - Pay sayisi duzeltmesi (pit_panel.shares_at, share_count_fix.md)
  - C1 sabit satin alma gucu TTM (macro_monthly.parquet varsa)
  - TMS 29 yeniden ifade geri alma + 2023Q4-2024Q3 kopru TTM (reexpression_class.parquet + TUFE varsa)
  - Is Yatirim HisseTekil PD piyasa degeri (market_cap_monthly.parquet varsa, yoksa fiyat x pay)

Yazilan dosyalar:
  quarterly.parquet, quarterly_ext.parquet   75/100 gun available_at (KAP tarihi uygulanmamis)
  factors_monthly.parquet                    75/100 gun gecikmeli aylik faktor paneli
  factors_monthly_kapdates.parquet           gercek KAP yayin tarihli panel (kap_archive.parquet varsa)
  monthly_prices.parquet, share_events.parquet

Ham borsapy cevaplari ticker basina data/research/raw/<T>.pkl olarak saklanir;
yarida kesilen kosu kaldigi yerden devam eder.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import pit_panel  # noqa: E402

OUT = ROOT / "data" / "research"
RAW = OUT / "raw"

RAW_VERSION = 2  # v1: borsapy'nin kartezyen-sismis tablolari (bkz. pit_panel.merge_statement_batches)

PANEL_DEFINITION = (
    "Point-in-time baseline: C1 (ias29_constant_unit_ttm_preregistration.md) "
    "+ pay sayisi duzeltmesi (share_count_fix.md) "
    "+ TMS 29 yeniden ifade geri alma + bridge_ttm (first_published_panel.md) "
    "+ Is Yatirim HisseTekil PD piyasa degeri (market_cap_source.md). "
    "Yedekler: c0/, pre_share_fix/, pre_point_in_time/.\n"
)


UPDATE_QUARTERS = 8  # son 2 batch (8 ceyrek): yeni ceyrek + TMS 29 yeniden ifade edilen onceki yil donemleri


def last_ended_quarter(as_of: date | None = None) -> tuple[int, int]:
    """as_of itibariyla takvim olarak bitmis en son ceyrek (yil, ay).

    borsapy._providers.isyatirim._get_periods Kasim ayinda Q2'de kaldigi icin
    Q3 yayinlarini atliyor; burada takvim olarak bitmis son ceyrekten baslanir.
    """
    d = as_of or date.today()
    for m, day in ((12, 31), (9, 30), (6, 30), (3, 31)):
        if (d.month, d.day) >= (m, day):
            return d.year, m
    return d.year - 1, 12


def quarter_periods(count: int, as_of: date | None = None) -> list[tuple[int, int]]:
    """Takvim olarak bitmis en son ceyrekten geriye dogru `count` adet (yil, ay) cifti."""
    year, period = last_ended_quarter(as_of)
    out: list[tuple[int, int]] = []
    for _ in range(count):
        out.append((year, period))
        period -= 3
        if period <= 0:
            period = 12
            year -= 1
    return out


def fetch_statement_upto_latest(
    ticker: str,
    statement_type: str,
    last_n: int,
    as_of: date | None = None,
    retries: int = 2,
) -> pd.DataFrame | None:
    """Is Yatirim sanayi sablonu, takvim olarak bitmis son ceyrekten geriye last_n donem.

    Is Yatirim API'si her cagrida 4 donem bekler; last_n 4'un kati secilmelidir.
    """
    from borsapy._providers.isyatirim import get_isyatirim_provider

    prov = get_isyatirim_provider()
    step = prov._MAX_PERIODS_PER_CALL
    n = max(step, ((last_n + step - 1) // step) * step)
    periods = quarter_periods(n, as_of=as_of)
    batches: list[pd.DataFrame] = []
    for i in range(0, len(periods), step):
        chunk = periods[i:i + step]
        for attempt in range(retries + 1):
            try:
                df = prov._fetch_financial_table(
                    symbol=ticker,
                    financial_group=prov.FINANCIAL_GROUP_INDUSTRIAL,
                    periods=chunk,
                    quarterly=True,
                    statement_type=statement_type,
                )
                if df is not None and not df.empty:
                    batches.append(df)
                break
            except Exception:  # noqa: BLE001
                if attempt < retries:
                    time.sleep(0.5 * (attempt + 1))
    merged = pit_panel.merge_statement_batches(batches)
    if merged.empty:
        return None
    return merged[sorted(merged.columns, key=prov._period_sort_key, reverse=True)]


def merge_updated_statement(old: pd.DataFrame | None, fresh: pd.DataFrame | None) -> pd.DataFrame | None:
    """Yeni cekilen son ceyrekleri mevcut gecmis tablo sutunlariyla birlestirir."""
    if fresh is None or fresh.empty:
        return old
    if old is None or old.empty:
        return fresh
    keep_cols = [c for c in old.columns if c not in fresh.columns]
    if not keep_cols:
        return fresh
    merged = pit_panel.merge_statement_batches([fresh, old[keep_cols]])
    if merged.empty:
        return old
    from borsapy._providers.isyatirim import get_isyatirim_provider
    prov = get_isyatirim_provider()
    return merged[sorted(merged.columns, key=prov._period_sort_key, reverse=True)]


def fetch_raw(ticker: str, refresh: bool, update: bool = False, as_of: date | None = None) -> dict | None:
    path = RAW / f"{ticker}.pkl"
    raw = pickle.loads(path.read_bytes()) if path.exists() and not refresh else None
    if raw is not None and raw.get("version") == RAW_VERSION and not update:
        return raw
    import borsapy as bp
    t = bp.Ticker(ticker)

    def safe(fn, retries: int = 2, **kw):
        for attempt in range(retries + 1):
            try:
                res = fn(**kw)
                if res is not None:
                    return res
            except Exception:  # noqa: BLE001
                pass
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
        return None

    if raw is None or update:
        px_raw = safe(t.history, period="max", adjust=False)
        px_adj = safe(t.history, period="max", adjust=True)
        splits = safe(lambda: t.splits)
        if raw is None:
            raw = {"px_raw": px_raw, "px_adj": px_adj, "splits": splits}
        else:
            if px_raw is not None and not px_raw.empty:
                raw["px_raw"] = px_raw
            if px_adj is not None and not px_adj.empty:
                raw["px_adj"] = px_adj
            if splits is not None:
                raw["splits"] = splits

    if update and raw.get("bs") is not None and raw.get("inc") is not None:
        fresh_bs = fetch_statement_upto_latest(ticker, "balance_sheet", UPDATE_QUARTERS, as_of=as_of)
        fresh_inc = fetch_statement_upto_latest(ticker, "income_stmt", UPDATE_QUARTERS, as_of=as_of)
        raw["bs"] = merge_updated_statement(raw.get("bs"), fresh_bs)
        raw["inc"] = merge_updated_statement(raw.get("inc"), fresh_inc)
    else:
        # v1 onbellekte fiyat/bolunme saglam; yalniz tablolar yeniden cekilir
        raw["bs"] = fetch_statement_upto_latest(ticker, "balance_sheet", 60, as_of=as_of)
        raw["inc"] = fetch_statement_upto_latest(ticker, "income_stmt", 60, as_of=as_of)
    raw["version"] = RAW_VERSION
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(raw))
    return raw


def load_cached_raw(ticker: str, raw_dir: Path = RAW) -> dict | None:
    path = raw_dir / f"{ticker}.pkl"
    if not path.exists():
        return None
    return pickle.loads(path.read_bytes())


def build_panel_from_raw(
    raw_by_ticker: dict[str, dict],
    sectors: dict[str, str],
    research_dir: Path = OUT,
    out_dir: Path | None = None,
    use_undo: bool = True,
    use_isy_mcap: bool = True,
    write_prices_and_events: bool = True,
    write_definition: bool = False,
) -> dict:
    """Ham ticker sozlugunden nokta-zamanli panel dosyalarini kurar ve yazar.

    Varsayilan adimlar:
      1. C1 sabit satin alma gucu TTM (macro_monthly.parquet varsa)
      2. TMS 29 yeniden ifade geri alma + bridge_ttm (reexpression_class.parquet + TUFE varsa)
      3. Is Yatirim HisseTekil PD piyasa degeri (market_cap_monthly.parquet varsa; yoksa shares_at)
      4. lag75 (factors_monthly.parquet) ve KAP tarihli (factors_monthly_kapdates.parquet) paneller
    """
    target = out_dir or research_dir
    longs, pxs, evs = [], [], []
    for tk in sorted(raw_by_ticker):
        raw = raw_by_ticker[tk]
        if not raw:
            continue
        longs.append(pit_panel.statements_long(tk, raw.get("bs"), raw.get("inc")))
        pxs.append(pit_panel.monthly_prices(tk, raw.get("px_raw"), raw.get("px_adj")))
        evs.append(pit_panel.split_events(tk, raw.get("splits")))

    long = pd.concat([x for x in longs if not x.empty], ignore_index=True) if any(not x.empty for x in longs) else pd.DataFrame()
    macro_path = research_dir / "macro_monthly.parquet"
    cpi = pit_panel.cpi_index(pd.read_parquet(macro_path)["cpi_mom"]) if macro_path.exists() else None
    if cpi is None:
        print("UYARI: macro_monthly.parquet yok; TTM C0 (TMS 29 birim duzeltmesi yok).")

    stats: dict = {"c1": cpi is not None, "undo_reexpression": False, "bridge_ttm": False, "isyatirim_mcap": False}
    classes_path = research_dir / "reexpression_class.parquet"
    if use_undo:
        if cpi is not None and classes_path.exists():
            long, undo_stats = pit_panel.undo_reexpression(long, pd.read_parquet(classes_path), cpi)
            stats["undo_reexpression"] = True
            stats.update(undo_stats)
        else:
            print("UYARI: reexpression_class.parquet veya macro_monthly.parquet yok; TMS 29 yeniden ifadesi geri alinmadi.")

    q = pit_panel.quarterly_table(long, cpi=cpi)
    if stats["undo_reexpression"] and cpi is not None and not q.empty:
        q = pit_panel.bridge_ttm(q, long, cpi)
        stats["bridge_ttm"] = True

    mcaps = None
    mc_path = research_dir / "market_cap_monthly.parquet"
    if use_isy_mcap:
        if mc_path.exists():
            mcaps = pd.read_parquet(mc_path)[["ticker", "date", "mcap"]]
            stats["isyatirim_mcap"] = True
        else:
            print("UYARI: market_cap_monthly.parquet yok; piyasa degeri fiyat x pay (shares_at).")

    px = pd.concat([x for x in pxs if not x.empty], ignore_index=True) if any(not x.empty for x in pxs) else pd.DataFrame()
    ev = pd.concat([x for x in evs if not x.empty], ignore_index=True) if any(not x.empty for x in evs) else pd.DataFrame()

    factors_lag75 = pit_panel.build_monthly_factors(q, px, ev, sectors, market_caps=mcaps)
    stats["lag75_rows"] = len(factors_lag75)
    if not factors_lag75.empty and "mcap_source" in factors_lag75:
        stats["lag75_mcap_source"] = factors_lag75["mcap_source"].value_counts().to_dict()

    target.mkdir(parents=True, exist_ok=True)
    q.to_parquet(target / "quarterly.parquet", index=False)
    q.to_parquet(target / "quarterly_ext.parquet", index=False)
    if write_prices_and_events:
        px.to_parquet(target / "monthly_prices.parquet", index=False)
        if not ev.empty:
            ev.to_parquet(target / "share_events.parquet", index=False)
    factors_lag75.to_parquet(target / "factors_monthly.parquet", index=False)

    archive = research_dir / "kap_archive.parquet"
    if archive.exists():
        dates = pit_panel.kap_report_dates(pd.read_parquet(archive))
        q_kap = pit_panel.apply_report_dates(q, dates)
        kap_share = 100 * float((q_kap["available_source"] == "kap").mean()) if len(q_kap) else 0.0
        print(f"KAP yayin tarihi eslesen ceyrek: %{kap_share:.1f}")
        factors_kap = pit_panel.build_monthly_factors(q_kap, px, ev, sectors, market_caps=mcaps)
        factors_kap.to_parquet(target / "factors_monthly_kapdates.parquet", index=False)
        stats["kapdates_rows"] = len(factors_kap)
        if not factors_kap.empty and "mcap_source" in factors_kap:
            stats["kapdates_mcap_source"] = factors_kap["mcap_source"].value_counts().to_dict()
    else:
        print("UYARI: data/research/kap_archive.parquet yok; factors_monthly_kapdates.parquet yazilmadi.")

    if write_definition:
        (target / "PANEL_DEFINITION.txt").write_text(PANEL_DEFINITION, encoding="utf-8")

    stats["quarterly_rows"] = len(q)
    if not factors_lag75.empty:
        stats["date_range"] = [str(factors_lag75["date"].min().date()), str(factors_lag75["date"].max().date())]
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--update", action="store_true", help="Fiyat/bolunme ve son 8 ceyregi guncelle")
    ap.add_argument("--rebuild", action="store_true",
                    help="Ag erisimi olmadan yalniz data/research/raw/*.pkl onbelleginden paneli yeniden kur")
    ap.add_argument("--no-undo", action="store_true", help="TMS 29 yeniden ifadesini geri alma (teshis icin)")
    ap.add_argument("--no-isy", action="store_true", help="Is Yatirim PD yerine yalniz fiyat x pay kullan")
    ap.add_argument("--out", default="", help="Cikti alt klasoru (varsayilan: data/research/)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    sector_rows = json.loads((ROOT / "config" / "fintables_ticker_sektor.json").read_text(encoding="utf-8"))
    sectors = {r["ticker"]: r["sektor"] for r in sector_rows}
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif args.rebuild:
        tickers = sorted(f.stem for f in RAW.glob("*.pkl")
                         if f.stem in sectors and sectors[f.stem] not in pit_panel.FINANCIAL_SECTORS)
    else:
        tickers = sorted(t for t, s in sectors.items() if s not in pit_panel.FINANCIAL_SECTORS)

    raw_by_ticker: dict[str, dict] = {}
    failed = []
    if args.rebuild:
        for tk in tickers:
            raw = load_cached_raw(tk)
            if raw is None:
                failed.append((tk, "onbellek yok"))
            else:
                raw_by_ticker[tk] = raw
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(fetch_raw, t, args.refresh, args.update): t for t in tickers}
            for n, fut in enumerate(as_completed(futs), 1):
                tk = futs[fut]
                try:
                    raw = fut.result()
                except Exception as exc:  # noqa: BLE001
                    failed.append((tk, str(exc)[:80]))
                    continue
                if raw is not None:
                    raw_by_ticker[tk] = raw
                if n % 50 == 0:
                    print(f"  {n}/{len(tickers)}", flush=True)

    out_dir = (OUT / args.out) if args.out else OUT
    full_build = not args.tickers and not args.no_undo and not args.no_isy
    stats = build_panel_from_raw(
        raw_by_ticker,
        sectors,
        research_dir=OUT,
        out_dir=out_dir,
        use_undo=not args.no_undo,
        use_isy_mcap=not args.no_isy,
        write_prices_and_events=not args.out,
        write_definition=full_build and not args.out,
    )
    dr = stats.get("date_range", ["-", "-"])
    print(f"Hisse: {len(tickers)} (basarisiz {len(failed)}), ceyrek satiri {stats['quarterly_rows']}, "
          f"lag75 faktor satiri {stats['lag75_rows']}, kapdates {stats.get('kapdates_rows', 0)}, "
          f"{dr[0]} .. {dr[1]}")
    print(json.dumps(stats, indent=1, ensure_ascii=False))
    if failed:
        print("Basarisiz:", failed[:10])


if __name__ == "__main__":
    main()
