"""The nightly trial loop (scripts/tune_loop.py, D-82): keep and revert, the guard, the holdout, the config edit."""
import json
import shutil
from dataclasses import replace
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
    """The loop's mechanics on the synthetic Vancouver history with its static ladder (good 150): at threshold 70
    every good fare is a candidate and half of them are wrong; at 72 only the near-low ones are."""
    s, refs, cities = load_world()
    return replace(s, ladder_mode="static"), refs, cities


@pytest.fixture(scope="module")
def rolling_world():
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
    assert kept == ["dayoff.candidate_threshold 70 → 72"] and res["trials"][[t["kept"] for t in res["trials"]].index(True)]["confidence"] >= 0.9
    assert all(t["why"] in ("not better by 1", "changes no decision up to its bound") or t["why"].startswith("guardrail")
               for t in res["trials"] if not t["kept"])


def test_holdout_never_reaches_selection(world):
    s, refs, cities = world
    rows = synthetic_history()
    hold = sorted({r["scan_date"] for r in rows})[-5:]   # windows(21): a 5-day holdout
    moved = [{**r, "price_pp": r["price_pp"] + 40} if r["scan_date"] in hold else r for r in rows]
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



def test_a_proposal_runs_only_as_one_step_from_the_current_config(world):
    """D-82: one step a trial. A --try two steps away, off the grid, moving two keys, or a second step on top of a
    kept first one never runs; a real one-step proposal runs first."""
    s, refs, cities = world
    bad = [{"rolling_ladder.good": 35}, {"dayoff.candidate_threshold": 71},
           {"dayoff.candidate_threshold": 72, "weekend.candidate_threshold": 72}]
    res = tl.run_night(synthetic_history(), s, refs, cities, day=NIGHT, budget=3, keys=keys(s),
                       proposals=[*bad, {"dayoff.candidate_threshold": 72}, {"dayoff.candidate_threshold": 68}])
    moves = [t["move"] for t in res["trials"]]
    assert all(m not in moves for m in bad) and moves[0] == {"dayoff.candidate_threshold": 72}
    assert res["trials"][0]["kept"] and {"dayoff.candidate_threshold": 68} not in moves   # 72 kept: 68 is two steps


def setup(tmp_path, monkeypatch, days: int, ladder_mode: str = "static"):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(ROOT / "config", tmp_path / "config")
    text = (ROOT / "tests/fixtures/scoring.yaml").read_text(encoding="utf-8")
    assert "ladder_mode: rolling" in text
    (tmp_path / "config/scoring.yaml").write_bytes(text.replace("ladder_mode: rolling", f"ladder_mode: {ladder_mode}").encode("utf-8"))
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
    assert "| kept: better by" in log and "of 1000 redraws |" in log and "| night | 16 trials, 1 kept: live on main |" in log
    yml = (tmp_path / "config/scoring.yaml").read_text(encoding="utf-8")
    assert "    candidate_threshold: 72   # pass-1 score" in yml        # the line changed, its comment kept
    assert yml.count("candidate_threshold: 70") == 1                     # the weekend class untouched
    assert "ladder_mode: static" in yml                                   # nothing else in the file moved
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


def test_a_change_that_does_nothing_never_wins_a_redraw():
    day = {"deal": {"tp": 1, "fp": 1, "fn": 0}, "ladder": {"tp": 2, "fp": 1, "fn": 1}, "judgements": 4}
    cur = {"by_day": {f"2026-11-{d}": day for d in range(10, 16)}}
    assert tl.confidence(cur, cur, 7) == 0.0
    assert tl.confidence({"by_day": {}}, {"by_day": {}}, 7) == 0.0      # no judged day, no evidence


def test_the_redraws_tell_a_steady_gain_from_one_lucky_day():
    """D-89: a gain on every day wins every redraw; the same total gain from one day out of six wins only the redraws
    that include that day (about two in three), under the 90% the keep rule needs."""
    plain = {"deal": {"tp": 0, "fp": 0, "fn": 0}, "ladder": {"tp": 2, "fp": 2, "fn": 4}, "judgements": 8}
    better = {"deal": {"tp": 0, "fp": 0, "fn": 0}, "ladder": {"tp": 3, "fp": 2, "fn": 3}, "judgements": 8}
    lucky = {"deal": {"tp": 0, "fp": 0, "fn": 0}, "ladder": {"tp": 8, "fp": 2, "fn": 0}, "judgements": 8}
    days = [f"2026-11-{d}" for d in range(10, 16)]
    cur = {"by_day": {d: plain for d in days}}
    steady = {"by_day": {d: better for d in days}}
    one_day = {"by_day": {d: (lucky if d == days[0] else plain) for d in days}}
    assert tl.confidence(cur, steady, 7) == 1.0
    assert 0.55 < tl.confidence(cur, one_day, 7) < tl.CONFIDENCE


def test_a_menu_step_crosses_a_flat_stretch(world):
    """D-89: from a threshold of 60 the steps to 62 ... 70 change no decision on this history (every candidate scores
    71 or 73); the trial steps on to 72, the first value that does, and the keep rule judges that."""
    s, refs, cities = world
    low = tl.with_values(s, {"dayoff.candidate_threshold": 60})
    surface = {**tl.SURFACE, "dayoff.candidate_threshold": (60, 80, 2)}
    res = tl.run_night(synthetic_history(), low, refs, cities, day=NIGHT, budget=1, keys=["dayoff.candidate_threshold"],
                       surface=surface)
    (t,) = res["trials"]
    assert t["move"] == {"dayoff.candidate_threshold": 72} and t["change"] == "dayoff.candidate_threshold 60 → 72" and t["kept"]
    res = tl.run_night(synthetic_history(), s, refs, cities, day=NIGHT, budget=1, keys=["rolling_window_days"])
    assert res["trials"][0]["why"] == "changes no decision up to its bound" and not res["trials"][0]["kept"]


def test_the_candidate_floor_follows_the_data(rolling_world):
    """D-89: a few points under the best score logged on the train days, never under 60 (the lowest pass-1 score
    from which a hit is still possible) and never over William's 65; the hit line is not on the surface."""
    s, _, _ = rolling_world
    rows = synthetic_history()                                   # best logged score 73: William's 65 stands
    assert tl.surface_for(rows, s)["dayoff.candidate_threshold"] == (65, 80, 2)
    low = [{**r, "score": min(r["score"], 66)} for r in rows]    # best 66: floor 62
    assert tl.surface_for(low, s)["weekend.candidate_threshold"] == (62, 80, 2)
    lower = [{**r, "score": min(r["score"], 55)} for r in rows]  # best 55: the hard floor, 60
    assert tl.surface_for(lower, s)["dayoff.candidate_threshold"] == (60, 80, 2)
    hold = sorted({r["scan_date"] for r in rows})[-5:]           # the holdout's scores never shape the surface
    spiky = [{**r, "score": 99} if r["scan_date"] in hold else {**r, "score": min(r["score"], 55)} for r in rows]
    assert tl.surface_for(spiky, s)["dayoff.candidate_threshold"] == (60, 80, 2)
    assert not any("hit_threshold" in k for k in tl.surface_for(rows, s))


def test_a_rolling_night_scores_what_the_future_will_judge(tmp_path, monkeypatch, capsys):
    """The real regime: with 21 days the replay builds each route's ladder from 8 earlier days, so the train score
    is not stuck at 0 while the live ladders need 14 (D-89)."""
    setup(tmp_path, monkeypatch, days=21, ladder_mode="rolling")
    assert tl.main(["--date", "2026-11-30"]) == 0
    run = json.loads((tmp_path / "data/tuning/runs.jsonl").read_text(encoding="utf-8"))
    assert run["start"]["score"] > 0 and run["rules"]["holdout_days"] == 5 and run["rules"]["replay_min_days"] == 8
