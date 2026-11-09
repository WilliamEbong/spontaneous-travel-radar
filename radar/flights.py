"""Google Flights one-way legs via fast-flights' fetcher, with our own payload parser.

fast-flights 3.1.0's parser reads only payload[3][0] ("other flights") and drops payload[2][0]
("best flights"), which often holds the cheapest fare (docs/notes/day-one-smoke.md), so
parse_items reads both lists from the raw page.
"""
import json
import random
import sys
import time
import zlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fast_flights import FlightQuery, Passengers, create_query
from fast_flights.fetcher import fetch_flights_html
from selectolax.lexbor import LexborHTMLParser

from radar.config import City
from radar.windows import Window

HOME = "YYC"
HOME_TZ = "America/Edmonton"
EXCLUDE_BASIC = True   # William's hard constraint; see docs/notes/decisions.md D-03


@dataclass(frozen=True)
class LegQuery:
    origin: str
    dest: str
    day: date
    earliest_dep_hour: int | None = None
    latest_dep_hour: int | None = None
    earliest_arr_hour: int | None = None
    latest_arr_hour: int | None = None
    max_stops: int = 1
    origin_tz: str = HOME_TZ
    dest_tz: str = HOME_TZ

    def key(self) -> str:
        return (f"{self.origin}-{self.dest}-{self.day}-{self.earliest_dep_hour}-{self.latest_dep_hour}"
                f"-{self.earliest_arr_hour}-{self.latest_arr_hour}-s{self.max_stops}")


@dataclass(frozen=True)
class Leg:
    origin: str
    dest: str
    dep: datetime                    # tz-aware, local to the origin airport
    arr: datetime                    # tz-aware, local to the destination airport
    airlines: tuple[str, ...]        # IATA carrier codes, in segment order
    flight_numbers: tuple[str, ...]
    stops: int
    layover_min: int                 # 0 when non-stop
    duration_min: int
    price_cad_2pax: int              # carry-on included, 2 adults


class FetchError(Exception):
    """Blocked page, parse failure or exhausted budget. No flights is an empty list, not this."""


class Budget:
    """Fetch attempts shared by one scan, retries included."""

    def __init__(self, max_attempts: int = 900):
        self.max_attempts = max_attempts
        self.used = 0

    def take(self) -> bool:
        if self.used >= self.max_attempts:
            return False
        self.used += 1
        return True


def parse_items(html: str) -> list:
    """Raw itinerary items from a Google Flights page: best list + other list."""
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        raise FetchError("no data script in page (blocked, consent page or layout change)")
    data = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        return []
    payload = json.loads(data)
    return [it for part in (payload[2], payload[3]) if part and part[0] for it in part[0]]


def _hm(v) -> tuple[int, int]:
    # Google omits zero parts: [8] = 08:00, [None, 31] = 00:31, None = 00:00
    p = [*(v or []), None, None]
    return p[0] or 0, p[1] or 0


def _dt(d, t, tz: str) -> datetime:
    return datetime(*d, *_hm(t), tzinfo=ZoneInfo(tz))


def to_leg(raw, origin: str, dest: str, origin_tz: str, dest_tz: str) -> Leg | None:
    """One raw Google item -> Leg; None for 2+ stops or a missing price."""
    try:
        price = raw[1][0][1]
        segs = raw[0][2]
    except (IndexError, TypeError):
        return None
    if not price or not segs or len(segs) > 2:
        return None
    dep = _dt(segs[0][20], segs[0][8], origin_tz)
    arr = _dt(segs[-1][21], segs[-1][10], dest_tz)
    layover = 0
    for a, b in zip(segs, segs[1:]):  # both times local to the connecting airport
        layover += int((datetime(*b[20], *_hm(b[8])) - datetime(*a[21], *_hm(a[10]))).total_seconds() // 60)
    carriers = [s[22][0] for s in segs if s[22]]
    return Leg(
        origin=origin, dest=dest, dep=dep, arr=arr,
        airlines=tuple(dict.fromkeys(carriers)),
        flight_numbers=tuple(f"{s[22][0]} {s[22][1]}" for s in segs if s[22] and s[22][1]),
        stops=len(segs) - 1, layover_min=layover,
        duration_min=int((arr - dep).total_seconds() // 60), price_cad_2pax=int(price),
    )


def _weekend(w: Window) -> date:
    return next(d for d in w.days_off if d.weekday() == 5)


def _rotates_in(airport: str, scan_date: date) -> bool:
    # crc32, not hash(): str hashes are salted per process
    return (scan_date.toordinal() + zlib.crc32(airport.encode())) % 2 == 0


def _merge(roles: list[dict]) -> dict:
    """Loosest filter across roles: a bound survives only if every role sets it."""
    out = {}
    for f, pick in (("earliest_dep_hour", min), ("latest_dep_hour", max),
                    ("earliest_arr_hour", min), ("latest_arr_hour", max)):
        vals = [r.get(f) for r in roles]
        out[f] = None if None in vals else pick(vals)
    return out


def build_queries(cities: list[City], windows: list[Window], scan_date: date) -> list[LegQuery]:
    weekends = sorted({_weekend(w) for w in windows})
    roles: dict[tuple, list[dict]] = {}
    order: dict[tuple, tuple] = {}
    for w in windows:
        wk = weekends.index(_weekend(w))
        for c in cities:
            for i, apt in enumerate(c.airports):
                if (i > 0 or wk >= 3) and not _rotates_in(apt, scan_date):
                    continue  # ponytail: fixed rotation; smarter coverage if health shows gaps
                for o, d, day, role in (
                    (HOME, apt, w.out_dates[0], {"earliest_dep_hour": 19}),
                    (HOME, apt, w.out_dates[1], {"latest_dep_hour": 12}),
                    (apt, HOME, w.back_dates[0], {}),                     # may land after midnight: exact check in itineraries
                    (apt, HOME, w.back_dates[1], {"latest_arr_hour": 16}),
                ):
                    k = (o, d, day, c.tz)
                    roles.setdefault(k, []).append(role)
                    order[k] = min(order.get(k, (99,)), (wk, i, day.toordinal()))
    qs = []
    for (o, d, day, tz), rs in sorted(roles.items(), key=lambda kv: order[kv[0]]):
        qs.append(LegQuery(o, d, day, **_merge(rs), max_stops=1,
                           origin_tz=HOME_TZ if o == HOME else tz, dest_tz=HOME_TZ if d == HOME else tz))
    return qs


def _fetch_items(q: LegQuery) -> list:
    query = create_query(
        flights=[FlightQuery(q.day.isoformat(), q.origin, q.dest,
                             earliest_departure_hour=q.earliest_dep_hour, latest_departure_hour=q.latest_dep_hour,
                             earliest_arrival_hour=q.earliest_arr_hour, latest_arrival_hour=q.latest_arr_hour)],
        trip="one-way", passengers=Passengers(adults=2), currency="CAD", max_stops=q.max_stops,
        carry_on_bags=1, exclude_basic_economy=EXCLUDE_BASIC,
    )
    return parse_items(fetch_flights_html(query))


def fetch_leg(q: LegQuery, budget: Budget, *, sleep_range=(3.0, 7.0), cache_dir=None, retry_wait=30.0) -> list[Leg]:
    """Cached per scan day; every network attempt (retries too) takes one unit of budget."""
    path = Path(cache_dir or f"data/cache/{date.today()}") / f"{q.key()}.json"
    if path.exists():
        items = json.loads(path.read_text(encoding="utf-8"))
    else:
        items, err = None, None
        for attempt in range(2):
            if not budget.take():
                raise FetchError("budget")
            if attempt:
                time.sleep(retry_wait)
            time.sleep(random.uniform(*sleep_range))
            try:
                items = _fetch_items(q)
                break
            except Exception as e:  # noqa: BLE001 - any fetch/parse failure gets one retry
                err = e
                print(f"fetch {q.key()} attempt {attempt + 1}: {type(e).__name__}: {e}", file=sys.stderr)
        if items is None:
            raise FetchError(f"{type(err).__name__}: {err}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(items), encoding="utf-8")
    return [leg for it in items if (leg := to_leg(it, q.origin, q.dest, q.origin_tz, q.dest_tz))]
