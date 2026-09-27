"""sector_rotation: BIST sektor endeksleri icin Goreli Rotasyon Grafigi (RRG).

Amac: "herkesin girdigi" (Leading) degil, goreli gucu HENUZ dusukken ivmesi
pozitife donen (Improving) sektorleri erken isaretlemek.

Yontem (JdK RS-Ratio/RS-Momentum'un acik kaynak yaklasimi; orijinal formul
tescillidir, bu bir yaklasiktir):
  haftalik kapanis (Cuma), benchmark XU100
  RS          = 100 * sektor / XU100
  RS-Ratio    = 100 + (RS - ort_N(RS)) / std_N(RS)                  N = 26 hafta
  RS-Momentum = 100 + (d_k - ort_N(d_k)) / std_N(d_k),  d_k = RS-Ratio(t) - RS-Ratio(t-k), k = 4
Kadranlar: Leading (R>100, M>100), Weakening (R>100, M<100),
           Lagging (R<100, M<100), Improving (R<100, M>100).
future_star: son FRESH_WEEKS haftada Lagging'den Improving'e gecmis sektor.

BILGI amaclidir; final_score'a bagli DEGIL (priors_are_disclosed: pencere
uzunluklari kalibre edilmedi, BIST uzerinde isabet olculmedi).
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

BENCHMARK = "XU100"
RATIO_WINDOW_WEEKS = 26
MOMENTUM_LAG_WEEKS = 4
FRESH_WEEKS = 3
TAIL_WEEKS = 5

# config/fintables_ticker_sektor.json sektor adi -> BIST sektor endeksi.
# Eslesmeyen/BILINMIYOR sektorler supersector'e (XUSIN/XUHIZ) duser.
SECTOR_INDEX_MAP: dict[str, str] = {
    "Bankacılık": "XBANK",
    "Holding": "XHOLD",
    "Girişim Sermayesi Yat. Ort.": "XHOLD",
    "Gıda ve İçecek": "XGIDA",
    "Tarım, Hayvancılık, Balıkçılık": "XGIDA",
    "Kimya ve Plastik": "XKMYA",
    "Ana Metal": "XMANA",
    "Metal Eşya ve Makine": "XMESY",
    "Otomotiv": "XMESY",
    "Otomotiv Yan Sanayi": "XMESY",
    "Dayanıklı Tüketim Ürünleri": "XMESY",
    "Savunma": "XMESY",
    "Taş, Toprak, Çimento": "XTAST",
    "Cam, Seramik, Porselen": "XTAST",
    "Tekstil, Giyim ve Deri": "XTEKS",
    "Kağıt ve Kağıt Ürünleri": "XKAGT",
    "Enerji Üretim ve Dağıtım": "XELKT",
    "İnşaat": "XINSA",
    "Turizm": "XTRZM",
    "Ulaştırma": "XULAS",
    "Servis Taşımacılığı ve Araç Kiralama": "XULAS",
    "Haberleşme": "XILTM",
    "Bilişim ve Yazılım": "XBLSM",
    "Gıda Perakendeciliği": "XTCRT",
    "Toptan ve Perakende Ticaret": "XTCRT",
    "Giyim, Tekstil ve Deri Ürünleri Perakendeciliği": "XTCRT",
    "Teknolojik Ürün Ticareti": "XTCRT",
    "Sigorta": "XSGRT",
    "Emeklilik": "XSGRT",
    "Gayrimenkul": "XGMYO",
    "Faktoring": "XFINK",
    "Finansal Kiralama": "XFINK",
    "Tasarruf Finansman": "XFINK",
    "Aracı Kurum": "XAKUR",
    "Spor": "XSPOR",
    "Madencilik ve Taş Ocakçılığı": "XMADN",
    "Menkul Kıymet Yat. Ort.": "XYORT",
}
FALLBACK_INDICES = ("XUSIN", "XUHIZ")


def sector_index_for(sector: str | None, supersector: str | None) -> tuple[str | None, str]:
    """(endeks kodu, kaynak) -- kaynak 'sector' veya 'supersector_fallback'."""
    code = SECTOR_INDEX_MAP.get(sector or "")
    if code:
        return code, "sector"
    if supersector in FALLBACK_INDICES:
        return supersector, "supersector_fallback"
    return None, "unmapped"


def _weekly(closes: pd.Series) -> pd.Series:
    s = closes.dropna().sort_index()
    return s.resample("W-FRI").last().dropna()


def quadrant(rs_ratio: float, rs_momentum: float) -> str:
    if rs_ratio >= 100:
        return "Leading" if rs_momentum >= 100 else "Weakening"
    return "Improving" if rs_momentum >= 100 else "Lagging"


def compute_rrg(sector_closes: pd.Series, bench_closes: pd.Series,
                ratio_window: int = RATIO_WINDOW_WEEKS,
                momentum_lag: int = MOMENTUM_LAG_WEEKS) -> dict | None:
    """Gunluk kapanis serilerinden (DatetimeIndex) son haftanin RRG noktasi.
    Yetersiz gecmiste None doner (sahte bir kadran uretilmez)."""
    sec, ben = _weekly(sector_closes), _weekly(bench_closes)
    df = pd.concat({"s": sec, "b": ben}, axis=1, join="inner").dropna()
    if len(df) < 2 * ratio_window + momentum_lag:
        return None
    rs = 100.0 * df["s"] / df["b"]
    ratio = 100.0 + (rs - rs.rolling(ratio_window).mean()) / rs.rolling(ratio_window).std()
    d = ratio - ratio.shift(momentum_lag)
    mom = 100.0 + (d - d.rolling(ratio_window).mean()) / d.rolling(ratio_window).std()
    pts = pd.concat({"r": ratio, "m": mom}, axis=1).dropna()
    if len(pts) < FRESH_WEEKS + 1:
        return None
    quads = [quadrant(r, m) for r, m in zip(pts["r"], pts["m"])]
    current = quads[-1]
    weeks_in = 1
    for q in reversed(quads[:-1]):
        if q != current:
            break
        weeks_in += 1
    prior = next((q for q in reversed(quads[:-weeks_in])), None)
    future_star = current == "Improving" and weeks_in <= FRESH_WEEKS and prior == "Lagging"
    tail = pts.tail(TAIL_WEEKS)
    return {
        "week_end": pts.index[-1].date().isoformat(),
        "rs_ratio": round(float(pts["r"].iloc[-1]), 2),
        "rs_momentum": round(float(pts["m"].iloc[-1]), 2),
        "quadrant": current,
        "weeks_in_quadrant": weeks_in,
        "prior_quadrant": prior,
        "future_star": bool(future_star),
        "tail": [[round(float(r), 2), round(float(m), 2)] for r, m in zip(tail["r"], tail["m"])],
    }


def _live_enabled() -> bool:
    return os.environ.get("BIST_DATA_MODE", "mock").strip().lower() == "live"


def _index_closes(code: str, as_of_date: str) -> pd.Series | None:
    import borsapy as bp
    try:
        h = bp.Index(code).history(period="2y")
    except Exception:
        return None
    if h is None or h.empty:
        return None
    s = h["Close"].astype(float)
    s.index = pd.to_datetime(s.index).tz_localize(None)
    cutoff = datetime.strptime(as_of_date, "%Y-%m-%d")
    return s[s.index <= cutoff]  # ileriye bakis yok


def compute_sector_rotation(as_of_date: str, codes: list[str] | None = None) -> dict[str, dict]:
    """Canli modda her sektor endeksi icin RRG. Mock modda bos doner: sentetik
    endeks serisiyle uydurma bir rotasyon sinyali uretilmez."""
    if not _live_enabled():
        return {}
    bench = _index_closes(BENCHMARK, as_of_date)
    if bench is None:
        return {}
    codes = codes or sorted(set(SECTOR_INDEX_MAP.values()) | set(FALLBACK_INDICES))
    out: dict[str, dict] = {}
    for code in codes:
        closes = _index_closes(code, as_of_date)
        if closes is None:
            continue
        rrg = compute_rrg(closes, bench)
        if rrg:
            out[code] = rrg
    return out


def annotate_candidates(candidates: list[dict], rotation: dict[str, dict]) -> None:
    for c in candidates:
        code, source = sector_index_for(c.get("sector"), c.get("supersector"))
        rrg = rotation.get(code) if code else None
        c["sector_index"] = code
        c["sector_index_source"] = source
        c["rrg_quadrant"] = rrg["quadrant"] if rrg else None
        c["rrg_future_star"] = bool(rrg and rrg["future_star"])


def persist(as_of_date: str, rotation: dict[str, dict]) -> None:
    if not rotation:
        return
    from core import db
    rows = [{"as_of_date": as_of_date, "index_code": k, "week_end": v["week_end"],
             "rs_ratio": v["rs_ratio"], "rs_momentum": v["rs_momentum"], "quadrant": v["quadrant"],
             "weeks_in_quadrant": v["weeks_in_quadrant"], "future_star": int(v["future_star"])}
            for k, v in rotation.items()]
    conn = db.get_connection()
    try:
        conn.executemany(
            """INSERT INTO sector_rotation (as_of_date, index_code, week_end, rs_ratio, rs_momentum,
               quadrant, weeks_in_quadrant, future_star)
               VALUES (:as_of_date, :index_code, :week_end, :rs_ratio, :rs_momentum, :quadrant,
                       :weeks_in_quadrant, :future_star)
               ON CONFLICT(as_of_date, index_code) DO UPDATE SET
                 week_end=excluded.week_end, rs_ratio=excluded.rs_ratio,
                 rs_momentum=excluded.rs_momentum, quadrant=excluded.quadrant,
                 weeks_in_quadrant=excluded.weeks_in_quadrant, future_star=excluded.future_star""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
