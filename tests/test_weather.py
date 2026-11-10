from datetime import date, timedelta

import pytest

from radar.weather import Weather, score_from_daily, weather_line, weather_score
from tests.conftest import FIXTURES, city, load_fixture


def test_weather_formula():
    assert score_from_daily([20.0, 22.0], [10, 10]) == pytest.approx(9.5)
    assert score_from_daily([38.0], [0]) == pytest.approx(10 - 11 / 3)      # 11 C over 27
    assert score_from_daily([-5.0], [80]) == 0


def test_weather_reads_forecast_from_cache(tmp_path):
    (tmp_path / "om-chicago.json").write_text((FIXTURES / "om_chicago.json").read_text())
    first = date.fromisoformat(load_fixture("om_chicago.json")["daily"]["time"][0])
    w = weather_score(city("chicago"), [first, first + timedelta(days=1)], today=first, cache_dir=tmp_path)
    score, source = w[:2]
    assert source == "forecast" and 0 <= score <= 10
    assert w.highs == (14.6, 15.8) and w.precip == (1, 1)                   # the fixture's first two days
    assert weather_line(w) == "highs 15–16 °C, rain chance 1% (forecast)"   # D-75: the breakdown's weather line


def test_weather_falls_back_to_normals():
    far = [date.today() + timedelta(days=40)]
    score, source = weather_score(city("chicago"), far)[:2]
    assert source == "normals" and 0 <= score <= 10
    jan = weather_score(city("chicago"), [date(2027, 1, 16), date(2027, 1, 17)], today=date(2026, 11, 10))
    assert jan.months == ("January",) and weather_line(jan) == "January normals: highs −1 °C, rain on 11 of 30 days"
    assert weather_line(Weather(7.0, "given")) == "score 7.0 of 10 as given"
