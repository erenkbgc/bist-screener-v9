"""Ileriye donuk karar kaydi (config/live_rule.json, portfolio_backtest_preregistration.md).

Her aylik dengelemede canli kuralin listesi ve o ayki evren, zaman damgasi ve kural
surumuyle data/forward_record/decisions.jsonl dosyasina EKLENIR. Dosya yalnizca
buyur: bir tarihin kaydi yazildiktan sonra degismez. CI bu dosyayi repoya
commit'ler; git gecmisi kaydin ne zaman yazildiginin kanitidir.

Yalnizca canli veri modunda ve uretim veritabaniyla yazar; testler ve mock
kosular kayda dokunmaz.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from core import db

ROOT = Path(__file__).resolve().parent.parent
RULE_PATH = ROOT / "config" / "live_rule.json"
RECORD_PATH = ROOT / "data" / "forward_record" / "decisions.jsonl"


def live_rule() -> dict:
    return json.loads(RULE_PATH.read_text(encoding="utf-8"))


def load_decisions(path: Path | None = None) -> list[dict]:
    p = path or RECORD_PATH
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _production_live() -> bool:
    live = os.environ.get("BIST_DATA_MODE", "mock").strip().lower() == "live"
    return live and Path(db.DB_PATH).resolve() == db.PRODUCTION_DB_PATH.resolve()


def append_decision(rebalance_date: str, holdings: list[str], universe: list[str],
                    path: Path | None = None, force: bool = False) -> bool:
    """Kaydi ekler; yazdiysa True. Baslangictan once, ayni tarih zaten varsa veya
    (force olmadan) uretim/canli kosu degilse yazmaz."""
    if not force and not _production_live():
        return False
    rule = live_rule()
    if rebalance_date < rule["forward_record"]["start"]:
        return False
    p = path or RECORD_PATH
    if any(d["rebalance_date"] == rebalance_date for d in load_decisions(p)):
        return False
    rec = {"rebalance_date": rebalance_date, "rule_version": rule["version"],
           "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "holdings": sorted(holdings), "universe": sorted(universe)}
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True
