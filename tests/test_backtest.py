"""The replay harness and the hindsight price score (scripts/backtest.py, D-82)."""
import random
from dataclasses import replace

import pytest

from scripts.backtest import evaluate, judge, load_world, windows
from tests.conftest import history_row, synthetic_history

W1, W2 = "2027-01-15_fri-off", "2027-01-22_fri-off"


@pytest.fixture(scope="module")
def world():
    return load_world()


@pytest.fixture(scope="module")
def static_world(world):
    """The metric on fixed ladders (Vancouver's static ladder, good 150): what these hand-built cases are about."""
    s, refs, cities = world
    return replace(s, ladder_mode="static"), refs, cities


def test_metric_on_a_hand_built_fixture(static_world):
    s, refs, cities = static_world
    rows = [history_row("2026-11-09", W1, 100, 73), history_row("2026-11-10", W1, 105, 60),
            history_row("2026-11-11", W1, 130, 60),
            history_row("2026-11-10", W2, 100, 73), history_row("2026-11-11", W2, 100, 73)]   # 2 scan days: not judged
    ev = evaluate(rows, s, refs, cities, holdout_days=0)
    t = ev["train"]
    # static Vancouver ladder (good 150): all three are good; near the low (100 x 1.10): 100 and 105
    assert (t["deal"]["tp"], t["deal"]["fp"], t["deal"]["fn"]) == (1, 0, 1)        # only the 73 is a candidate
    assert (t["ladder"]["tp"], t["ladder"]["fp"], t["ladder"]["fn"]) == (2, 1, 0)
    assert t["deal"]["f"] == pytest.approx(1.25 / 1.5, abs=1e-4)                   # F0.5 = 1.25 tp / (1.25 tp + .25 fn + fp)
    assert t["ladder"]["f"] == pytest.approx(2.5 / 3.5, abs=1e-4)
    assert ev["score"] == pytest.approx(50 * (0.8333 + 0.7143), abs=0.01)
    assert t["judgements"] == 3 and t["good_rate"] == 1.0 and t["candidate_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert ev["holdout"]["judgements"] == 0 and ev["mode"] == "hindsight"


def test_labels_blend_in_at_thirty(static_world):
    s, refs, cities = static_world
    rows = [history_row("2026-11-09", W1, 100, 73), history_row("2026-11-10", W1, 105, 60),
            history_row("2026-11-11", W1, 130, 60)]
    base = evaluate(rows, s, refs, cities, holdout_days=0)["score"]
    tap = lambda ts: {"ts": ts, "city": "vancouver", "window_id": W1, "price_pp": 100, "label": "book"}  # noqa: E731
    assert evaluate(rows, s, refs, cities, holdout_days=0, labels=[tap("2026-11-09T20:00")] * 29)["mode"] == "hindsight"
    on_cand = evaluate(rows, s, refs, cities, holdout_days=0, labels=[tap("2026-11-09T20:00")] * 30)   # joins the candidate
    late = evaluate(rows, s, refs, cities, holdout_days=0, labels=[tap("2026-11-12T08:00")] * 30)      # joins day 3: missed
    assert on_cand["mode"] == "blend" and on_cand["score"] == pytest.approx((base + 100) / 2, abs=0.01)
    assert late["score"] == pytest.approx(base / 2, abs=0.01)


def test_replay_is_deterministic(world):
    s, refs, cities = world
    rows = synthetic_history()
    a = evaluate(rows, s, refs, cities)
    shuffled = rows[:]
    random.Random(7).shuffle(shuffled)
    assert evaluate(rows, s, refs, cities) == a == evaluate(shuffled, s, refs, cities)


def test_replay_reproduces_the_logged_score(world):
    s, refs, cities = world
    rows = synthetic_history(days=3)
    assert all(j["score"] == r["score"] for r, j in zip(rows, judge(rows, s, refs, cities).values()))


def test_replay_starts_from_the_logged_score_not_the_rounded_components(world):
    """D-41: a variant is score - price_pts + new price points. The logged components are rounded to 2 places, so
    adding them up again can land a point off; a full point of drift in them must not move the replayed score."""
    s, refs, cities = world
    rows = synthetic_history(days=3)
    drifted = [{**r, "components": {**r["components"], "time": r["components"]["time"] + 1.0}} for r in rows]
    assert [j["score"] for j in judge(drifted, s, refs, cities).values()] == [r["score"] for r in rows]


def test_holdout_never_reaches_the_train_score(world):
    s, refs, cities = world
    rows = synthetic_history()
    hold = sorted({r["scan_date"] for r in rows})[-windows(21, s)[0]:]
    moved = [{**r, "price_pp": 1} if r["scan_date"] in hold else r for r in rows]   # every holdout fare changes
    a, b = evaluate(rows, s, refs, cities), evaluate(moved, s, refs, cities)
    assert a["train"] == b["train"] and a["holdout"] != b["holdout"] and a["by_day"] == b["by_day"]
    assert a["data"]["train_days"] == ["2026-11-09", "2026-11-24"] and a["data"]["holdout_days"] == ["2026-11-25", "2026-11-29"]


def test_threshold_change_moves_the_deal_term(static_world):
    s, refs, cities = static_world
    rows = synthetic_history()
    up = replace(s, trip_classes={**s.trip_classes, "dayoff": {**s.trip_classes["dayoff"], "candidate_threshold": 72}})
    a, b = evaluate(rows, s, refs, cities), evaluate(rows, up, refs, cities)
    assert a["train"]["deal"]["precision"] < 0.6 and b["train"]["deal"]["precision"] == 1.0   # about half were wrong at 70
    assert b["score"] > a["score"] + 1


def test_windows_start_small_and_grow_to_the_full_design(world):
    """D-89: the holdout is a quarter of the days (3 to 7); a replayed route ladder needs half the train days of
    earlier fares (5 to the live 14). From about 35 days the replay judges every day exactly as the scan did."""
    s, _, _ = world
    assert [windows(n, s) for n in (3, 15, 21, 28, 34, 35, 90)] == [(3, 5), (3, 6), (5, 8), (7, 10), (7, 13), (7, 14), (7, 14)]


def test_only_rolling_judgements_count_in_rolling_mode(world):
    """D-89: a judgement made on a route's static ladder (too few earlier days) is left out in rolling mode, where no
    trial moves it and no future day looks like it; in static mode every judgement counts."""
    s, refs, cities = world
    rows = synthetic_history()                          # 21 days: replay ladders from 8 earlier days, so from 11-17
    j = judge(rows, s, refs, cities, min_days=8)
    assert {k[2] for k, v in j.items() if v["counted"]} == {f"2026-11-{d}" for d in range(17, 30)}
    assert all(v["counted"] for v in judge(rows, replace(s, ladder_mode="static"), refs, cities).values())
    ev = evaluate(rows, s, refs, cities)
    assert ev["rules"]["replay_min_days"] == 8 and ev["train"]["judgements"] == 8 * 4 and ev["train"]["score"] > 0
    assert sorted(ev["by_day"]) == [f"2026-11-{d:02d}" for d in range(9, 25)]
    assert sum(p["judgements"] for p in ev["by_day"].values()) == ev["train"]["judgements"]


def test_the_scan_rule_is_still_reproduced_at_full_size(world):
    """With min_days at the live rolling_min_days the replay's ladders are the scan's: nothing changes for a
    history of 35 days or more."""
    s, refs, cities = world
    rows = synthetic_history()
    assert judge(rows, s, refs, cities) == judge(rows, s, refs, cities, min_days=s.rolling_min_days)


def test_every_trial_is_scored_on_the_same_trips(world):
    """Codex: a shorter rolling window must not win by dropping trips. Whether a judgement counts depends on the scan
    days alone; with a gap in the history the shorter window falls back to the static ladder on the same trips."""
    s, refs, cities = world
    rows = [r for r in synthetic_history(days=21) if not "2026-11-12" <= r["scan_date"] <= "2026-11-18"]   # a week missing
    short = replace(s, rolling_window_days=5)
    a, b = judge(rows, s, refs, cities, min_days=6), judge(rows, short, refs, cities, min_days=6)
    assert {k for k, v in a.items() if v["counted"]} == {k for k, v in b.items() if v["counted"]} != set()
    assert evaluate(rows, s, refs, cities)["calls"].keys() == evaluate(rows, short, refs, cities)["calls"].keys()
