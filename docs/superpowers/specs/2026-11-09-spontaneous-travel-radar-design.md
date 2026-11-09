# Spontaneous Travel Radar: Design

Date: 2026-11-09
Owner: William Ebong (Calgary, YYC)
Status: design complete; build plan to follow in a separate session; build with Opus 5.5 starting 2026-11-10.
**v2 (2026-11-09):** the price model, the passes and the page changed; section 14 supersedes 7.3 to 7.5 and parts of 6 and 7.

## 1. Intent

William and a partner want to take short, spontaneous trips: one vacation day (or a stat holiday) turned into a ~2-day visit to a North American city, home with time to decompress before work. The system watches fares, lodging and context for about 20 cities and surfaces only the deals that would be crazy to pass up. It is not a general flight-search tool.

For the first month it runs in **learning mode**: it collects, scores and logs, but sends no alerts. William and Claude review weekly, tune the scoring, then switch alerts on.

## 2. Goals, non-goals, anti-goals

**Goals**

- Catch exceptional complete-trip deals (flights for two plus two nights) inside a strict time window, and present them with enough context to book in five minutes.
- Cost nothing extra to run. No paid APIs, no paid hosting.
- Use almost no Claude usage. Deterministic code does everything it can; Claude is invoked only when something exceptional is found, plus one short weekly digest during month one.
- Give William one shareable page he can check once a day.
- Build its own price history so "exceptional" becomes data-driven rather than guessed.

**Non-goals**

- Booking. The system links out; a human books.
- Flexible-date or long-trip search.
- Tracking cities outside the list, or trips that break the window rule.
- Airbnb scraping (breaks Airbnb's terms; Google Hotels' vacation-rental toggle covers most of it).
- Perfect fare accuracy. A good-enough signal that sends William to Google Flights is the product.

**Anti-goals** (failure even if it "works")

- Alerting more than a few times a month, or on "20% cheaper than usual" deals. Noise kills trust; William stops reading it.
- Flagging basic/ULCC headline fares that are not real once a carry-on is added.
- Burning Claude usage on a daily loop William never reads.
- Costing money by surprise (API overage, hosting upgrade).

## 3. Hard constraints

1. **Trip window** (the only hard filter, Section 4; since 2026-11-09 one rule per trip class, D-52). Day-off trips (Section 4) start at least 6 weeks out so both of you can get the time approved, and run to 16 weeks out. Weekend-only trips need no day off: leave Friday from 5:30pm through Saturday noon, home in Calgary by 4pm Sunday, non-stop only, 3 hours or less in the air, 3 to 42 days out, and they fire only when exceptional (amazing fare, score 88+, complete trip within 70% of the city's bar). Day-off rule: leave from 7:30pm the evening before Day 1 through the end of Day 1, home in Calgary by 4pm on the last day off. Since 2026-11-09 (D-50) a later Day-1 start is not filtered out: the time score charges for it, and a trip with under 10% of the window's possible waking hours is dropped (D-51).
2. **Two adults**, round trip from Calgary (YYC). Single tickets are useless.
3. **$0 new spend.** Free tiers and free hosting only. Nothing with a credit card on file.
4. **Claude usage is scarce.** Runs on William's Max plan but must be rare and short; William saves usage for coding. Target: at most 4 to 8 Claude runs per month, each on a cheap model where the task allows, each reading a pre-computed JSON summary rather than raw data.
5. Prices shown in **CAD**, taxes in, with a realistic carry-on allowance.

## 4. The trip window rule

Given a block of three consecutive days off, Day 1, Day 2, Day 3 (Day 3 is the last day off; work resumes Day 4):

- **Depart:** from 7:30pm Calgary time on the evening before Day 1, up to 11:59pm Calgary time on Day 1. Until 2026-11-09 this ended at noon; William softened it (D-50) because good Day-1 afternoon flights were never priced. A late start costs time-score points instead (Section 7).
- **Return:** land in Calgary from the evening of Day 2 (after about 5pm) until **4:00pm Calgary time on Day 3**. 4pm is the absolute latest, not the goal; earlier landings score higher.

Both bounds are evaluated in Calgary local time regardless of the destination's zone. An itinerary outside this window is discarded before scoring, and so is one with less than 10% of the window's best possible waking hours (D-51).

**Trip classes (D-52).** Day-off windows (the table below) are scanned with Day 1 from `dayoff_min_weeks` (default 6, set on the dashboard) to 10 weeks beyond that, basic fares excluded. Weekend windows (one per weekend, no day off, the rule in Section 3) are scanned 3 to 42 days out, basic fares allowed, for cities with `air_time_min` of 180 or less. Settings live in `config/scoring.yaml: trip_classes`.

**Window generation.** Day-off blocks come from weekends plus one vacation day, and from stat holidays:

| Pattern | Day 1..3 | Depart | Return |
|---|---|---|---|
| Friday off | Fri, Sat, Sun | Thu 7:30pm to Fri 11:59pm | Sat ~5pm to Sun 4pm |
| Monday off | Sat, Sun, Mon | Fri 7:30pm to Sat 11:59pm | Sun ~5pm to Mon 4pm |
| Stat on Fri or Mon | same as above, no vacation day used | | |
| Stat on Thu or Tue | 4-day block with one vacation day (Thu+Fri+Sat+Sun, or Sat+Sun+Mon+Tue) | 7:30pm the evening before Day 1 to 11:59pm Day 1 | evening of Day 3 to 4pm Day 4 |

The general form: for a block of N consecutive days off, depart from 7:30pm the evening before Day 1 to 11:59pm Day 1; return from the evening of Day N−1 to 4pm Day N. Hotel nights are counted from the itinerary, not the window: a Thursday-evening arrival with a Sunday departure is 3 nights (an arrival before 5am books the previous night). The time-there score is normalised to the best possible for that window's length (about 49.5 waking hours for a 3-day block). The 3-day windows embedded in a 4-day block are generated too; they are just other windows, and a cheaper shorter trip can outscore the longer one.

Stat holidays are hard-coded in `config/holidays.yaml` for the current and next year, with a selectable calendar: `alberta` (default), `ontario`, or `federal`. William's employer is Ontario-based, so this is an open question (Section 11). The window generator looks 3 to 45 days ahead. Both the Friday-off and Monday-off pattern are generated for every weekend; they share scan dates (Thu, Fri, Sat out; Sat, Sun, Mon back), so one set of date queries covers both.

**Connections.** Non-stop and same-plane "direct" flights are preferred. One connection is allowed but is not special-cased in the rule; it simply loses points on time-on-ground and convenience (Section 7), so it must be much cheaper to surface. Two or more connections are discarded.

## 5. Cities

Twenty cities, chosen for "worth it in two days" first and travel friction second. Each has a fixed **city rank** (0 to 10, how good it is in a vacuum), fixed logistics facts, and a seasonal note. All of these live in `config/cities.yaml` and William can edit them.

### Tier 1: non-stop from YYC

| City | Airports | Air time | Rank | Notes |
|---|---|---|---|---|
| New York | EWR (non-stop), JFK/LGA via connection | 4.5h | 10 | +2h zone; Thursday-night departures matter. NJ Transit/PATH from EWR. |
| Chicago | ORD, MDW | 3.3h | 9 | Blue Line from ORD. +1h zone. |
| Montreal | YUL | 4.3h | 9 | Cheapest big-city hotels; 747 bus / REM. +2h. |
| San Francisco | SFO (OAK via connection) | 2.7h | 8 | BART. Hotels expensive, fares often not. |
| Vancouver | YVR | 1.5h | 8 | Canada Line. Zero friction. |
| Seattle | SEA | 1.6h | 8 | Link light rail. |
| Las Vegas | LAS | 2.6h | 7 | Cheapest fares from YYC. Weekend hotels spike, resort fees $35 to $57/night. |
| Toronto | YYZ (YTZ via Porter) | 3.9h | 8 | UP Express. +2h. |
| Portland | PDX | 1.8h | 7 | MAX light rail. No sales tax. Check route is year-round. |
| Denver | DEN | 2.3h | 7 | A Line train. Hotels cheap on weekends. |
| San Diego | SAN | 3.2h | 8 | Airport 10 min from downtown. Likely seasonal. |
| Los Angeles | LAX (BUR via connection) | 3.2h | 7 | Pick one base: Santa Monica, DTLA, Silver Lake. Car otherwise. |
| Nashville | BNA | 3.5h | 7 | WestJet, likely seasonal. |
| Austin | AUS | 3.5h | 7 | WestJet, likely seasonal. |
| Palm Springs | PSP | 2.7h | 6 | Winter only (roughly Nov to Apr). The decompress trip. |

### Tier 2: one connection, exceptional fares only

| City | Airports | Door-to-door | Rank | Notes |
|---|---|---|---|---|
| New Orleans | MSY | ~7h | 9 | Food and music. |
| Mexico City | MEX, NLU | ~7h | 9 | Best food city on the continent; cheap on the ground. Central time, no DST. |
| Quebec City | YQB | ~6h | 8 | Check for a seasonal non-stop. |
| Boston | BOS | ~6.5h | 8 | +2h. Silver Line from airport. |
| Washington DC | DCA (IAD) | ~6.5h | 8 | Metro from DCA. Free museums. |

Bench (not tracked, swap in by editing config): Miami, Santa Fe, Savannah/Charleston, Salt Lake City, Victoria, Kelowna, Ottawa, Minneapolis, Phoenix.

Route seasonality changes yearly. The collector does not hard-code which routes exist; it queries every city every scan and records "no non-stop found" as data. Tier only affects the score, not what is queried.

## 6. Architecture

Two tiers, split so the expensive thing (Claude) runs only when the cheap thing (a script) finds something.

```
                 ┌──────────────────────────────────────────────┐
  daily cron     │  COLLECTOR  (Python, no LLM)                  │
  ──────────────▶│  fast-flights → quotes → window filter →      │
                 │  realistic price → score → JSONL + JSON       │
                 │  + Ticketmaster events + Open-Meteo weather   │
                 │  + on candidate hit: Google Hotels check      │
                 │    (SerpApi free tier, hard-capped) →         │
                 │    re-score → hits/<id>.json + templated .md  │
                 └───────┬──────────────────────────┬────────────┘
                         │ commit data/*, hits/*    │ live hit committed
                         ▼                          ▼  (GitHub webhook event)
                 ┌───────────────┐          ┌────────────────────────────┐
                 │  DASHBOARD    │          │  CLAUDE ROUTINE (cheap     │
                 │  static page  │          │  model): read hit JSON,    │
                 │  GitHub Pages │          │  write a short judgment    │
                 └───────────────┘          │  brief, email William      │
                                            └────────────────────────────┘
```

Everything the dashboard needs is produced by the collector; Claude adds judgment and delivery only, so the system is complete even if the routine never fires.

### 6.1 Tier 0: configuration (hard-coded, editable)

- `config/cities.yaml`: the 20 cities, airports, rank, tier, airport-to-core minutes and cost, car-needed flag, 1 to 3 target neighbourhoods, seasonal months, monthly climate normals (high/low/rain days) for weather scoring beyond the 16-day forecast.
- `config/holidays.yaml`: Alberta + federal stats for 2026 and 2027.
- `config/scoring.yaml`: weights, bands, thresholds (Section 7). Tuned during month one.
- `config/airlines.yaml`: carry-on surcharge table for ULCC/basic fares (Section 7.2).

### 6.2 Tier 1: collector (deterministic, free)

> v2: Ticketmaster is gone, the hotel check is pass 2 (hotels and rentals, three candidates a scan) and pass 3 is the daily routine's; see section 14.

- Python, `fast-flights` v3 (reads Google Flights; verified API: `create_query(flights=[FlightQuery(date, from_airport, to_airport, earliest_departure_hour, latest_departure_hour, earliest_arrival_hour, latest_arrival_hour, max_stops)], trip, passengers=Passengers(adults=2), currency="CAD", carry_on_bags=1, exclude_basic_economy=True)` then `get_flights(query)` returning itineraries with per-segment airports, dates, times, airline codes, duration and price). `carry_on_bags=1` makes Google price the fare with a carry-on, which is the "realistic price" for free. Its free fetcher does **not** expose Google's low/typical/high label (only its paid data-source integration does), so the cold-start baseline is the absolute bands plus our own history; recovering the label from the raw payload is an optional spike, never a dependency. Risk: Google bot detection. See 6.5.
- One scan per day (William's call; cadence is a config knob). Each scan: for every city, every weekend in range, query the shared date set (out Thu/Fri/Sat, back Sat/Sun/Mon). Builder decides between round-trip queries and one-way sums after testing what `fast-flights` returns; the design requires per-segment departure/arrival times, airline, stop count, and total price for 2 adults in CAD.
- Request budget: about 500 to 900 Google requests per scan. Spread them out (a few seconds between requests, randomized) and scan nearer weekends daily, farther ones every second day, if blocks appear.
- Every quote is appended to `data/history/YYYY-MM-DD.jsonl` (one line per quote, committed), so history accumulates from day one and git stores small text deltas rather than a new binary blob per scan. SQLite, if used at all, is rebuilt inside the run from the JSONL and never committed. The latest scan is exported to `data/latest.json` for the dashboard.
- Events: Ticketmaster Discovery API (free, 5,000 calls/day), one call per city per window, cached per day. Weather: Open-Meteo forecast (free, 16 days), one call per city per day.
- Scoring (Section 7) runs here. A quote that passes the flight-side threshold becomes a **candidate hit**. For candidates only, the collector runs the **hotel check**: Google Hotels via SerpApi's free tier (key in an Actions secret; hard cap in code of 3 searches per candidate and 60 per month, so the 250/month free quota is never exceeded), 2 nights, 2 adults, target neighbourhoods, 3.5-star and up, rating 8+/4.3+, free cancellation, total with taxes and fees. It keeps the 3 best options, assigns the hotel band (7.5), re-scores with real lodging, and writes `hits/<date>-<city>.json` plus a deterministic templated `hits/<date>-<city>.md` brief (dates, flights with times and airline, realistic price for two, hotels and totals, airport-to-core, events, weather, time-on-ground, score, Google Flights and Google Hotels links). During month one these go to `hits/dry-run/` and nothing fires; this also means the hotel check gets exercised on real candidates before alerts go live. After month one a live hit is committed to `hits/`, which fires the Claude routine via a GitHub webhook trigger.
- Weekly, the collector also writes `data/weekly-summary.json` (would-have-fired list, band distribution per city, Google-label agreement, request health) for the digest routine.
- Hosting: **GitHub Actions cron, first choice** (free, PC-independent). **Fallback: Windows Task Scheduler on William's PC** if Google blocks GitHub's IP ranges; residential IPs at this rate are rarely blocked. Day one of the build includes a block test from both. Whichever host runs the collector, it commits results to the same repo.

### 6.3 Dashboard (static, free, zero Claude)

> v2 page order: hits, passed (70+), every city, notes; section 14.4.

- A single static HTML page served by GitHub Pages from the repo, reading `data/latest.json`, `data/history/*.json` and `hits/`. Shareable URL, checked once a day.
- Sections: (1) **Best right now**, one row per city: cheapest realistic fare for two in any window, dates, our band, history percentile once available, worth-it score, a 30-day sparkline. (2) **Hits**, each rendering its templated brief from `hits/`. (3) **Would-have-fired** list during month one, from `hits/dry-run/`. (4) **Weekly digests**, from `data/digests/<date>.md`. (5) **Health**: last scan time, request count, block/error status, SerpApi searches used this month, per-city "no non-stop found" flags.
- Plain and readable on a phone. Charts follow the `dataviz` skill. This is a tool, not a showpiece.
- GitHub Pages on a free account requires a **public repo**. The repo holds fare data and code only; API keys live in Actions secrets. If William prefers private, the fallback is Netlify's free tier (connects to private GitHub repos) or a Claude Artifact republished by the routine (costs usage). Decision below.

### 6.4 Tier 2: Claude routine (rare, cheap)

- A Claude cloud routine, fired by a GitHub webhook trigger when a file lands in `hits/`. Verified available: routines accept cron schedules and GitHub-event webhook triggers. Fallback if webhook wiring fails: a daily 7am routine that exits immediately when `hits/` is empty.
- Model: Haiku or Sonnet. The routine reads one small JSON (`hits/<id>.json`, which already contains flights, hotel options, events, weather and the score) and does only what needs judgment:
  1. **Judgment brief**: 8 to 10 lines. Is this actually worth booking, what to watch (late check-in, resort fees, an event that will make the city loud or expensive), which of the three hotels to take and why, anything that smells wrong (basic fare, bad times). It does not re-fetch data or browse.
  2. **Deliver**: email the templated brief plus its judgment to William through the routine's Gmail connector. Writing back to the repo is optional: if the routine can commit, it appends a "Claude's take" section to `hits/<id>.md`; if not, the email is the only Claude output and the dashboard still shows the templated brief. The build verifies which it is on day one and records the answer.
- Month one: no hit routine. One **weekly digest** routine (Monday 7am) reads `data/weekly-summary.json` and writes a 15-line review for William: what would have fired, whether the bands look right, what to tune. It is committed to `data/digests/<date>.md` (shown on the dashboard) if the routine can commit, otherwise emailed. Four runs total.

### 6.5 Risks and mitigations

| Risk | Mitigation |
|---|---|
| Google blocks `fast-flights` | Low, randomized request rate; run from PC residential IP; cache aggressively; degrade to fewer windows rather than fail. Last resort: Travelpayouts free cached-fare API as a coarse signal (1 adult, coverage of YYC unproven). |
| `fast-flights` breaks on a Google layout change (maintainer "really busy") | Pin the version; health panel shows parse failures; keep a small fixture test so breakage is obvious. Fork-and-patch is acceptable. |
| No real historical baseline at start | Two signals: absolute CAD bands seeded from research (Section 7.3) and our own history once it exists (percentile of the last 90 days per route). Month one is the warm-up. Google's low/typical/high label is not available from the free fetcher; if the builder can extract it from the raw payload cheaply it is recorded as a third signal. |
| ULCC headline fares look exceptional | Carry-on surcharge table; never alert on a fare whose realistic price is not in band. |
| GitHub Actions free minutes | ~5 to 15 min/day is well under the 2,000/month private cap, and unlimited for public repos. |
| SerpApi free tier exhaustion (250/month) | Hotel checks only on hits; hard cap in code; the routine says "hotel check skipped" rather than failing. |
| Claude usage creep | Routine runs only on hits plus 4 digests; compact JSON input; cheap model; no browsing in the routine. |

## 7. Scoring

> Superseded in part by section 14 (v2): no flight or hotel bands, no per-city bar, no events factor, basic fares allowed. The time, convenience and weather measures below still apply.

### 7.1 Worth-it score (0 to 100)

| Factor | Weight | Measure |
|---|---|---|
| Price | 40 | Realistic total for two (flights + estimated 2 nights lodging + airport transfers) against the route's band (7.3) and history percentile. Past the bad line the points go negative, -10 per bad-line width down to -40, so a cheaper all-bad trip still beats a dearer one (D-56). |
| Time there | 15 | Waking hours on the ground: destination arrival + 1h to departure − 2h, minus 8h per night, computed in local times. Scaled against the best possible for that window (49.5h for a 3-day block): 0 points at 10% of it, full points at 70% (real trips top out near 70-75% once flight time is counted), linear between; under 10% the trip is dropped. Anchors in `config/scoring.yaml: time_curve` (D-51). |
| Convenience | 10 | Non-stop 10, direct 9, one connection under 2.5h 5, longer 2. Minus for airport-to-core over 45 min, car needed, red-eye arrivals after midnight. |
| City rank | 15 | Fixed per city from config. |
| Things on | 10 | Ticketmaster events in the window, weighted by venue size. Large events raise the score but set a "hotel spike" flag. |
| Weather | 10 | Open-Meteo forecast inside 16 days; climate normals beyond. Palm Springs in July scores near zero; Montreal in January scores low unless an event carries it. |

Weights live in `config/scoring.yaml`. During month one they are tuned weekly from the "would-have-fired" list.

Until the hotel check runs, lodging in the price factor is an estimate: the city's "Good" hotel band midpoint (7.5) divided by 2 nights, times the itinerary's hotel nights, converted to CAD. The hotel check on candidates replaces it with real numbers and re-scores; only then are the three hit gates (score, per-city bar, re-alert rule) decided, and only one itinerary per city-window can become a hit.

**Currency.** Flights come from Google in CAD. US hotel bands are USD. A single `usd_cad` rate in `config/scoring.yaml` (seeded at 1.40, refreshed by hand or by the builder from a free rate source if trivial) converts everything to CAD for scoring and display. This is the only place currency conversion happens.

### 7.2 Realistic price

- Fare for 2 adults, taxes in, CAD (Google Flights currency parameter), queried with `carry_on_bags=1` and `exclude_basic_economy=True` so Google itself prices the carry-on and drops basic fares.
- Fallback only, if the smoke test shows Google ignores the bag parameter for an airline: carry-on surcharge per person, round trip, from `config/airlines.yaml` (Flair +$110, Spirit/Frontier +$120), applied by airline code and noted on the quote.
- Airport transfers: 2 people × 2 ways from config.

### 7.3 Flight bands (per person, round trip, realistic price, CAD)

Seeded from research into Kayak 12-month averages, YYC Deals posts and Going/Hopper methodology (percentile of history is the long-term signal; absolute bands are the cold-start signal).

| Band | % below route's typical | YVR | SEA/PDX | Medium (LAS, LAX, SFO, SAN, DEN, PSP) | YYZ | YUL/ORD/BNA/AUS | NYC + Tier 2 |
|---|---|---|---|---|---|---|---|
| Bad | < 15% | > 190 | > 330 | > 350 | > 300 | > 400 | > 500 |
| Average | 15 to 25% | 150 to 190 | 260 to 330 | 280 to 350 | 240 to 300 | 320 to 400 | 400 to 500 |
| Good | 25 to 40% | 120 to 150 | 200 to 260 | 220 to 280 | 190 to 240 | 250 to 320 | 320 to 400 |
| Amazing | 40%+ | < 120 | < 200 | < 220 | < 190 | < 250 | < 320 |

Context from research: deal communities treat 10% as noise, 20 to 25% as "book if dates work", 30 to 40% as a postable deal, 45%+ as "book now". YYC Deals only posts 30%+ below typical best, and adds $100 to $120 to ULCC fares before comparing.

### 7.4 "Exceptional" (what fires an alert)

All three must hold, tuned in month one:

1. Flight band **Amazing** (or Good with our own history percentile ≤ 10% once 14+ days of history exist for the route).
2. Worth-it score **≥ 80**.
3. Complete trip for two (realistic flights + lodging from the hotel check, or the estimate if the check was skipped + airport transfers) under a **per-city absolute bar** in `config/cities.yaml`. The bar is seeded from the bands so it is reachable: 2 × the city's "Amazing" flight threshold + the "Good" hotel band midpoint in CAD + transfers, rounded up to the nearest $50. Example seeds: Vancouver ~$550, Las Vegas ~$1,000, Chicago ~$1,100, New York ~$1,450. William can lower any of them to make a city harder to trigger.

Expected rate once tuned: a few alerts a month, not a few a week. Re-alert on the same city-window only if the price drops another 15%.

### 7.5 Hotel bands (2 nights, 1 room, fees in, pre-tax; USD in the US, CAD in Canada)

Bands are for 2 nights; a 3-night window scales them by 1.5.

| Band | Cheap (LAS Sun to Thu, DEN, YUL, SEA, PDX, YQB) | Mid (ORD, YVR, YYZ, BOS, DC, BNA, AUS, MEX, MSY, LAX, SAN, PSP, LAS Fri to Sat) | Expensive (NYC, SF, LAS event weekends, YVR Jul to Aug) |
|---|---|---|---|
| Bad | > 400 | > 600 | > 900 |
| Average | 280 to 400 | 440 to 600 | 650 to 900 |
| Good | 200 to 280 | 320 to 440 | 450 to 650 |
| Amazing | < 200 | < 320 | < 450 |

Hotel floor: 3.5 stars and up, guest rating 8.0+/10 or 4.3+/5, free cancellation, in or next to a target neighbourhood, check-in available after 10pm when the itinerary lands late, check-out noon or later preferred.

## 8. Month one: learning run

- Weeks 1 to 4: collector runs daily, alerts off, hits written to `hits/dry-run/`.
- Each Monday the digest routine summarizes: how many would-have-fired, which cities, band distribution, Google-label agreement with our bands, request health. William and Claude adjust `config/scoring.yaml` in a short session.
- Exit criteria to turn alerts on: 21+ days of history for every city; false positives in the dry-run list reviewed; bands and the per-city bars adjusted; the hotel check has run on at least three dry-run candidates within the SerpApi free quota and its totals verified by hand against Google Hotels once.
- Historical seeding: the research baselines in 7.3 stand in for history until our own exists. If the builder finds a free source of route price history (Google's price-insights appear in some scraped responses), it is recorded alongside, never trusted alone.

## 9. Repo layout (proposal; builder may adjust)

```
spontaneous-travel/
  README.md                  what it is, how to run, where the dashboard is
  docs/superpowers/specs/    this design
  config/                    cities, holidays, scoring, airlines (YAML)
  radar/                     python package: windows.py, flights.py, score.py,
                             events.py, weather.py, store.py, export.py, main.py
  tests/                     one small check per non-trivial module (fixtures, no network)
  data/                      latest.json, history/YYYY-MM-DD.jsonl, weekly-summary.json, digests/
  hits/                      live hits (<id>.json + templated <id>.md brief), dry-run/
  site/                      index.html + minimal js/css for GitHub Pages
  routine/                   PROMPT-hit.md, PROMPT-weekly.md, setup notes
  .github/workflows/         scan.yml (cron), pages.yml
```

Per William's standing rules this is a new app build, so the build session runs the Spec Kit init sequence from his `CLAUDE.md` before coding, and uses the speckit-* skills (constitution once, then specify, plan, tasks, implement, converge). Ponytail applies: stdlib and the already-chosen libraries first, no abstractions for one use, one small runnable check per non-trivial module.

## 10. Decisions made in this design (William can flip any of these)

| Decision | Choice | Why |
|---|---|---|
| Collector host | GitHub Actions first, PC Task Scheduler fallback | Free, PC-independent; fallback covers Google blocking datacenter IPs. |
| Dashboard | GitHub Pages static page, repo public | Zero Claude usage, shareable, free. Data is fares only; keys in secrets. |
| Scan cadence | Once daily (~6am MT), configurable | William's call; fine for learning mode. |
| Flight data | `fast-flights` (Google Flights) | Only free source with 2-adult round trips and stop data. |
| Lodging in the collector | Estimated from bands; real Google Hotels check (SerpApi free tier, hard-capped) only on candidate hits, done by the collector not by Claude | No free bulk hotel source; deterministic code does everything it can; the check gets exercised during month one. |
| History storage | Append-only JSONL per day, committed; no SQLite in the repo | Text deltas stay small in a public repo; a binary DB per scan would bloat history forever. |
| Currency | Single `usd_cad` in config (seeded 1.40) | Flights already in CAD; hotel bands in USD need one rate; no API dependency. |
| Complete-trip bar | Per city, derived from the bands | A per-rank bar made NYC, SF and Vegas unreachable even on Amazing fares. |
| Airbnb | Not scraped | Terms of service; Google Hotels vacation-rental toggle instead. |
| Claude trigger | GitHub webhook → cloud routine; cron fallback | Routine fires only on hits. |
| Notification | Dashboard first; email on live hits via the routine's Gmail connector | William checks the page daily; email only for the rare hit. |
| Routine model | Haiku or Sonnet | Judgment tasks are small; saves usage. |
| Lookahead | 3 to 45 days | Spontaneous but bookable. |
| Flight currency | CAD from Google Flights directly | No conversion on the flight side. |

## 11. Open questions, defaulted

Answered by default so the build can start; William can change any of them in the morning.

1. **Public repo acceptable?** Default yes (needed for free GitHub Pages).
2. **Email alerts to williamebong@gmail.com on live hits?** Default yes, hits only, never digests.
3. **Any three consecutive days off, or only weekend-anchored?** Default: weekend-anchored plus stat holidays, as described.
4. **Minimum lead time?** Default 3 days.
5. **Hotel floor?** Default 3.5 stars, rating 8+/4.3+, free cancellation.
6. **Neighbourhoods per city?** Builder seeds well-known central areas in `config/cities.yaml`; William edits.
7. **Scan from PC or GitHub?** Decided by the day-one block test.
8. **Which stat-holiday calendar does your employer observe?** Default `alberta` (Family Day, Heritage Day, Remembrance Day). If ProServeIT follows Ontario (Boxing Day, no Heritage Day, no Remembrance Day), switch `calendar: ontario` in `config/holidays.yaml`. A wrong calendar only creates or misses a window; nothing breaks.

## 12. Left to the builder

- Verify `fast-flights` round-trip output shape and pick round-trip vs one-way-sum queries (the free fetcher returns outbound options with a round-trip price; return-leg times need their own one-way query).
- Request pacing and caching strategy; the daily request budget.
- Exact SQLite schema and JSON export shapes.
- Dashboard implementation details (vanilla HTML/JS, no framework unless it earns it).
- Ticketmaster venue-size weighting; Open-Meteo variables used for the weather score.
- Webhook trigger wiring for the Claude routine, and the fallback cron.
- Test fixtures (recorded Google Flights responses) so tests need no network.
- Seeding climate normals and neighbourhood lists in config.

## 13. Research sources

Data-source scan (2026-11-09): Amadeus Self-Service decommissioned July 2026; SerpApi Google Flights/Hotels pricing and free tier; `fast-flights` v3.1.0 (github.com/AWeirdDev/flights); Travelpayouts Data API docs; Ticketmaster Discovery API limits; Open-Meteo pricing; Airbnb ToS 11.1; Booking/Expedia partner-only access.

Deal calibration (2026-11-09): Going deal grades (standard deviations below route average; Top-15% ≈ −2.6 SD); Hopper "better than 95% of prices seen"; Kayak typical range (good deal = below lower bound, 19 to 28% under the 12-month average on YYC routes); Google Flights low/typical/high; Dollar Flight Club bottom-25%; YYC Deals posting floor (30%+ below typical best, ULCC +$100 to $120); Kayak 12-month YYC averages and YYC Deals posted fares 2022 to 2026 for YVR, SEA, LAS, LAX, SFO, DEN, PSP/PHX, YYZ, YUL, ORD, NYC, Mexico sun; 2025 hotel ADRs for NYC, Chicago, SF, Las Vegas, Vancouver, Toronto, Montreal, Seattle, Denver; STR weekday/weekend premiums; HotelTonight 16 to 17% typical same-day discount.

## 14. v2 deal model (2026-11-09)

Day one showed the v1 price model judged trips against weekends that do not exist (seeded bands, fixed per-city
bars, Standard-only fares) and counted crowds as events. William's v2 decisions are final (`BUILD-PLAN-v2.md`);
build decisions D-57 to D-72; spec `specs/002-deal-model-and-passes/`. This section replaces 7.3 to 7.5, the
events factor in 7.1, the basic-fare exclusion in 7.2, the Ticketmaster call in 6.2, the would-have-fired list in
6.3, and the routine's role in 6.4.

### 14.1 Route ladders

`config/references.yaml` gives every city a flights ladder (typical, good, exceptional; CAD per person, round
trip, carry-on, any fare family) from `docs/research/2026-11-09-fare-references.md`, and a room ladder per season
(winter = check-in Nov to Mar) per night before tax in the city's hotel currency, from Google Hotels
(`scripts/room_references.py`, D-68) or, for two city-seasons, the old tiers as estimates. Hotel tax is a factor
per country, Vancouver 1.185 from Google's own totals. Fares include AC and WestJet Basic and Flair, with the bag
priced in (D-57).

### 14.2 One price term

Typical trip T = 2 x typical fare + nights x typical room x tax + transfers (CAD). share = complete trip / T.
Price points (weight 45): 45 at share 0.60 or less, 25 at 0.75, 0 at 1.00, -10 at 1.30, straight lines, and the
same slope past 1.30 down to -100 (D-59). The other weights: time 20, convenience 10, city 15, weather 10, with the
7.1 measures. A trip's ladder label (exceptional, good, typical, above) comes from its fare per person alone and
is shown, not scored. No budget anywhere in scoring; an optional overall cap (`cap_cad`, off) can block a hit.

### 14.3 Three passes

| Pass | Who | What | Cost |
|---|---|---|---|
| 1 | collector, every trip | score with lodging at the season's good room rate (D-58) | free |
| 2 | collector, at most 3 candidates a scan | Google Hotels (4-5 star, 4.3+) and vacation rentals within 6 km of the centre (3 to 6 km = fringe, -3 convenience); best option by score; rescore the same price term | 2 SerpApi lookups each, cap 200 a month |
| 3 | `radar-daily` (Opus), at most 3 a day | what is on for those dates against `config/interests.yaml` (uniqueness x fit x affordability, up to +10), Airbnb by a Sonnet subagent, then `radar.main finalize` | candidates only, cached 7 days |

Candidate: fare at or under the route's good and pass-1 score 70+ (per class). Hit: final score 80+ (per class).
A city-window checked in the last 7 days is not checked again unless its fare drops 15% (D-66). A hit needs real
lodging, from pass 2 or a concrete Airbnb total for the exact dates (D-73). A candidate that
cannot reach the hit line even with 10 what's-on points is dropped after pass 2 (D-67). Files: `hits/candidates/`,
then `hits/dry-run/` (learning-run hit), `hits/` (live hit) or `hits/near-miss/` (D-69).

### 14.4 The two classes on the page

The dashboard leads with hits, then every trip that scored 70+ and the pass it reached, then every city's best
deal with its ladder, then the daily note. Hits and Passed list "No day off needed" first, then "Needs a day off".
Weekend trips carry a gold border and gold label; day-off trips stay neutral; the label is always printed (D-72).
The Settings panel has a switch and a hit line per class, read-only ladders and the optional cap.
