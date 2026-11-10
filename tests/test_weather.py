import json
from datetime import date, timedelta

import pytest

from radar.weather import Weather, score_from_daily, weather_line, weather_score
from tests.conftest import FIXTURES, city, load_fixture


def test_weather_formula():
    assert score_from_daily([20.0, 22.0], [10, 10]) == pytest.approx(9.5)
    assert score_from_daily([38.0], [0]) == pytest.approx(10 - 11 / 3)      # 11 C over 27
    assert score_from_daily([-5.0], [80]) == 0


def test_weather_reads_forecast_from_cache(tmp_path):
    (tmp_path / "om-chicago.json").write_text((FIXTURES / "om_chicago.json").read_text(encoding="utf-8"), encoding="utf-8")
    first = date.fromisoformat(load_fixture("om_chicago.json")["daily"]["time"][0])
    w = weather_score(city("chicago"), [first, first + timedelta(days=1)], today=first, cache_dir=tmp_path)
    score, source = w[:2]
    assert source == "forecast" and 0 <= score <= 10
    assert w.highs == (14.6, 15.8) and w.precip == (1, 1)                   # the fixture's first two days
    assert w.days == ("2026-11-09", "2026-11-10") and w.codes == (0, 1)       # D-77: the sky word's inputs
    assert weather_line(w) == "sunny, highs 15–16 °C both days"              # D-75: the breakdown's weather line
    wet = weather_score(city("chicago"), [first + timedelta(days=n) for n in (3, 4, 5)], today=first, cache_dir=tmp_path)
    assert weather_line(wet) == "rain Thu–Fri, partly cloudy Sat, highs 6–10 °C"   # codes 63, 61, 2; 83% and 63% are rain days already
    # a cache file written before the sky word existed (no weathercode) keeps the plain line
    daily = load_fixture("om_chicago.json")
    del daily["daily"]["weathercode"]
    (tmp_path / "om-chicago.json").write_text(json.dumps(daily), encoding="utf-8")
    old = weather_score(city("chicago"), [first, first + timedelta(days=1)], today=first, cache_dir=tmp_path)
    assert old.codes == () and weather_line(old) == "highs 15–16 °C, rain chance 1% (forecast)"


def test_forecast_line_reads_like_a_forecast():
    """D-77: sky word, highs, 'all 3 days' or per-day runs, and 'rain likely' on a wet day whose sky word is not wet."""
    days = ("2026-11-13", "2026-11-14", "2026-11-15")   # Fri, Sat, Sun
    assert weather_line(Weather(9.5, "forecast", (22, 23, 24), (5, 10, 5), (), days, (0, 1, 0))) == "sunny, highs 22–24 °C all 3 days"
    assert weather_line(Weather(5, "forecast", (6, 8, 7), (20, 60, 30), (), days, (3, 3, 3))) == "cloudy, highs 6–8 °C all 3 days, rain likely Sat (60%)"
    assert weather_line(Weather(5, "forecast", (6, 8, 7), (20, 60, 70), (), days, (0, 0, 61))) == "sunny Fri–Sat, rain Sun, highs 6–8 °C, rain likely Sat (60%)"
    assert weather_line(Weather(5, "forecast", (-3,), (40,), (), days[:1], (71,))) == "snow, highs −3 °C"
    assert weather_line(Weather(5, "forecast", (6, 8), (20, 60), (), days[:2], (3, None))) == "highs 6–8 °C, rain chance 20–60% (forecast)"


def test_weather_falls_back_to_normals():
    far = [date.today() + timedelta(days=40)]
    score, source = weather_score(city("chicago"), far)[:2]
    assert source == "normals" and 0 <= score <= 10
    jan = weather_score(city("chicago"), [date(2027, 1, 16), date(2027, 1, 17)], today=date(2026, 11, 10))
    assert jan.months == ("January",) and weather_line(jan) == "January normals: highs −1 °C, rain on 11 of 30 days"
    assert weather_line(Weather(7.0, "given")) == "score 7.0 of 10 as given"
