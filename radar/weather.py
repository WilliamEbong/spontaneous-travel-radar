"""Weather score 0..10: Open-Meteo forecast inside 16 days, climate normals beyond. Never raises."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

from radar.config import City

URL = "https://api.open-meteo.com/v1/forecast"
HORIZON_DAYS = 15   # forecast_days=16 covers today + 15


def score_from_daily(highs_c: list[float], precip_prob: list[float]) -> float:
    """Per day: 10, minus 1 per 3 C the high sits outside 15-27 C, minus precip%/20; floor 0; mean."""
    scores = []
    for hi, p in zip(highs_c, precip_prob):
        off = max(0.0, 15 - hi, hi - 27)
        scores.append(max(0.0, 10 - off / 3 - (p or 0) / 20))
    return sum(scores) / len(scores) if scores else 5.0


def normals_score(city: City, days: list[date]) -> float:
    return score_from_daily([city.climate[d.month][0] for d in days],
                            [city.climate[d.month][2] / 30 * 100 for d in days])


def weather_score(city: City, days: list[date], *, today: date | None = None, cache_dir=None) -> tuple[float, str]:
    today = today or date.today()
    if not days or max(days) > today + timedelta(days=HORIZON_DAYS) or cache_dir is None:
        return normals_score(city, days), "normals"
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
        return score_from_daily(highs, [daily["precipitation_probability_max"][i] for i in rows]), "forecast"
    except (httpx.HTTPError, ValueError, KeyError) as e:
        print(f"open-meteo {city.key}: {type(e).__name__}: {e}", file=sys.stderr)
        return normals_score(city, days), "normals"
