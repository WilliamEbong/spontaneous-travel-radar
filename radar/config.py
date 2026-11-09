"""Load and validate the YAML config (config/*.yaml) into dataclasses."""
from dataclasses import MISSING, dataclass, fields
from datetime import date, datetime

import yaml


@dataclass(frozen=True)
class City:
    key: str
    name: str
    country: str                       # CA | US | MX (Ticketmaster countryCode)
    tier: int
    rank: int
    airports: tuple[str, ...]          # first = preferred non-stop
    tz: str                            # IANA
    lat: float
    lon: float
    airport_to_core_min: int
    air_time_min: int                  # non-stop air time from YYC (door-to-door for one-stop cities)
    transfer_cost_cad_pp_each_way: int
    car_needed: bool
    neighbourhoods: tuple[str, ...]
    season_months: tuple[int, ...]     # empty = year-round
    flight_group: str
    hotel_group: str
    hotel_currency: str                # CAD | USD
    bar_cad: int                       # complete-trip bar for two
    climate: dict[int, tuple[float, float, int]]  # month -> (mean_high_c, mean_low_c, rain_days)
    enabled: bool = True               # false = the scan skips the city (set from the dashboard's Settings panel)


@dataclass(frozen=True)
class Scoring:
    weights: dict[str, int]
    flight_bands: dict[str, dict[str, int]]
    hotel_bands: dict[str, dict[str, int]]
    usd_cad: float
    mode: str
    score_threshold: int
    realert_drop_pct: int
    dayoff_min_weeks: int             # Settings panel, 2-12
    weekend_trips: bool               # Settings panel
    serpapi_monthly_cap: int
    serpapi_per_candidate_cap: int
    time_curve: dict[str, float]      # {zero_at, full_at}: share of the window's best possible waking hours
    trip_classes: dict[str, dict]     # {"dayoff": {...}, "weekend": {...}}, see config/scoring.yaml


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
        out.append(City(**v))
    return out


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
    # the two Settings-panel values, so a bad hand edit fails here instead of mid-scan
    if not isinstance(s.dayoff_min_weeks, int) or not 2 <= s.dayoff_min_weeks <= 12:
        raise ValueError(f"{path}: dayoff_min_weeks must be a whole number from 2 to 12")
    if not isinstance(s.weekend_trips, bool):
        raise ValueError(f"{path}: weekend_trips must be true or false")
    return s


def load_airline_surcharges(path="config/airlines.yaml") -> dict[str, int]:
    return dict(_read(path))
