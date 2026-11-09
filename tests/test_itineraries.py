from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from radar.config import load_cities
from radar.flights import Leg
from radar.itineraries import assemble, best_possible_hours, hotel_dates, hours_on_ground, in_window
from radar.windows import generate_windows


def leg(o, d, dep, arr, tz_o, tz_d, price=400, stops=0):
    return Leg(o, d, datetime.fromisoformat(dep).replace(tzinfo=ZoneInfo(tz_o)),
               datetime.fromisoformat(arr).replace(tzinfo=ZoneInfo(tz_d)), ("WS",), ("WS 1",), stops, 0, 90, price)


W = next(w for w in generate_windows(date(2026, 11, 10), set()) if w.id == "2026-11-20_fri-off")


def test_evening_out_and_after_midnight_return_are_in_window():
    out = leg("YYC", "LAX", "2026-11-19T19:45", "2026-11-19T22:00", "America/Edmonton", "America/Los_Angeles")
    back = leg("LAX", "YYC", "2026-11-21T22:30", "2026-11-22T01:40", "America/Los_Angeles", "America/Edmonton")
    assert in_window(out, back, W)          # Review Focus 1


def test_return_after_4pm_day3_is_out():
    out = leg("YYC", "YVR", "2026-11-20T08:00", "2026-11-20T08:30", "America/Edmonton", "America/Vancouver")
    back = leg("YVR", "YYC", "2026-11-22T15:00", "2026-11-22T17:20", "America/Vancouver", "America/Edmonton")
    assert not in_window(out, back, W)


def test_out_before_1930_is_out():
    out = leg("YYC", "YVR", "2026-11-19T19:00", "2026-11-19T19:30", "America/Edmonton", "America/Vancouver")
    back = leg("YVR", "YYC", "2026-11-22T10:00", "2026-11-22T12:20", "America/Vancouver", "America/Edmonton")
    assert not in_window(out, back, W)


def test_return_landing_before_5pm_day2_is_out():
    out = leg("YYC", "YVR", "2026-11-20T08:00", "2026-11-20T08:30", "America/Edmonton", "America/Vancouver")
    back = leg("YVR", "YYC", "2026-11-21T14:00", "2026-11-21T16:30", "America/Vancouver", "America/Edmonton")
    assert not in_window(out, back, W)


def test_hours_on_ground_crosses_time_zones():
    out = leg("YYC", "EWR", "2026-11-19T19:45", "2026-11-20T01:30", "America/Edmonton", "America/New_York")   # Review Focus 2
    back = leg("EWR", "YYC", "2026-11-22T07:00", "2026-11-22T09:45", "America/New_York", "America/Edmonton")
    # 01:30 Fri -> 07:00 Sun local = 53.5h; minus 3h overhead and 16h sleep = 34.5
    assert hours_on_ground(out, back, 2) == pytest.approx(34.5)


def test_hotel_dates_cover_the_arrival_night():
    out = leg("YYC", "EWR", "2026-11-19T19:45", "2026-11-20T01:30", "America/Edmonton", "America/New_York")
    back = leg("EWR", "YYC", "2026-11-22T07:00", "2026-11-22T09:45", "America/New_York", "America/Edmonton")
    assert hotel_dates(out, back) == (date(2026, 11, 19), date(2026, 11, 22))      # 01:30 arrival needs Thursday night
    out2 = leg("YYC", "LAX", "2026-11-19T19:45", "2026-11-19T22:00", "America/Edmonton", "America/Los_Angeles")
    back2 = leg("LAX", "YYC", "2026-11-22T06:30", "2026-11-22T10:00", "America/Los_Angeles", "America/Edmonton")
    assert hotel_dates(out2, back2) == (date(2026, 11, 19), date(2026, 11, 22))


def test_best_possible_hours_fri_off():
    # 19:30 Thu -> 16:00 Sun = 68.5h; minus 3 minus 16 = 49.5
    assert best_possible_hours(W) == pytest.approx(49.5)


def test_assemble_keeps_only_in_window_pairs_and_sums_prices():
    la = next(c for c in load_cities() if c.key == "los_angeles")
    outs = [leg("YYC", "LAX", "2026-11-20T08:00", "2026-11-20T09:30", "America/Edmonton", "America/Los_Angeles", 300),
            leg("YYC", "LAX", "2026-11-19T15:00", "2026-11-19T16:30", "America/Edmonton", "America/Los_Angeles", 100)]
    backs = [leg("LAX", "YYC", "2026-11-22T09:00", "2026-11-22T12:30", "America/Los_Angeles", "America/Edmonton", 250)]
    trips = assemble(la, W, outs, backs)
    assert len(trips) == 1 and trips[0].flights_cad_2pax == 550 and trips[0].nights == 2
