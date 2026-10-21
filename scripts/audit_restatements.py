#!/usr/bin/env python3
"""Geriye donuk duzeltme denetimi (docs/plan_2026-10-21.md P2-5).

Soru: veri saglayicisinin (Is Yatirim, data/research/raw/*.pkl) eski ceyrekler icin
verdigi rakamlar, sirketin KAP'ta ILK yayinladigi rakamlarla ayni mi? Fark varsa
backtest, karar aninda bilinmeyen (sonradan duzeltilmis) veriyi kullanmis olur.

Orneklem: 2014-2022 arasi finansal olmayan panel hisselerinin "Finansal Rapor"
bildirimleri; her (hisse, donem) icin ilk yayin; sabit tohumla 60 adet. Donem,
yayin ayindan: Sub-Nis -> onceki yil Q4, May -> Q1, Tem-Agu -> Q2, Eki-Kas -> Q3.
Karsilastirilan kalemler: TOPLAM VARLIKLAR ve DONEM KARI (ZARARI) (ikisi de
kumulatif). Birim farki (TL / bin TL / milyon TL) 10'un kuvveti olarak ayiklanir;
toplam varliklari 10'un kuvvetiyle eslesmeyen raporlar (USD raporlayanlar vb.)
ayri sayilir.

    python scripts/audit_restatements.py
"""
from __future__ import annotations

import json
import math
import pickle
import re
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from research_long_term import load  # noqa: E402

RESEARCH = ROOT / "data" / "research"
CACHE = RESEARCH / "kap_reports"
SEED = 20261021
N_SAMPLE = 60
TOL = 0.005
RESTATE_BAND = 0.10  # 10'un kuvvetine %10 icinde: ayni para birimi, rakam degismis
ITEMS = {"total_assets": ("TOPLAM VARLIKLAR", "bs"), "net_income": ("DÖNEM KARI (ZARARI)", "inc")}
KAP_LABELS = {"total_assets": ("TOPLAM VARLIKLAR", "TOPLAM AKTİFLER", "Toplam Varlıklar"),
              "net_income": ("DÖNEM KARI (ZARARI)", "DÖNEM KARI/ZARARI", "Dönem Karı (Zararı)",
                             "DÖNEM NET KARI (ZARARI)", "DÖNEM NET KARI/ZARARI")}
_NUM = re.compile(r"^\(?-?[\d.]+(,\d+)?\)?$")


def period_of(ts: pd.Timestamp) -> str | None:
    m, y = ts.month, ts.year
    if m in (2, 3, 4):
        return f"{y - 1}Q4"
    if m == 5:
        return f"{y}Q1"
    if m in (7, 8):
        return f"{y}Q2"
    if m in (10, 11):
        return f"{y}Q3"
    return None


def parse_number(tok: str) -> float | None:
    tok = tok.strip()
    if not _NUM.match(tok):
        return None
    neg = tok.startswith("(") or tok.startswith("-")
    v = float(tok.strip("()-").replace(".", "").replace(",", "."))
    return -v if neg else v


def kap_text(index: int) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{index}.txt"
    if f.exists():
        return f.read_text(encoding="utf-8")
    raw = requests.get(f"https://www.kap.org.tr/tr/Bildirim/{index}",
                       headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
    raw = raw.replace("\\u003c", "<").replace("\\u003e", ">").replace('\\"', '"')
    txt = re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", raw))
    f.write_text(txt, encoding="utf-8")
    time.sleep(1.0)
    return txt


def first_value(txt: str, labels: tuple[str, ...]) -> float | None:
    """Etiketten sonraki cari donem sayisi. Dipnot referansi (100'den kucuk tamsayi ve
    ardindan baska sayi) atlanir."""
    for label in labels:
        for m in re.finditer(r"\|" + re.escape(label) + r"\|", txt):
            nums = [v for v in (parse_number(t) for t in txt[m.end(): m.end() + 500].split("|")[:8]) if v is not None]
            if len(nums) >= 2 and float(nums[0]).is_integer() and 0 <= nums[0] < 100:
                nums = nums[1:]
            if nums:
                return nums[0]
    return None


def unit_gap(provider: float, kap: float) -> tuple[int, float] | None:
    """(10'un kuvveti, o kuvvete gore goreli fark); isaret farkli veya sifirsa None."""
    if provider == 0 or kap == 0 or (provider > 0) != (kap > 0):
        return None
    k = round(math.log10(abs(provider / kap)))
    return k, provider / (kap * 10 ** k) - 1


def main() -> None:
    panel = load()
    tickers = {t for t in panel["ticker"].unique() if (RESEARCH / "raw" / f"{t}.pkl").exists()}
    k = pd.read_parquet(RESEARCH / "kap_archive.parquet")
    k = k[(k["subject"] == "Finansal Rapor") & k["stock_code"].isin(tickers)
          & (k["published_at"].dt.year.between(2014, 2022))].copy()
    k["period"] = k["published_at"].map(period_of)
    k = k.dropna(subset=["period"]).sort_values("published_at")
    first = k.groupby(["stock_code", "period"], as_index=False).first()
    sample = first.sample(n=N_SAMPLE, random_state=SEED)

    rows = []
    for _, r in sample.iterrows():
        d = pickle.loads((RESEARCH / "raw" / f"{r['stock_code']}.pkl").read_bytes())
        txt = kap_text(int(r["disclosure_index"]))
        row = {"ticker": r["stock_code"], "period": r["period"], "disclosure_index": int(r["disclosure_index"]),
               "published_at": str(r["published_at"])}
        for name, (label, table) in ITEMS.items():
            tab = d.get(table)
            prov = None
            if tab is not None and label in tab.index and r["period"] in tab.columns:
                s = tab.loc[label, r["period"]]
                prov = float(s.iloc[0] if isinstance(s, pd.Series) else s)
            row[f"{name}_provider"] = prov
            row[f"{name}_kap"] = first_value(txt, KAP_LABELS[name])
        ta_p, ta_k = row["total_assets_provider"], row["total_assets_kap"]
        ni_p, ni_k = row["net_income_provider"], row["net_income_kap"]
        if None in (ta_p, ta_k, ni_p, ni_k) or any(pd.isna(x) for x in (ta_p, ni_p)):
            row["status"] = "missing"
        else:
            ta = unit_gap(ta_p, ta_k)
            if ta is None or abs(ta[1]) > RESTATE_BAND:
                row["status"] = "other_currency_or_unit"
            else:
                scale = 10 ** ta[0]
                row["ta_rel_diff"] = round(ta[1], 4)
                row["ni_rel_diff"] = round(ni_p / (ni_k * scale) - 1, 4) if ni_k else None
                ni_ok = ni_k != 0 and abs(ni_p / (ni_k * scale) - 1) < TOL
                row["status"] = "match" if abs(ta[1]) < TOL and ni_ok else "differs"
        rows.append(row)
        print(row["ticker"], row["period"], row["status"], flush=True)

    df = pd.DataFrame(rows)
    counts = df["status"].value_counts().to_dict()
    comparable = counts.get("match", 0) + counts.get("differs", 0)
    result = {"as_of": date.today().isoformat(), "n_sample": len(df), "counts": counts,
              "comparable": comparable,
              "differs_share": round(counts.get("differs", 0) / comparable, 3) if comparable else None,
              "differs": df[df["status"] == "differs"].to_dict("records"),
              "rows": df.to_dict("records")}
    out = ROOT / "data" / "reports" / f"audit_restatements_{date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(json.dumps({k: result[k] for k in ("n_sample", "counts", "comparable", "differs_share")}, indent=1))
    print(f"JSON: {out}")


if __name__ == "__main__":
    main()
