#!/usr/bin/env python3
"""core/decay.py'ye ince CLI sarmalayicisi: tek bir olay icin effective_weight'i gosterir."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core.decay import effective_weight, load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument("--days-since-published", type=int, required=True)
    args = parser.parse_args()
    cfg = load_config()
    cat = cfg["categories"][args.category]
    half_life = cfg["half_life_days"][args.category]
    print(effective_weight(cat["weight"], args.days_since_published, half_life))


if __name__ == "__main__":
    main()
