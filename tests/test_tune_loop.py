"""The nightly trial loop (scripts/tune_loop.py, D-82): keep and revert, the guard, the holdout, the config edit."""
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

import radar.config

from scripts import tune_loop as tl
from scripts.backtest import load_world
from tests.conftest import synthetic_history

ROOT = Path(__file__).resolve().parents[1]
NIGHT = date(2026, 11, 30)


@pytest.fixture(scope="module")
def world():
    return load_world()


def keys(s):
    return tl.movable(s, False)


def test_keep_then_revert(world):
    s, refs, cities = world
    res = tl.run_night(synthetic_history(), s, refs, cities, day=NIGHT, budget=2, keys=keys(s),
                       proposals=[{"dayoff.candidate_threshold": 72}, {"dayoff.candidate_threshold": 74}])
    assert [t["kept"] for t in res["trials"]] == [True, False]
    assert res["trials"][1]["why"] == "not better by 1"          # at 74 no trip is a candidate: worse
    assert tl.get(res["config"], "dayoff.candidate_threshold") == 72 and not res["vetoed"]


def test_menu_night_keeps_only_what_helps(world):
    s, refs, cities = world
    res = tl.run_night(synthetic_history(), s, refs, cities, day=NIGHT, budget=16, keys=keys(s))
    kept = [t["change"] for t in res["trials"] if t["kept"]]
    assert kept == ["dayoff.candidate_threshold 70 → 72"] and len(res["trials"]) == 16
    assert all(t["why"] == "not better by 1" for t in res["trials"] if not t["kept"])


def test_holdout_never_reaches_selection(world):
    s, refs, cities = world
    rows = synthetic_history()
    last7 = sorted({r["scan_date"] for r in rows})[-7:]
    moved = [{**r, "price_pp": r["price_pp"] + 40} if r["scan_date"] in last7 else r for r in rows]
    a = tl.run_night(rows, s, refs, cities, day=NIGHT, budget=16, keys=keys(s))
    b = tl.run_night(moved, s, refs, cities, day=NIGHT, budget=16, keys=keys(s))
    pick = lambda res: [(t["change"], t["kept"], t["after"]["train"]) for t in res["trials"]]  # noqa: E731
    assert pick(a) == pick(b)


def test_guardrail_blocks_a_flood(world):
    s, refs, cities = world
    cur = {"good_rate": 0.20, "candidate_rate": 0.02}
    assert tl.guard({"good_rate": 0.25, "candidate_rate": 0.01}, cur) == ""
    assert tl.guard({"good_rate": 0.45, "candidate_rate": 0.02}, cur).startswith("guardrail: trips called good")
    assert tl.guard({"good_rate": 0.50, "candidate_rate": 0.02}, {"good_rate": 0.60, "candidate_rate": 0.02}) == ""  # closer


def test_proposals_held_to_the_surface(world):
    s, _, _ = world
    with pytest.raises(ValueError, match="not on tonight's surface"):
        tl.parse_try("trip_classes.dayoff.hit_threshold=75", s, keys(s))
    with pytest.raises(ValueError, match="outside"):
        tl.parse_try("rolling_ladder.good=50", s, keys(s))
    with pytest.raises(ValueError, match="not on tonight's surface"):
        tl.parse_try("weights.time=22,weights.price=43", s, keys(s))   # weights locked until 30 taps
    assert tl.parse_try("price_curve.share_0=0.55", s, keys(s)) == {"price_curve.share_0": 0.55}


def setup(tmp_path, monkeypatch, days: int):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(ROOT / "config", tmp_path / "config")
    shutil.copy(ROOT / "tests/fixtures/scoring.yaml", tmp_path / "config/scoring.yaml")
    monkeypatch.setattr(radar.config, "SCORING", "config/scoring.yaml")
    hist = tmp_path / "data/history"
    hist.mkdir(parents=True)
    rows = synthetic_history(days=days)
    for day in sorted({r["scan_date"] for r in rows}):
        (hist / f"{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows if r["scan_date"] == day), encoding="utf-8")


def test_guard_collects_until_fourteen_days(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch, days=13)
    before = (tmp_path / "config/scoring.yaml").read_bytes()
    assert tl.main(["--date", "2026-11-30"]) == 0
    assert capsys.readouterr().out.strip() == "collecting, 13 of 14 days"
    assert not (tmp_path / "docs").exists() and not (tmp_path / "data/tuning").exists()
    assert (tmp_path / "config/scoring.yaml").read_bytes() == before


def test_dry_run_writes_log_runs_and_config(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch, days=21)
    assert tl.main(["--date", "2026-11-30"]) == 0
    out = capsys.readouterr().out
    assert "CONFIG_CHANGED=yes" in out and "COMMIT_MESSAGE=tune: 2026-11-30: dayoff.candidate_threshold 70 → 72" in out
    log = (tmp_path / "docs/tuning-log.md").read_text(encoding="utf-8")
    assert "| kept: better by" in log and "| reverted: not better by 1 |" in log and "| night | 16 trials, 1 kept: live on main |" in log
    yml = (tmp_path / "config/scoring.yaml").read_text(encoding="utf-8")
    assert "    candidate_threshold: 72   # pass-1 score" in yml        # the line changed, its comment kept
    assert yml.count("candidate_threshold: 70") == 1                     # the weekend class untouched
    assert b"\r\n" not in (tmp_path / "config/scoring.yaml").read_bytes()
    run = [json.loads(line) for line in (tmp_path / "data/tuning/runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(run) == 1 and run[0]["kept"][0]["move"] == {"dayoff.candidate_threshold": 72}
    assert run[0]["start"]["settings"]["candidate_threshold"]["dayoff"] == 70 and run[0]["data"]["scan_days"] == 21
    assert tl.main(["--date", "2026-11-30"]) == 0 and capsys.readouterr().out.strip() == "already ran 2026-11-30"
    assert "a day-off trip needs 72 points for a closer look (was 70)" in tl.summary(7)


def test_a_failed_config_write_is_undone_and_logged(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch, days=21)
    before = (tmp_path / "config/scoring.yaml").read_bytes()

    def broken(path=None):
        raise ValueError("read-back broke")
    monkeypatch.setattr(tl, "load_scoring", broken)   # the read-back fails after the file was replaced
    assert tl.main(["--date", "2026-11-30"]) == 0
    out = capsys.readouterr().out
    assert "CONFIG_WRITE_FAILED=ValueError: read-back broke" in out and "CONFIG_CHANGED=no" in out and "COMMIT_MESSAGE" not in out
    assert (tmp_path / "config/scoring.yaml").read_bytes() == before and not list((tmp_path / "config").glob("*.tmp"))
    assert "the config write failed (ValueError: read-back broke), nothing changed" in (tmp_path / "docs/tuning-log.md").read_text(encoding="utf-8")
    run = json.loads((tmp_path / "data/tuning/runs.jsonl").read_text(encoding="utf-8"))
    assert run["config_error"] and run["kept"] == [] and set(run["fingerprints"]) == {"code", "references", "cities", "history"}
