"""concentration_check: aday listesinin profil/sektor bazinda asiri yogunlasmasini
uyarir. explicit_non_action: otomatik eleme yapmaz.
"""
from __future__ import annotations

from collections import Counter

from core.payload import format_number

# report/validate.py::find_orphan_numbers, HTML'deki HER sayisal token'in
# payload icinde bulunmasini zorunlu kilar. Bu yuzden mesaj icine gomulen
# `pct` DEGERI de core.payload.format_number ile bicimlendirilir (elle
# `:.0f`/`:.2f` KULLANILMAZ, bkz. core/payload.py::format_number docstring'i)
# VE ayni `pct` sayisi payload'a girebilsin diye warning sozlugunde ham
# float olarak da tutulur (bkz. run.py -> payload_mod.build_report_payload
# concentration_warnings parametresi).


def check_concentration(candidates: list[dict]) -> list[dict]:
    warnings = []
    total = len(candidates)
    if total == 0:
        return warnings

    profile_counts = Counter(c["ratio_profile"] for c in candidates)
    for profile, count in profile_counts.items():
        pct = count / total * 100
        if pct > 50:
            warnings.append({"dimension": "ratio_profile", "value": profile, "pct": pct,
                              "message": f"'{profile}' profili adaylarin yuzde {format_number(pct)}'ini olusturuyor."})

    sector_counts = Counter(c["sector"] for c in candidates)
    for sector, count in sector_counts.items():
        pct = count / total * 100
        if pct > 50:
            warnings.append({"dimension": "sector", "value": sector, "pct": pct,
                              "message": f"'{sector}' sektoru adaylarin yuzde {format_number(pct)}'ini olusturuyor."})

    return warnings
