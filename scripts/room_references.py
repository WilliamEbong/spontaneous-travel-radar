"""Room ladders from Google Hotels (BUILD-PLAN-v2 T9). Spends one SerpApi lookup per city and season.

    python scripts/room_references.py [--dry-run] [city ...]

For each city: the pass-2 hotels search (4-5 star, rated 4.3+, within 6 km of the centre, cheapest first) for
15-17 Jan 2027 (winter) and 16-18 Jul 2027 (summer). typical = median nightly pre-tax rate of the ten cheapest
acceptable, good = 0.75 x typical, exceptional = 0.57 x typical, rounded to $5, written into
config/references.yaml with `source: google-hotels <today>`. Fewer than 3 acceptable rooms keeps the old line.
Vancouver's researched winter line is kept. Lookups are counted in data/serpapi_usage.json like any other.
Responses are cached in data/cache/rooms/ by city and dates: after changing a city's first neighbourhood (the
query text), delete that city's cache files, or the old answer is re-measured instead of a new lookup.
"""
import os
import re
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar.config import load_cities, load_scoring  # noqa: E402
from radar.hotels import parse_options, search  # noqa: E402
from radar.main import load_dotenv  # noqa: E402

SEASONS = {"winter": (date(2027, 1, 15), date(2027, 1, 17)), "summer": (date(2027, 7, 16), date(2027, 7, 18))}
KEEP = {("vancouver", "winter")}   # researched by hand on 2026-11-09


def r5(x: float) -> int:
    return int(5 * round(x / 5))


def ladder(nightly: list[float]) -> dict | None:
    """None when fewer than 3 acceptable rooms: too thin to call a market."""
    ten = sorted(nightly)[:10]
    if len(ten) < 3:
        return None
    t = statistics.median(ten)
    return {"typical": r5(t), "good": r5(0.75 * t), "exceptional": r5(0.57 * t)}


def set_rooms(text: str, city: str, season: str, lad: dict, source: str) -> str:
    """Replace one `    <season>: {...}` line inside the city's block, nothing else."""
    start = text.index(f"\n{city}:\n") + 1
    nxt = re.search(r"^\S", text[start + len(city) + 2:], re.M)
    end = start + len(city) + 2 + (nxt.start() if nxt else len(text))
    line = f"    {season}: {{typical: {lad['typical']}, good: {lad['good']}, exceptional: {lad['exceptional']}, source: {source}}}"
    new, n = re.subn(rf"^    {season}: \{{.*\}}$", line, text[start:end], count=1, flags=re.M)
    assert n == 1, (city, season)
    return text[:start] + new + text[end:]


def main(argv) -> int:
    load_dotenv(ROOT / ".env")
    dry = "--dry-run" in argv
    only = {a for a in argv if not a.startswith("--")}
    key = None if dry else os.environ.get("SERPAPI_KEY")
    if not dry and not key:
        print("SERPAPI_KEY is not set (.env)", file=sys.stderr)
        return 1
    s, refs_path = load_scoring(), ROOT / "config/references.yaml"
    text = refs_path.read_text(encoding="utf-8")
    source = f"google-hotels {date.today()}"
    spent = 0
    for c in load_cities(ROOT / "config/cities.yaml"):
        if only and c.key not in only:
            continue
        for season, (ci, co) in SEASONS.items():
            if (c.key, season) in KEEP:
                continue
            if dry:
                print(f"would look up {c.key} {season} {ci}")
                continue
            payload, why, n = search(c, ci, co, "hotel", s, api_key=key, cache_dir=ROOT / "data/cache/rooms", today=date.today())
            spent += n
            if payload is None:
                print(f"{c.key:14} {season}: skipped ({why})")
                continue
            opts = [o for o in parse_options(payload, c, "hotel", s) if o.nightly_pre_tax]
            lad = ladder([o.nightly_pre_tax for o in opts])
            kms = sorted(o.km for o in opts)
            print(f"{c.key:14} {season}: {len(payload.get('properties', []))} found, {len(opts)} acceptable"
                  + (f" ({kms[0]}-{kms[-1]} km)" if kms else "") + f" -> {lad or 'kept the old line'}")
            if lad:
                text = set_rooms(text, c.key, season, lad, source)
    if not dry:
        refs_path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
    print(f"SerpApi lookups spent: {spent}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
