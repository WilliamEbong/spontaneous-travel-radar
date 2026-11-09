"""Pass 2 lodging: Google Hotels and vacation rentals through SerpApi's free tier, candidates only (FR-310, FR-311).

One hotels lookup and one rentals lookup per candidate, each counted against the monthly cap before it is made.
Options more than MAX_KM from the city centre are discarded; past CENTRAL_KM they are "fringe".
"""
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from radar.config import City, Scoring

URL = "https://serpapi.com/search.json"
USAGE_PATH = "data/serpapi_usage.json"   # committed {"YYYY-MM": n}; NOT in data/cache (Actions runners start empty)
CENTRAL_KM, MAX_KM = 3.0, 6.0            # ponytail: straight-line km stand in for "about 20 minutes"; swap for transit time if it misleads
MIN_RATING = 4.3
KINDS = ("hotel", "rental")


@dataclass(frozen=True)
class Option:
    kind: str                     # hotel | rental
    name: str
    link: str
    total: float                  # whole stay, taxes in, in `currency`
    currency: str
    total_cad: float
    taxes_estimated: bool         # True = pre-tax rate x the city's hotel_tax (the response gave no after-tax total)
    nightly_pre_tax: float | None
    rating: float
    stars: int | None             # hotels only
    km: float                     # straight line to the city centre
    fringe: bool                  # CENTRAL_KM < km <= MAX_KM
    deal: str | None              # Google's "21% less than usual"
    deal_label: str | None        # "Deal" | "Great Deal"
    detail: str                   # rentals: "Entire apartment, Sleeps 2"; hotels: check-in time


@dataclass(frozen=True)
class LodgingCheck:
    options: tuple[Option, ...]   # acceptable options, cheapest first
    skipped: str | None           # None | "quota" | "no-key" | "error": why a search did not run
    searches: int                 # SerpApi lookups spent


def serpapi_reserve(month: str, s: Scoring, path=None) -> bool:
    """Count a search before making it; False (and no increment) if it would pass the monthly cap."""
    p = Path(path or USAGE_PATH)
    usage = json.loads(p.read_text()) if p.exists() else {}
    if usage.get(month, 0) >= s.serpapi_monthly_cap:
        return False
    usage[month] = usage.get(month, 0) + 1
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(usage, indent=1, sort_keys=True))
    os.replace(tmp, p)
    return True


def used_this_month(month: str, path=None) -> int:
    p = Path(path or USAGE_PATH)
    return json.loads(p.read_text()).get(month, 0) if p.exists() else 0


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine, km."""
    r = math.pi / 180
    h = math.sin((lat2 - lat1) * r / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def parse_options(payload: dict, city: City, kind: str, s: Scoring) -> list[Option]:
    """Acceptable options from one SerpApi google_hotels response: rated 4.3+, hotels 4-5 star, within MAX_KM."""
    out = []
    for p in payload.get("properties", []):
        g = p.get("gps_coordinates") or {}
        rating = p.get("overall_rating") or 0
        if "latitude" not in g or rating < MIN_RATING or (kind == "hotel" and (p.get("extracted_hotel_class") or 0) < 4):
            continue
        km = km_between(city.lat, city.lon, g["latitude"], g["longitude"])
        tr = p.get("total_rate") or {}
        total = tr.get("extracted_after_taxes_fees") or tr.get("extracted_lowest")
        estimated = not total and bool(tr.get("extracted_before_taxes_fees"))
        if estimated:
            total = tr["extracted_before_taxes_fees"] * city.hotel_tax
        if km > MAX_KM or not total:
            continue
        cad = total * s.usd_cad if city.hotel_currency == "USD" else total
        out.append(Option(
            kind=kind, name=p.get("name", ""), link=p.get("link", ""), total=round(float(total), 2), currency=city.hotel_currency,
            total_cad=round(cad, 2), taxes_estimated=estimated,
            nightly_pre_tax=(p.get("rate_per_night") or {}).get("extracted_before_taxes_fees"), rating=round(float(rating), 2),
            stars=p.get("extracted_hotel_class"), km=round(km, 1), fringe=km > CENTRAL_KM,
            deal=p.get("deal"), deal_label=p.get("deal_description"),
            detail=", ".join((p.get("essential_info") or [])[:2]) if kind == "rental" else (p.get("check_in_time") or "").replace(" ", " "),
        ))
    return out


def search(city: City, check_in: date, check_out: date, kind: str, s: Scoring, *, api_key: str | None, cache_dir,
           today: date | None = None) -> tuple[dict | None, str | None, int]:
    """(payload, skipped reason, lookups spent). Cached per scan day; an error is not retried (a retry spends quota)."""
    if not api_key:
        return None, "no-key", 0
    path = Path(cache_dir) / f"serpapi-{kind}-{city.key}-{check_in}-{check_out}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None, 0
    except (OSError, ValueError):   # missing or half-written cache file = cache miss
        pass
    if not serpapi_reserve((today or date.today()).strftime("%Y-%m"), s):   # quota month = month of use
        return None, "quota", 0
    params = {"engine": "google_hotels", "q": f"{city.neighbourhoods[0]}, {city.name}",   # one neighbourhood: a list errored (D-63)
              "check_in_date": check_in.isoformat(), "check_out_date": check_out.isoformat(), "adults": 2,
              "currency": city.hotel_currency, "gl": "ca" if city.country == "CA" else "us", "hl": "en",
              "sort_by": 3, "rating": 8, "api_key": api_key}
    params.update({"hotel_class": "4,5"} if kind == "hotel" else {"vacation_rentals": "true"})
    try:
        r = httpx.get(URL, params=params, timeout=40)
        r.raise_for_status()
        payload = r.json()
    except (httpx.HTTPError, ValueError) as e:
        print(f"serpapi {kind} {city.key}: {type(e).__name__}", file=sys.stderr)   # the URL holds the key: never print it
        return None, "error", 1
    payload.pop("search_parameters", None)
    payload.pop("search_metadata", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)
    return payload, None, 1


def check_lodging(city: City, check_in: date, check_out: date, s: Scoring, *, api_key: str | None, cache_dir,
                  today: date | None = None) -> LodgingCheck:
    opts, skipped, spent = [], None, 0
    for kind in KINDS:
        payload, why, n = search(city, check_in, check_out, kind, s, api_key=api_key, cache_dir=cache_dir, today=today)
        spent += n
        skipped = skipped or why
        if payload:
            opts += parse_options(payload, city, kind, s)
    return LodgingCheck(tuple(sorted(opts, key=lambda o: o.total_cad)), skipped, spent)
