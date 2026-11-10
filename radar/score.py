"""The pass-1 score: the complete trip against its route's typical trip, plus time, convenience, city and weather (v2, D-57).

Price is one thing, the complete trip for two (flights + lodging + transfers), as a share of what the route
normally costs (config/references.yaml). Flights alone only decide the ladder label and who gets a closer look.
"""
from dataclasses import asdict, dataclass, field
from datetime import date

from radar.config import City, Reference, Scoring
from radar.itineraries import Trip
from radar.weather import Weather, weather_line

WINTER = (11, 12, 1, 2, 3)   # room references: winter = check-in Nov to Mar (ponytail: two seasons; finer later)


def season(d: date) -> str:
    return "winter" if d.month in WINTER else "summer"


def to_cad(amount: float, currency: str, s: Scoring) -> float:
    return amount * s.usd_cad if currency == "USD" else amount


def transfers_cad(city: City) -> int:
    return 4 * city.transfer_cost_cad_pp_each_way   # two people, two ways


def room_night_cad(city: City, ref: Reference, check_in: date, level: str, s: Scoring) -> float:
    """One night at the route's typical/good/exceptional rate, taxes in, CAD."""
    return to_cad(ref.rooms[season(check_in)][level], city.hotel_currency, s) * city.hotel_tax


def typical_trip_cad(trip: Trip, city: City, ref: Reference, s: Scoring) -> float:
    """What this trip normally costs for two: typical fares, typical room nights, transfers."""
    return 2 * ref.flights["typical"] + trip.nights * room_night_cad(city, ref, trip.check_in, "typical", s) + transfers_cad(city)


def lodging_estimate_cad(trip: Trip, city: City, ref: Reference, s: Scoring) -> float:
    """Pass 1 has no real lodging yet: assume the season's good room rate, so a great fare can earn a closer look (D-58)."""
    return trip.nights * room_night_cad(city, ref, trip.check_in, "good", s)


def price_points(share: float, curve: dict) -> float:
    """Full points at or under the first share, straight lines between the points, and past the last point the
    same slope continues down to the floor (D-59), so the cheaper of two dear trips still scores higher."""
    pts = curve["points"]
    if share <= pts[0][0]:
        return float(pts[0][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if share <= x1:
            return y0 + (y1 - y0) * (share - x0) / (x1 - x0)
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    return max(float(curve["floor"]), y1 + (y1 - y0) * (share - x1) / (x1 - x0))


def price_component(total_cad: float, typical_cad: float, s: Scoring) -> tuple[float, float]:
    """(share, the price component on the price weight's scale)."""
    share = total_cad / typical_cad
    return share, s.weights["price"] * price_points(share, s.price_curve) / s.price_curve["points"][0][1]


def ladder_label(price_pp: float, flights: dict) -> str:
    for name in ("exceptional", "good", "typical"):
        if price_pp <= flights[name]:
            return name
    return "above"


def time_points(hours: float, best: float, curve: dict) -> float:
    """0..1: zero at curve['zero_at'] of the window's best possible waking hours, full at curve['full_at']."""
    r = hours / best if best else 0.0
    return max(0.0, min(1.0, (r - curve["zero_at"]) / (curve["full_at"] - curve["zero_at"])))


def worth_flying(trip: Trip, s: Scoring) -> bool:
    """Hard floor (D-51): below zero_at of the possible time there is no trip worth flying."""
    return trip.best_possible_hours > 0 and trip.hours_on_ground >= s.time_curve["zero_at"] * trip.best_possible_hours


def convenience(trip: Trip, city: City) -> float:
    """0..10 from the flights and the city; pass 2 takes 3 more off for fringe lodging (FRINGE_PTS)."""
    legs = (trip.out, trip.back)
    if all(leg.stops == 0 for leg in legs):
        c = 10
    else:
        c = 5 if max(leg.layover_min for leg in legs if leg.stops) <= 150 else 2
    c -= 2 if city.airport_to_core_min > 45 else 0
    c -= 3 if city.car_needed else 0
    c -= 2 if trip.out.arr.hour < 5 else 0      # arrival after midnight
    return max(0, c)


FRINGE_PTS = 3   # lodging 3 to 6 km from the centre (pass 2)


def convenience_component(conv_pts: float, fringe: bool, s: Scoring) -> float:
    return s.weights["convenience"] * max(0, conv_pts - (FRINGE_PTS if fringe else 0)) / 10


@dataclass(frozen=True)
class Components:
    price: float
    time: float
    convenience: float
    city: float
    weather: float


@dataclass(frozen=True)
class Scored:
    trip: Trip
    ladder: str                       # exceptional | good | typical | above (flights per person vs the route)
    price_pp: int
    lodging_cad: float
    lodging_source: str               # "estimate" | "hotels" | "rentals" | "airbnb"
    total_cad: float                  # flights + lodging + transfers, for two
    typical_cad: float                # the route's typical complete trip for these nights
    share: float                      # total_cad / typical_cad
    conv_pts: float                   # convenience 0..10 before any fringe penalty
    components: Components
    score: int
    candidate: bool
    history_pct: float | None = None
    inputs: dict = field(default_factory=dict)   # what the components were computed from, for the score breakdown


def is_candidate(price_pp: float, score: int, good_pp: float, threshold: int) -> bool:
    """Pass 2 only for a fare at or under the route's good and a pass-1 score at the class's threshold (FR-308)."""
    return price_pp <= good_pp and score >= threshold


def score_trip(trip: Trip, city: City, ref: Reference, s: Scoring, *, weather_score: "float | Weather",
               history_pct: float | None, lodging_cad: float | None = None) -> Scored:
    """lodging_cad None uses the pass-1 estimate (D-58); history_pct is shown, not scored (v2).
    weather_score: the Weather from radar.weather (its per-day figures feed the breakdown) or a bare 0..10 number."""
    w = s.weights
    wx = weather_score if isinstance(weather_score, Weather) else Weather(float(weather_score), "given")
    price_pp = round(trip.flights_cad_2pax / 2)
    lodging = lodging_estimate_cad(trip, city, ref, s) if lodging_cad is None else lodging_cad
    total = trip.flights_cad_2pax + lodging + transfers_cad(city)
    typical = typical_trip_cad(trip, city, ref, s)
    share, price = price_component(total, typical, s)
    conv = convenience(trip, city)
    comp = Components(
        price=price,
        time=w["time"] * time_points(trip.hours_on_ground, trip.best_possible_hours, s.time_curve),
        convenience=convenience_component(conv, False, s),
        city=w["city"] * city.rank / 10,
        weather=w["weather"] * max(0.0, min(10.0, wx.score)) / 10,
    )
    score = round(sum(vars(comp).values()))
    legs = (trip.out, trip.back)
    inputs = {   # plain values only: the candidate file carries them so pass 3 can re-render the lines
        "weights": dict(w), "hours": round(trip.hours_on_ground, 1), "best_hours": round(trip.best_possible_hours, 1),
        "stops": [trip.out.stops, trip.back.stops], "layover_min": max((leg.layover_min for leg in legs if leg.stops), default=0),
        "airport_to_core_min": city.airport_to_core_min, "car_needed": city.car_needed, "night_arrival": trip.out.arr.hour < 5,
        "city_name": city.name, "rank": city.rank, "nights": trip.nights, "weather": wx._asdict(),
    }
    return Scored(
        trip=trip, ladder=ladder_label(price_pp, ref.flights), price_pp=price_pp, lodging_cad=round(lodging, 2),
        lodging_source="estimate" if lodging_cad is None else "given", total_cad=round(total, 2),
        typical_cad=round(typical, 2), share=round(share, 4), conv_pts=conv, components=comp, score=score,
        candidate=is_candidate(price_pp, score, ref.flights["good"], s.trip_classes[trip.trip_class]["candidate_threshold"]),
        history_pct=history_pct, inputs=inputs,
    )


def rescore(components: dict, *, flights_cad: float, lodging_cad: float, transfers: float, typical_cad: float,
            conv_pts: float, fringe: bool, s: Scoring) -> dict:
    """Pass 2 and pass 3: the same trip with real lodging. Only the price and convenience components move.
    Works on plain numbers so finalize can run from a candidate file alone."""
    total = flights_cad + lodging_cad + transfers
    share, price = price_component(total, typical_cad, s)
    comp = {**components, "price": price, "convenience": convenience_component(conv_pts, fringe, s)}
    return {"components": {k: round(v, 2) for k, v in comp.items()}, "score": round(sum(comp.values())),
            "total_cad": round(total, 2), "share": round(share, 4), "lodging_cad": round(lodging_cad, 2)}


def components_dict(x: Scored) -> dict:
    return {k: round(v, 2) for k, v in asdict(x.components).items()}


# ---- score breakdown: every criterion with its input and its points, for the dashboard (D-75) ----

LABELS = {"price": "Price", "time": "Time there", "convenience": "Convenience", "city": "City", "weather": "Weather",
          "lodging": "Lodging", "whats_on": "What's on"}


def _money(v) -> str:
    return f"${v:,.0f}"


def price_line(total_cad: float, typical_cad: float, share: float) -> str:
    return f"complete trip {_money(total_cad)} for two, {share * 100:.0f}% of what this route normally costs (~{_money(typical_cad)})"


def convenience_line(i: dict, fringe: bool, room: bool) -> str:
    """'non-stop both ways · central room'; penalties print their points so the total can be followed."""
    stops = i["stops"]
    if not any(stops):
        parts = ["non-stop both ways"]
    else:   # a connection starts at 5 of 10, a layover over 150 min at 2 (convenience())
        n = "one stop each way" if all(stops) else "one stop"
        parts = [f"{n}, {i['layover_min']} min layover, " + ("−8" if i["layover_min"] > 150 else "−5")]
    if i["airport_to_core_min"] > 45:
        parts.append(f"airport {i['airport_to_core_min']} min from the centre, −2")
    if i["car_needed"]:
        parts.append("car needed, −3")
    if i["night_arrival"]:
        parts.append("arrives after midnight, −2")
    if room:
        parts.append("room on the fringe, −3" if fringe else "central room")
    return " · ".join(parts)


def breakdown(inputs: dict, components: dict, *, total_cad: float, typical_cad: float, share: float,
              fringe: bool = False, lodging: str | None = None, events: tuple[float, str] | None = None) -> list[dict]:
    """Ordered rows {key, label, points, max, input}; the points are the components as computed, so they sum to the
    score. Works on plain numbers (inputs as score_trip stores them) so pass 2 and pass 3 can build theirs too."""
    w = inputs["weights"]
    lines = {
        "price": price_line(total_cad, typical_cad, share),
        "time": f"{inputs['hours']:.1f} h there of {inputs['best_hours']:.1f} possible",
        "convenience": convenience_line(inputs, fringe, lodging is not None),
        "city": f"{inputs['city_name']}, rank {inputs['rank']}/10",
        "weather": weather_line(Weather(**inputs["weather"])),
    }
    rows = [{"key": k, "label": LABELS[k], "points": round(components[k], 2), "max": w[k], "input": line} for k, line in lines.items()]
    if lodging is not None:
        rows.append({"key": "lodging", "label": LABELS["lodging"], "points": None, "max": None, "input": lodging})
    if events is not None:
        rows.append({"key": "whats_on", "label": LABELS["whats_on"], "points": round(events[0], 2), "max": 10, "input": events[1]})
    return rows


def breakdown_of(x: Scored) -> list[dict]:
    """Pass 1: the trip as score_trip saw it."""
    return breakdown(x.inputs, components_dict(x), total_cad=x.total_cad, typical_cad=x.typical_cad, share=x.share)


def best_per_window(scored: list[Scored]) -> list[Scored]:
    """One winner per (city, window): highest score, then lowest total."""
    best: dict[tuple[str, str], Scored] = {}
    for x in scored:
        k = (x.trip.city_key, x.trip.window_id)
        if k not in best or (x.score, -x.total_cad) > (best[k].score, -best[k].total_cad):
            best[k] = x
    return list(best.values())

