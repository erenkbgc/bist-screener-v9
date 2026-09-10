"""regime_taxonomy statik taramasi: regime_taxonomy ciktisindan scoring.py'ye
hicbir import/veri akisi olmamali."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_IMPORT_RE = lambda name: re.compile(  # noqa: E731
    rf"^\s*(from\s+core(\.{name})?\s+import\s+(\w*\.)*{name}\b|import\s+core\.{name}\b)",
    re.MULTILINE,
)


def test_scoring_does_not_import_regime_taxonomy():
    source = (REPO_ROOT / "core" / "scoring.py").read_text(encoding="utf-8")
    assert not _IMPORT_RE("regime_taxonomy").search(source)


def test_regime_taxonomy_does_not_import_scoring():
    source = (REPO_ROOT / "core" / "regime_taxonomy.py").read_text(encoding="utf-8")
    assert not _IMPORT_RE("scoring").search(source)


def test_payload_does_not_import_regime_taxonomy():
    """payload da regime_taxonomy'yi skorlama amaciyla kullanmamali (yalnizca
    raporlama icin regime_log tablosundaki etiketler DB'den okunur)."""
    source = (REPO_ROOT / "core" / "payload.py").read_text(encoding="utf-8")
    assert not _IMPORT_RE("regime_taxonomy").search(source)
