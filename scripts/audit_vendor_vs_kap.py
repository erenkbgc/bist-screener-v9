#!/usr/bin/env python3
"""Veri saglayicisi (Is Yatirim) ile KAP rakamlari: value_sn girdileri (denetim, test degil).

docs/research/vendor_vs_kap_audit.md. scripts/audit_restatements.py'nin genisletilmisi:
  - kalemler: hasilat, esas faaliyet kari, ana ortaklik net kari, toplam varliklar,
    ana ortaklik ozkaynagi, nakit, odenmis sermaye, finansal borc;
  - her (hisse, donem) icin iki KAP rakami: ILK yayin (o donemin ilk "Finansal Rapor"u) ve
    DUZELTILMIS (bir yil sonraki ayni ceyrek raporunun onceki donem kolonu). Gelir
    tablosu kalemleri her ceyrek icin, bilanco kalemleri yalnizca Q4 icin duzeltilmis
    rakamla karsilastirilabilir (bilanco onceki kolonu onceki yil sonudur).
Siniflar: match_first (ilk yayinla ayni), restated (ilkinden farkli, duzeltilmisle ayni),
vendor_only (ikisinden de farkli), missing.

    python scripts/audit_vendor_vs_kap.py
"""
from __future__ import annotations

import json
import pickle
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_restatements import kap_text, parse_number, period_of, unit_gap  # noqa: E402
from research_long_term import load  # noqa: E402

RESEARCH = ROOT / "data" / "research"
SEED = 20261025
N_SAMPLE = 80
TOL = 0.005
# (Is Yatirim satiri, tablo, KAP etiketleri, toplanacak mi)
ITEMS = {
    "revenue": ("Satış Gelirleri", "inc", ("Hasılat",), False),
    "op_profit": ("FAALİYET KARI (ZARARI)", "inc", ("ESAS FAALİYET KARI (ZARARI)",), False),
    "ni_parent": ("Ana Ortaklık Payları", "inc", ("Ana Ortaklık Payları",), False),
    "total_assets": ("TOPLAM VARLIKLAR", "bs", ("TOPLAM VARLIKLAR",), False),
    "equity_parent": ("Ana Ortaklığa Ait Özkaynaklar", "bs", ("Ana Ortaklığa Ait Özkaynaklar",), False),
    "cash": ("Nakit ve Nakit Benzerleri", "bs", ("Nakit ve Nakit Benzerleri",), False),
    "paid_in": ("Ödenmiş Sermaye", "bs", ("Ödenmiş Sermaye",), False),
}
# Finansal borc: KAP'ta borclanmalar ve kiralama ayri satirlar; Is Yatirim'in iki
# "Finansal Borçlar" satirinin toplami ile iki tanim denenir.
DEBT_BORROW = ("Kısa Vadeli Borçlanmalar", "Uzun Vadeli Borçlanmaların Kısa Vadeli Kısımları", "Uzun Vadeli Borçlanmalar")
INCOME = {k for k, v in ITEMS.items() if v[1] == "inc"}


def values(txt: str, label: str) -> tuple[float | None, float | None]:
    """Etiketten sonraki (cari, onceki) donem sayilari; dipnot referansi atlanir."""
    for m in re.finditer(r"\|" + re.escape(label) + r"\|", txt):
        nums = [v for v in (parse_number(t) for t in txt[m.end(): m.end() + 500].split("|")[:9]) if v is not None]
        if len(nums) >= 3 and float(nums[0]).is_integer() and 0 <= nums[0] < 100:
            nums = nums[1:]
        if nums:
            return nums[0], (nums[1] if len(nums) > 1 else None)
    return None, None


def debt_values(txt: str) -> tuple[float | None, float | None]:
    cur = prev = 0.0
    found = False
    for lab in DEBT_BORROW:
        c, p = values(txt, lab)
        if c is not None:
            found = True
            cur += c
            prev += p or 0.0
    return (cur, prev) if found else (None, None)


def vendor(raw: dict, table: str, label: str, period: str, sum_dupes: bool = False) -> float | None:
    tab = raw.get(table)
    if tab is None or period not in tab.columns:
        return None
    idx = pd.Index([str(i).strip() for i in tab.index])
    s = pd.to_numeric(tab.loc[idx == label, period], errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.sum() if sum_dupes else s.iloc[0])


def classify(v: float | None, first: float | None, restated: float | None, scale: float) -> str:
    if v is None or first is None:
        return "missing"
    def same(a, b):
        return b is not None and (abs(a - b * scale) <= TOL * max(abs(b * scale), 1.0))
    if same(v, first):
        return "match_first"
    if restated is not None and same(v, restated):
        return "restated"
    return "vendor_only" if restated is not None else "differs_no_restated"


def next_year(period: str) -> str:
    return f"{int(period[:4]) + 1}{period[4:]}"


def main() -> None:
    panel = load()
    tickers = {t for t in panel["ticker"].unique() if (RESEARCH / "raw" / f"{t}.pkl").exists()}
    k = pd.read_parquet(RESEARCH / "kap_archive.parquet")
    k = k[(k["subject"] == "Finansal Rapor") & k["stock_code"].isin(tickers)].copy()
    k["period"] = k["published_at"].map(period_of)
    k = k.dropna(subset=["period"]).sort_values("published_at")
    first = k.groupby(["stock_code", "period"], as_index=False).first()
    key = set(zip(first["stock_code"], first["period"]))
    has_next = pd.Series([(s, next_year(p)) in key for s, p in zip(first["stock_code"], first["period"])],
                         index=first.index)
    first = first[first["period"].between("2014Q1", "2025Q2") & has_next]
    sample = first.sample(n=N_SAMPLE, random_state=SEED)
    all_first = k.groupby(["stock_code", "period"])["disclosure_index"].first().to_dict()

    rows = []
    for _, r in sample.iterrows():
        tk, per = r["stock_code"], r["period"]
        raw = pickle.loads((RESEARCH / "raw" / f"{tk}.pkl").read_bytes())
        t1 = kap_text(int(r["disclosure_index"]))
        t2 = kap_text(int(all_first[(tk, next_year(per))]))
        ta_v = vendor(raw, "bs", "TOPLAM VARLIKLAR", per)
        ta_k = values(t1, "TOPLAM VARLIKLAR")[0]
        gap = unit_gap(ta_v, ta_k) if ta_v and ta_k else None
        row = {"ticker": tk, "period": per, "first_index": int(r["disclosure_index"])}
        if gap is None or abs(gap[1]) > 0.10:
            row["status"] = "unit_or_currency_unmatched"
            rows.append(row)
            continue
        scale = 10.0 ** gap[0]
        for name, (lab, table, kap_labels, _) in ITEMS.items():
            v = vendor(raw, table, lab, per)
            f1 = r1 = None
            for kl in kap_labels:
                f1 = values(t1, kl)[0]
                if f1 is not None:
                    break
            if name in INCOME or per.endswith("Q4"):
                for kl in kap_labels:
                    r1 = values(t2, kl)[1]
                    if r1 is not None:
                        break
            row[name] = classify(v, f1, r1, scale)
        v = vendor(raw, "bs", "Finansal Borçlar", per, sum_dupes=True)
        f1 = debt_values(t1)[0]
        r1 = debt_values(t2)[1] if per.endswith("Q4") else None
        row["fin_debt"] = classify(v, f1, r1, scale)
        rows.append(row)
        print(tk, per, {c: row.get(c) for c in [*ITEMS, "fin_debt"]}, flush=True)

    df = pd.DataFrame(rows)
    items = [*ITEMS, "fin_debt"]
    ok = df[df.get("status").isna()] if "status" in df else df
    summary = {c: ok[c].value_counts().to_dict() for c in items if c in ok}
    result = {"as_of": date.today().isoformat(), "n_sample": len(df),
              "unit_or_currency_unmatched": int((df.get("status") == "unit_or_currency_unmatched").sum()),
              "summary": summary, "rows": df.to_dict("records")}
    out = ROOT / "data" / "reports" / f"audit_vendor_vs_kap_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(json.dumps({k: result[k] for k in ("n_sample", "unit_or_currency_unmatched", "summary")}, indent=1, ensure_ascii=False))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
