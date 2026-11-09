"""Load and validate the YAML config (config/*.yaml) into dataclasses."""
from dataclasses import dataclass, fields
from datetime import date

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
    transfer_cost_cad_pp_each_way: int
    car_needed: bool
    neighbourhoods: tuple[str, ...]
    season_months: tuple[int, ...]     # empty = year-round
    flight_group: str
    hotel_group: str
    hotel_currency: str                # CAD | USD
    bar_cad: int                       # complete-trip bar for two
    climate: dict[int, tuple[float, float, int]]  # month -> (mean_high_c, mean_low_c, rain_days)


@dataclass(frozen=True)
class Scoring:
    weights: dict[str, int]
    flight_bands: dict[str, dict[str, int]]
    hotel_bands: dict[str, dict[str, int]]
    usd_cad: float
    mode: str
    score_threshold: int
    realert_drop_pct: int
    lookahead_min_days: int
    lookahead_max_days: int
    serpapi_monthly_cap: int
    serpapi_per_candidate_cap: int


def _read(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cities(path="config/cities.yaml") -> list[City]:
    names = [f.name for f in fields(City)]
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
        out.append(City(**v))
    return out


def load_holidays(path="config/holidays.yaml") -> set[date]:
    raw = _read(path)
    return set(raw[raw["calendar"]])   # yaml.safe_load parses ISO dates to date


def load_scoring(path="config/scoring.yaml") -> Scoring:
    raw = _read(path)
    return Scoring(**{f.name: raw[f.name] for f in fields(Scoring)})


def load_airline_surcharges(path="config/airlines.yaml") -> dict[str, int]:
    return dict(_read(path))
