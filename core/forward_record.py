"""Ileriye donuk karar kaydi (config/live_rule.json, portfolio_backtest_preregistration.md).

Her aylik dengelemede canli kuralin listesi ve o ayki evren, zaman damgasi ve kural
surumuyle data/forward_record/decisions.jsonl dosyasina EKLENIR. Dosya yalnizca
buyur: bir tarihin kaydi yazildiktan sonra degismez. CI bu dosyayi repoya
commit'ler; git gecmisi kaydin ne zaman yazildiginin kanitidir.

Yalnizca canli veri modunda ve uretim veritabaniyla yazar; testler ve mock
kosular kayda dokunmaz.

Sema 2 (2026-10-17): her kayit status ("ok" / "no_decision"), kod commit SHA'si
ve karar anindaki ayrintilari (siralama evreni, hisse basina dort oran,
valid_metric_count, fiyat/likidite/finansal tablo tarihleri, veri sagligi) tasir.
Karar uretilemeyen aylar da "no_decision" olarak yazilir; degerlendirme yalnizca
basarili kararlari fiyatlar ama bos aylari sayar. Sema 1 kayitlari "ok" sayilir.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from core import db

ROOT = Path(__file__).resolve().parent.parent
RULE_PATH = ROOT / "config" / "live_rule.json"
RECORD_PATH = ROOT / "data" / "forward_record" / "decisions.jsonl"
SCHEMA = 2


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


def is_ok(rec: dict) -> bool:
    return rec.get("status", "ok") == "ok"


def _code_sha() -> str | None:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return (out.stdout.strip() or None) if out.returncode == 0 else None


def _write(rec: dict, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _base(rebalance_date: str, status: str) -> dict:
    return {"schema": SCHEMA, "rebalance_date": rebalance_date, "status": status,
            "rule_version": live_rule()["version"],
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_sha": _code_sha()}


def append_decision(rebalance_date: str, holdings: list[str], universe: list[str],
                    path: Path | None = None, force: bool = False, details: dict | None = None) -> bool:
    """Kaydi ekler; yazdiysa True. Baslangictan once, ayni tarihin basarili kaydi
    zaten varsa veya (force olmadan) uretim/canli kosu degilse yazmaz."""
    if not force and not _production_live():
        return False
    if rebalance_date < live_rule()["forward_record"]["start"]:
        return False
    p = path or RECORD_PATH
    if any(d["rebalance_date"] == rebalance_date and is_ok(d) for d in load_decisions(p)):
        return False
    rec = {**_base(rebalance_date, "ok"), "holdings": sorted(holdings), "universe": sorted(universe),
           **(details or {})}
    _write(rec, p)
    return True


def append_no_decision(as_of_date: str, reason: str, path: Path | None = None, force: bool = False,
                       details: dict | None = None) -> bool:
    """Karar uretilemeyen kosuyu kaydeder (bos evren, veri hatasi, durdurulan kosu).
    Ayin basarili karari zaten varsa yazmaz: o ay icin karar verilmistir. Ayni gun
    icin tek kayit."""
    if not force and not _production_live():
        return False
    if as_of_date < live_rule()["forward_record"]["start"]:
        return False
    p = path or RECORD_PATH
    recs = load_decisions(p)
    if any(is_ok(d) and d["rebalance_date"][:7] == as_of_date[:7] for d in recs):
        return False
    if any(d["rebalance_date"] == as_of_date for d in recs):
        return False
    _write({**_base(as_of_date, "no_decision"), "reason": reason, **(details or {})}, p)
    return True
