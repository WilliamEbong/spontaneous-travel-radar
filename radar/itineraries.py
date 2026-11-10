"""Pair one-way legs into trips per window; enforce the trip-window rule; hours awake there."""
from dataclasses import dataclass
from datetime import date, timedelta, timezone

from radar.config import City
from radar.flights import Leg
from radar.windows import CALGARY, Window

# Defaults for config/scoring.yaml: time_rule (D-next); the scan passes the config's values through assemble().
OVERHEAD_H = 4.5   # per trip: 1 h after landing, 2.5 h at the airport before the return flight, 1 h of other airport time
SLEEP_H = 10       # per night


@dataclass(frozen=True)
class Trip:
    city_key: str
    airport: str                  # "EWR", or "EWR/LGA" for an open jaw within the city
    window_id: str
    out: Leg
    back: Leg
    flights_cad_2pax: int         # one-way sums only
    check_in: date                # destination-local hotel dates
    check_out: date
    nights: int
    hours_on_ground: float        # hours awake there: landing to take-off, minus the airport overhead and the nights' sleep
    trip_class: str = "dayoff"    # from the window (D-52)


def out_ok(out: Leg, w: Window) -> bool:
    return w.depart_from <= out.dep.astimezone(CALGARY) <= w.depart_to


def back_ok(back: Leg, w: Window) -> bool:
    return w.return_from <= back.arr.astimezone(CALGARY) <= w.return_to


def in_window(out: Leg, back: Leg, w: Window) -> bool:
    return out_ok(out, w) and back_ok(back, w)


def hotel_dates(out: Leg, back: Leg) -> tuple[date, date]:
    """An arrival before 05:00 local needs the previous night's room."""
    check_in = out.arr.date() - timedelta(days=1 if out.arr.hour < 5 else 0)
    return check_in, back.dep.date()


def hours_on_ground(out: Leg, back: Leg, nights: int, *, overhead_h: float = OVERHEAD_H, sleep_h: float = SLEEP_H) -> float:
    """Hours awake there, the same measure for every trip class and window."""
    h = (back.dep.astimezone(timezone.utc) - out.arr.astimezone(timezone.utc)).total_seconds() / 3600  # UTC: DST-safe
    return max(0.0, h - overhead_h - sleep_h * nights)


def assemble(city: City, w: Window, outs: list[Leg], backs: list[Leg], *,
             overhead_h: float = OVERHEAD_H, sleep_h: float = SLEEP_H) -> list[Trip]:
    nonstop = w.trip_class == "weekend"   # weekend-only trips: non-stop is part of the hard rule (D-52)
    outs = [o for o in outs if out_ok(o, w) and not (nonstop and o.stops)]
    backs = [b for b in backs if back_ok(b, w) and not (nonstop and b.stops)]
    trips = []
    for o in outs:
        for b in backs:
            if b.dep <= o.arr:
                continue
            ci, co = hotel_dates(o, b)
            nights = (co - ci).days
            trips.append(Trip(
                city_key=city.key, airport=o.dest if o.dest == b.origin else f"{o.dest}/{b.origin}",
                window_id=w.id, out=o, back=b, flights_cad_2pax=o.price_cad_2pax + b.price_cad_2pax,
                check_in=ci, check_out=co, nights=nights,
                hours_on_ground=hours_on_ground(o, b, nights, overhead_h=overhead_h, sleep_h=sleep_h), trip_class=w.trip_class,
            ))
    return trips
