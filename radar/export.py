"""JSON the dashboard and the weekly digest read: latest, series, indexes, weekly summary. All writes atomic."""
import json
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from radar.config import City
from radar.score import Scored


def write_json(path, obj) -> None:
    """Temp file + os.replace: a crash never leaves a partial file (Review Focus 3)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _row(x: Scored, city: City) -> dict:
    t = x.trip
    return {
        "city": t.city_key, "city_name": city.name, "airport": t.airport, "window_id": t.window_id,
        "dates": {"out_dep": t.out.dep.isoformat(), "out_arr": t.out.arr.isoformat(),
                  "back_dep": t.back.dep.isoformat(), "back_arr": t.back.arr.isoformat(),
                  "check_in": t.check_in.isoformat(), "check_out": t.check_out.isoformat(), "nights": t.nights},
        "airlines": "+".join(dict.fromkeys(t.out.airlines + t.back.airlines)),
        "flights_cad_2pax": t.flights_cad_2pax, "price_pp": x.price_pp, "band": x.band,
        "history_pct": None if x.history_pct is None else round(x.history_pct, 1), "score": x.score,
        "candidate": x.candidate, "hours_on_ground": round(t.hours_on_ground, 1),
        "stops": [t.out.stops, t.back.stops], "total_cad": round(x.total_cad), "bar_cad": city.bar_cad,
    }


def write_latest(winners: list[Scored], cheapest: list[Scored], cities: list[City], health: dict, *, scan_date: date,
                 scan_ts: str, mode: str, hits: list[str], candidates: list[str], path="data/latest.json") -> None:
    """best_by_city: each city's cheapest in-window trip (design 6.3); windows: the top-scoring trip per city-window."""
    by_key = {c.key: c for c in cities}
    order = lambda r: (-r["score"], r["total_cad"])  # noqa: E731
    rows = sorted((_row(x, by_key[x.trip.city_key]) for x in winners), key=order)
    write_json(path, {
        "scan_date": scan_date.isoformat(), "scan_ts": scan_ts, "mode": mode,
        "best_by_city": sorted((_row(x, by_key[x.trip.city_key]) for x in cheapest), key=order), "windows": rows,
        "cities": [{"key": c.key, "name": c.name, "tier": c.tier, "rank": c.rank} for c in cities],
        "hits": hits, "candidates": candidates, "health": health,
    })


def write_series(history: list[dict], path="data/series.json", days: int = 30) -> None:
    """{city: [[scan_date, cheapest price_pp that day], ...]} for the last `days` scan days."""
    lo: dict[str, dict[str, int]] = defaultdict(dict)
    for r in history:
        d = lo[r["city"]]
        d[r["scan_date"]] = min(d.get(r["scan_date"], r["price_pp"]), r["price_pp"])
    write_json(path, {c: sorted(v.items())[-days:] for c, v in sorted(lo.items())})


def _hit_files(root):
    for p in sorted(Path(root).glob("**/*.json")):
        if p.name != "index.json":
            yield p, json.loads(p.read_text(encoding="utf-8"))


def write_hits_index(root="hits") -> None:
    rows = [{"id": h["id"], "city": h["city"], "city_name": h.get("city_name", h["city"]), "mode": h["mode"],
             "is_hit": h.get("is_hit", False), "score": h["score"], "total_cad": h["price"]["total_cad"],
             "created": h["created"], "path_json": p.as_posix(), "path_md": p.with_suffix(".md").as_posix()}
            for p, h in _hit_files(root)]
    write_json(Path(root) / "index.json", sorted(rows, key=lambda r: r["created"], reverse=True))


def write_digests_index(root="data/digests") -> None:
    files = sorted(Path(root).glob("*.md"), reverse=True)
    write_json(Path(root) / "index.json", [{"date": p.stem, "path": p.as_posix()} for p in files])


def _pct(sorted_vals: list[int], q: float):
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))] if sorted_vals else None


def write_weekly_summary(history: list[dict], hits_dir="hits/dry-run", path="data/weekly-summary.json",
                         latest_path="data/latest.json", today: date | None = None) -> None:
    """Compact input for the Monday digest routine: what would have fired, band spread, request health."""
    today = today or date.today()
    since = (today - timedelta(days=7)).isoformat()
    week = [r for r in history if r["scan_date"] >= since]
    winners = [r for r in week if r.get("winner")]
    bands: dict[str, Counter] = defaultdict(Counter)
    prices: dict[str, list[int]] = defaultdict(list)
    nonstop: dict[str, list[bool]] = defaultdict(list)
    for r in winners:
        bands[r["city"]][r["band"]] += 1
    for r in week:
        prices[r["city"]].append(r["price_pp"])
        nonstop[r["city"]].append(r["stops_out"] == 0 and r["stops_back"] == 0)
    hits = [h for _, h in _hit_files(hits_dir) if h["created"][:10] >= since]
    latest = json.loads(Path(latest_path).read_text(encoding="utf-8")) if Path(latest_path).exists() else {}
    cities = sorted(set(prices))
    write_json(path, {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": [since, today.isoformat()], "scan_days": len({r["scan_date"] for r in week}),
        "history_days_total": len({r["scan_date"] for r in history}),
        "would_have_fired": [{"id": h["id"], "score": h["score"], "total_cad": h["price"]["total_cad"],
                              "bar_cad": h["price"]["bar_cad"], "band": h["price"]["band"]} for h in hits if h.get("is_hit")],
        "near_misses": [{"id": h["id"], "score": h["score"], "gate": h["gate"]} for h in hits if not h.get("is_hit")],
        "band_distribution": {c: dict(bands[c]) for c in cities},
        "price_pp": {c: {"min": min(prices[c]), "p10": _pct(sorted(prices[c]), 0.1), "p25": _pct(sorted(prices[c]), 0.25),
                         "p50": _pct(sorted(prices[c]), 0.5), "p90": _pct(sorted(prices[c]), 0.9)} for c in cities},
        "nonstop_share": {c: round(sum(nonstop[c]) / len(nonstop[c]), 2) for c in cities},
        "google_label_agreement": "not available: the free fast-flights fetch carries no low/typical/high label",
        "request_health": latest.get("health", {}),
    })
