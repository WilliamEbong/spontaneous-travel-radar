"""Flight/hotel bands, the 0-100 worth-it score and the candidate rule (design section 7)."""
from dataclasses import dataclass

from radar.config import City, Scoring
from radar.itineraries import Trip

PRICE_ANCHORS = (40, 28, 14, 0)   # score at the amazing, good, average thresholds and at the bad floor


def _band(value: float, b: dict) -> str:
    for name in ("amazing", "good", "average"):
        if value <= b[name]:
            return name
    return "bad"


def flight_band(price_pp: int, group: str, bands: dict) -> str:
    return _band(price_pp, bands[group])


def hotel_band(total_2n: float, group: str, bands: dict) -> str:
    return _band(total_2n, bands[group])


def band_price_score(price_pp: float, b: dict) -> float:
    """Piecewise linear through (amazing, 40), (good, 28), (average, 14), (average + (average - good), 0)."""
    xs = (b["amazing"], b["good"], b["average"], 2 * b["average"] - b["good"])
    if price_pp <= xs[0]:
        return 40.0
    for (x0, y0), (x1, y1) in zip(zip(xs, PRICE_ANCHORS), zip(xs[1:], PRICE_ANCHORS[1:])):
        if price_pp <= x1:
            return y0 + (y1 - y0) * (price_pp - x0) / (x1 - x0)
    return 0.0


def time_points(hours: float, best: float, curve: dict) -> float:
    """0..1: zero at curve['zero_at'] of the window's best possible waking hours, full at curve['full_at']."""
    r = hours / best if best else 0.0
    return max(0.0, min(1.0, (r - curve["zero_at"]) / (curve["full_at"] - curve["zero_at"])))


def worth_flying(trip: Trip, s: Scoring) -> bool:
    """Hard floor (D-51): below zero_at of the possible time there is no trip worth flying."""
    return trip.best_possible_hours > 0 and trip.hours_on_ground >= s.time_curve["zero_at"] * trip.best_possible_hours


@dataclass(frozen=True)
class Components:
    price: float
    time: float
    convenience: float
    city: float
    events: float
    weather: float


@dataclass(frozen=True)
class Scored:
    trip: Trip
    band: str
    price_pp: int
    lodging_cad: float
    lodging_source: str               # "estimate" | "serpapi"
    total_cad: float
    components: Components
    score: int
    candidate: bool
    hotel_spike: bool
    history_pct: float | None = None


def to_cad(amount: float, currency: str, s: Scoring) -> float:
    return amount * s.usd_cad if currency == "USD" else amount


def lodging_estimate_cad(city: City, nights: int, s: Scoring) -> float:
    b = s.hotel_bands[city.hotel_group]
    return to_cad((b["amazing"] + b["good"]) / 2 / 2 * nights, city.hotel_currency, s)


def convenience(trip: Trip, city: City) -> float:
    legs = (trip.out, trip.back)
    if all(leg.stops == 0 for leg in legs):
        c = 10
    else:
        c = 5 if max(leg.layover_min for leg in legs if leg.stops) <= 150 else 2
    c -= 2 if city.airport_to_core_min > 45 else 0
    c -= 3 if city.car_needed else 0
    c -= 2 if trip.out.arr.hour < 5 else 0      # arrival after midnight
    return max(0, c)


BANDS = ("amazing", "good", "average", "bad")


def _candidate(band: str, history_pct: float | None, trip_class: str, s: Scoring) -> bool:
    if trip_class == "weekend":   # weekend-only trips: only the gate band or better (D-52)
        return BANDS.index(band) <= BANDS.index(s.trip_classes["weekend"]["gate_band"])
    return band == "amazing" or (band == "good" and history_pct is not None and history_pct <= 10)


def score_trip(trip: Trip, city: City, s: Scoring, *, n_events: int, weather_score: float,
               history_pct: float | None, lodging_cad: float | None = None) -> Scored:
    """lodging_cad None uses the band estimate; a real hotel total re-scores through the same function."""
    w = s.weights
    price_pp = round(trip.flights_cad_2pax / 2)
    band = flight_band(price_pp, city.flight_group, s.flight_bands)
    p = band_price_score(price_pp, s.flight_bands[city.flight_group])
    if history_pct is not None:
        p = 0.5 * p + 0.5 * 40 * (1 - history_pct / 100)
    comp = Components(
        price=w["price"] * p / 40,
        time=w["time"] * time_points(trip.hours_on_ground, trip.best_possible_hours, s.time_curve),
        convenience=w["convenience"] * convenience(trip, city) / 10,
        city=w["city"] * city.rank / 10,
        events=w["events"] * min(10.0, 3 + 1.5 * n_events) / 10,
        weather=w["weather"] * max(0.0, min(10.0, weather_score)) / 10,
    )
    source = "estimate" if lodging_cad is None else "serpapi"
    lodging = lodging_estimate_cad(city, trip.nights, s) if lodging_cad is None else lodging_cad
    return Scored(
        trip=trip, band=band, price_pp=price_pp, lodging_cad=round(lodging, 2), lodging_source=source,
        total_cad=round(trip.flights_cad_2pax + lodging + 4 * city.transfer_cost_cad_pp_each_way, 2),
        components=comp, score=round(sum(vars(comp).values())),
        candidate=_candidate(band, history_pct, trip.trip_class, s),
        hotel_spike=n_events >= 6, history_pct=history_pct,
    )


def best_per_window(scored: list[Scored]) -> list[Scored]:
    """One winner per (city, window): highest score, then lowest total."""
    best: dict[tuple[str, str], Scored] = {}
    for x in scored:
        k = (x.trip.city_key, x.trip.window_id)
        if k not in best or (x.score, -x.total_cad) > (best[k].score, -best[k].total_cad):
            best[k] = x
    return list(best.values())
