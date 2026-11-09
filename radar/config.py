"""Load and validate the YAML config (config/*.yaml) into dataclasses."""
from dataclasses import MISSING, dataclass, fields
from datetime import date, datetime

import yaml

HOTEL_TAX = {"CA": 1.15, "US": 1.16, "MX": 1.19}   # room taxes and fees where cities.yaml sets no hotel_tax


@dataclass(frozen=True)
class City:
    key: str
    name: str
    country: str                       # CA | US | MX
    tier: int
    rank: int
    airports: tuple[str, ...]          # first = preferred non-stop
    tz: str                            # IANA
    lat: float                         # city centre: weather, and the lodging distance cut (pass 2)
    lon: float
    airport_to_core_min: int
    air_time_min: int                  # non-stop air time from YYC (door-to-door for one-stop cities)
    transfer_cost_cad_pp_each_way: int
    car_needed: bool
    neighbourhoods: tuple[str, ...]    # the first one is the lodging search's query text
    season_months: tuple[int, ...]     # empty = year-round
    hotel_currency: str                # CAD | USD
    climate: dict[int, tuple[float, float, int]]  # month -> (mean_high_c, mean_low_c, rain_days)
    enabled: bool = True               # false = the scan skips the city (set from the dashboard's Settings panel)
    hotel_tax: float = 0.0             # factor on pre-tax room rates; 0 in the dataclass means "use HOTEL_TAX"


@dataclass(frozen=True)
class Reference:
    """A route's ladders (config/references.yaml). flights: CAD per person round trip; rooms[season]: per night pre-tax."""
    flights: dict[str, int]            # {typical, good, exceptional}
    rooms: dict[str, dict]             # {"winter": {typical, good, exceptional, source}, "summer": {...}}
    confidence: str                    # high | medium | low
    nonstop: str                       # year-round | seasonal | none


@dataclass(frozen=True)
class Scoring:
    weights: dict[str, int]
    price_curve: dict                  # {points: [[share, points], ...], floor}
    usd_cad: float
    mode: str
    cap_cad: int | None                # optional cap on a hit's complete trip for two; None = off
    realert_drop_pct: int
    dayoff_min_weeks: int              # Settings panel, 2-12
    serpapi_monthly_cap: int
    time_curve: dict[str, float]       # {zero_at, full_at}: share of the window's best possible waking hours
    trip_classes: dict[str, dict]      # {"dayoff": {...}, "weekend": {...}}, see config/scoring.yaml


def _read(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cities(path="config/cities.yaml") -> list[City]:
    names = [f.name for f in fields(City) if f.default is MISSING]
    out = []
    for raw in _read(path)["cities"]:
        missing = [n for n in names if n not in raw]
        if missing:
            raise ValueError(f"city {raw.get('key', '?')}: missing {', '.join(missing)}")
        v = {n: raw[n] for n in names}
        for n in ("airports", "neighbourhoods", "season_months"):
            v[n] = tuple(v[n])
        v["climate"] = {int(m): tuple(x) for m, x in v["climate"].items()}
        if len(v["climate"]) != 12:
            raise ValueError(f"city {v['key']}: climate needs 12 months")
        v["enabled"] = raw.get("enabled", True)
        if not isinstance(v["enabled"], bool):
            raise ValueError(f"city {v['key']}: enabled must be true or false, not {raw['enabled']!r}")
        v["hotel_tax"] = float(raw.get("hotel_tax") or HOTEL_TAX[v["country"]])
        if not 1 <= v["hotel_tax"] < 1.5:
            raise ValueError(f"city {v['key']}: hotel_tax {v['hotel_tax']} is not a factor like 1.15")
        out.append(City(**v))
    return out


LADDER = ("exceptional", "good", "typical")


def _ladder(d, where: str) -> dict:
    if not isinstance(d, dict) or not all(isinstance(d.get(k), (int, float)) and d[k] > 0 for k in LADDER):
        raise ValueError(f"{where}: needs positive typical, good and exceptional")
    if not d["exceptional"] < d["good"] < d["typical"]:
        raise ValueError(f"{where}: needs exceptional < good < typical, got {d['exceptional']}/{d['good']}/{d['typical']}")
    return d


def load_references(path="config/references.yaml", keys=None) -> dict[str, Reference]:
    """keys: every city key in cities.yaml; each must have an entry."""
    raw = _read(path) or {}
    missing = sorted(set(keys or ()) - set(raw))
    if missing:
        raise ValueError(f"{path}: no ladder for {', '.join(missing)}")
    out = {}
    for k, r in raw.items():
        rooms = r.get("rooms") or {}
        if set(rooms) != {"winter", "summer"}:
            raise ValueError(f"{path}: {k}.rooms needs winter and summer")
        out[k] = Reference(flights=_ladder(r.get("flights"), f"{path}: {k}.flights"),
                           rooms={s: _ladder(rooms[s], f"{path}: {k}.rooms.{s}") for s in ("winter", "summer")},
                           confidence=str(r.get("confidence", "")), nonstop=str(r.get("nonstop", "")))
    return out


def load_interests(path="config/interests.yaml") -> dict:
    """William's interests profile, read by the pass-3 research and by the affordability lines in finalize."""
    raw = _read(path) or {}
    lists = ("music_love", "interests", "dislikes")
    for k in lists:
        if not isinstance(raw.get(k), list) or not raw[k] or not all(isinstance(x, str) and x for x in raw[k]):
            raise ValueError(f"{path}: {k} must be a non-empty list of text")
    p = raw.get("concert_price_cad")
    if not isinstance(p, dict) or not all(isinstance(p.get(k), int) and p[k] > 0 for k in ("lesser_known", "famous")) \
            or p["lesser_known"] >= p["famous"]:
        raise ValueError(f"{path}: concert_price_cad needs whole-dollar lesser_known < famous")
    if not isinstance(raw.get("uniqueness_test"), str) or not raw["uniqueness_test"].strip():
        raise ValueError(f"{path}: uniqueness_test must be one sentence")
    return raw


def load_holidays(path="config/holidays.yaml") -> set[date]:
    raw = _read(path)
    return set(raw[raw["calendar"]])   # yaml.safe_load parses ISO dates to date


def load_days_off(path="config/days_off.yaml") -> tuple[set[date], set[date]]:
    """(extra, blocked) from the dashboard's Settings panel: extra days off count like stat holidays,
    blocked dates get no trips. Dates may be bare (YAML dates) or quoted ISO strings."""
    raw = _read(path) or {}
    if not isinstance(raw, dict) or set(raw) - {"extra", "blocked"}:
        raise ValueError(f"{path}: expected only the keys extra and blocked")
    out = []
    for k in ("extra", "blocked"):
        vals = raw.get(k) or []
        if not isinstance(vals, list):
            raise ValueError(f"{path}: {k} must be a list of dates")
        days = set()
        for v in vals:
            if isinstance(v, datetime):
                v = v.date()
            try:
                days.add(v if isinstance(v, date) else date.fromisoformat(str(v)))
            except ValueError:
                raise ValueError(f"{path}: {k} has an invalid date {v!r} (use YYYY-MM-DD)") from None
        out.append(days)
    both = out[0] & out[1]
    if both:
        raise ValueError(f"{path}: {min(both)} is both extra and blocked")
    return out[0], out[1]


def load_scoring(path="config/scoring.yaml") -> Scoring:
    raw = _read(path)
    s = Scoring(**{f.name: raw[f.name] for f in fields(Scoring)})
    # the Settings-panel values, so a bad hand edit fails here instead of mid-scan
    if not isinstance(s.dayoff_min_weeks, int) or not 2 <= s.dayoff_min_weeks <= 12:
        raise ValueError(f"{path}: dayoff_min_weeks must be a whole number from 2 to 12")
    if s.cap_cad is not None and (not isinstance(s.cap_cad, int) or s.cap_cad <= 0):
        raise ValueError(f"{path}: cap_cad must be a whole number of dollars or null")
    for name, c in s.trip_classes.items():
        if not isinstance(c.get("enabled"), bool):
            raise ValueError(f"{path}: trip_classes.{name}.enabled must be true or false")
        for k in ("candidate_threshold", "hit_threshold"):
            if not isinstance(c.get(k), int) or not 0 <= c[k] <= 110:
                raise ValueError(f"{path}: trip_classes.{name}.{k} must be a whole number from 0 to 110")
    xs = [x for x, _ in s.price_curve["points"]]
    if xs != sorted(xs) or len(xs) < 2:
        raise ValueError(f"{path}: price_curve.points must be at least two [share, points] pairs in rising share order")
    return s


def load_airline_surcharges(path="config/airlines.yaml") -> dict[str, int]:
    return dict(_read(path))
