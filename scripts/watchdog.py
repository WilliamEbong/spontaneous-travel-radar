"""Is the daily routine still running? Exit 1 (a failed GitHub run, which GitHub emails) when a whole day passed
without the daily note in data/digests/ or, once the loop has its 14 scan days, without a tuning night in
data/tuning/runs.jsonl. Standard library only: the scan workflow runs it without installing anything.

python scripts/watchdog.py [--date YYYY-MM-DD]
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

MIN_DAYS = 14   # scripts/tune_loop.py MIN_DAYS: before this the loop only reports "collecting" and writes nothing


def problems(today: date, root=".") -> list[str]:
    root, out = Path(root), []
    yesterday = (today - timedelta(days=1)).isoformat()   # the scan runs before the 08:30 routine: yesterday's is fine
    notes = sorted(p.stem for p in (root / "data/digests").glob("????-??-??.md"))
    if not notes or notes[-1] < yesterday:
        out.append(f"no daily note since {notes[-1] if notes else 'ever'}: the radar-daily routine has not run")
    if len(list((root / "data/history").glob("*.jsonl"))) >= MIN_DAYS:
        runs = root / "data/tuning/runs.jsonl"
        lines = [line for line in runs.read_text(encoding="utf-8").splitlines() if line.strip()] if runs.exists() else []
        last = json.loads(lines[-1])["date"] if lines else None
        if not last or last < yesterday:
            out.append(f"no tuning night since {last or 'ever'}: section T of the daily routine has not run")
    return out


def main(argv=None) -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--date")
    args = a.parse_args(argv)
    # Calgary is UTC-6 all year from November 2026 (D-24); a fixed offset needs no zone data on the runner
    today = date.fromisoformat(args.date) if args.date else datetime.now(timezone(timedelta(hours=-6))).date()
    found = problems(today)
    for p in found:
        print(f"::error::{p}")
    print("loops ok" if not found else f"{len(found)} problem(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
