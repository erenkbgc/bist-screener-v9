"""Nokta-zamanli (point-in-time) arastirma paneli: gecmis temel veri + fiyat.

Neden: skorlama modelinin hicbir parcasi gecmis veride kesitsel olarak test
edilmemisti (agirliklar, esikler, yakinsama alfa'si varsayimdi). Bu modul
2011+ ceyreklik tablolar ve gunluk fiyatlardan, her ay sonu icin YALNIZCA o
tarihte kamuya acik olan veriyle faktor degerleri uretir.

Kurallar:
  - Gelir tablosu Is Yatirim'de YIL ICI KUMULATIF (YTD) gelir: 2026Q2 = ilk
    yari. Ceyreklik tutar = YTD_q - YTD_{q-1} (ayni yil), TTM = son 4 ceyrek.
  - Yayin gecikmesi (ihtiyatli, ileriye bakissiz): Q1-Q3 donem sonu + 75 gun,
    Q4 + 100 gun (SPK sureleri + uzatmalar).
  - Pay sayisi = Odenmis Sermaye (BIST'te nominal 1 TL). Bilanco tarihinden
    sonraki bedelli/bedelsiz islemler `splits` ile ileri tasinir, boylece
    piyasa degeri = ham fiyat x o gunku pay sayisi.
  - Getiriler duzeltilmis (adjust=True) fiyattan; seviyeler ham fiyattan.
  - Finansal sirketler (banka/sigorta/leasing/araci kurum/MKYO) haric:
    farkli tablo sablonu ve literaturdeki standart uygulama.
"""
from __future__ import annotations

import math
from datetime import timedelta

import numpy as np
import pandas as pd

LAG_DAYS_INTERIM = 75
LAG_DAYS_ANNUAL = 100

BS_ITEMS = {
    "total_assets": ("TOPLAM VARLIKLAR",),
    "equity_parent": ("Ana Ortaklığa Ait Özkaynaklar",),
    "equity": ("Özkaynaklar",),
    "paid_in": ("Ödenmiş Sermaye",),
    "cash": ("Nakit ve Nakit Benzerleri",),
    "fin_debt": ("Finansal Borçlar",),  # kisa + uzun vade: tekrarlanan satirlar toplanir
    # Faz 2 on-kaydi (docs/research/long_term_preregistration.md): sikinti/F7 girdileri
    "current_assets": ("Dönen Varlıklar",),
    "current_liab": ("Kısa Vadeli Yükümlülükler",),
    "noncurrent_liab": ("Uzun Vadeli Yükümlülükler",),
    "retained": ("Geçmiş Yıllar Kar/Zararları",),
}
INC_ITEMS = {
    "revenue": ("Satış Gelirleri",),
    "gross_profit": ("BRÜT KAR (ZARAR)",),
    "op_profit": ("FAALİYET KARI (ZARARI)", "Net Faaliyet Kar/Zararı"),
    "ni_parent": ("Ana Ortaklık Payları",),
    "net_income": ("DÖNEM KARI (ZARARI)",),
    "ebit": ("Finansman Gideri Öncesi Faaliyet Karı/Zararı",),
    "fin_expense": ("(Esas Faaliyet Dışı) Finansal Giderler (-)",),
}
SUM_DUPLICATES = {"fin_debt"}

FINANCIAL_SECTORS = {
    "Bankacılık", "Sigorta", "Emeklilik", "Faktoring", "Finansal Kiralama",
    "Tasarruf Finansman", "Aracı Kurum", "Menkul Kıymet Yat. Ort.", "Varlık Yönetimi",
}


def merge_statement_batches(batches: list[pd.DataFrame]) -> pd.DataFrame:
    """Donem batch'lerini yan yana birlestirir.

    borsapy 0.11 batch'leri satir ADI uzerinden ``join`` eder; ayni ad birden
    fazla geciyorsa (orn. kisa ve uzun vadeli "Finansal Borçlar") her batch
    satir sayisini katlar -- 15 batch'te 2^15 kopya ve toplanan kalemlerde
    cop degerler. Burada satir, (ad, batch icindeki sira) ile eslenir.
    """
    keyed = []
    for df in batches:
        if df is None or df.empty:
            continue
        occ = df.groupby(level=0).cumcount()
        keyed.append(df.set_index([df.index, occ]))
    if not keyed:
        return pd.DataFrame()
    result = keyed[0]
    for extra in keyed[1:]:
        new_cols = [c for c in extra.columns if c not in result.columns]
        if new_cols:
            result = result.join(extra[new_cols], how="outer", sort=False)
    result.index = result.index.get_level_values(0)
    return result


def _pick(df: pd.DataFrame, labels: tuple[str, ...], sum_dupes: bool) -> pd.Series | None:
    idx = pd.Index([str(i).strip() for i in df.index])
    for lbl in labels:
        mask = idx == lbl
        if mask.any():
            rows = df.loc[mask]
            if sum_dupes:
                return rows.apply(pd.to_numeric, errors="coerce").sum(axis=0, min_count=1)
            return pd.to_numeric(rows.iloc[0], errors="coerce")
    return None


def statements_long(ticker: str, bs: pd.DataFrame | None, inc: pd.DataFrame | None) -> pd.DataFrame:
    """(ticker, period, item, value) -- ham, YTD haliyle."""
    out = []
    for df, items in ((bs, BS_ITEMS), (inc, INC_ITEMS)):
        if df is None or df.empty:
            continue
        for item, labels in items.items():
            s = _pick(df, labels, item in SUM_DUPLICATES)
            if s is None:
                continue
            for period, v in s.items():
                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                    out.append({"ticker": ticker, "period": str(period), "item": item, "value": float(v)})
    return pd.DataFrame(out)


def period_end(period: str) -> pd.Timestamp:
    """'2026Q2' -> 2026-06-30."""
    y, q = int(period[:4]), int(period[-1])
    return pd.Timestamp(year=y, month=3 * q, day=1) + pd.offsets.MonthEnd(0)


def available_at(period: str) -> pd.Timestamp:
    lag = LAG_DAYS_ANNUAL if period.endswith("Q4") else LAG_DAYS_INTERIM
    return period_end(period) + timedelta(days=lag)


def quarterly_table(long: pd.DataFrame) -> pd.DataFrame:
    """Genis tablo: index (ticker, period_end), kolonlar kalemler; akis kalemleri
    icin ceyreklik (q_*) ve TTM (ttm_*) kolonlari eklenir."""
    if long.empty:
        return pd.DataFrame()
    w = long.pivot_table(index=["ticker", "period"], columns="item", values="value", aggfunc="first").reset_index()
    w["period_end"] = w["period"].map(period_end)
    w["available_at"] = w["period"].map(available_at)
    w["year"] = w["period"].str[:4].astype(int)
    w["q"] = w["period"].str[-1].astype(int)
    w = w.sort_values(["ticker", "period_end"])
    for item in INC_ITEMS:
        if item not in w:
            continue
        prev = w.groupby(["ticker", "year"])[item].shift(1)
        prev_q = w.groupby(["ticker", "year"])["q"].shift(1)
        disc = np.where(w["q"] == 1, w[item],
                        np.where(prev_q == w["q"] - 1, w[item] - prev, np.nan))
        w[f"q_{item}"] = disc
        # TTM: ardisik 4 ceyrek sart (eksik ceyrek varsa NaN, uydurulmaz)
        consec = w.groupby("ticker")["period_end"].diff().dt.days.between(80, 100)
        roll = w.groupby("ticker")[f"q_{item}"].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
        ok = consec.groupby(w["ticker"]).rolling(3, min_periods=3).sum().reset_index(level=0, drop=True) == 3
        w[f"ttm_{item}"] = roll.where(ok)
    return w.reset_index(drop=True)


def split_events(ticker: str, splits: pd.DataFrame | None) -> pd.DataFrame:
    if splits is None or len(splits) == 0:
        return pd.DataFrame(columns=["ticker", "date", "rights_pct", "bonus_pct"])
    s = splits.copy()
    s.index = pd.to_datetime(s.index).tz_localize(None) if getattr(s.index, "tz", None) else pd.to_datetime(s.index)
    return pd.DataFrame({
        "ticker": ticker, "date": s.index,
        "rights_pct": pd.to_numeric(s.get("RightsIssue", 0), errors="coerce").fillna(0.0).values,
        "bonus_pct": (pd.to_numeric(s.get("BonusFromCapital", 0), errors="coerce").fillna(0.0)
                      + pd.to_numeric(s.get("BonusFromDividend", 0), errors="coerce").fillna(0.0)).values,
    })


def monthly_prices(ticker: str, raw: pd.DataFrame | None, adj: pd.DataFrame | None) -> pd.DataFrame:
    """Ay sonu ham/duzeltilmis kapanis, 60 gunluk gunluk volatilite (duzeltilmis),
    60 gunluk medyan TL hacim."""
    if raw is None or adj is None or raw.empty or adj.empty:
        return pd.DataFrame()
    r = raw.copy()
    a = adj.copy()
    for d in (r, a):
        d.index = pd.to_datetime(d.index)
        if getattr(d.index, "tz", None) is not None:
            d.index = d.index.tz_localize(None)
    daily = pd.DataFrame({"raw": r["Close"].astype(float), "adj": a["Close"].astype(float),
                          "tl_vol": r["Close"].astype(float) * r["Volume"].astype(float)}).dropna(subset=["raw", "adj"])
    ret = daily["adj"].pct_change()
    daily["vol60"] = ret.rolling(60, min_periods=40).std()
    daily["tlvol60"] = daily["tl_vol"].rolling(60, min_periods=40).median()
    m = daily.resample("ME").last()
    m["ticker"] = ticker
    return m.dropna(subset=["raw"]).reset_index(names="date")


def shares_at(t: pd.Timestamp, paid_in: float, stmt_end: pd.Timestamp, events: pd.DataFrame) -> float:
    """Bilanco tarihindeki pay sayisini t'ye kadarki bedelli/bedelsiz islemlerle ileri tasi."""
    f = 1.0
    if not events.empty:
        ev = events[(events["date"] > stmt_end) & (events["date"] <= t)]
        for _, e in ev.iterrows():
            f *= 1.0 + (e["rights_pct"] + e["bonus_pct"]) / 100.0
    return paid_in * f


def build_monthly_factors(q: pd.DataFrame, px: pd.DataFrame, events: pd.DataFrame,
                          sectors: dict[str, str]) -> pd.DataFrame:
    """Her (ticker, ay sonu) icin nokta-zamanli faktor satiri + ileri 1 aylik getiri."""
    rows = []
    q = q.sort_values(["ticker", "available_at"])
    ev_by = {t: g for t, g in events.groupby("ticker")} if not events.empty else {}
    q_by = {t: g for t, g in q.groupby("ticker")}
    for tk, p in px.groupby("ticker"):
        p = p.sort_values("date").reset_index(drop=True)
        qt = q_by.get(tk)
        if qt is None:
            continue
        ev = ev_by.get(tk, pd.DataFrame(columns=["date", "rights_pct", "bonus_pct"]))
        adj = p["adj"].values
        for i in range(len(p)):
            t = p.at[i, "date"]
            avail = qt[qt["available_at"] <= t]
            if avail.empty or i < 13:
                continue
            last = avail.iloc[-1]
            paid_in = last.get("paid_in")
            if not paid_in or paid_in <= 0 or not np.isfinite(paid_in):
                continue
            shares = shares_at(t, paid_in, last["period_end"], ev)
            mcap = p.at[i, "raw"] * shares
            if not mcap or mcap <= 0:
                continue
            eq = last.get("equity_parent")
            if eq is None or not np.isfinite(eq):
                eq = last.get("equity")
            ni = last.get("ttm_ni_parent")
            if ni is None or not np.isfinite(ni):
                ni = last.get("ttm_net_income")
            ev_val = mcap + (last.get("fin_debt") or 0.0) - (last.get("cash") or 0.0)
            # SUE: mevsimsel rastgele yuruyus (Foster-Olsen-Shevlin), son 8 degisimin std'si
            qn = avail["q_ni_parent"] if "q_ni_parent" in avail else pd.Series(dtype=float)
            sue = np.nan
            if len(qn.dropna()) >= 12:
                chg = (qn - qn.shift(4)).dropna()
                if len(chg) >= 8 and chg.iloc[-8:].std() > 0:
                    sue = chg.iloc[-1] / chg.iloc[-8:].std()
            rights_12m = 0.0
            if not ev.empty:
                e12 = ev[(ev["date"] > t - pd.DateOffset(months=12)) & (ev["date"] <= t)]
                rights_12m = float(np.log(np.prod(1.0 + e12["rights_pct"].values / 100.0))) if len(e12) else 0.0
            ta = last.get("total_assets")
            rows.append({
                "date": t, "ticker": tk, "sector": sectors.get(tk, "BILINMIYOR"),
                "mcap": mcap, "size": math.log(mcap), "tlvol60": p.at[i, "tlvol60"],
                "bm": eq / mcap if eq and eq > 0 else np.nan,
                "ep": ni / mcap if ni is not None and np.isfinite(ni) else np.nan,
                "sp": last.get("ttm_revenue") / mcap if last.get("ttm_revenue") else np.nan,
                "ey": (last.get("ttm_op_profit") / ev_val) if (last.get("ttm_op_profit") is not None
                                                               and np.isfinite(last.get("ttm_op_profit", np.nan)) and ev_val > 0) else np.nan,
                "gpa": (last.get("ttm_gross_profit") / ta) if (ta and ta > 0 and last.get("ttm_gross_profit") is not None) else np.nan,
                "roe": (ni / eq) if (eq and eq > 0 and ni is not None and np.isfinite(ni)) else np.nan,
                "mom_12_1": adj[i - 1] / adj[i - 12] - 1 if adj[i - 12] > 0 else np.nan,
                "str_1m": adj[i] / adj[i - 1] - 1 if adj[i - 1] > 0 else np.nan,
                "vol60": p.at[i, "vol60"],
                "nsi_rights_12m": rights_12m,
                "sue": sue,
                "fwd_ret_1m": adj[i + 1] / adj[i] - 1 if i + 1 < len(p) and adj[i] > 0 else np.nan,
                "fwd_ret_6m": adj[i + 6] / adj[i] - 1 if i + 6 < len(p) and adj[i] > 0 else np.nan,
                "stmt_period": last["period"],
            })
    return pd.DataFrame(rows)


def monthly_market(daily: pd.DataFrame) -> pd.DataFrame:
    """Gunluk usdtry/xu100 (data/research/fx.parquet) -> ay sonu son deger."""
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    return d.set_index("date")[["usdtry", "xu100"]].resample("ME").last()


def add_usd_returns(factors: pd.DataFrame, market_m: pd.DataFrame) -> pd.DataFrame:
    """fwd_ret_{1m,6m} (TL, duzeltilmis) yanina USD ve XU100'e gore fazla getiri ekler.

    usd: (1 + r_TL) / (1 + r_USDTRY) - 1, ayni pencere ve ay sonu kapanisi.
    xs : r_TL - r_XU100 (aritmetik fark; XU100 temettu haric fiyat endeksi,
         hisse getirisi temettu dahil duzeltilmis -- fark temettu verimi kadar
         yukari yanlidir).
    Kur veya endeks degeri eksik ayda yeni kolonlar NaN kalir.
    """
    m = market_m.sort_index()
    out = factors.copy()
    key = pd.to_datetime(out["date"]).dt.to_period("M").dt.to_timestamp("M")
    for h in (1, 6):
        fx_ret = (m["usdtry"].shift(-h) / m["usdtry"] - 1).reindex(key).values
        xu_ret = (m["xu100"].shift(-h) / m["xu100"] - 1).reindex(key).values
        r = out[f"fwd_ret_{h}m"].values
        out[f"fwd_ret_{h}m_usd"] = (1 + r) / (1 + fx_ret) - 1
        out[f"fwd_ret_{h}m_xs"] = r - xu_ret
    return out
