"""CLI.

python -m radar.main scan [--offline] [--today YYYY-MM-DD] [--cities a,b] [--budget N]
python -m radar.main export       # rebuild series.json and the hits/digests indexes from what is on disk
python -m radar.main summarize    # data/weekly-summary.json
"""
import argparse
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from radar.config import load_cities, load_holidays, load_scoring
from radar.events import fetch_events, notable_count
from radar.export import write_digests_index, write_hits_index, write_latest, write_series, write_weekly_summary
from radar.flights import HOME, Budget, FetchError, build_queries, fetch_leg
from radar.hits import finalize_hit, gates, previous_hit, write_hit
from radar.hotels import HotelCheck, check_hotels, used_this_month
from radar.itineraries import assemble
from radar.score import score_trip
from radar.store import append_quotes, quote_row, read_history, route_percentile
from radar.weather import weather_score
from radar.windows import CALGARY, generate_windows

OFFLINE_DIR = "tests/fixtures/offline"
MAX_HOTEL_CHECKS_PER_SCAN = 3   # ponytail: spreads the 60/month SerpApi cap; raise if candidates go unchecked
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
    cities = load_cities()
    if args.cities:
        keep = set(args.cities.split(","))
        cities = [c for c in cities if c.key in keep]
    by_key = {c.key: c for c in cities}
    windows = generate_windows(today, holidays, s.lookahead_min_days, s.lookahead_max_days)
    queries = build_queries(cities, windows, today)

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
            legs[(q.origin, q.dest, q.day)] = fetch_leg(q, budget, cache_dir=flight_cache,
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
        answered = [v for (o, d, _), v in legs.items() if (o == HOME and d in c.airports) or (d == HOME and o in c.airports)]
        if answered and not any(leg.stops == 0 for v in answered for leg in v):
            no_nonstop.append(c.key)

    tm_key = None if args.offline else os.environ.get("TICKETMASTER_KEY")
    serp_key = None if args.offline else os.environ.get("SERPAPI_KEY")
    history = [r for r in read_history(90, today=today) if r["scan_date"] != today.isoformat()]  # a re-run must not see itself
    by_city_hist: dict[str, list] = {}
    for r in history:
        by_city_hist.setdefault(r["city"], []).append(r)
    pct_memo: dict[tuple, float | None] = {}

    def pct(city_key, price_pp):
        k = (city_key, price_pp)
        if k not in pct_memo:
            pct_memo[k] = route_percentile(price_pp, city_key, by_city_hist.get(city_key, []))
        return pct_memo[k]

    winners, rows, context = [], [], {}
    for c in cities:
        for w in windows:
            outs = [leg for d in w.out_dates for a in c.airports for leg in legs.get((HOME, a, d), [])]
            backs = [leg for d in w.back_dates for a in c.airports for leg in legs.get((a, HOME, d), [])]
            trips = assemble(c, w, outs, backs)
            if not trips:
                continue
            evs = fetch_events(c, w.days_off[0], w.days_off[-1], api_key=tm_key, cache_dir=day_cache)
            n = notable_count(evs, w.days_off)
            wx = weather_score(c, list(w.days_off), today=today, cache_dir=None if args.offline else day_cache)
            sc = [score_trip(t, c, s, n_events=n, weather_score=wx[0], history_pct=pct(c.key, round(t.flights_cad_2pax / 2)))
                  for t in trips]
            win = max(sc, key=lambda x: (x.score, -x.total_cad))
            winners.append(win)
            context[(c.key, w.id)] = (evs, wx)
            cheapest = {}
            for x in sc:
                if x.trip.airport not in cheapest or x.trip.flights_cad_2pax < cheapest[x.trip.airport].trip.flights_cad_2pax:
                    cheapest[x.trip.airport] = x
            logged = list(cheapest.values()) + ([win] if win not in cheapest.values() else [])
            rows += [quote_row(x, today, scan_ts, x is win) for x in logged]

    hit_ids, cand_ids, checks = [], [], 0
    for x in sorted((x for x in winners if x.candidate), key=lambda x: -x.score):
        c, wid = by_key[x.trip.city_key], x.trip.window_id
        hid = f"{today}_{c.key}_{wid}"
        prev = previous_hit(c.key, wid, exclude_id=hid)
        g = gates(x, c, s, prev)
        if not (g["score_ok"] and g["realert_ok"]):
            hc = HotelCheck((), None, "gated")   # lodging cannot change the score or the re-alert rule: save SerpApi
        elif checks >= MAX_HOTEL_CHECKS_PER_SCAN:
            hc = HotelCheck((), None, "cap")
        else:
            checks += 1
            hc = check_hotels(c, x.trip.check_in, x.trip.nights, s, api_key=serp_key, cache_dir=day_cache, today=today)
        x2, is_hit, reason = finalize_hit(x, c, hc, s, prev)
        cand_ids.append(hid)
        if s.mode == "dry-run" or is_hit:
            evs, wx = context[(c.key, wid)]
            j, _ = write_hit(x2, c, hc, evs, wx, s, gate=gates(x2, c, s, prev), is_hit=is_hit, scan_date=today)
            if is_hit:
                hit_ids.append(j.stem)
        print(f"candidate {c.key} {wid}: {reason}", file=sys.stderr)

    today_file = Path("data/history") / f"{today}.jsonl"
    today_file.unlink(missing_ok=True)   # a re-run on the same day replaces that day's rows
    append_quotes(today, rows)
    health = {
        "queries_planned": len(queries), "queries_answered": len(legs), "queries_attempted": budget.used,
        "budget_max": budget.max_attempts, "coverage_pct": round(100 * len(legs) / len(queries), 1) if queries else 0.0,
        "cache_hits": cache_hits, "budget_skipped": skipped, "fetch_error_count": len(errors),
        "fetch_errors": errors[:50], "blocked": blocked, "no_nonstop": no_nonstop,
        "windows": len(windows), "city_windows_with_trips": len(winners), "history_rows": len(rows),
        "serpapi_used_this_month": used_this_month(today.strftime("%Y-%m")), "serpapi_cap": s.serpapi_monthly_cap,
        "events_source": "ticketmaster" if tm_key else "none (no key)",
        "host": "github-actions" if os.environ.get("GITHUB_ACTIONS") else ("offline" if args.offline else "local"),
        "duration_s": round(time.time() - t0),
    }
    write_latest(winners, cities, health, scan_date=today, scan_ts=scan_ts, mode=s.mode, hits=hit_ids,
                 candidates=cand_ids)
    export()
    write_weekly_summary(read_history(90, today=today), today=today)
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
    sub.add_parser("export")
    sub.add_parser("summarize")
    args = ap.parse_args(argv)
    return {"scan": scan, "export": export, "summarize": summarize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
