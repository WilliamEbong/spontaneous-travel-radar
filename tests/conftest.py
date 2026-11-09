import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_leg(o, d, dep, arr, tz_o, tz_d, price=400, stops=0, layover=0):
    from radar.flights import Leg
    return Leg(o, d, datetime.fromisoformat(dep).replace(tzinfo=ZoneInfo(tz_o)),
               datetime.fromisoformat(arr).replace(tzinfo=ZoneInfo(tz_d)), ("WS",), ("WS 1",), stops, layover, 90, price)


def city(key):
    from radar.config import load_cities
    return next(c for c in load_cities() if c.key == key)


@pytest.fixture
def vancouver_trip_fixture():
    from radar.itineraries import Trip
    out = make_leg("YYC", "YVR", "2026-12-04T08:00", "2026-12-04T08:45", "America/Edmonton", "America/Vancouver", 110)
    back = make_leg("YVR", "YYC", "2026-12-06T13:00", "2026-12-06T15:30", "America/Vancouver", "America/Edmonton", 110)
    return Trip("vancouver", "YVR", "2026-12-04_fri-off", out, back, 220, date(2026, 12, 4), date(2026, 12, 6), 2, 35.0, 49.5)


@pytest.fixture
def nyc_one_stop_trip():
    from radar.itineraries import Trip
    out = make_leg("YYC", "EWR", "2026-12-04T07:00", "2026-12-04T16:00", "America/Edmonton", "America/New_York", 500, 1, 90)
    back = make_leg("EWR", "YYC", "2026-12-06T08:00", "2026-12-06T11:00", "America/New_York", "America/Edmonton", 500)
    return Trip("new_york", "EWR", "2026-12-04_fri-off", out, back, 1000, date(2026, 12, 4), date(2026, 12, 6), 2, 30.0, 49.5)


@pytest.fixture
def scored_vancouver(vancouver_trip_fixture):
    from radar.config import load_scoring
    from radar.score import score_trip
    return score_trip(vancouver_trip_fixture, city("vancouver"), load_scoring(), n_events=2, weather_score=8, history_pct=None)
