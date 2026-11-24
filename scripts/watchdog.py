"""Did the daily routine run yesterday? Exit 1 (a failed GitHub run, which GitHub emails) when yesterday has no
daily note in data/digests/ or, once the loop had its 14 scan days, no tuning night in data/tuning/runs.jsonl. Standard library only: the scan workflow runs it without installing
anything.

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
    yesterday = (today - timedelta(days=1)).isoformat()   # the check runs after yesterday's routine, maybe before today's
    notes = {p.stem for p in (root / "data/digests").glob("????-??-??.md")}
    if yesterday not in notes:
        out.append(f"no daily note for {yesterday}: the radar-daily routine did not run (latest: {max(notes, default='none')})")
    if len([p for p in (root / "data/history").glob("*.jsonl") if p.stem <= yesterday]) >= MIN_DAYS:   # tuning was due
        runs = root / "data/tuning/runs.jsonl"
        lines = [line for line in runs.read_text(encoding="utf-8").splitlines() if line.strip()] if runs.exists() else []
        nights = {json.loads(line)["date"] for line in lines}
        if yesterday not in nights:
            out.append(f"no tuning night for {yesterday}: section T of the daily routine did not run (latest: {max(nights, default='none')})")
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
