#!/usr/bin/env python3
"""Hangi sirketlerin rakamlari Is Yatirim'de TMS 29 ile yeniden ifade ediliyor?

docs/research/first_published_panel.md: Is Yatirim TMS 29 doneminde bir donemi, onu
onceki-donem kolonunda gosteren en son raporun birimine tasiyor (TUFE orani). TL
raporlayanlarda Q1-Q3 gelir tablosu kalemleri ertesi yil ayni ceyrek raporu gelince
x CPI(P+4)/CPI(P), yabanci fonksiyonel para birimli sirketlerde x 1.

P2-1 iyilestirmeleri (2026-11-22):
  - 2025Q2, 2024Q2, 2025Q1, 2024Q1 pencereleri denenir.
  - Konsolide/solo secimi toplam varliklarin Is Yatirim ile eslesmesine gore yapilir
    (bazi GYO'larda Is Yatirim solo tabloyu tutar: AGYO, ALGYO, AVGYO, HLGYO, RYGYO, TRGYO).
  - Tek bir kalemde (orn. Hasilat) dipnot veya yeniden siniflandirma sapmasi olursa
    tum gelir kalemleri (Hasilat, Ana Ortaklik Paylari, Faaliyet Kari) birlikte degerlendirilir.
  - Pay grubu dagitimi yapilan sirketlerde (KRDMA/KRDMB/KRDMD) ara donem bilanco
    toplam varlik orani (v_ta / k_ta) ile normalize edilir.
  - Ozel hesap donemli sirketler (01.04 -> +1 ceyrek: BORSK, MARTI, MRGYO; 01.07 -> +2 ceyrek:
    BALSU, MERKO) gelir tablosu baslangic tarihinden tespit edilir; yalnizca Q4'te yeniden
    ifade edilenler (MARTI, MRGYO) ``reexpressed_q4_only`` olarak siniflandirilir.

    python scripts/classify_reexpression.py
    python scripts/classify_reexpression.py --only-unknown
Cikti: data/research/reexpression_class.parquet
  (ticker, period, v_period, ratio, factor, cls, consolidated, fy_shift_q, note)
"""
from __future__ import annotations

import argparse
import math
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_restatements import kap_text  # noqa: E402
from audit_vendor_vs_kap import vendor  # noqa: E402
from build_first_published import parse, targets  # noqa: E402
from core import pit_panel  # noqa: E402
from rebuild_panels_first_published import _shift_period  # noqa: E402

RESEARCH = ROOT / "data" / "research"
OUT = RESEARCH / "reexpression_class.parquet"
TOL = 0.01
WINDOWS = (
    ("2025Q2", "2025-07-01", "2025-10-15"),
    ("2024Q2", "2024-07-01", "2024-10-15"),
    ("2025Q1", "2025-04-01", "2025-07-15"),
    ("2024Q1", "2024-04-01", "2024-07-15"),
)
Q4_CHECK_WINDOWS = (
    ("2025Q1", "2025-04-15", "2025-07-15"),  # Mart sonu yillik (v_period=2024Q4)
    ("2026Q1", "2026-04-15", "2026-07-15"),  # Mart sonu yillik (v_period=2025Q4)
)
ITEMS = (
    ("revenue", "Satış Gelirleri"),
    ("ni_parent", "Ana Ortaklık Payları"),
    ("op_profit", "FAALİYET KARI (ZARARI)"),
)
_INC_START = re.compile(r"01\.(\d\d)\.20\d\d\s*-\s*\d\d\.\d\d\.20\d\d")


def detect_fy_shift_q(txt: str) -> int:
    """Gelir tablosu donem baslangicindan ozel hesap donemi kaymasini (ceyrek) bulur."""
    m = _INC_START.search(txt)
    if not m:
        return 0
    return {"01": 0, "04": 1, "07": 2}.get(m.group(1), 0)


def _vendor_latest(raw: dict) -> str | None:
    inc = raw.get("inc")
    if inc is None or inc.empty:
        return None
    return max(str(c) for c in inc.columns)


def classify_one(raw: dict, fp: dict, v_period: str, factor: float,
                 is_q4: bool = False) -> tuple[str, float | None, str]:
    """Tek bir KAP raporu ile Is Yatirim tablosunu karsilastirir -> (cls, ratio, note)."""
    if not np.isfinite(factor) or factor <= 0:
        return "unknown", None, "no_factor"
    v_ta, k_ta = vendor(raw, "bs", "TOPLAM VARLIKLAR", v_period), fp.get("total_assets")
    if not v_ta or not k_ta or v_ta <= 0 or k_ta <= 0:
        return "unknown", None, "missing_ta"

    scale = 10.0 ** round(math.log10(v_ta / k_ta))
    r_ta = v_ta / (k_ta * scale)

    if is_q4:
        # Q4'te bilanco toplam varliklari da gelir kalemleriyle ayni carpanla yeniden ifade edilir
        ta_cls = ("reexpressed" if abs(r_ta / factor - 1) < TOL
                  else ("not_reexpressed" if abs(r_ta - 1) < TOL else "other"))
        votes = {ta_cls: [r_ta]} if ta_cls != "other" else {}
        for item, label in ITEMS:
            v, k = vendor(raw, "inc", label, v_period), fp.get(item)
            if v and k:
                r = v / (k * scale)
                c_i = ("reexpressed" if abs(r / factor - 1) < TOL
                       else ("not_reexpressed" if abs(r - 1) < TOL else "other"))
                if c_i != "other":
                    votes.setdefault(c_i, []).append(r)
        if ta_cls in ("reexpressed", "not_reexpressed") and len(votes.get(ta_cls, [])) >= 2:
            other = "not_reexpressed" if ta_cls == "reexpressed" else "reexpressed"
            if not votes.get(other):
                return ta_cls, float(np.median(votes[ta_cls])), "q4_match"
        return "unknown", r_ta, "q4_mismatch"

    # Ara donem (Q1-Q3): bilanco yeniden ifade edilmez; v_ta / (k_ta * scale) ~ 1 (veya pay grubu orani)
    share_class_alloc = False
    if abs(r_ta - 1.0) <= 0.02:
        denom_mult = scale
    elif 0.05 <= v_ta / k_ta <= 1.0:
        # Pay grubu oransal dagitimi (orn. KRDMA/KRDMB/KRDMD: 0.2108 / 0.1048 / 0.6844)
        denom_mult = v_ta / k_ta
        share_class_alloc = True
    else:
        return "unknown", r_ta, "ta_mismatch"

    votes: dict[str, list[float]] = {"reexpressed": [], "not_reexpressed": []}
    ratios: list[float] = []
    for item, label in ITEMS:
        v, k = vendor(raw, "inc", label, v_period), fp.get(item)
        if v and k:
            r = v / (k * denom_mult)
            ratios.append(r)
            if abs(r / factor - 1) < TOL:
                votes["reexpressed"].append(r)
            elif abs(r - 1) < TOL:
                votes["not_reexpressed"].append(r)

    min_votes = 2 if (share_class_alloc or len(ratios) >= 2) else 1
    for label_cls, opp in (("reexpressed", "not_reexpressed"), ("not_reexpressed", "reexpressed")):
        if len(votes[label_cls]) >= min_votes and len(votes[opp]) == 0:
            note = "share_class_ta_norm" if share_class_alloc else ("multi_item" if len(votes[label_cls]) >= 2 else "single_item")
            return label_cls, float(np.median(votes[label_cls])), note
        if len(votes[label_cls]) >= 2 and len(votes[label_cls]) > len(votes[opp]):
            return label_cls, float(np.median(votes[label_cls])), "majority_item"
    # Yedek: bilanco birebir eslesmisse ve Hasilat TUFE carpanina binde 1 icinde uyuyorsa
    # (kar kalemlerinde 2026 yeniden siniflandirmasi olan EGGUB/LRSHO/REEDR/SAFKR/TLMAN gibi)
    if not share_class_alloc and not votes["not_reexpressed"] and len(votes["reexpressed"]) == 1:
        v_rev, k_rev = vendor(raw, "inc", "Satış Gelirleri", v_period), fp.get("revenue")
        if v_rev and k_rev:
            r_rev = v_rev / (k_rev * denom_mult)
            if abs(r_rev / factor - 1) < 0.001:
                return "reexpressed", r_rev, "exact_rev_cpi"
    return "unknown", (ratios[0] if ratios else None), "item_mismatch"


def _ta_distance(raw: dict, fp: dict, v_period: str) -> float:
    v_ta, k_ta = vendor(raw, "bs", "TOPLAM VARLIKLAR", v_period), fp.get("total_assets")
    if not v_ta or not k_ta or v_ta <= 0 or k_ta <= 0:
        return 999.0
    scale = 10.0 ** round(math.log10(v_ta / k_ta))
    return abs(v_ta / (k_ta * scale) - 1.0)


def classify_ticker(tk: str, raw: dict, sub_t: pd.DataFrame, cpi: pd.Series) -> dict | None:
    c = lambda p: cpi.get(pit_panel.period_end(p).to_period("M"), np.nan)  # noqa: E731
    latest = _vendor_latest(raw)
    if not latest:
        return None
    inc_cols = set(str(col) for col in raw["inc"].columns)

    best_fallback = None
    for period, lo, hi in WINDOWS:
        d = sub_t[(sub_t["published_at"] >= lo) & (sub_t["published_at"] < hi)]
        pages = []
        for idx in d["disclosure_index"]:
            try:
                txt = kap_text(int(idx))
                p = parse(txt)
            except Exception as exc:  # noqa: BLE001
                print(f"HATA {tk} {idx}: {exc}", flush=True)
                continue
            if p and p["period"] == period:
                p["fy_shift_q"] = detect_fy_shift_q(txt)
                pages.append(p)
        if not pages:
            continue

        # Her sayfa icin vendor donemini (ozel hesap donemi dahil) ve TA yakinligini hesapla
        scored_pages = []
        for p in pages:
            sh = p["fy_shift_q"]
            v_per = _shift_period(period, -sh)
            dist = _ta_distance(raw, p, v_per)
            cons_rank = {True: 0, None: 1, False: 2}[p["consolidated"]]
            scored_pages.append((dist, cons_rank, v_per, p))
        scored_pages.sort(key=lambda x: (round(x[0], 4), x[1]))

        for _, _, v_per, p in scored_pages:
            sh = p["fy_shift_q"]
            if v_per not in inc_cols:
                continue
            is_q4 = v_per.endswith("Q4")
            nxt_v = f"{int(v_per[:4]) + 1}{v_per[4:]}"
            if is_q4:
                last_v = min(nxt_v, latest)
                if last_v <= v_per:
                    continue
                fac = c(_shift_period(last_v, sh)) / c(period)
            else:
                if nxt_v not in inc_cols:
                    continue
                fac = c(_shift_period(nxt_v, sh)) / c(period)
            cls, ratio, note = classify_one(raw, p, v_per, fac, is_q4=is_q4)
            res = {
                "ticker": tk, "period": period, "v_period": v_per,
                "ratio": ratio, "factor": float(fac) if np.isfinite(fac) else np.nan,
                "cls": cls, "consolidated": p["consolidated"],
                "fy_shift_q": sh, "note": note,
            }
            if best_fallback is None:
                best_fallback = res
            if cls != "unknown":
                # Ozel hesap donemli ve ara donem 'not_reexpressed' ise (orn. MARTI, MRGYO)
                # yillik (Q4) donemde yeniden ifade edilip edilmedigini kontrol et
                if cls == "not_reexpressed" and sh > 0 and not is_q4:
                    q4_res = _check_special_fy_q4(tk, raw, sub_t, sh, latest, c)
                    if q4_res is not None:
                        return q4_res
                return res
    return best_fallback


def _check_special_fy_q4(tk: str, raw: dict, sub_t: pd.DataFrame, sh: int,
                         latest: str, c) -> dict | None:
    """Ozel hesap doneminde ara donemler 1.0 iken Q4'un yeniden ifade edilip edilmedigini dener."""
    inc_cols = set(str(col) for col in raw["inc"].columns)
    for kap_per, lo, hi in Q4_CHECK_WINDOWS:
        v_per = _shift_period(kap_per, -sh)
        if not v_per.endswith("Q4") or v_per not in inc_cols:
            continue
        nxt_v = f"{int(v_per[:4]) + 1}{v_per[4:]}"
        last_v = min(nxt_v, latest)
        if last_v <= v_per:
            continue
        fac = c(_shift_period(last_v, sh)) / c(kap_per)
        d = sub_t[(sub_t["published_at"] >= lo) & (sub_t["published_at"] < hi)]
        for idx in d["disclosure_index"]:
            try:
                p = parse(kap_text(int(idx)))
            except Exception:  # noqa: BLE001
                continue
            if not p or p["period"] != kap_per:
                continue
            cls, ratio, _ = classify_one(raw, p, v_per, fac, is_q4=True)
            if cls == "reexpressed":
                return {
                    "ticker": tk, "period": kap_per, "v_period": v_per,
                    "ratio": ratio, "factor": float(fac),
                    "cls": "reexpressed_q4_only", "consolidated": p["consolidated"],
                    "fy_shift_q": sh, "note": "special_fy_q4_only",
                }
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-unknown", action="store_true",
                    help="yalnizca mevcut reexpression_class.parquet'te unknown olanlari yeniden dener")
    args = ap.parse_args()
    cpi = pit_panel.cpi_index(pd.read_parquet(RESEARCH / "macro_monthly.parquet")["cpi_mom"])
    t = targets()
    existing = pd.read_parquet(OUT) if (args.only_unknown and OUT.exists()) else None
    if existing is not None:
        keep = existing[existing["cls"] != "unknown"].copy()
        if "v_period" not in keep.columns:
            keep["v_period"] = keep["period"]
        if "fy_shift_q" not in keep.columns:
            keep["fy_shift_q"] = 0
        if "note" not in keep.columns:
            keep["note"] = "existing"
        tickers = sorted(existing.loc[existing["cls"] == "unknown", "ticker"].unique())
        rows = keep.to_dict("records")
    else:
        tickers = sorted(t["stock_code"].unique())
        rows = []

    for n, tk in enumerate(tickers, 1):
        raw_path = RESEARCH / "raw" / f"{tk}.pkl"
        if not raw_path.exists():
            continue
        raw = pickle.loads(raw_path.read_bytes())
        res = classify_ticker(tk, raw, t[t["stock_code"] == tk], cpi)
        if res:
            rows.append(res)
        if n % 25 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
            pd.DataFrame(rows).sort_values("ticker").to_parquet(OUT, index=False)

    df = pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)
    df.to_parquet(OUT, index=False)
    print(df["cls"].value_counts().to_dict(), f"-> {OUT}")


if __name__ == "__main__":
    main()
