"""Hit gates, hit JSON and the templated markdown brief (design 6.2, 7.4)."""
import json
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

from radar.config import City, Scoring
from radar.events import Event, is_notable
from radar.flights import Leg
from radar.hotels import HotelCheck
from radar.score import Scored, to_cad


def gates(x: Scored, city: City, s: Scoring, previous: dict | None) -> dict:
    return {"score_ok": x.score >= s.score_threshold, "bar_ok": x.total_cad <= city.bar_cad,
            "realert_ok": should_realert({"price": {"flights_cad_2pax": x.trip.flights_cad_2pax}}, previous, s.realert_drop_pct)}


def should_realert(hit: dict, previous: dict | None, drop_pct: int) -> bool:
    if not previous:
        return True
    return hit["price"]["flights_cad_2pax"] <= previous["price"]["flights_cad_2pax"] * (1 - drop_pct / 100)


def finalize_hit(scored: Scored, city: City, hotels: HotelCheck, s: Scoring, previous: dict | None) -> tuple[Scored, bool, str]:
    """Swap the lodging estimate for the cheapest real hotel (all-in when known), then apply all three gates."""
    x = scored
    if hotels.options:
        o = hotels.options[0]
        lodging = round(to_cad(o.total_all_in or o.total_pre_tax, o.currency, s), 2)
        total = round(x.trip.flights_cad_2pax + lodging + 4 * city.transfer_cost_cad_pp_each_way, 2)
        x = replace(x, lodging_cad=lodging, lodging_source="serpapi", total_cad=total)
    g = gates(x, city, s, previous)
    failed = [k.removesuffix("_ok") for k, ok in g.items() if not ok]
    return x, not failed, failed[0] if failed else "hit"


def previous_hit(city_key: str, window_id: str, root="hits", exclude_id: str | None = None) -> dict | None:
    """Latest earlier hit for this city-window; exclude_id skips the file a same-day re-run is about to overwrite."""
    best = None
    for p in list(Path(root).glob("*.json")) + list(Path(root).glob("dry-run/*.json")):
        if p.name == "index.json" or p.stem == exclude_id:
            continue
        h = json.loads(p.read_text(encoding="utf-8"))
        if h.get("city") == city_key and h.get("window_id") == window_id and h.get("is_hit"):
            if best is None or h["created"] > best["created"]:
                best = h
    return best


def _leg(leg: Leg) -> dict:
    return {"from": leg.origin, "to": leg.dest, "dep": leg.dep.isoformat(), "arr": leg.arr.isoformat(),
            "airlines": list(leg.airlines), "flight_numbers": list(leg.flight_numbers), "stops": leg.stops,
            "layover_min": leg.layover_min, "duration_min": leg.duration_min, "price_cad_2pax": leg.price_cad_2pax}


def write_hit(scored: Scored, city: City, hotels: HotelCheck, events: list[Event], weather: tuple[float, str],
              s: Scoring, root="hits", *, gate: dict | None = None, is_hit: bool | None = None,
              scan_date: date | None = None) -> tuple[Path, Path]:
    t = scored.trip
    gate = gate if gate is not None else gates(scored, city, s, None)
    scan_date = scan_date or date.today()
    hid = f"{scan_date}_{city.key}_{t.window_id}"
    nb = city.neighbourhoods[0] if city.neighbourhoods else city.name
    hit = {
        "id": hid, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": s.mode,
        "is_hit": all(gate.values()) if is_hit is None else is_hit,
        "city": city.key, "city_name": city.name, "window_id": t.window_id,
        "dates": {"check_in": t.check_in.isoformat(), "check_out": t.check_out.isoformat(), "nights": t.nights},
        "flights": {"out": _leg(t.out), "back": _leg(t.back)},
        "price": {"flights_cad_2pax": t.flights_cad_2pax, "price_pp": scored.price_pp, "band": scored.band,
                  "lodging_cad": scored.lodging_cad, "lodging_source": scored.lodging_source,
                  "transfers_cad": 4 * city.transfer_cost_cad_pp_each_way, "total_cad": scored.total_cad,
                  "bar_cad": city.bar_cad},
        "hotels": {"options": [asdict(o) for o in hotels.options], "band": hotels.band, "skipped": hotels.skipped},
        "events": [{"name": e.name, "date": e.date.isoformat(), "venue": e.venue, "segment": e.segment, "url": e.url}
                   for e in sorted(events, key=lambda e: (not is_notable(e), e.date))[:10]],
        "weather": {"score": round(weather[0], 1), "source": weather[1]},
        "hours_on_ground": round(t.hours_on_ground, 1), "airport_to_core_min": city.airport_to_core_min,
        "components": {k: round(v, 1) for k, v in asdict(scored.components).items()},
        "score": scored.score, "hotel_spike": scored.hotel_spike, "gate": gate,
        "links": {
            "google_flights": f"https://www.google.com/travel/flights?q={quote(f'Flights to {t.out.dest} from YYC on {t.out.dep.date()} through {t.back.dep.date()}')}",
            "google_hotels": f"https://www.google.com/travel/search?q={quote(f'hotels in {nb}, {city.name} {t.check_in} to {t.check_out}')}",
        },
    }
    d = Path(root) / ("dry-run" if s.mode == "dry-run" else "")
    d.mkdir(parents=True, exist_ok=True)
    j, m = d / f"{hid}.json", d / f"{hid}.md"
    j.write_text(json.dumps(hit, indent=1), encoding="utf-8")
    m.write_text(render_brief(hit), encoding="utf-8")
    return j, m


def _plain(s: str) -> str:
    """API-supplied names must not inject markdown links or emphasis into the brief."""
    return s.replace("[", "(").replace("]", ")").replace("*", "")


def _fmt_leg(leg: dict) -> str:
    dep, arr = datetime.fromisoformat(leg["dep"]), datetime.fromisoformat(leg["arr"])
    via = "non-stop" if not leg["stops"] else f"1 stop, {leg['layover_min'] // 60}h{leg['layover_min'] % 60:02d} layover"
    nums = ", ".join(leg["flight_numbers"]) or "/".join(leg["airlines"])
    return f"{leg['from']} {dep:%a %b %d %H:%M} → {leg['to']} {arr:%a %H:%M} local ({nums}; {via})"


def render_brief(hit: dict) -> str:
    p, h = hit["price"], hit["hotels"]
    lines = [
        f"# {hit['city_name']}: {hit['dates']['check_in']} to {hit['dates']['check_out']} ({hit['score']}/100)",
        "",
        f"Mode: {hit['mode']}{' (logged only, no alert)' if hit['mode'] == 'dry-run' else ''}. "
        f"Gates: score {'ok' if hit['gate']['score_ok'] else 'no'}, bar {'ok' if hit['gate']['bar_ok'] else 'no'}, "
        f"re-alert {'ok' if hit['gate']['realert_ok'] else 'no'}.",
        "",
        f"- **Out:** {_fmt_leg(hit['flights']['out'])}",
        f"- **Back:** {_fmt_leg(hit['flights']['back'])}",
        f"- **Flights for two:** ${p['flights_cad_2pax']:,} CAD with a carry-on each (${p['price_pp']:,} per person, band {p['band']})",
        f"- **Lodging, {hit['dates']['nights']} nights:** ${p['lodging_cad']:,.0f} CAD "
        f"({'cheapest hotel below, taxes in where shown' if p['lodging_source'] == 'serpapi' else 'estimate from the hotel band'})",
        f"- **Airport transfers:** ${p['transfers_cad']} CAD; airport to core about {hit['airport_to_core_min']} min",
        f"- **Complete trip for two:** ${p['total_cad']:,.0f} CAD (bar ${p['bar_cad']:,})",
        f"- **Time on the ground:** {hit['hours_on_ground']} waking hours",
        f"- **Weather:** {hit['weather']['score']}/10 ({hit['weather']['source']})",
        "",
        "## Hotels",
    ]
    if h["options"]:
        for o in h["options"]:
            all_in = f"${o['total_all_in']:,.0f} all-in" if o["total_all_in"] else "all-in unknown"
            fc = {True: "free cancellation", False: "no free cancellation", None: "cancellation unknown"}[o["free_cancel"]]
            lines.append(f"- [{_plain(o['name'])}]({o['link']}) in {_plain(o['neighbourhood'])}: ${o['total_pre_tax']:,.0f} {o['currency']} "
                         f"before taxes ({all_in}), {o['stars']}-star, rating {o['rating']}, {fc}, check-in {o['check_in'] or '?'}")
        lines.append(f"- Hotel band: {h['band']}" + (f" (check stopped early: {h['skipped']})" if h["skipped"] else ""))
    else:
        lines.append(f"- Hotel check skipped: {h['skipped'] or 'no options met the floor'}")
    lines += ["", "## Events"]
    lines += [f"- {e['date']}: {_plain(e['name'])} at {_plain(e['venue'])}" for e in hit["events"]] or ["- none found"]
    if hit.get("hotel_spike"):
        lines.append("- Big events this weekend: hotel prices may spike.")
    lines += ["", f"[Google Flights]({hit['links']['google_flights']}) · [Google Hotels]({hit['links']['google_hotels']})", ""]
    return "\n".join(lines)
