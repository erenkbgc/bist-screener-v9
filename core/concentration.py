"""concentration_check: aday listesinin profil/sektor bazinda asiri yogunlasmasini
uyarir. explicit_non_action: otomatik eleme yapmaz.
"""
from __future__ import annotations

from collections import Counter


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
                              "message": f"'{profile}' profili adaylarin yuzde {pct:.0f}'ini olusturuyor."})

    sector_counts = Counter(c["sector"] for c in candidates)
    for sector, count in sector_counts.items():
        pct = count / total * 100
        if pct > 50:
            warnings.append({"dimension": "sector", "value": sector, "pct": pct,
                              "message": f"'{sector}' sektoru adaylarin yuzde {pct:.0f}'ini olusturuyor."})

    return warnings
