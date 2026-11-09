"""Google Hotels via SerpApi's free tier, for candidates only, with a hard cap persisted in the repo."""
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import httpx

from radar.config import City, Scoring
from radar.score import hotel_band

URL = "https://serpapi.com/search.json"
USAGE_PATH = "data/serpapi_usage.json"   # committed {"YYYY-MM": n}; NOT in data/cache (Actions runners start empty)


@dataclass(frozen=True)
class HotelOption:
    name: str
    neighbourhood: str
    total_pre_tax: float          # band comparison (design 7.5: pre-tax)
    total_all_in: float | None    # display and trip total
    currency: str
    rating: float
    stars: int
    free_cancel: bool | None      # None = the response did not say
    late_checkin: bool | None
    check_in: str
    check_out: str
    link: str


@dataclass(frozen=True)
class HotelCheck:
    options: tuple[HotelOption, ...]
    band: str | None
    skipped: str | None           # None | "cap" | "no-key" | "error" | "gated" (score/re-alert gate failed first)


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


def band_for(total_pre_tax: float, city: City, nights: int, s: Scoring) -> str:
    """Bands are for 2 nights; scale thresholds by nights / 2 (a 3-night stay is x1.5)."""
    scaled = {k: v * nights / 2 for k, v in s.hotel_bands[city.hotel_group].items()}
    return hotel_band(total_pre_tax, city.hotel_group, {city.hotel_group: scaled})


def parse_properties(payload: dict, city: City, nights: int, s: Scoring, neighbourhood: str = "") -> HotelCheck:
    opts = []
    for p in payload.get("properties", []):
        total = p.get("total_rate") or {}
        pre = total.get("extracted_before_taxes_fees") or total.get("extracted_lowest")
        if not pre or (p.get("overall_rating") or 0) < 4.3 or (p.get("extracted_hotel_class") or 0) < 4:
            continue
        opts.append(HotelOption(
            name=p.get("name", ""), neighbourhood=neighbourhood, total_pre_tax=float(pre),
            total_all_in=float(total["extracted_lowest"]) if total.get("extracted_lowest") else None,
            currency=city.hotel_currency, rating=float(p["overall_rating"]), stars=int(p["extracted_hotel_class"]),
            free_cancel=p.get("free_cancellation"), late_checkin=None,
            check_in=p.get("check_in_time", ""), check_out=p.get("check_out_time", ""), link=p.get("link", ""),
        ))
    opts = tuple(sorted(opts, key=lambda o: o.total_pre_tax)[:3])
    return HotelCheck(opts, band_for(opts[0].total_pre_tax, city, nights, s) if opts else None, None)


def check_hotels(city: City, check_in: date, nights: int, s: Scoring, *, api_key: str | None, cache_dir,
                 today: date | None = None) -> HotelCheck:
    if not api_key:
        return HotelCheck((), None, "no-key")
    month = (today or date.today()).strftime("%Y-%m")   # quota month = month of use
    found, skipped = [], None
    for i, nb in enumerate(city.neighbourhoods[: s.serpapi_per_candidate_cap]):
        path = Path(cache_dir) / f"serpapi-{city.key}-{check_in}-{nights}-{i}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):   # missing or half-written cache file = cache miss
            payload = None
        if payload is None:
            if not serpapi_reserve(month, s):
                skipped = "cap"
                break
            try:
                r = httpx.get(URL, params={
                    "engine": "google_hotels", "q": f"{nb}, {city.name}", "check_in_date": check_in.isoformat(),
                    "check_out_date": (check_in + timedelta(days=nights)).isoformat(), "adults": 2,
                    "currency": city.hotel_currency, "hotel_class": "4,5", "rating": 8, "free_cancellation": "true",
                    "sort_by": 3, "gl": "us" if city.country != "CA" else "ca", "hl": "en", "api_key": api_key,
                }, timeout=30)
                r.raise_for_status()
                payload = r.json()
            except (httpx.HTTPError, ValueError) as e:
                print(f"serpapi {city.key} {nb}: {type(e).__name__}", file=sys.stderr)  # URL holds the key: never print it
                skipped = "error"
                continue
            payload.pop("search_parameters", None)
            payload.pop("search_metadata", None)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, path)
        found += parse_properties(payload, city, nights, s, nb).options
    opts = tuple(sorted(found, key=lambda o: o.total_pre_tax)[:3])
    return HotelCheck(opts, band_for(opts[0].total_pre_tax, city, nights, s) if opts else None, skipped)
