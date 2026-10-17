"""Nokta-zamanli (point-in-time) arastirma paneli: gecmis temel veri + fiyat.

Neden: skorlama modelinin hicbir parcasi gecmis veride kesitsel olarak test
edilmemisti (agirliklar, esikler, yakinsama alfa'si varsayimdi). Bu modul
2011+ ceyreklik tablolar ve gunluk fiyatlardan, her ay sonu icin YALNIZCA o
tarihte kamuya acik olan veriyle faktor degerleri uretir.

Kurallar:
  - Gelir tablosu Is Yatirim'de YIL ICI KUMULATIF (YTD) gelir: 2026Q2 = ilk
    yari. Ceyreklik tutar = YTD_q - YTD_{q-1} (ayni yil), TTM = son 4 ceyrek.
  - Yayin tarihi: KAP arsivindeki gercek ilk finansal rapor yayini
    (kap_report_dates / apply_report_dates). Eslesmeyen ceyrekte varsayim:
    Q1-Q3 donem sonu + 75 gun, Q4 + 100 gun (SPK sureleri + uzatmalar).
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


REPORT_SUBJECTS = {"Finansal Rapor", "Finansal Rapor Bildirimi"}
RULE_QUARTER = {"3 Aylık": 1, "6 Aylık": 2, "9 Aylık": 3, "Yıllık": 4}
MAX_MATCH_DAYS = 400
SESSION_CLOSE_HOUR = 18


def kap_report_dates(archive: pd.DataFrame) -> pd.DataFrame:
    """KAP arsivinden (ticker, period) -> ilk finansal rapor yayin zamani
    (docs/research/kap_report_dates_preregistration.md).

    Donem: o tipteki (3/6/9 Aylik, Yillik) yayindan kesin once biten en son ceyrek
    sonu; 400 gunden gec yayin eslesmez. Seans kapanisindan (18:00) sonra yayinlanan
    rapor ertesi gun kullanilabilir."""
    fr = archive[(archive["disclosureClass"] == "FR") & archive["subject"].isin(REPORT_SUBJECTS)
                 & archive["ruleType"].isin(RULE_QUARTER)].copy()
    if fr.empty:
        return pd.DataFrame(columns=["ticker", "period", "published_at", "kap_available_at"])
    pub = pd.to_datetime(fr["published_at"])
    qn = fr["ruleType"].map(RULE_QUARTER).astype(int)
    pe_same = pd.to_datetime(dict(year=pub.dt.year, month=3 * qn, day=1)) + pd.offsets.MonthEnd(0)
    year = np.where(pe_same < pub.dt.normalize(), pub.dt.year, pub.dt.year - 1)
    pe = pd.to_datetime(dict(year=year, month=3 * qn, day=1)) + pd.offsets.MonthEnd(0)
    fr = fr.assign(ticker=fr["stock_code"].str.strip(), published_at=pub,
                   period=[f"{y}Q{q}" for y, q in zip(year, qn)], lag=(pub.dt.normalize() - pe).dt.days)
    fr = fr[fr["lag"].between(1, MAX_MATCH_DAYS)]
    first = fr.sort_values("published_at").groupby(["ticker", "period"], as_index=False)["published_at"].first()
    after_close = first["published_at"].dt.hour >= SESSION_CLOSE_HOUR
    first["kap_available_at"] = first["published_at"].dt.normalize() + pd.to_timedelta(after_close.astype(int), unit="D")
    return first


def apply_report_dates(q: pd.DataFrame, dates: pd.DataFrame, strict: bool = False) -> pd.DataFrame:
    """available_at'i gercek KAP tarihiyle degistirir (varyant B). strict=True (varyant C):
    eslesmeyen ceyrek satirlari atilir. available_source: 'kap' | 'assumed'."""
    out = q.merge(dates[["ticker", "period", "kap_available_at"]], on=["ticker", "period"], how="left")
    has = out["kap_available_at"].notna()
    out["available_at"] = out["kap_available_at"].where(has, out["available_at"])
    out["available_source"] = np.where(has, "kap", "assumed")
    if strict:
        out = out[has]
    return out.drop(columns="kap_available_at").reset_index(drop=True)


IAS29_FIRST_PERIOD = "2023Q4"  # TMS 29: 2023-12-31 ve sonrasi biten donemler


def cpi_index(cpi_mom: pd.Series) -> pd.Series:
    """Aylik TUFE degisiminden (%) zincirleme endeks, PeriodIndex 'M'."""
    s = cpi_mom.dropna().sort_index()
    idx = pd.PeriodIndex(pd.to_datetime(s.index), freq="M")
    return pd.Series((1 + s.to_numpy() / 100).cumprod(), index=idx)


def quarterly_table(long: pd.DataFrame, cpi: pd.Series | None = None) -> pd.DataFrame:
    """Genis tablo: index (ticker, period_end), kolonlar kalemler; akis kalemleri
    icin ceyreklik (q_*) ve TTM (ttm_*) kolonlari eklenir.

    cpi (cpi_index ciktisi) verilirse TMS 29 donemlerinde (>= 2023Q4) akislar ortak
    satin alma gucune cevrilir (docs/research/ias29_constant_unit_ttm_preregistration.md, C1):
    onceki YTD satirin birimine tasinarak cikarilir, TTM'deki dort ceyrek satirin donem
    sonu birimine tasinarak toplanir. Daha eski satirlar degismez (C0). TUFE'si
    bilinmeyen ayda deger NaN kalir."""
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
        if cpi is not None:
            c_end = w["period_end"].dt.to_period("M").map(cpi).astype(float)
            c_prev = c_end.groupby([w["ticker"], w["year"]]).shift(1)
            adj = (w["period"] >= IAS29_FIRST_PERIOD).to_numpy()
            disc_c = np.where(w["q"] == 1, w[item],
                              np.where(prev_q == w["q"] - 1, w[item] - prev * c_end / c_prev, np.nan))
            disc = np.where(adj, disc_c, disc)
        w[f"q_{item}"] = disc
        # TTM: ardisik 4 ceyrek sart (eksik ceyrek varsa NaN, uydurulmaz)
        consec = w.groupby("ticker")["period_end"].diff().dt.days.between(80, 100)
        roll = w.groupby("ticker")[f"q_{item}"].rolling(4, min_periods=4).sum().reset_index(level=0, drop=True)
        ok = consec.groupby(w["ticker"]).rolling(3, min_periods=3).sum().reset_index(level=0, drop=True) == 3
        ttm = roll.where(ok)
        if cpi is not None:
            real = (w[f"q_{item}"] / c_end).groupby(w["ticker"]).rolling(4, min_periods=4).sum() \
                .reset_index(level=0, drop=True)
            ttm = ttm.where(~adj, (real * c_end).where(ok))
        w[f"ttm_{item}"] = ttm
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


def _equity(last) -> float | None:
    eq = last.get("equity_parent")
    if eq is None or not np.isfinite(eq):
        eq = last.get("equity")
    return eq


def _ttm_net_income(last) -> float | None:
    ni = last.get("ttm_ni_parent")
    if ni is None or not np.isfinite(ni):
        ni = last.get("ttm_net_income")
    return ni


def value_ratios(last, mcap: float) -> dict[str, float]:
    """value_sn'in dort orani (B/M, E/P, S/P, EBIT/EV): son kullanilabilir ceyrek
    satiri (quarterly_table) ve piyasa degerinden. Panel ve canli skor ayni
    fonksiyonu kullanir (core/live_data.py::live_value_inputs)."""
    eq, ni = _equity(last), _ttm_net_income(last)
    # Eksik borc/nakit 0 sayilmaz (borcsuz sirket satiri 0 olarak raporlar);
    # bilinmeyen net borcla EV piyasa degerine esitlenip EBIT/EV sisiyordu.
    fd, cash = last.get("fin_debt"), last.get("cash")
    ev_val = (mcap + fd - cash) if fd is not None and cash is not None \
        and np.isfinite(fd) and np.isfinite(cash) else np.nan
    op = last.get("ttm_op_profit")
    return {
        "bm": eq / mcap if eq and eq > 0 else np.nan,
        "ep": ni / mcap if ni is not None and np.isfinite(ni) else np.nan,
        "sp": last.get("ttm_revenue") / mcap if last.get("ttm_revenue") else np.nan,
        "ey": (op / ev_val) if (op is not None and np.isfinite(op) and np.isfinite(ev_val) and ev_val > 0) else np.nan,
    }


def latest_value_ratios(ticker: str, bs: pd.DataFrame | None, inc: pd.DataFrame | None,
                        mcap: float | None) -> dict:
    """Canli: saglayicinin dondurdugu en son ceyrekle value_ratios (+ stmt_period).
    Saglayicidaki her ceyrek yayinlanmistir; tablo yoksa oranlar NaN."""
    out = {"bm": np.nan, "ep": np.nan, "sp": np.nan, "ey": np.nan, "stmt_period": None}
    long = statements_long(ticker, bs, inc)
    if long.empty or not mcap or mcap <= 0:
        return out
    q = quarterly_table(long)
    last = q.iloc[-1]  # period_end'e gore sirali
    return {**value_ratios(last, mcap), "stmt_period": last["period"]}


def fetch_statement(ticker: str, statement_type: str, last_n: int) -> pd.DataFrame | None:
    """Is Yatirim sanayi sablonu, ceyreklik (YTD) son last_n donem. borsapy
    ``get_financial_statements`` esdegeri, kartezyen join hatasi olmadan
    (merge_statement_batches). Panel (build_pit_panel) ve canli skor ayni cekimi kullanir."""
    from datetime import datetime

    from borsapy._providers.isyatirim import get_isyatirim_provider

    prov = get_isyatirim_provider()
    periods = prov._get_periods(datetime.now().year, True, count=last_n)
    step = prov._MAX_PERIODS_PER_CALL
    batches = []
    for i in range(0, len(periods), step):
        try:
            batches.append(prov._fetch_financial_table(
                symbol=ticker, financial_group=prov.FINANCIAL_GROUP_INDUSTRIAL,
                periods=periods[i:i + step], quarterly=True, statement_type=statement_type,
            ))
        except Exception:  # noqa: BLE001
            continue
    df = merge_statement_batches(batches)
    if df.empty:
        return None
    return df[sorted(df.columns, key=prov._period_sort_key, reverse=True)]


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
            eq, ni = _equity(last), _ttm_net_income(last)
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
                **value_ratios(last, mcap),
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
