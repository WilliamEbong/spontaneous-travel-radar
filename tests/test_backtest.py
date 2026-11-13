"""The replay harness and the hindsight price score (scripts/backtest.py, D-82)."""
import random
from dataclasses import replace

import pytest

from scripts.backtest import evaluate, judge, load_world
from tests.conftest import history_row, synthetic_history

W1, W2 = "2027-01-15_fri-off", "2027-01-22_fri-off"


@pytest.fixture(scope="module")
def world():
    return load_world()


def test_metric_on_a_hand_built_fixture(world):
    s, refs, cities = world
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


def test_labels_blend_in_at_thirty(world):
    s, refs, cities = world
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


def test_holdout_never_reaches_the_train_score(world):
    s, refs, cities = world
    rows = synthetic_history()
    last7 = sorted({r["scan_date"] for r in rows})[-7:]
    moved = [{**r, "price_pp": 1} if r["scan_date"] in last7 else r for r in rows]   # every holdout fare changes
    a, b = evaluate(rows, s, refs, cities), evaluate(moved, s, refs, cities)
    assert a["train"] == b["train"] and a["holdout"] != b["holdout"]
    assert a["data"]["train_days"] == ["2026-11-09", "2026-11-22"] and a["data"]["holdout_days"] == ["2026-11-23", "2026-11-29"]


def test_threshold_change_moves_the_deal_term(world):
    s, refs, cities = world
    rows = synthetic_history()
    up = replace(s, trip_classes={**s.trip_classes, "dayoff": {**s.trip_classes["dayoff"], "candidate_threshold": 72}})
    a, b = evaluate(rows, s, refs, cities), evaluate(rows, up, refs, cities)
    assert a["train"]["deal"]["precision"] < 0.6 and b["train"]["deal"]["precision"] == 1.0   # about half were wrong at 70
    assert b["score"] > a["score"] + 1
