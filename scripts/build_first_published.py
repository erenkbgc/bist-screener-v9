#!/usr/bin/env python3
"""Ilk yayinlanan KAP finansal tablo rakamlari (P3-1, docs/research/first_published_panel.md).

Is Yatirim TMS 29 doneminde her donemi ertesi yil raporunun onceki-donem kolonuyla
degistiriyor (docs/research/vendor_vs_kap_audit.md). Bu script likit finansal-disi
hisselerin "Finansal Rapor" bildirimlerini KAP'tan ceker (onbellek: data/research/
kap_reports/), donemi sayfadaki "Cari Dönem" tarihinden okur (yayin ayindan degil:
TMS 29 sure uzatmalari ayi kaydiriyor), konsolide raporu tercih eder ve her
(hisse, donem) icin ILK yayinin cari donem rakamlarini yazar.

    python scripts/build_first_published.py            # 2023-01..bugun yayinlari
    python scripts/build_first_published.py --parse-only

Cikti: data/research/first_published.parquet
  ticker, period, consolidated, disclosure_index, published_at, <kalemler> (KAP birimi)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_restatements import CACHE, kap_text  # noqa: E402
from audit_vendor_vs_kap import values  # noqa: E402

RESEARCH = ROOT / "data" / "research"
OUT = RESEARCH / "first_published.parquet"
START = "2023-01-01"
# pit_panel kalem adi -> KAP etiketleri (ilk eslesen, cari donem kolonu)
LABELS = {
    "total_assets": ("TOPLAM VARLIKLAR",),
    "equity_parent": ("Ana Ortaklığa Ait Özkaynaklar",),
    "equity": ("TOPLAM ÖZKAYNAKLAR", "Toplam Özkaynaklar"),
    "paid_in": ("Ödenmiş Sermaye",),
    "cash": ("Nakit ve Nakit Benzerleri",),
    "revenue": ("Hasılat",),
    "gross_profit": ("BRÜT KAR (ZARAR)", "Brüt Kar (Zarar)"),
    "op_profit": ("ESAS FAALİYET KARI (ZARARI)",),
    "ni_parent": ("Ana Ortaklık Payları",),
    "net_income": ("DÖNEM KARI (ZARARI)",),
}
DEBT = ("Kısa Vadeli Borçlanmalar", "Uzun Vadeli Borçlanmaların Kısa Vadeli Kısımları", "Uzun Vadeli Borçlanmalar")
_PERIOD = re.compile(r"Cari Dönem\|(\d\d)\.(\d\d)\.(20\d\d)")
_NATURE = re.compile(r"Niteliği\|[\s\\rn|]*(Konsolide Olmayan|Konsolide)")


def parse(txt: str) -> dict | None:
    m = _PERIOD.search(txt)
    if not m:
        return None
    d, mo, y = m.groups()
    if (d, mo) not in (("31", "03"), ("30", "06"), ("30", "09"), ("31", "12")):
        return None
    nat = _NATURE.search(txt)
    row = {"period": f"{y}Q{int(mo) // 3}",
           "consolidated": None if nat is None else nat.group(1) == "Konsolide"}
    for item, labels in LABELS.items():
        v = None
        for lab in labels:
            v = values(txt, lab)[0]
            if v is not None:
                break
        row[item] = v
    debt = [values(txt, lab)[0] for lab in DEBT]
    row["fin_debt"] = sum(x for x in debt if x is not None) if any(x is not None for x in debt) else None
    return row


def targets() -> pd.DataFrame:
    f = pd.read_parquet(RESEARCH / "factors_monthly.parquet")
    f = f[f["date"] >= "2023-06-01"]
    liq = f[f["tlvol60"] >= f.groupby("date")["tlvol60"].transform(lambda s: s.quantile(0.3))]["ticker"].unique()
    k = pd.read_parquet(RESEARCH / "kap_archive.parquet")
    k = k[(k["subject"] == "Finansal Rapor") & k["stock_code"].isin(liq) & (k["published_at"] >= START)]
    return k.sort_values("published_at")[["stock_code", "disclosure_index", "published_at"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parse-only", action="store_true")
    args = ap.parse_args()
    t = targets()
    rows, failed = [], 0
    for n, r in enumerate(t.itertuples(index=False), 1):
        f = CACHE / f"{int(r.disclosure_index)}.txt"
        if args.parse_only and not (f.exists() and f.stat().st_size > 0):
            continue
        try:
            txt = kap_text(int(r.disclosure_index))
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"HATA {r.stock_code} {r.disclosure_index}: {exc}", flush=True)
            continue
        p = parse(txt)
        if p:
            rows.append({"ticker": r.stock_code, "disclosure_index": int(r.disclosure_index),
                         "published_at": r.published_at, **p})
        if n % 100 == 0:
            print(f"{n}/{len(t)} parsed {len(rows)} failed {failed}", flush=True)
    df = pd.DataFrame(rows)
    # Donem basina: konsolide rapor varsa onun ilk yayini, yoksa ilk yayin
    df["_rank"] = df["consolidated"].map({True: 0, None: 1, False: 2})
    df = df.sort_values(["ticker", "period", "_rank", "published_at"])
    first = df.groupby(["ticker", "period"], as_index=False).first().drop(columns="_rank")
    first.to_parquet(OUT, index=False)
    print(f"{len(t)} bildirim, {len(df)} ayrisan, {len(first)} (hisse, donem); basarisiz {failed}. {OUT}")


if __name__ == "__main__":
    main()
