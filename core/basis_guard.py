"""basis_guard: raporlama bazi (TMS 29 enflasyon duzeltmesi vs. nominal) ayrimini korur.

Spec: basis_guard, P1_reporting_basis_split, P2_bank_timeseries_break.
"""
from __future__ import annotations

from datetime import date

REGULATOR_MAPPING = {
    "BDDK": ["bankacilik", "finansal kiralama", "faktoring", "finansman", "tasarruf finansman", "varlik yonetim"],
    "SPK_TFRS": ["diger tum sektorler"],
}

_BDDK_NOMINAL_CUTOFF = date(2025, 1, 1)


def resolve_reporting_basis(regulator: str, period_end: str | None) -> str:
    """regulator + donem bilgisine gore reporting_basis dondurur: 'nominal' | 'unknown'.

    inflation_basis_truthful_labeling (v12 T0-3):
    Mevzuat geregi SPK_TFRS sirketleri TMS 29 uygulamak zorunda olsa da (Turkiye
    hala IAS 29 hiperenflasyon listesinde), mevcut veri saglayicimiz (Is Yatirim /
    borsapy) bilanco ve gelir tablolarini nominal/tarihi maliyetli olarak sunmaktadir
    (sanayi XI_29'da net parasal pozisyon kalemi yok, UFRS'de 2022-2025 degerleri 0.0,
    ozkaynakta enflasyon duzeltme kalemi yok). SPK_TFRS icin otomatik 'adjusted'
    etiketi kaldirilmistir; veri beslemesi gercegi 'nominal'dir.
    """
    if regulator in ("BDDK", "SPK_TFRS"):
        return "nominal"
    return "unknown"


def basis_break(basis_a: str, basis_b: str) -> bool:
    """Iki donem arasinda baz farkliligi var mi (buyume/sloan/piotroski gibi donem-karsilastirmali
    hesaplarin bloke edilmesi gerekir mi)."""
    if basis_a == "unknown" or basis_b == "unknown":
        return True
    return basis_a != basis_b


def is_scorable(reporting_basis: str) -> bool:
    """unknown bazli satirlar skorlanmaz."""
    return reporting_basis != "unknown"


def unknown_ratio(rows: list[dict], basis_field: str = "reporting_basis") -> float:
    if not rows:
        return 0.0
    unknown = sum(1 for r in rows if r.get(basis_field) == "unknown")
    return unknown / len(rows)


UNKNOWN_RATIO_HALT_THRESHOLD = 0.30


class BasisGuardHaltError(Exception):
    """basis_guard unknown oranini yuzde 30 uzerinde bulursa akis durur (hard_stop_gate)."""
