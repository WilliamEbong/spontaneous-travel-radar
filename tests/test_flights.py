from datetime import date, timedelta

import pytest

from radar.config import load_cities
from radar.flights import Budget, FetchError, LegQuery, build_queries, fetch_leg, parse_items, to_leg
from radar.windows import generate_windows
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


def test_build_queries_roles_and_filters():
    cities = [c for c in load_cities() if c.key in ("vancouver", "new_york")]
    ws = [w for w in generate_windows(date(2026, 11, 10), set()) if w.days_off[0] in (date(2026, 11, 20), date(2026, 11, 21))]
    qs = build_queries(cities, ws, scan_date=date(2026, 11, 10))
    sat = [q for q in qs if q.day == date(2026, 11, 21) and q.origin == "YVR"]      # Day N-1 for fri-off: unfiltered
    assert len(sat) == 1 and sat[0].earliest_arr_hour is None and sat[0].latest_arr_hour is None
    sun = [q for q in qs if q.day == date(2026, 11, 22) and q.origin == "YVR"]      # Day N (fri-off) and N-1 (mon-off)
    assert len(sun) == 1 and sun[0].latest_arr_hour is None
    mon = [q for q in qs if q.day == date(2026, 11, 23) and q.origin == "YVR"]      # Day N only
    assert mon[0].latest_arr_hour == 16 and mon[0].origin_tz == "America/Vancouver"
    thu = [q for q in qs if q.day == date(2026, 11, 19) and q.dest == "YVR"]
    assert thu[0].earliest_dep_hour == 19
    assert all(q.max_stops == 1 for q in qs)


def test_budget_exhaustion_is_a_fetch_error(tmp_path):
    with pytest.raises(FetchError):
        fetch_leg(LegQuery("YYC", "YVR", date(2026, 12, 4)), Budget(max_attempts=0), cache_dir=tmp_path)


def test_rotation_keeps_secondary_airports_alternating():
    cities = [c for c in load_cities() if c.key == "new_york"]
    ws = generate_windows(date(2026, 11, 10), set())
    a = {q.dest for q in build_queries(cities, ws, scan_date=date(2026, 11, 10)) if q.origin == "YYC"}
    b = {q.dest for q in build_queries(cities, ws, scan_date=date(2026, 11, 11)) if q.origin == "YYC"}
    assert "EWR" in a and "EWR" in b and (a ^ b) <= {"JFK", "LGA"} and (a | b) == {"EWR", "JFK", "LGA"}


def test_disabled_city_gets_no_queries():
    from dataclasses import replace
    cities = [replace(c, enabled=c.key != "vancouver") for c in load_cities() if c.key in ("vancouver", "seattle")]
    qs = build_queries(cities, generate_windows(date(2026, 11, 10), set()), scan_date=date(2026, 11, 10))
    assert qs and not any("YVR" in (q.origin, q.dest) for q in qs)


def test_full_matrix_fits_the_budget():
    ws = generate_windows(date(2026, 11, 10), set())
    assert len(build_queries(load_cities(), ws, scan_date=date(2026, 11, 10))) <= 800   # headroom for retries


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
