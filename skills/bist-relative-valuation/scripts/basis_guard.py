#!/usr/bin/env python3
"""core/basis_guard.py'ye ince CLI sarmalayicisi: bir regulator/donem icin
reporting_basis'i cozer."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core.basis_guard import resolve_reporting_basis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regulator", required=True, choices=["BDDK", "SPK_TFRS"])
    parser.add_argument("--period-end", default=None)
    args = parser.parse_args()
    print(resolve_reporting_basis(args.regulator, args.period_end))


if __name__ == "__main__":
    main()
