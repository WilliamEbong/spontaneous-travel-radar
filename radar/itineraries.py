"""Pair one-way legs into trips per window; enforce the trip-window rule; hours on the ground."""
from dataclasses import dataclass
from datetime import date, timedelta, timezone

from radar.config import City
from radar.flights import Leg
from radar.windows import CALGARY, Window

OVERHEAD_H = 3   # 1h after landing + 2h before departure (design section 7.1)
SLEEP_H = 8


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
    hours_on_ground: float
    best_possible_hours: float


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


def hours_on_ground(out: Leg, back: Leg, nights: int) -> float:
    h = (back.dep.astimezone(timezone.utc) - out.arr.astimezone(timezone.utc)).total_seconds() / 3600  # UTC: DST-safe
    return max(0.0, h - OVERHEAD_H - SLEEP_H * nights)


def best_possible_hours(w: Window) -> float:
    span = w.return_to.astimezone(timezone.utc) - w.depart_from.astimezone(timezone.utc)
    return span.total_seconds() / 3600 - OVERHEAD_H - SLEEP_H * w.window_nights


def assemble(city: City, w: Window, outs: list[Leg], backs: list[Leg]) -> list[Trip]:
    best = best_possible_hours(w)
    outs = [o for o in outs if out_ok(o, w)]
    backs = [b for b in backs if back_ok(b, w)]
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
                hours_on_ground=hours_on_ground(o, b, nights), best_possible_hours=best,
            ))
    return trips
