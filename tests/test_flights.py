from datetime import date, timedelta

import pytest

from radar.config import load_cities, load_scoring
from radar.flights import Budget, FetchError, LegQuery, build_queries, fetch_leg, parse_items, to_leg
from radar.windows import class_windows, generate_windows, weekend_windows
from tests.conftest import load_fixture


def test_to_leg_parses_fixture_non_stop():
    raw = load_fixture("ff_yyc_yvr_oneway.json")[0]
    leg = to_leg(raw, "YYC", "YVR", "America/Edmonton", "America/Vancouver")
    assert leg.stops == 0 and leg.price_cad_2pax > 0 and leg.layover_min == 0
    assert leg.dep.tzinfo is not None and leg.arr < leg.dep + timedelta(hours=3)
    assert leg.airlines and leg.flight_numbers[0].startswith(leg.airlines[0])


def test_to_leg_one_stop_layover():
    raw = load_fixture("ff_one_stop.json")[0]
    leg = to_leg(raw, "YYC", "LAS", "America/Edmonton", "America/Los_Angeles")
    assert leg.stops == 1 and 0 < leg.layover_min < 24 * 60
    assert leg.duration_min == pytest.approx((leg.arr - leg.dep).total_seconds() / 60)


def test_to_leg_drops_two_stop():
    raw = load_fixture("ff_two_stop.json")[0]
    assert to_leg(raw, "YYC", "MSY", "America/Edmonton", "America/Chicago") is None


def test_garbled_page_is_a_fetch_error():
    with pytest.raises(FetchError):
        parse_items("<html><body>unusual traffic</body></html>")


CLASSES = load_scoring().trip_classes
EVERY_DAY = {**CLASSES, "dayoff": {**CLASSES["dayoff"], "rotate_days": 1}}   # rotation off, to test roles


def test_build_queries_roles_and_filters():
    cities = [c for c in load_cities() if c.key in ("vancouver", "new_york")]
    ws = [w for w in generate_windows(date(2026, 11, 10), set()) if w.days_off[0] in (date(2026, 11, 20), date(2026, 11, 21))]
    qs = build_queries(cities, ws, date(2026, 11, 10), EVERY_DAY)
    sat = [q for q in qs if q.day == date(2026, 11, 21) and q.origin == "YVR"]      # Day N-1 for fri-off: unfiltered
    assert len(sat) == 1 and sat[0].earliest_arr_hour is None and sat[0].latest_arr_hour is None
    sun = [q for q in qs if q.day == date(2026, 11, 22) and q.origin == "YVR"]      # Day N (fri-off) and N-1 (mon-off)
    assert len(sun) == 1 and sun[0].latest_arr_hour is None
    mon = [q for q in qs if q.day == date(2026, 11, 23) and q.origin == "YVR"]      # Day N only
    assert mon[0].latest_arr_hour == 16 and mon[0].origin_tz == "America/Vancouver"
    thu = [q for q in qs if q.day == date(2026, 11, 19) and q.dest == "YVR"]
    assert thu[0].earliest_dep_hour == 19
    sat_out = [q for q in qs if q.day == date(2026, 11, 21) and q.dest == "YVR"]   # Day 1 (mon-off): whole day (D-50)
    assert len(sat_out) == 1 and sat_out[0].latest_dep_hour is None and sat_out[0].earliest_dep_hour is None
    assert all(q.max_stops == 1 for q in qs)


def test_budget_exhaustion_is_a_fetch_error(tmp_path):
    with pytest.raises(FetchError):
        fetch_leg(LegQuery("YYC", "YVR", date(2026, 12, 4)), Budget(max_attempts=0), cache_dir=tmp_path)


def _out_days(qs, dest):
    return {q.day for q in qs if q.origin == "YYC" and q.dest == dest}


def test_dayoff_rotation_covers_each_city_weekend_once_in_three_days():
    cities = [c for c in load_cities() if c.key == "new_york"]
    ws = generate_windows(date(2026, 11, 10), set(), 42, 112)
    days = [_out_days(build_queries(cities, ws, date(2026, 11, 10 + i), CLASSES), "EWR") for i in range(3)]
    every = {d for w in ws for d in w.out_dates}
    assert all(days) and set().union(*days) == every                                  # all weekends seen in 3 days
    assert sum(len(d) for d in days) == len(every)                                      # ...each exactly once
    jfk = [_out_days(build_queries(cities, ws, date(2026, 11, 10 + i), CLASSES), "JFK") for i in range(9)]
    assert set().union(*jfk) == every and sum(len(d) for d in jfk) == len(every)        # secondary: once in 9 days


def test_weekend_queries_are_non_stop_short_hops_with_basic_fares():
    ws = weekend_windows(date(2026, 11, 10), 3, 42, "17:30", "12:00")
    qs = build_queries(load_cities(), ws, date(2026, 11, 10), CLASSES)
    dests = {q.dest for q in qs if q.origin == "YYC"}
    assert dests == {"SFO", "YVR", "SEA", "LAS", "PDX", "DEN", "PSP"}                  # air time <= 180 min, first airport
    assert all(q.max_stops == 0 and not q.exclude_basic and q.key().endswith("-weekend") for q in qs)
    fri = [q for q in qs if q.dest == "YVR" and q.day == date(2026, 11, 13)]
    sat = [q for q in qs if q.dest == "YVR" and q.day == date(2026, 11, 14)]
    sun = [q for q in qs if q.origin == "YVR" and q.day == date(2026, 11, 15)]
    assert fri[0].earliest_dep_hour == 17 and sat[0].latest_dep_hour == 12 and sun[0].latest_arr_hour == 16


def test_classes_never_share_a_query():
    s = load_scoring()
    today = date(2026, 11, 10)   # both classes over the same weekends, to force same-day legs
    ws = generate_windows(today, set()) + weekend_windows(today, 3, 42, "17:30", "12:00")
    qs = build_queries([c for c in load_cities() if c.key == "vancouver"], ws, today, EVERY_DAY)
    both = {(q.origin, q.dest, q.day) for q in qs if q.trip_class == "weekend"} & {(q.origin, q.dest, q.day) for q in qs if q.trip_class == "dayoff"}
    assert both and all(q.exclude_basic == s.trip_classes[q.trip_class]["exclude_basic"] for q in qs)   # same day, two queries
    assert len({q.key() for q in qs}) == len(qs)


def test_disabled_city_gets_no_queries():
    from dataclasses import replace
    cities = [replace(c, enabled=c.key != "vancouver") for c in load_cities() if c.key in ("vancouver", "seattle")]
    qs = build_queries(cities, generate_windows(date(2026, 11, 10), set()), date(2026, 11, 10), EVERY_DAY)
    assert qs and not any("YVR" in (q.origin, q.dest) for q in qs)


def test_daily_volume_stays_under_todays_702():
    s = load_scoring()
    for i in range(7):
        today = date(2026, 11, 10) + timedelta(days=i)
        n = len(build_queries(load_cities(), class_windows(today, s, set()), today, s.trip_classes))
        assert 500 <= n <= 702, (today, n)                                              # D-52 budget


def test_slim_items_parse_the_same():
    from radar.flights import slim
    for name, dest, tz in (("ff_yyc_yvr_oneway.json", "YVR", "America/Vancouver"), ("ff_one_stop.json", "LAS", "America/Los_Angeles")):
        for raw in load_fixture(name):
            assert to_leg(slim(raw), "YYC", dest, "America/Edmonton", tz) == to_leg(raw, "YYC", dest, "America/Edmonton", tz)


def test_corrupt_cache_file_is_a_miss(tmp_path):
    q = LegQuery("YYC", "YVR", date(2026, 12, 4))
    (tmp_path / f"{q.key()}.json").write_text("[[half-writ")
    with pytest.raises(FetchError, match="budget"):       # re-fetch attempted (no budget), no JSONDecodeError
        fetch_leg(q, Budget(max_attempts=0), cache_dir=tmp_path)
