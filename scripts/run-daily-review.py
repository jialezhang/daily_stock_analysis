#!/usr/bin/env python3
"""Manual entry for daily multi-market review generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.daily_review.runner import run_daily_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily review and generate markdown report.")
    parser.add_argument("--send-telegram", action="store_true", help="Send generated report to Telegram.")
    parser.add_argument("--use-llm", action="store_true", help="Use configured LLM to generate summary.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_daily_review(send_telegram=args.send_telegram, use_llm=args.use_llm)
    print(report.splitlines()[0])


if __name__ == "__main__":
    main()
