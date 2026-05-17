#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta


PRESET_DAYS = {
    "1d": 1,
    "3d": 3,
    "7d": 7,
    "14d": 14,
    "30d": 30,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve summary time presets into absolute dates.")
    parser.add_argument("--preset", choices=sorted(PRESET_DAYS))
    parser.add_argument("--since")
    parser.add_argument("--until")
    return parser.parse_args()


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def payload_for_dates(since: date, until: date, preset: str | None) -> dict[str, object]:
    if since > until:
        raise SystemExit("since must be on or before until")
    days = (until - since).days + 1
    return {
        "preset": preset or "custom",
        "since": since.isoformat(),
        "until": until.isoformat(),
        "days": days,
        "label": f"{since.isoformat()} ~ {until.isoformat()}",
    }


def main() -> None:
    args = parse_args()
    if args.preset:
        today = date.today()
        days = PRESET_DAYS[args.preset]
        since = today - timedelta(days=days - 1)
        print(json.dumps(payload_for_dates(since, today, args.preset), ensure_ascii=False, indent=2))
        return
    if args.since and args.until:
        print(
            json.dumps(
                payload_for_dates(parse_day(args.since), parse_day(args.until), None),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    raise SystemExit("pass either --preset or both --since and --until")


if __name__ == "__main__":
    main()
