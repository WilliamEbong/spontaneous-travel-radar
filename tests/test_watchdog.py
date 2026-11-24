"""The loops' watchdog (scripts/watchdog.py): a day without a daily note or a tuning night must fail loudly."""
import json
from datetime import date

from scripts.watchdog import problems


def _repo(tmp_path, note_days=(), run_days=(), scan_days=15):
    (tmp_path / "data/digests").mkdir(parents=True)
    (tmp_path / "data/tuning").mkdir(parents=True)
    (tmp_path / "data/history").mkdir(parents=True)
    for d in note_days:
        (tmp_path / f"data/digests/{d}.md").write_text("note", encoding="utf-8")
    (tmp_path / "data/tuning/runs.jsonl").write_text("".join(json.dumps({"date": d}) + "\n" for d in run_days), encoding="utf-8")
    for i in range(scan_days):
        (tmp_path / f"data/history/2026-11-{9 + i:02d}.jsonl").write_text("", encoding="utf-8")
    return tmp_path


def test_a_healthy_morning_has_no_problems(tmp_path):
    root = _repo(tmp_path, note_days=["2026-11-22", "2026-11-23"], run_days=["2026-11-22", "2026-11-23"])
    assert problems(date(2026, 11, 24), root) == []        # before today's routine: yesterday's note is the newest
    assert problems(date(2026, 11, 23), root) == []


def test_a_missed_day_of_the_routine_is_reported(tmp_path):
    root = _repo(tmp_path, note_days=["2026-11-21"], run_days=["2026-11-22"])
    out = problems(date(2026, 11, 24), root)
    assert len(out) == 2 and "daily note" in out[0] and "2026-11-21" in out[0] and "tuning" in out[1]


def test_tuning_is_not_expected_while_it_is_still_collecting(tmp_path):
    root = _repo(tmp_path, note_days=["2026-11-23"], run_days=[], scan_days=13)
    assert problems(date(2026, 11, 24), root) == []         # under 14 scan days the loop writes nothing (D-82)
    assert problems(date(2026, 11, 24), _repo(tmp_path / "b", note_days=["2026-11-23"], scan_days=14))   # from 14 it must


def test_the_start_guard_matches_the_tuning_loop():
    from scripts import tune_loop
    from scripts.watchdog import MIN_DAYS
    assert MIN_DAYS == tune_loop.MIN_DAYS
