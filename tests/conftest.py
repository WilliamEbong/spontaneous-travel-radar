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


def ref(key):
    from radar.config import load_references
    return load_references()[key]


@pytest.fixture
def vancouver_trip_fixture():
    from radar.itineraries import Trip
    out = make_leg("YYC", "YVR", "2026-12-04T08:00", "2026-12-04T08:45", "America/Edmonton", "America/Vancouver", 110)
    back = make_leg("YVR", "YYC", "2026-12-06T13:00", "2026-12-06T15:30", "America/Vancouver", "America/Edmonton", 110)
    return Trip("vancouver", "YVR", "2026-12-04_fri-off", out, back, 220, date(2026, 12, 4), date(2026, 12, 6), 2, 31.0)


@pytest.fixture
def nyc_one_stop_trip():
    from radar.itineraries import Trip
    out = make_leg("YYC", "EWR", "2026-12-04T07:00", "2026-12-04T16:00", "America/Edmonton", "America/New_York", 500, 1, 90)
    back = make_leg("EWR", "YYC", "2026-12-06T08:00", "2026-12-06T11:00", "America/New_York", "America/Edmonton", 500)
    return Trip("new_york", "EWR", "2026-12-04_fri-off", out, back, 1000, date(2026, 12, 4), date(2026, 12, 6), 2, 24.0)


@pytest.fixture
def scored_vancouver(vancouver_trip_fixture):
    from radar.config import load_scoring
    from radar.score import score_trip
    return score_trip(vancouver_trip_fixture, city("vancouver"), ref("vancouver"), load_scoring(), weather_score=8, history_pct=None)


def history_row(day: str, window: str, price_pp: int, score: int, *, city="vancouver", trip_class="dayoff") -> dict:
    """A logged winner for the backtest (D-82). Its complete trip is far under any typical trip, so the price
    component stays at the full 45 under every variant and its replayed score is exactly `score`."""
    from datetime import timedelta
    from radar.config import load_scoring
    back = (date.fromisoformat(window[:10]) + timedelta(days=2)).isoformat()
    return {"scan_date": day, "city": city, "window_id": window, "trip_class": trip_class, "winner": True,
            "price_pp": price_pp, "share": 0.1, "total_cad": 100.0, "nights": 2, "score": score, "candidate": False,
            "out_arr": f"{window[:10]}T08:45:00-08:00", "back_dep": f"{back}T13:00:00-08:00",
            "components": {"price": 45.0, "time": score - 45.0, "convenience": 0.0, "city": 0.0, "weather": 0.0},
            "inputs": {"weights": dict(load_scoring().weights)}}


CYCLE = (120, 130, 145, 150, 190)   # one weekend's fares over five days: the low is 120, near the low is 132 or less


def cycle_score(price: int) -> int:
    """Near-low fares 73, good fares that are not near the low 71, the rest 50: at 70 every good fare is sent for a
    closer look (half of them wrongly); at 72 only the near-low ones are."""
    return 73 if price <= 130 else 71 if price <= 150 else 50


def synthetic_history(days: int = 21, windows: int = 4) -> list[dict]:
    """Vancouver day-off weekends priced every day from 2026-11-09, each going round CYCLE."""
    from datetime import timedelta
    out = []
    for d in range(days):
        day = (date(2026, 11, 9) + timedelta(days=d)).isoformat()
        for w in range(windows):
            window = (date(2027, 1, 15) + timedelta(days=7 * w)).isoformat() + "_fri-off"
            price = CYCLE[(d + w) % len(CYCLE)]
            out.append(history_row(day, window, price, cycle_score(price)))
    return out
