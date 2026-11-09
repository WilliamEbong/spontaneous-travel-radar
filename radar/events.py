"""Ticketmaster Discovery v2: events in the city during a window. Never raises; [] on any failure."""
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from radar.config import City

URL = "https://app.ticketmaster.com/discovery/v2/events.json"


@dataclass(frozen=True)
class Event:
    name: str
    date: date
    segment: str
    venue: str
    url: str


def event_bounds(city: City, start: date, end: date) -> tuple[str, str]:
    """Destination-local midnight boundaries converted to UTC, as Ticketmaster wants them."""
    tz = ZoneInfo(city.tz)
    lo = datetime.combine(start, datetime.min.time(), tzinfo=tz)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz) - timedelta(seconds=1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return lo.astimezone(timezone.utc).strftime(fmt), hi.astimezone(timezone.utc).strftime(fmt)


def parse_events(payload: dict) -> list[Event]:
    out = []
    for e in payload.get("_embedded", {}).get("events", []):
        try:
            cls = (e.get("classifications") or [{}])[0]
            out.append(Event(
                name=e["name"], date=date.fromisoformat(e["dates"]["start"]["localDate"]),
                segment=(cls.get("segment") or {}).get("name", ""),
                venue=((e.get("_embedded") or {}).get("venues") or [{}])[0].get("name", ""),
                url=e.get("url", ""),
            ))
        except (KeyError, ValueError):
            continue
    return out


# ponytail: venue-name keywords stand in for capacity (the Discovery API has no capacity field);
# swap for a venue-id list if the digest shows misses.
BIG_VENUE = re.compile(r"\b(stadium|arena|field|center|centre|garden|dome|coliseum|amphitheat(re|er)"
                       r"|ballpark|speedway|bowl|sphere|forum)\b", re.IGNORECASE)


def is_notable(e: Event) -> bool:
    return bool(BIG_VENUE.search(e.venue))


def notable_count(events: list[Event], days) -> int:
    """Distinct big-venue events on the window's days (a raw count saturates: Chicago has ~240 a weekend)."""
    days = set(days)
    return len({e.name for e in events if e.date in days and is_notable(e)})


def fetch_events(city: City, start: date, end: date, *, api_key: str | None, cache_dir) -> list[Event]:
    if not api_key:
        return []
    path = Path(cache_dir) / f"tm-{city.key}-{start}-{end}.json"
    try:
        return parse_events(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):   # missing or half-written cache file = cache miss
        pass
    lo, hi = event_bounds(city, start, end)
    try:
        time.sleep(0.25)   # Ticketmaster allows 5 requests per second
        r = httpx.get(URL, params={"apikey": api_key, "city": city.name, "countryCode": city.country,
                                   "startDateTime": lo, "endDateTime": hi, "size": 200, "sort": "date,asc"},
                      timeout=10)
        r.raise_for_status()
        payload = r.json()
    except (httpx.HTTPError, ValueError) as e:
        print(f"ticketmaster {city.key} {start}: {type(e).__name__}", file=sys.stderr)  # never log the URL: it has the key
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)
    return parse_events(payload)
