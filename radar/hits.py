"""Candidates (pass 2), pass 3 (finalize) and the markdown briefs (v2, FR-312, FR-313).

Layout: hits/candidates/<id>.json (written by the scan), then finalize writes the three-pass result to
hits/dry-run/<id>.json (learning-run hit), hits/<id>.json (live hit) or hits/near-miss/<id>.json (D-69).
"""
import json
import re
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from radar.config import City, Reference, Scoring
from radar.flights import Leg
from radar.hotels import LodgingCheck
from radar.score import Scored, breakdown, breakdown_of, components_dict, rescore, transfers_cad

ROOT = "hits"
EVENTS_CAP = 10
CLASS_LABEL = {"weekend": "No day off needed", "dayoff": "Needs a day off"}
MAX_OPTIONS = 8   # options kept per candidate file, best score first
HTTPS = re.compile(r"https://[^\s()<>\[\]]+")   # a link the brief may render: https, nothing that closes the markdown


def candidate_id(scan_date: date, city_key: str, window_id: str) -> str:
    return f"{scan_date}_{city_key}_{window_id}"


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1), encoding="utf-8")


def previous_candidate(city_key: str, window_id: str, *, today: date, days: int = 7, root=ROOT,
                       exclude_id: str | None = None) -> dict | None:
    """The latest candidate for this city-window within `days` (today's included, so a re-run spends nothing) whose
    lodging check completed and which the routine has decided (or which was dropped after pass 2), D-66.
    A check skipped for quota, an error or no key does not count, and neither does a candidate still awaiting
    pass 3: a missed routine run gets a fresh candidate the next day instead of a week's silence (review, D-73)."""
    since, best = (today - timedelta(days=days)).isoformat(), None
    for p in Path(root, "candidates").glob("*.json"):
        if p.stem == exclude_id:
            continue
        h = json.loads(p.read_text(encoding="utf-8"))
        settled = h["status"] != "awaiting_pass3" or h["scan_date"] == today.isoformat()
        if (h["city"], h["window_id"]) == (city_key, window_id) and h["pass2"]["skipped"] is None and settled and h["scan_date"] >= since:
            if best is None or h["scan_date"] > best["scan_date"]:
                best = h
    return best


def fare_dropped(flights_cad: float, previous: dict, drop_pct: int) -> bool:
    return flights_cad <= previous["flights"]["cad_2pax"] * (1 - drop_pct / 100)


def lodging_line(opt: dict | None, nights: int, estimate_cad: float) -> str:
    """The breakdown's lodging row: the option chosen in pass 2, or the estimate that still stands in."""
    if opt is None:
        return f"nothing acceptable within 6 km; the route's good room rate stands in ({_money(estimate_cad)} for {nights} nights)"
    deal = f" (Google: {_plain(opt['deal'])})" if opt.get("deal") else ""
    return f"{_plain(opt['name'])}, {opt['kind']}, {_money(opt['total_cad'] / nights)} a night all-in, total {_money(opt['total_cad'])}{deal}"


def pass2(x: Scored, city: City, check: LodgingCheck, s: Scoring) -> dict:
    """Score every acceptable option on the real total; the best score wins, then the lower total (D-65)."""
    base = dict(components=components_dict(x), flights_cad=x.trip.flights_cad_2pax, transfers=transfers_cad(city),
                typical_cad=x.typical_cad, conv_pts=x.conv_pts, s=s)
    opts = []
    for o in check.options:
        r = rescore(base["components"], lodging_cad=o.total_cad, fringe=o.fringe,
                    **{k: v for k, v in base.items() if k != "components"})
        opts.append({**asdict(o), "trip_score": r["score"], "trip_total_cad": r["total_cad"], "result": r})
    opts.sort(key=lambda o: (-o["trip_score"], o["trip_total_cad"]))
    out = {"searches": check.searches, "skipped": check.skipped, "options": [{k: v for k, v in o.items() if k != "result"}
                                                                             for o in opts[:MAX_OPTIONS]]}
    nights = x.trip.nights
    if opts:
        best, r = opts[0], opts[0]["result"]
        bd = breakdown(x.inputs, r["components"], total_cad=r["total_cad"], typical_cad=x.typical_cad, share=r["share"],
                       fringe=best["fringe"], lodging=lodging_line(best, nights, x.lodging_cad))
        return {**out, "chosen": 0, **r, "lodging_source": best["kind"], "fringe": best["fringe"], "breakdown": bd}
    bd = breakdown(x.inputs, components_dict(x), total_cad=x.total_cad, typical_cad=x.typical_cad, share=x.share,
                   lodging=lodging_line(None, nights, x.lodging_cad))
    return {**out, "chosen": None, "components": components_dict(x), "score": x.score, "total_cad": x.total_cad,
            "share": x.share, "lodging_cad": x.lodging_cad, "lodging_source": "estimate", "fringe": False, "breakdown": bd}


def _leg(leg: Leg) -> dict:
    return {"from": leg.origin, "to": leg.dest, "dep": leg.dep.isoformat(), "arr": leg.arr.isoformat(),
            "airlines": list(leg.airlines), "flight_numbers": list(leg.flight_numbers), "stops": leg.stops,
            "layover_min": leg.layover_min, "duration_min": leg.duration_min, "price_cad_2pax": leg.price_cad_2pax}


def links(city: City, out_dest: str, out_day: str, back_day: str, check_in: str, check_out: str) -> dict:
    nb = city.neighbourhoods[0]
    return {
        "google_flights": "https://www.google.com/travel/flights?q=" + quote(f"Flights to {out_dest} from YYC on {out_day} through {back_day}"),
        "google_hotels": "https://www.google.com/travel/search?q=" + quote(f"hotels in {nb}, {city.name} {check_in} to {check_out}"),
        "airbnb": f"https://www.airbnb.ca/s/{quote(f'{nb}, {city.name}')}/homes?checkin={check_in}&checkout={check_out}&adults=2",
    }


def write_candidate(x: Scored, city: City, ref: Reference, p2: dict, weather: tuple[float, str], s: Scoring, *,
                    scan_date: date, root=ROOT) -> tuple[Path, Path]:
    """hits/candidates/<id>.json and .md. Status awaiting_pass3, or dropped when the lodging check did not run (the
    next scan retries), when even the full what's-on points cannot reach the hit line, or when the optional cap
    blocks it (D-67): no Opus research is spent on those."""
    t, cls = x.trip, s.trip_classes[x.trip.trip_class]
    cid = candidate_id(scan_date, city.key, t.window_id)
    drop = None
    if p2["skipped"] and p2["chosen"] is None:
        drop = f"no lodging check ({p2['skipped']}); the next scan tries again"
    elif p2["score"] + EVENTS_CAP < cls["hit_threshold"]:
        drop = f"pass-2 score {p2['score']} cannot reach the hit line {cls['hit_threshold']} even with {EVENTS_CAP} what's-on points"
    elif s.cap_cad is not None and p2["total_cad"] > s.cap_cad:
        drop = f"complete trip ${p2['total_cad']:,.0f} is over the ${s.cap_cad:,} cap"
    cand = {
        "id": cid, "scan_date": scan_date.isoformat(), "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": s.mode, "stage": "near_miss" if drop else "candidate", "status": "dropped" if drop else "awaiting_pass3",
        "drop_reason": drop, "is_hit": False,
        "city": city.key, "city_name": city.name, "window_id": t.window_id, "trip_class": t.trip_class,
        "class_label": CLASS_LABEL[t.trip_class], "hit_threshold": cls["hit_threshold"],
        "dates": {"check_in": t.check_in.isoformat(), "check_out": t.check_out.isoformat(), "nights": t.nights},
        "flights": {"out": _leg(t.out), "back": _leg(t.back), "cad_2pax": t.flights_cad_2pax, "price_pp": x.price_pp},
        "ladder": {"label": x.ladder, **ref.flights, "confidence": ref.confidence, "nonstop": ref.nonstop},
        "typical_cad": x.typical_cad, "transfers_cad": transfers_cad(city), "conv_pts": x.conv_pts,
        "hours_on_ground": round(t.hours_on_ground, 1), "airport_to_core_min": city.airport_to_core_min,
        "weather": {"score": round(weather[0], 1), "source": weather[1]},
        "inputs": x.inputs,   # what the pass-1 components were computed from; finalize re-renders the breakdown from it
        "pass1": {"score": x.score, "components": components_dict(x), "lodging_cad": x.lodging_cad,
                  "lodging_source": "estimate", "total_cad": x.total_cad, "share": x.share, "breakdown": breakdown_of(x)},
        "pass2": p2, "pass3": None, "final_score": None,
        "score": p2["score"], "total_cad": p2["total_cad"], "breakdown": p2.get("breakdown"),
        "links": links(city, t.out.dest, t.out.dep.date().isoformat(), t.back.dep.date().isoformat(),
                       t.check_in.isoformat(), t.check_out.isoformat()),
    }
    j = Path(root, "candidates", f"{cid}.json")
    _write_json(j, cand)
    m = j.with_suffix(".md")
    m.write_text(render_brief(cand), encoding="utf-8")
    return j, m


# ---- pass 3 ----

def affordability(price_cad: float, famous: bool, interests: dict) -> float:
    """Free 1.0, up to $30 0.8, up to the lesser-known concert line ($60) 0.6, up to the famous line ($100) 0.3 if
    famous, else 0 (BUILD-PLAN-v2 T6). Per person, CAD."""
    p = interests["concert_price_cad"]
    if price_cad <= 0:
        return 1.0
    if price_cad <= 30:
        return 0.8
    if price_cad <= p["lesser_known"]:
        return 0.6
    return 0.3 if famous and price_cad <= p["famous"] else 0.0


def _check_research(r: dict, path) -> None:
    items = r.get("items") if isinstance(r, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"{path}: items must be a list (empty when nothing fits)")
    for i, it in enumerate(items):
        ok = (isinstance(it, dict) and isinstance(it.get("name"), str) and isinstance(it.get("reason"), str)
              and isinstance(it.get("uniqueness"), (int, float)) and 0 <= it["uniqueness"] <= 3
              and isinstance(it.get("fit"), (int, float)) and 0 <= it["fit"] <= 1
              and isinstance(it.get("price_cad"), (int, float)) and it["price_cad"] >= 0
              and isinstance(it.get("famous"), bool))
        if not ok:
            raise ValueError(f"{path}: item {i} needs name, reason, uniqueness 0-3, fit 0-1, price_cad >= 0 and famous true/false")
    a = r.get("airbnb")
    if a is not None and not isinstance(a, dict):
        raise ValueError(f"{path}: airbnb must be an object ({{\"hint\": ...}} when there is no price)")
    a = a or {}
    if a.get("total_cad") is not None and (not isinstance(a["total_cad"], (int, float)) or a["total_cad"] <= 0
                                           or not HTTPS.fullmatch(str(a.get("link", "")))):
        raise ValueError(f"{path}: an Airbnb price counts only with a positive total_cad and an https link")


def finalize(cid: str, research_path, s: Scoring, interests: dict, *, root=ROOT) -> Path:
    """Pass 3: what's on (+ up to 10) and an Airbnb price that beats the lodging found, then the hit decision.
    A hit needs real lodging (pass 2 or a concrete Airbnb total for these exact dates), never the pass-1 estimate."""
    cpath = Path(root, "candidates", f"{cid}.json")
    cand = json.loads(cpath.read_text(encoding="utf-8"))
    research = json.loads(Path(research_path).read_text(encoding="utf-8"))
    _check_research(research, research_path)
    items = []
    for it in research["items"]:
        a = affordability(it["price_cad"], it["famous"], interests)
        items.append({**it, "affordability": a, "points": round(it["uniqueness"] * it["fit"] * a, 2)})
    events = round(min(EVENTS_CAP, sum(it["points"] for it in items)), 1)
    p2 = cand["pass2"]
    base = {k: p2[k] for k in ("components", "score", "total_cad", "share", "lodging_cad", "lodging_source")}
    nights = cand["dates"]["nights"]
    lodging = next((row["input"] for row in p2.get("breakdown") or () if row["key"] == "lodging"), None)
    fringe = p2.get("fringe", False)
    airbnb = research.get("airbnb") or {}
    same_stay = (airbnb.get("check_in"), airbnb.get("check_out")) == (cand["dates"]["check_in"], cand["dates"]["check_out"])
    if airbnb.get("total_cad") is not None and same_stay and (base["lodging_source"] == "estimate" or airbnb["total_cad"] < base["lodging_cad"]):
        r = rescore(p2["components"], flights_cad=cand["flights"]["cad_2pax"], lodging_cad=airbnb["total_cad"],
                    transfers=cand["transfers_cad"], typical_cad=cand["typical_cad"], conv_pts=cand["conv_pts"], fringe=False, s=s)
        base, fringe = {**r, "lodging_source": "airbnb"}, False   # listed neighbourhoods only, so never fringe
        lodging = f"Airbnb: {_plain(airbnb.get('title') or 'listing')}, {_money(airbnb['total_cad'] / nights)} a night all-in, total {_money(airbnb['total_cad'])}"
    final = round(base["score"] + events)
    on = ", ".join(f"{_plain(it['name'])} (+{it['points']:g})" for it in sorted(items, key=lambda it: -it["points"]) if it["points"] > 0)
    events_line = f"+{events:g}: {on or 'nothing that passes the Calgary test'}"
    bd = breakdown(cand["inputs"], base["components"], total_cad=base["total_cad"], typical_cad=cand["typical_cad"], share=base["share"],
                   fringe=fringe, lodging=lodging, events=(events, events_line)) if cand.get("inputs") else None   # None: a pre-D-75 candidate file
    cls = s.trip_classes[cand["trip_class"]]
    why = None
    if base["lodging_source"] == "estimate":
        why = "no real lodging found (no hotel or rental within 6 km, no Airbnb total for these dates)"
    elif s.cap_cad is not None and base["total_cad"] > s.cap_cad:
        why = f"complete trip ${base['total_cad']:,.0f} is over the ${s.cap_cad:,} cap"
    elif final < cls["hit_threshold"]:
        why = f"final {final} is under the hit line {cls['hit_threshold']}"
    is_hit = why is None
    out = {**cand, "mode": s.mode, "stage": "hit" if is_hit else "near_miss", "status": "done", "is_hit": is_hit,
           "drop_reason": why, "hit_threshold": cls["hit_threshold"], "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "pass3": {"events_pts": events, "items": items, "negatives": [str(n) for n in research.get("negatives") or []],
                     "airbnb": airbnb or None, "airbnb_used": base["lodging_source"] == "airbnb",
                     "research": Path(research_path).as_posix(), "researched": research.get("researched"), **base, "breakdown": bd},
           "final_score": final, "score": final, "total_cad": base["total_cad"], "breakdown": bd}
    for old in ("", "dry-run", "near-miss"):   # a re-run with other research must not leave the earlier verdict behind
        for ext in (".json", ".md"):
            Path(root, old, cid + ext).unlink(missing_ok=True)
    sub = ("dry-run" if s.mode == "dry-run" else "") if is_hit else "near-miss"
    j = Path(root, sub, f"{cid}.json")
    _write_json(j, out)
    j.with_suffix(".md").write_text(render_brief(out), encoding="utf-8")
    cand["status"] = "done"
    _write_json(cpath, cand)
    return j


# ---- the brief ----

def _plain(s) -> str:
    """API- and research-supplied text must not inject markdown links or emphasis into the brief."""
    return str(s).replace("[", "(").replace("]", ")").replace("*", "").replace("\n", " ")


def _link(text, url) -> str:
    """[text](url) only for a plain https URL; anything else (empty, http, brackets) prints the text alone."""
    return f"[{_plain(text)}]({url})" if HTTPS.fullmatch(str(url or "")) else _plain(text)


def _fmt_leg(leg: dict) -> str:
    dep, arr = datetime.fromisoformat(leg["dep"]), datetime.fromisoformat(leg["arr"])
    via = "non-stop" if not leg["stops"] else f"1 stop, {leg['layover_min'] // 60}h{leg['layover_min'] % 60:02d} layover"
    nums = ", ".join(leg["flight_numbers"]) or "/".join(leg["airlines"])
    return f"{leg['from']} {dep:%a %b %d %H:%M} → {leg['to']} {arr:%a %H:%M} local ({nums}; {via})"


def _money(v) -> str:
    return f"${v:,.0f}"


def render_brief(h: dict) -> str:
    p1, p2, p3, lad = h["pass1"], h["pass2"], h.get("pass3"), h["ladder"]
    best = p3 or p2
    chosen = p2["options"][p2["chosen"]] if p2.get("chosen") is not None else None
    lodging = {"estimate": "estimate at the route's good room rate (no real lodging found yet)",
               "airbnb": "Airbnb listing below"}.get(best["lodging_source"])
    if lodging is None and chosen:
        lodging = f"{_plain(chosen['name'])}, {chosen['kind']}, {chosen['km']} km from the centre" + (" (fringe)" if chosen["fringe"] else "")
    stage = {"hit": "Hit", "near_miss": "Near miss", "candidate": "Awaiting the what's-on research"}[h["stage"]]
    lines = [
        f"# {h['city_name']}: {h['dates']['check_in']} to {h['dates']['check_out']} ({h['score']})",
        "",
        f"{h['class_label']}. {stage}" + (f": {h['drop_reason']}" if h.get("drop_reason") else "") + ". "
        + ("Learning run: nothing is emailed." if h["mode"] == "dry-run" else "Live."),
        "",
        f"- **Out:** {_fmt_leg(h['flights']['out'])}",
        f"- **Back:** {_fmt_leg(h['flights']['back'])}",
        f"- **Flights for two:** {_money(h['flights']['cad_2pax'])} with a carry-on each ({_money(h['flights']['price_pp'])} per person, "
        f"{lad['label']}: this route is typically {_money(lad['typical'])}, good {_money(lad['good'])}, exceptional {_money(lad['exceptional'])})",
        f"- **Lodging, {h['dates']['nights']} nights:** {_money(best['lodging_cad'])} all-in ({lodging})",
        f"- **Airport transfers:** {_money(h['transfers_cad'])}; airport to core about {h['airport_to_core_min']} min",
        f"- **Complete trip for two:** {_money(best['total_cad'])}, {best['share'] * 100:.0f}% of what this trip typically costs ({_money(h['typical_cad'])})",
        f"- **Time on the ground:** {h['hours_on_ground']} waking hours",
        f"- **Weather:** {h['weather']['score']}/10 ({h['weather']['source']})",
        "",
        "## Score",
        f"- Pass 1, fares with lodging estimated: {p1['score']}",
        f"- Pass 2, real lodging: {p2['score']}" + (f" (lodging check: {p2['skipped']})" if p2.get("skipped") else ""),
    ]
    if p3:
        if p3["lodging_source"] == "airbnb":
            lines.append(f"- Airbnb beat it: {p3['score']}")
        lines.append(f"- What's on: +{p3['events_pts']:g}")
        lines.append(f"- **Final: {h['final_score']}** (hit line {h['hit_threshold']})")
    lines += ["", "## Lodging options"]
    for o in p2["options"][:5]:
        stars = f"{o['stars']}-star, " if o.get("stars") else ""
        deal = f", Google: {_plain(o['deal'])}" if o.get("deal") else ""
        lines.append(f"- {_link(o['name'], o['link'])} {o['kind']}, {stars}rated {o['rating']}, {o['km']} km"
                     f"{' (fringe)' if o['fringe'] else ''}: {_money(o['total'])} {o['currency']} all-in{deal}. Trip score {o['trip_score']}")
    if not p2["options"]:
        lines.append(f"- None found: {p2.get('skipped') or 'no 4-5 star place rated 4.3+ within 6 km'}")
    if p3:
        a = p3.get("airbnb") or {}
        if a.get("total_cad") is not None:
            used = "" if p3.get("airbnb_used") else " (not used: other dates, or not cheaper)"
            lines.append(f"- Airbnb: {_link(a.get('title') or 'listing', a.get('link'))} {_money(a['total_cad'])} all-in{used}")
        elif a.get("hint"):
            lines.append(f"- Airbnb: {_plain(a['hint'])}")
        lines += ["", "## What's on"]
        for it in sorted(p3["items"], key=lambda it: -it["points"]):
            when = f"{_plain(it['date'])}: " if it.get("date") else ""
            lines.append(f"- {when}{_plain(it['name'])}, +{it['points']:g}. {_plain(it['reason'])}")
        if not p3["items"]:
            lines.append("- Nothing that passes the Calgary test.")
        for n in p3["negatives"]:
            lines.append(f"- Watch: {_plain(n)}")
    ln = h["links"]
    lines += ["", f"[Google Flights]({ln['google_flights']}) · [Google Hotels]({ln['google_hotels']}) · [Airbnb]({ln['airbnb']})", ""]
    return "\n".join(lines)
