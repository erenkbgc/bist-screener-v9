#!/usr/bin/env python3
"""report/validate.py'ye ince CLI sarmalayicisi."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core.payload import build_report_payload
from report.validate import validate_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--html-file", required=True)
    args = parser.parse_args()

    payload = build_report_payload(args.as_of_date)
    html_content = Path(args.html_file).read_text(encoding="utf-8")
    result = validate_report(html_content, payload)
    print(result)
    sys.exit(0 if result["is_valid"] else 1)


if __name__ == "__main__":
    main()
