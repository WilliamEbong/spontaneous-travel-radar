from dataclasses import replace

import pytest

from radar.config import load_scoring
from radar.score import (best_per_window, flight_band, hotel_band, lodging_estimate_cad, score_trip, time_points,
                         worth_flying)
from tests.conftest import city


def test_flight_band_thresholds():
    b = load_scoring().flight_bands
    assert flight_band(119, "yvr", b) == "amazing" and flight_band(120, "yvr", b) == "amazing"
    assert flight_band(121, "yvr", b) == "good" and flight_band(190, "yvr", b) == "average" and flight_band(191, "yvr", b) == "bad"
    assert flight_band(319, "nyc_tier2", b) == "amazing"


def test_hotel_band_expensive():
    b = load_scoring().hotel_bands
    assert hotel_band(449, "expensive", b) == "amazing" and hotel_band(901, "expensive", b) == "bad"


def test_score_amazing_nonstop_vancouver_is_candidate(vancouver_trip_fixture):
    s = score_trip(vancouver_trip_fixture, city("vancouver"), load_scoring(), n_events=2, weather_score=8, history_pct=None)
    assert s.band == "amazing" and s.candidate
    assert s.components.price == 40 and s.components.city == 12 and s.components.time == 15   # r = 0.71
    assert s.score == 91 and s.lodging_source == "estimate"
    assert s.total_cad == pytest.approx(220 + 380 + 40)   # flights + mid good-band midpoint (CAD) + transfers


def test_time_curve_is_linear_between_its_anchors():
    curve = {"zero_at": 0.4, "full_at": 0.9}
    assert [time_points(r * 100, 100, curve) for r in (0.3, 0.4, 0.65, 0.9, 1.0)] == pytest.approx([0, 0, 0.5, 1, 1])


def test_time_curve_on_the_two_toronto_trips():
    """2026-11-21 mon-off, best possible 49.5 h: red-eye 01:20 out / 15:39 home keeps 34.9 h on the ground;
    the 14:25 out / 06:15 back trip Google shows keeps about 15 h. Price decides between them (D-51)."""
    s = load_scoring()
    assert 15 * time_points(34.9, 49.5, s.time_curve) == pytest.approx(15)
    assert 15 * time_points(15.0, 49.5, s.time_curve) == pytest.approx(5, abs=0.5)


def test_floor_drops_a_trip_with_too_little_time(vancouver_trip_fixture):
    s = load_scoring()
    assert worth_flying(vancouver_trip_fixture, s)
    assert not worth_flying(replace(vancouver_trip_fixture, hours_on_ground=0.09 * 49.5), s)


def test_connection_costs_convenience(nyc_one_stop_trip):
    s = score_trip(nyc_one_stop_trip, city("new_york"), load_scoring(), n_events=0, weather_score=5, history_pct=None)
    assert s.components.convenience <= 5 and s.band == "average" and not s.candidate   # 500 pp = nyc average line


def test_history_percentile_blends(vancouver_trip_fixture):
    s = score_trip(vancouver_trip_fixture, city("vancouver"), load_scoring(), n_events=0, weather_score=5, history_pct=50)
    assert s.components.price == pytest.approx(0.5 * 40 + 0.5 * 20)


def test_lodging_estimate_converts_usd_and_scales_nights():
    assert lodging_estimate_cad(city("new_york"), 3, load_scoring()) == pytest.approx(550 / 2 * 3 * 1.40)


def test_best_per_window_keeps_one(vancouver_trip_fixture, nyc_one_stop_trip):
    s = load_scoring()
    a = score_trip(vancouver_trip_fixture, city("vancouver"), s, n_events=0, weather_score=5, history_pct=None)
    b = score_trip(vancouver_trip_fixture, city("vancouver"), s, n_events=6, weather_score=5, history_pct=None)
    c = score_trip(nyc_one_stop_trip, city("new_york"), s, n_events=0, weather_score=5, history_pct=None)
    best = best_per_window([a, b, c])
    assert len(best) == 2 and b in best and b.hotel_spike
