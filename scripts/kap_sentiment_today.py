#!/usr/bin/env python3
"""Son N gunun KAP bildirimlerini ceker, govde metnini FinBERT ile puanlar.

    python scripts/kap_sentiment_today.py --tickers THYAO,ASELS --days 3
    python scripts/kap_sentiment_today.py --days 1            # varsayilan izleme listesi

Cikti: konsol tablosu + data/reports/kap_sentiment_<tarih>.json
BILGI amaclidir; final_score'a baglanmaz (bkz. core/kap_sentiment.py SINIR notu).
Gereksinim: pip install -r requirements-nlp.txt (torch, transformers, sentencepiece)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import kap_sentiment  # noqa: E402
from core.live_data import _NOISE_TITLE_RE, _categorize_kap_title  # noqa: E402

DEFAULT_TICKERS = ("THYAO,PGSUS,TAVHL,ASELS,FROTO,TOASO,TUPRS,EREGL,BIMAS,MGROS,"
                   "SISE,ARCLK,KCHOL,SAHOL,TCELL,ENKAI,PETKM,KRDMD,DOAS,AKBNK,GARAN,YKBNK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=DEFAULT_TICKERS)
    ap.add_argument("--days", type=int, default=3, help="Geriye kac takvim gunu")
    ap.add_argument("--as-of-date", default=date.today().isoformat())
    ap.add_argument("--limit", type=int, default=30, help="Hisse basina en fazla bildirim")
    ap.add_argument("--from-payload", default=None,
                    help="Gunluk tarama payload JSON'u: hisse listesi predictions'tan alinir "
                         "(otomasyon: yalnizca o gun raporlanan adaylar)")
    ap.add_argument("--max-tickers", type=int, default=80)
    args = ap.parse_args()
    if args.from_payload:
        payload_path = Path(args.from_payload)
        if not payload_path.exists():
            print(f"payload yok ({payload_path}), KAP sentiment atlandi")
            return
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        tickers_from_payload = list(dict.fromkeys(p["ticker"] for p in payload.get("predictions", [])))
        if not tickers_from_payload:
            print("payload'da aday yok, KAP sentiment atlandi")
            return
        args.tickers = ",".join(tickers_from_payload[:args.max_tickers])

    import borsapy as bp

    as_of = datetime.strptime(args.as_of_date, "%Y-%m-%d").date()
    cutoff = as_of - timedelta(days=args.days)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    results: list[dict] = []
    seen: set[str] = set()

    for t in tickers:
        try:
            kap = bp.Ticker(t)._get_kap()
            df = kap.get_disclosures(t, limit=args.limit)
        except Exception as exc:
            print(f"[{t}] bildirim listesi alinamadi: {exc}", file=sys.stderr)
            continue
        for _, r in df.iterrows():
            try:
                published = datetime.strptime(r["Date"], "%d.%m.%Y %H:%M:%S")
            except Exception:
                continue
            if not (cutoff <= published.date() <= as_of):
                continue
            title = str(r.get("Title") or "")
            url = str(r.get("URL") or "")
            disclosure_id = url.rstrip("/").split("/")[-1]
            category, _ = _categorize_kap_title(title)
            row = {"ticker": t, "published_at": published.isoformat(sep=" "), "title": title,
                   "url": url, "rule_category": category}
            if _NOISE_TITLE_RE.search(title):
                row.update(label="skipped_noise", score=None)
                results.append(row)
                continue
            if disclosure_id in seen:  # ayni bildirim birden cok sirkete iliştirilebilir
                row.update(label="duplicate", score=None)
                results.append(row)
                continue
            seen.add(disclosure_id)
            try:
                html = kap.get_disclosure_content(disclosure_id)
                row.update(kap_sentiment.analyze_disclosure_html(html))
            except Exception as exc:
                row.update(label="error", score=None, error=str(exc)[:200])
            results.append(row)

    scored = [r for r in results if isinstance(r.get("score"), float)]
    scored.sort(key=lambda r: r["score"])
    print(f"\nKAP FinBERT | {cutoff} .. {as_of} | {len(scored)} puanlandi, "
          f"{len(results) - len(scored)} atlandi\n")
    for r in scored:
        peak = r.get("peak_score")
        peak_txt = f"peak {peak:+.2f}" if isinstance(peak, float) else "peak   n/a"
        print(f"{r['score']:+.2f} {peak_txt} {r['label']:8s} {r['ticker']:6s} {r['published_at'][:16]}  "
              f"{(r.get('summary') or r['title'])[:70]}")
        if r.get("peak_sentence") and isinstance(peak, float) and abs(peak) >= 0.5:
            print(f"         >> {r['peak_sentence'][:160]}")

    out = ROOT / "data" / "reports" / f"kap_sentiment_{as_of.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {out}")


if __name__ == "__main__":
    main()
