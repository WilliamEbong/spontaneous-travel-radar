"""Day-one smoke test of fast-flights against live Google Flights.

Run from the repo root: python scripts/smoke_fast_flights.py
Writes raw itinerary fixtures to tests/fixtures/ (the Google JSON items radar.flights.to_leg parses).

fast-flights 3.1.0's parser reads only payload[3][0] ("other flights") and drops payload[2][0]
("best flights"), which often holds the cheapest fare; this script reads both lists itself.
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from fast_flights import FlightQuery, Passengers, create_query
from fast_flights.fetcher import fetch_flights_html
from selectolax.lexbor import LexborHTMLParser

FIX = Path("tests/fixtures")
today = date.today()
D = today + timedelta(days=21 + (4 - (today + timedelta(days=21)).weekday()) % 7)  # first Friday >= 21 days out
D2 = D + timedelta(days=2)


def q(legs, trip="one-way", bags=True, basic=True, adults=2, max_stops=None):
    return create_query(
        flights=legs, trip=trip, passengers=Passengers(adults=adults), currency="CAD",
        max_stops=max_stops, carry_on_bags=1 if bags else 0, exclude_basic_economy=basic,
    )


def items(html):
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        raise RuntimeError("no ds:1 script (blocked or layout change)")
    data = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        return []
    pl = json.loads(data)
    return [it for part in (pl[2], pl[3]) if part and part[0] for it in part[0]]


def hm(t):
    return f"{(t or [0])[0] or 0:02d}:{(t + [0, 0])[1] or 0:02d}" if t else "00:00"


def run(label, query):
    time.sleep(4)
    try:
        res = items(fetch_flights_html(query))
    except Exception as e:  # noqa: BLE001 - smoke test reports everything
        print(f"[{label}] {type(e).__name__}: {e}")
        return None
    res.sort(key=lambda it: it[1][0][1] if it[1] and it[1][0] and it[1][0][1] else 10**9)
    print(f"[{label}] {len(res)} results")
    for it in res[:3]:
        f = it[0]
        segs = " | ".join(f"{s[3]} {s[20]} {hm(s[8])} -> {s[6]} {s[21]} {hm(s[10])} ({s[11]}m) {s[22][0]}{s[22][1]}" for s in f[2])
        print(f"    price={it[1][0][1]} code={f[0]} airlines={f[1]} :: {segs}")
    return res


def cheapest(res):
    return min((it[1][0][1] for it in res or [] if it[1] and it[1][0] and it[1][0][1]), default=None)


def dump(res, name, pick=lambda it: True):
    rows = [it for it in res or [] if pick(it)]
    if rows:
        FIX.mkdir(parents=True, exist_ok=True)
        (FIX / name).write_text(json.dumps(rows))
        print(f"    wrote {FIX / name} ({len(rows)} rows)")


nsegs = lambda n: lambda it: len(it[0][2]) == n  # noqa: E731
print(f"D={D} ({D:%a}) D+2={D2} ({D2:%a})")

# 1. one-way YYC->YVR, non-stop, carry-on priced, basic excluded
r1 = run("1 YYC-YVR bags+nobasic", q([FlightQuery(D.isoformat(), "YYC", "YVR")], max_stops=0))
dump(r1, "ff_yyc_yvr_oneway.json")

# 2. flag effects: none / bags only / no-basic only; Flair; 1 adult (is the price a total for 2?)
r2 = run("2 none", q([FlightQuery(D.isoformat(), "YYC", "YVR")], bags=False, basic=False, max_stops=0))
r2b = run("2 bags only", q([FlightQuery(D.isoformat(), "YYC", "YVR")], basic=False, max_stops=0))
r2c = run("2 nobasic only", q([FlightQuery(D.isoformat(), "YYC", "YVR")], bags=False, max_stops=0))
print(f"    cheapest both={cheapest(r1)} none={cheapest(r2)} bags-only={cheapest(r2b)} nobasic-only={cheapest(r2c)}")
f8 = [FlightQuery(D.isoformat(), "YYC", "YVR", airlines=["F8"])]
print(f"    Flair: none={cheapest(run('2 F8 none', q(f8, bags=False, basic=False, max_stops=0)))} "
      f"bags-only={cheapest(run('2 F8 bags only', q(f8, basic=False, max_stops=0)))} "
      f"both={cheapest(run('2 F8 both', q(f8, max_stops=0)))}")
r2a = run("2 1 adult", q([FlightQuery(D.isoformat(), "YYC", "YVR")], adults=1, max_stops=0))
print(f"    cheapest 2 adults={cheapest(r1)} 1 adult={cheapest(r2a)}")

# 3. return leg with latest_arrival_hour=16
r3 = run("3 YVR-YYC arr<=16", q([FlightQuery(D2.isoformat(), "YVR", "YYC", latest_arrival_hour=16)], max_stops=0))
late = [it for it in r3 or [] if tuple(it[0][2][-1][21]) != D2.timetuple()[:3] or (it[0][2][-1][10] or [0])[0] >= 16]
print(f"    results landing after 16:00 or on another day: {len(late)} of {len(r3 or [])}")

# 4. round trip vs one-way sums (information only; v1 sums one-ways)
for apt in ("YVR", "LAS"):
    rt = run(f"4 RT YYC-{apt}", q([FlightQuery(D.isoformat(), "YYC", apt), FlightQuery(D2.isoformat(), apt, "YYC")], trip="round-trip", max_stops=0))
    out = r1 if apt == "YVR" else run(f"4 OW YYC-{apt}", q([FlightQuery(D.isoformat(), "YYC", apt)], max_stops=0))
    back = run(f"4 OW {apt}-YYC", q([FlightQuery(D2.isoformat(), apt, "YYC")], max_stops=0))
    print(f"    {apt}: round-trip cheapest={cheapest(rt)} one-way sum={(cheapest(out) or 0) + (cheapest(back) or 0)}")

# 5. one-stop YYC->LAS; YYC->MSY with up to 2 stops (for a two-stop fixture)
r5 = run("5 YYC-LAS stops<=1", q([FlightQuery(D.isoformat(), "YYC", "LAS")], max_stops=1))
for it in [it for it in r5 or [] if nsegs(2)(it)][:2]:
    a, b = it[0][2]
    print(f"    via {a[6]}: arr {a[21]} {hm(a[10])} dep {b[20]} {hm(b[8])}")
dump(r5, "ff_one_stop.json", nsegs(2))
dump(run("5 YYC-MSY stops<=2", q([FlightQuery(D.isoformat(), "YYC", "MSY")], max_stops=2)), "ff_two_stop.json", nsegs(3))

# 6. YYC->MSY non-stop should be empty; one-stop should have results
run("6 YYC-MSY nonstop", q([FlightQuery(D.isoformat(), "YYC", "MSY")], max_stops=0))
run("6 YYC-MSY stops<=1", q([FlightQuery(D.isoformat(), "YYC", "MSY")], max_stops=1))
sys.exit(0)
