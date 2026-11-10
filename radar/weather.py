"""Weather score 0..10: Open-Meteo forecast inside 16 days, climate normals beyond. Never raises."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import NamedTuple

import httpx

from radar.config import City

URL = "https://api.open-meteo.com/v1/forecast"
HORIZON_DAYS = 15   # forecast_days=16 covers today + 15
MONTHS = ("", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


class Weather(NamedTuple):
    """The score and the per-day figures it was computed from, so the dashboard can show them (score breakdown)."""
    score: float
    source: str                   # forecast | normals | given (tests and callers that pass a bare number)
    highs: tuple = ()             # C per trip day
    precip: tuple = ()            # % per trip day: rain chance (forecast) or rain days / 30 (normals)
    months: tuple = ()            # month names the normals came from


def score_from_daily(highs_c: list[float], precip_prob: list[float]) -> float:
    """Per day: 10, minus 1 per 3 C the high sits outside 15-27 C, minus precip%/20; floor 0; mean."""
    scores = []
    for hi, p in zip(highs_c, precip_prob):
        off = max(0.0, 15 - hi, hi - 27)
        scores.append(max(0.0, 10 - off / 3 - (p or 0) / 20))
    return sum(scores) / len(scores) if scores else 5.0


def normals_score(city: City, days: list[date]) -> Weather:
    highs = [city.climate[d.month][0] for d in days]
    precip = [city.climate[d.month][2] / 30 * 100 for d in days]
    return Weather(score_from_daily(highs, precip), "normals", tuple(highs), tuple(precip),
                   tuple(dict.fromkeys(MONTHS[d.month] for d in days)))


def _range(vals, unit: str) -> str:
    lo, hi = round(min(vals)), round(max(vals))
    return (f"{lo}{unit}" if lo == hi else f"{lo}–{hi}{unit}").replace("-", "−")


def weather_line(w: Weather) -> str:
    """One plain line of the inputs behind the score: 'highs 6–8 °C, rain chance 40–60% (forecast)'."""
    if w.source == "forecast" and w.highs:
        return f"highs {_range(w.highs, ' °C')}, rain chance {_range(w.precip, '%')} (forecast)"
    if w.source == "normals" and w.highs:
        rain_days = round(sum(w.precip) / len(w.precip) * 0.3)
        return f"{'/'.join(w.months)} normals: highs {_range(w.highs, ' °C')}, rain on {rain_days} of 30 days"
    return f"score {w.score:.1f} of 10 as given"


def weather_score(city: City, days: list[date], *, today: date | None = None, cache_dir=None) -> Weather:
    """(score, source, per-day highs and precipitation): a tuple, so `score, source = weather_score(...)[:2]` still reads."""
    today = today or date.today()
    if not days or max(days) > today + timedelta(days=HORIZON_DAYS) or cache_dir is None:
        return normals_score(city, days)
    path = Path(cache_dir) / f"om-{city.key}.json"
    try:
        if not path.exists():
            r = httpx.get(URL, params={"latitude": city.lat, "longitude": city.lon, "forecast_days": 16,
                                       "daily": "temperature_2m_max,precipitation_probability_max",
                                       "timezone": "auto"}, timeout=10)
            r.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(r.text, encoding="utf-8")
        daily = json.loads(path.read_text(encoding="utf-8"))["daily"]
        idx = {d: i for i, d in enumerate(daily["time"])}
        rows = [idx[d.isoformat()] for d in days]
        highs = [daily["temperature_2m_max"][i] for i in rows]
        if None in highs:
            raise ValueError("missing forecast high")
        precip = [daily["precipitation_probability_max"][i] or 0 for i in rows]
        return Weather(score_from_daily(highs, precip), "forecast", tuple(highs), tuple(precip))
    except (httpx.HTTPError, ValueError, KeyError) as e:
        print(f"open-meteo {city.key}: {type(e).__name__}: {e}", file=sys.stderr)
        return normals_score(city, days)
