"""CLI.

python -m radar.main scan [--offline] [--today YYYY-MM-DD] [--cities a,b] [--budget N]
python -m radar.main finalize <candidate id> --research data/research/<city>-<window>.json   # pass 3 (radar-daily)
python -m radar.main export       # rebuild series.json and the hits/digests indexes from what is on disk
python -m radar.main summarize    # data/weekly-summary.json
"""
import argparse
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from radar.config import load_cities, load_days_off, load_holidays, load_interests, load_references, load_scoring
from radar.export import write_digests_index, write_hits_index, write_latest, write_series, write_weekly_summary
from radar.flights import HOME, Budget, FetchError, build_queries, fetch_leg
from radar.hits import candidate_id, fare_dropped, finalize, pass2, previous_candidate, write_candidate
from radar.hotels import check_lodging, used_this_month
from radar.itineraries import assemble
from radar.score import score_trip, worth_flying
from radar.store import append_quotes, quote_row, read_history, route_percentile
from radar.weather import weather_score
from radar.windows import CALGARY, class_windows

OFFLINE_DIR = "tests/fixtures/offline"
MAX_CANDIDATES_PER_SCAN = 3     # pass 2 (2 SerpApi lookups each) for the top three; the 200/month cap holds at 3 a day
BLOCK_STREAK = 15               # consecutive fetch errors that mean Google is blocking: stop fetching


def load_dotenv(path=".env") -> None:
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def scan(args) -> int:
    t0 = time.time()
    scan_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    today = date.fromisoformat(args.today) if args.today else datetime.now(CALGARY).date()
    s, holidays = load_scoring(), load_holidays()
    extra, blocked = load_days_off()
    all_cities = load_cities()
    refs = load_references(keys=[c.key for c in all_cities])
    cities = [c for c in all_cities if c.enabled]
    if args.cities:
        keep = set(args.cities.split(","))
        cities = [c for c in cities if c.key in keep]
    by_key = {c.key: c for c in cities}
    windows = class_windows(today, s, holidays, extra=extra, blocked=blocked)
    classes = s.trip_classes
    if args.offline:   # the rotation only spreads Google requests; fixtures cost nothing, so read every city-weekend
        classes = {**classes, "dayoff": {**classes["dayoff"], "rotate_days": 1}}
    queries = build_queries(cities, windows, today, classes)

    day_cache = Path(f"data/cache/{today}")
    flight_cache = Path(OFFLINE_DIR) if args.offline else day_cache
    budget = Budget(0 if args.offline else args.budget)
    legs, errors, skipped, cache_hits, streak, blocked = {}, [], 0, 0, 0, False
    for q in queries:
        cached = (flight_cache / f"{q.key()}.json").exists()
        if (blocked or time.time() - t0 > args.deadline_min * 60) and not cached:
            skipped += 1   # past the deadline: score what we have rather than lose the day to the job timeout
            continue
        try:
            legs[(q.trip_class, q.origin, q.dest, q.day)] = fetch_leg(q, budget, cache_dir=flight_cache,
                                                        sleep_range=(0, 0) if args.offline else (3.0, 7.0))
            cache_hits += cached
            streak = 0
        except FetchError as e:
            if str(e) == "budget":
                skipped += 1
                continue
            errors.append({"route": f"{q.origin}-{q.dest}", "day": q.day.isoformat(), "error": str(e)[:200]})
            streak += 1
            blocked = blocked or streak >= BLOCK_STREAK
    print(f"fetched {len(legs)}/{len(queries)} queries, {len(errors)} errors, {skipped} skipped", file=sys.stderr)

    no_nonstop = []
    for c in cities:
        answered = [v for (_, o, d, _), v in legs.items() if (o == HOME and d in c.airports) or (d == HOME and o in c.airports)]
        if answered and not any(leg.stops == 0 for v in answered for leg in v):
            no_nonstop.append(c.key)

    serp_key = None if args.offline else os.environ.get("SERPAPI_KEY")
    history = [r for r in read_history(90, today=today) if r["scan_date"] != today.isoformat()]  # a re-run must not see itself
    by_city_hist: dict[tuple, list] = {}
    for r in history:   # a quote is compared only with earlier quotes of its own class (D-52)
        by_city_hist.setdefault((r["city"], r.get("trip_class", "dayoff")), []).append(r)
    pct_memo: dict[tuple, float | None] = {}

    def pct(city_key, trip_class, price_pp):
        k = (city_key, trip_class, price_pp)
        if k not in pct_memo:
            pct_memo[k] = route_percentile(price_pp, city_key, by_city_hist.get((city_key, trip_class), []))
        return pct_memo[k]

    # pass 1: score every in-window trip; one winner per city-window
    winners, logged, weather = [], [], {}
    for c in cities:
        for w in windows:
            cls = w.trip_class   # a class's legs never pair with the other class's windows
            outs = [leg for d in w.out_dates for a in c.airports for leg in legs.get((cls, HOME, a, d), [])]
            backs = [leg for d in w.back_dates for a in c.airports for leg in legs.get((cls, a, HOME, d), [])]
            trips = [t for t in assemble(c, w, outs, backs) if worth_flying(t, s)]
            if not trips:
                continue
            wx = weather_score(c, list(w.days_off), today=today, cache_dir=None if args.offline else day_cache)
            sc = [score_trip(t, c, refs[c.key], s, weather_score=wx[0], history_pct=pct(c.key, cls, round(t.flights_cad_2pax / 2)))
                  for t in trips]
            win = max(sc, key=lambda x: (x.score, -x.total_cad))
            winners.append(win)
            weather[(c.key, w.id)] = wx
            cheapest = {}
            for x in sc:
                if x.trip.airport not in cheapest or x.trip.flights_cad_2pax < cheapest[x.trip.airport].trip.flights_cad_2pax:
                    cheapest[x.trip.airport] = x
            logged += [(x, x is win) for x in list(cheapest.values()) + ([win] if win not in cheapest.values() else [])]

    # pass 2: real lodging for the top candidates; pass 3 is the daily routine's (radar.main finalize)
    passes, cand_ids, checks, lookups = {}, [], 0, 0
    for x in sorted((x for x in winners if x.candidate), key=lambda x: (-x.score, x.total_cad)):
        c, wid = by_key[x.trip.city_key], x.trip.window_id
        cid = candidate_id(today, c.key, wid)
        prev = previous_candidate(c.key, wid, today=today, exclude_id=cid)
        if prev and not fare_dropped(x.trip.flights_cad_2pax, prev, s.realert_drop_pct):
            passes[id(x)] = (2, prev["id"])   # looked at within 7 days and the fare has not dropped enough: no new lookups
            print(f"candidate {c.key} {wid}: seen as {prev['id']}", file=sys.stderr)
            continue
        if checks >= MAX_CANDIDATES_PER_SCAN:
            print(f"candidate {c.key} {wid}: over the {MAX_CANDIDATES_PER_SCAN} a scan", file=sys.stderr)
            continue
        checks += 1
        check = check_lodging(c, x.trip.check_in, x.trip.check_out, s, api_key=serp_key, cache_dir=day_cache, today=today)
        lookups += check.searches
        write_candidate(x, c, refs[c.key], pass2(x, c, check, s), weather[(c.key, wid)], s, scan_date=today)
        passes[id(x)] = (2, cid)
        cand_ids.append(cid)
        print(f"candidate {c.key} {wid}: pass 2, {len(check.options)} lodging options, {check.skipped or 'ok'}", file=sys.stderr)
    none = (1, None)
    rows = [quote_row(x, today, scan_ts, win, pass_=passes.get(id(x), none)[0], candidate_id=passes.get(id(x), none)[1])
            for x, win in logged]

    today_file = Path("data/history") / f"{today}.jsonl"
    today_file.unlink(missing_ok=True)   # a re-run on the same day replaces that day's rows
    append_quotes(today, rows)
    health = {
        "queries_planned": len(queries), "queries_answered": len(legs), "queries_attempted": budget.used,
        "budget_max": budget.max_attempts, "coverage_pct": round(100 * len(legs) / len(queries), 1) if queries else 0.0,
        "cache_hits": cache_hits, "budget_skipped": skipped, "fetch_error_count": len(errors),
        "fetch_errors": errors[:50], "blocked": blocked, "no_nonstop": no_nonstop,
        "windows": len(windows), "city_windows_with_trips": len(winners), "history_rows": len(rows),
        "candidates": sum(x.candidate for x in winners), "pass2_checks": checks, "serpapi_lookups": lookups,
        "serpapi_used_this_month": used_this_month(today.strftime("%Y-%m")), "serpapi_cap": s.serpapi_monthly_cap,
        "host": "github-actions" if os.environ.get("GITHUB_ACTIONS") else ("offline" if args.offline else "local"),
        "duration_s": round(time.time() - t0),
    }
    classes = {k: {"enabled": v["enabled"], "candidate_threshold": v["candidate_threshold"], "hit_threshold": v["hit_threshold"]}
               for k, v in s.trip_classes.items()}
    classes["dayoff"]["min_weeks"] = s.dayoff_min_weeks
    write_latest(winners, cities, refs, health, scan_date=today, scan_ts=scan_ts, mode=s.mode,
                 candidates=cand_ids, passes=passes, classes=classes)
    export()
    write_weekly_summary(read_history(90, today=today), today=today)
    return 0


def finalize_cmd(args) -> int:
    """Pass 3 for one candidate: the routine writes the research file, this does the arithmetic and the files."""
    path = finalize(args.id, args.research, load_scoring(), load_interests())
    write_hits_index()
    print(path.as_posix())
    return 0


def export(_args=None) -> int:
    write_series(read_history(90))
    write_hits_index()
    write_digests_index()
    return 0


def summarize(_args=None) -> int:
    write_weekly_summary(read_history(90))
    return 0


def main(argv=None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("scan")
    sp.add_argument("--offline", action="store_true", help="read flights from tests/fixtures/offline; no APIs")
    sp.add_argument("--today", help="scan date YYYY-MM-DD (default: today in Calgary)")
    sp.add_argument("--cities", help="comma-separated city keys")
    sp.add_argument("--budget", type=int, default=900, help="max Google Flights fetch attempts")
    sp.add_argument("--deadline-min", type=float, default=110, help="stop starting new fetches after this many minutes")
    fp = sub.add_parser("finalize")
    fp.add_argument("id", help="candidate id, the file name in hits/candidates/ without .json")
    fp.add_argument("--research", required=True, help="data/research/<city>-<window>.json")
    sub.add_parser("export")
    sub.add_parser("summarize")
    args = ap.parse_args(argv)
    return {"scan": scan, "finalize": finalize_cmd, "export": export, "summarize": summarize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
