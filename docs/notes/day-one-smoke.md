# Day-one smoke test: fast-flights

Date: 2026-11-09, run from William's PC (residential IP). `fast-flights==3.1.0`, Python 3.12.13.
Probe dates: Friday 2026-12-04 out, Sunday 2026-12-06 back. Script: `scripts/smoke_fast_flights.py`.
About 60 requests over two runs, 4 s apart: no block, no error page.

## Headline findings

1. **Upstream parser bug: fast-flights 3.1.0 drops Google's "best flights" list.** Google's payload has
   two itinerary lists: `payload[2][0]` ("best") and `payload[3][0]` ("other"). The library parses only
   `[3][0]`. On YYC→YVR the best list held the three cheapest fares (499 for two) and the library
   reported 583 as the cheapest. `radar/flights.py` therefore calls `fetch_flights_html` from the
   library and parses both lists itself (same indices as upstream). The library's `get_flights` is
   not used.
2. **Prices are totals for all passengers.** YYC→YVR WS101: 1 adult 250, 2 adults 499.
3. **`carry_on_bags=1` works.** Flair YYC→YVR for two: 159 without, 245 with the bag flag
   (+$43 per person per leg). Google prices the carry-on itself, so the airline surcharge table is
   not needed while Google keeps doing this. Verified, not assumed.
4. **`exclude_basic_economy=True` removes Flair entirely and WestJet UltraBasic.** Cheapest YYC→YVR
   for two: 159 (no flags), 245 (bag only), 499 (no-basic only), 499 (both). The no-basic flag, not
   the bag, doubles the price. William's hard constraint keeps it on; see decisions.md D-03.
5. **`latest_arrival_hour` is not strict.** YVR→YYC with `latest_arrival_hour=16`: 4 of 13 results
   land after 16:00 or after midnight the next day (e.g. AC8074 23:10 → 01:38 Mon). The hard window
   check in `radar/itineraries.py` is what enforces the rule; Google's hour filters only trim results.
6. **Round trip vs one-way sum (information only; v1 sums one-ways):** YVR 966 vs 967 (same).
   LAS 1,778 vs 2,050: one-way sums run 15% above the round-trip price on that route.
7. **No non-stop:** YYC→MSY with `max_stops=0` returns an empty list (with the library's own parser
   it raised `TypeError: 'NoneType' object is not subscriptable`, not `FlightsNotFound`).
   `max_stops=1` returns 9 itineraries; `max_stops=2` returns 3-segment ones (fixture written).

## Object shapes (raw Google JSON, what `radar.flights.to_leg` parses)

One itinerary `it`:
- `it[0][0]`: airline code of the itinerary (`"WS"`, `"AC"`, or `"multi"` for mixed carriers)
- `it[0][1]`: airline names, e.g. `["WestJet", "Delta"]`
- `it[0][2]`: segments; `it[1][0][1]`: price (int, CAD, total for all passengers; may be missing)
- segment `s`: `s[3]` from code, `s[6]` to code, `s[8]` departure time, `s[10]` arrival time,
  `s[20]` departure date `[y, m, d]`, `s[21]` arrival date, `s[11]` duration (min),
  `s[17]` aircraft, `s[22]` `[carrier code, flight number, None, carrier name]`
- times omit zero parts: `[8]` is 08:00, `[None, 31]` is 00:31, `None` is 00:00
- times are local to each airport; a layover is the gap between one segment's arrival and the
  next one's departure, both local to the connecting airport, so naive subtraction is correct.
- Flight numbers *are* available at `s[22]` (the library's parser ignores them).
- The one-way payload carries no low/typical/high price label (`payload[7][0]` is the price-filter
  range). Google's label is not recoverable from these searches; history percentile replaces it.

## Price level vs the seeded bands (flag for William)

Realistic (carry-on, no basic) fares are far above the seeded bands: YVR round trip for two
966 → 483 per person vs the "bad" threshold of 190; LAS non-stop 2,050 → 1,025 per person vs 350.
One weekend, so not conclusive, but with these bands nothing may reach "amazing" in month one,
which would also leave the hotel check unexercised. The first full scans will show the distribution;
the weekly digest is where to retune (decisions.md D-04).

## GitHub Actions block test

See the section appended after Task 1 below.
