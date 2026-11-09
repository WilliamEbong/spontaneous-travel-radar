from datetime import date, timedelta

import pytest

from radar.weather import score_from_daily, weather_score
from tests.conftest import FIXTURES, city, load_fixture


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
