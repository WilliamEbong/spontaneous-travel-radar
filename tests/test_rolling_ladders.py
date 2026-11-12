"""Rolling route ladders (D-82, docs/TUNING-PLAN.md (d))."""
from dataclasses import replace
from datetime import date, timedelta

import pytest

from radar.config import load_scoring
from radar.store import rolling_flights

STATIC = {"exceptional": 120, "good": 150, "typical": 200}
TODAY = date(2026, 12, 1)


def rows(days: int, prices=range(100, 200), window="2027-01-15_fri-off", start=TODAY):
    """One row per price on each of `days` scan days before `start`."""
    return [{"scan_date": (start - timedelta(days=d)).isoformat(), "window_id": window, "price_pp": p}
            for d in range(1, days + 1) for p in prices]


@pytest.fixture
def rolling():
    return replace(load_scoring(), ladder_mode="rolling", ladder_exclude_ranges=())


def test_static_mode_returns_the_static_ladder(rolling):
    assert rolling_flights(rows(30), TODAY, replace(rolling, ladder_mode="static"), STATIC) is STATIC


def test_fallback_until_min_days(rolling):
    assert rolling_flights(rows(13), TODAY, rolling, STATIC) is STATIC
    assert rolling_flights(rows(14), TODAY, rolling, STATIC) != STATIC


def test_percentiles_from_known_rows(rolling):
    # prices 100..199 on every day: nearest-rank percentiles 10/25/50 are 110, 125, 150
    assert rolling_flights(rows(20), TODAY, rolling, STATIC) == {"exceptional": 110, "good": 125, "typical": 150}


def test_never_uses_today_or_future_rows(rolling):
    past = rows(20)
    future = [{"scan_date": (TODAY + timedelta(days=d)).isoformat(), "window_id": "2027-01-15_fri-off", "price_pp": 1}
              for d in range(0, 30)]
    assert rolling_flights(past + future, TODAY, rolling, STATIC) == rolling_flights(past, TODAY, rolling, STATIC)


def test_window_days_bound_the_history(rolling):
    old = rows(20, prices=[5], start=TODAY - timedelta(days=61))   # all older than 60 days
    assert rolling_flights(rows(20) + old, TODAY, rolling, STATIC) == rolling_flights(rows(20), TODAY, rolling, STATIC)


def test_excluded_windows_never_feed_the_ladder(rolling):
    s = replace(rolling, ladder_exclude_ranges=((date(2026, 12, 18), date(2027, 1, 4)),))
    xmas = rows(20, prices=[999], window="2026-12-25_weekend")
    assert rolling_flights(rows(20) + xmas, TODAY, s, STATIC) == rolling_flights(rows(20), TODAY, s, STATIC)
    assert rolling_flights(xmas, TODAY, s, STATIC) is STATIC   # nothing left: static


def test_rungs_kept_in_order(rolling):
    flat = rolling_flights(rows(20, prices=[300]), TODAY, rolling, STATIC)
    assert flat == {"exceptional": 300, "good": 301, "typical": 302}


def test_config_rejects_bad_percentiles(tmp_path):
    text = open("config/scoring.yaml", encoding="utf-8").read()
    bad = tmp_path / "scoring.yaml"
    bad.write_text(text.replace("rolling_ladder: {exceptional: 10, good: 25,", "rolling_ladder: {exceptional: 30, good: 25,"),
                   encoding="utf-8")
    with pytest.raises(ValueError, match="rolling_ladder"):
        load_scoring(bad)
