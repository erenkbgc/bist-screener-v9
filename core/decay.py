"""catalyst_engine.decay_model: yayimlanma tarihine gore agirlik sonumu.

formula: effective_weight = base_weight * 0.5 ** (days_since_published / half_life_days)
"""
from __future__ import annotations

from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "catalyst_decay.yaml"


def load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def effective_weight(base_weight: float, days_since_published: int, half_life_days: float) -> float:
    if half_life_days <= 0:
        return 0.0
    return base_weight * (0.5 ** (days_since_published / half_life_days))
