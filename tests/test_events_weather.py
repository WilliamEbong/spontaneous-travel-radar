from datetime import date, timedelta

import pytest

from radar.events import Event, event_bounds, fetch_events, notable_count, parse_events
from radar.weather import score_from_daily, weather_score
from tests.conftest import FIXTURES, city, load_fixture


def test_parse_events_fixture():
    evs = parse_events(load_fixture("tm_chicago.json"))
    assert evs and all(e.segment and e.name for e in evs)


def test_notable_count_filters_dates_venues_and_duplicates():
    d = date(2026, 12, 5)
    evs = [Event("Bulls v Heat", d, "Sports", "United Center", ""),
           Event("Bulls v Heat", d, "Sports", "United Center", ""),
           Event("Jazz trio", d, "Music", "Green Mill", ""),
           Event("Bears v Packers", d + timedelta(days=9), "Sports", "Soldier Field", "")]
    assert notable_count(evs, [d, d + timedelta(days=1)]) == 1


def test_event_bounds_are_utc_of_local_midnight():
    start, end = event_bounds(city("chicago"), date(2026, 12, 4), date(2026, 12, 6))     # Chicago is UTC-6 in December
    assert start == "2026-12-04T06:00:00Z" and end == "2026-12-07T05:59:59Z"


def test_no_key_means_no_events(tmp_path):
    assert fetch_events(city("chicago"), date(2026, 12, 4), date(2026, 12, 6), api_key=None, cache_dir=tmp_path) == []


def test_weather_formula():
    assert score_from_daily([20.0, 22.0], [10, 10]) == pytest.approx(9.5)
    assert score_from_daily([38.0], [0]) == pytest.approx(10 - 11 / 3)      # 11 C over 27
    assert score_from_daily([-5.0], [80]) == 0


def test_weather_reads_forecast_from_cache(tmp_path):
    (tmp_path / "om-chicago.json").write_text((FIXTURES / "om_chicago.json").read_text())
    first = date.fromisoformat(load_fixture("om_chicago.json")["daily"]["time"][0])
    score, source = weather_score(city("chicago"), [first, first + timedelta(days=1)], today=first, cache_dir=tmp_path)
    assert source == "forecast" and 0 <= score <= 10


def test_weather_falls_back_to_normals():
    far = [date.today() + timedelta(days=40)]
    score, source = weather_score(city("chicago"), far)
    assert source == "normals" and 0 <= score <= 10
