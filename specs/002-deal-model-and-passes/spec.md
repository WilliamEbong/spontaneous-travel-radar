# Spec: Deal model v2 and three passes

Feature directory `specs/002-deal-model-and-passes/` (the name the build plan gives; `002-trip-classes`
already uses the number). Source: `BUILD-PLAN-v2.md` (its "What William decided" section is final),
`docs/research/2026-11-09-fare-references.md`. Base design:
`docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md`.

## Overview

Day one showed the v1 price model was wrong: a seeded "bad" line zeroed the price score for every
real fare, fixed per-city bars described weekends that do not exist, Standard-only fares hid the Basic
fares William actually flies, and Ticketmaster counts measured crowds. v2 judges every trip against
what its own route normally costs, prices the complete trip for two, and looks closer only at the
few trips that are already exceptional: pass 1 scores everything for free, pass 2 finds real lodging
for at most three candidates a day, pass 3 (the daily routine) researches what is on. Quiet is the
correct outcome on most days.

## User scenarios

- **US1 (P1) Relative price.** William sees each trip judged against its route's ladder
  (typical / good / exceptional), so a $200 Vancouver fare reads "good, not exceptional" and a $450
  Toronto fare is not "bad" just because a seeded line said so.
  *Test:* the Vancouver worked example scores as the research doc's ladder says; among two pricey
  trips in one window the cheaper wins.
- **US2 (P1) Real fares.** Fares include AC Basic, WestJet Basic and Flair with a carry-on priced in,
  for both trip classes. *Test:* a fresh YYC-YVR fetch with basic fares allowed shows Flair and a
  cheaper WestJet fare than the Standard-only fetch.
- **US3 (P1) Candidates get a closer look.** A trip whose flights are at or under the route's `good`
  and whose pass-1 score is 70+ becomes a candidate; up to three a day get a Google Hotels and a
  vacation-rentals lookup within about 20 minutes of the centre, and are rescored on the real total.
  *Test:* fixture lookups; a central hotel at $650 beats a fringe rental at $550 when price saturates.
- **US4 (P1) What is on.** The daily routine researches the candidate's dates against William's
  interests and adds up to 10 points; 80+ is a hit. In the learning run nothing is emailed; hits and
  near misses show on the page. *Test:* `radar.main finalize` on a fixture research file.
- **US5 (P2) The page.** The dashboard leads with hits, then every trip that scored 70+ and how far
  it got, then each city's best deal with its ladder; the two trip classes stay visibly apart.
  *Test:* Playwright, four data states, 375 px and 1280 px, light and dark, clean console.
- **US6 (P2) Settings.** Per-class switch and hit threshold, an optional overall cap (off), the
  ladders read-only. *Test:* Playwright with a mocked GitHub API.
- **US7 (P3) Room references.** 19 cities get winter and summer room ladders from Google Hotels.
  *Test:* `config/references.yaml` sources say `google-hotels`, counter recorded.

## Functional requirements

- **FR-301** `config/references.yaml`: per city `flights {typical, good, exceptional}` (CAD per
  person, round trip, carry-on), `rooms {winter, summer}` each `{typical, good, exceptional, source}`
  per night pre-tax in the city's hotel currency, `confidence` (high|medium|low), `nonstop`
  (year-round|seasonal|none). The loader fails on a missing city or exceptional < good < typical not
  holding.
- **FR-302** Typical trip T = 2 x flights.typical + nights x rooms[season].typical x hotel tax (in
  CAD) + 4 x transfer. Season is winter for check-in months Nov to Mar. `share` = complete trip /
  T. Price points (weight 45): 45 at share <= 0.60, 25 at 0.75, 0 at 1.00, -10 at 1.30, straight
  lines between, the same slope past 1.30 down to a floor of -40.
- **FR-303** Hotel tax per city: `hotel_tax` in `cities.yaml` where set (Vancouver 1.185), else
  1.15 CA, 1.16 US, 1.19 MX.
- **FR-304** Weights `{price: 45, time: 20, convenience: 10, city: 15, weather: 10}`. No events
  component, no flight or hotel bands, no per-city bar in scoring or gates. An optional overall
  `cap_cad` (null = off) can block a hit whose complete trip is over it.
- **FR-305** Ladder label per trip from flights per person: `exceptional`, `good`, `typical`,
  `above`.
- **FR-306** Basic fares allowed in both classes (`exclude_basic_economy` false), carry-on priced.
- **FR-307** Ticketmaster removed from code, workflow, tests and the `.env` example.
- **FR-308** Candidate = flights per person <= route `good` and pass-1 score >= the class's
  `candidate_threshold` (70). Per class in `trip_classes`: `enabled`, `candidate_threshold`,
  `hit_threshold` (80). Weekend hard rules (non-stop, 3 h or less) stay.
- **FR-309** History rows and `latest.json` rows carry `ladder`, `share`, `pass` (1|2|3) and
  `final_score` (null until pass 3).
- **FR-310** Pass 2 (collector), at most 3 candidates a scan, highest pass-1 score first: one Google
  Hotels lookup (4 to 5 star, rating 4.3+) and one vacation-rentals lookup (rating 4.3+), the stay's
  dates, 2 adults, query text in the city's first neighbourhood; options more than 6 km from the
  city centre are discarded, 3 to 6 km are "fringe" (convenience -3). Each option is scored on the
  real total; the best score wins (then the lower total). Google's `deal` text is kept.
- **FR-311** SerpApi self-cap 200 a month, counted before each call, errors not retried, a skipped
  check recorded as `quota`, `no-key` or `error`.
- **FR-312** Pass-2 output `hits/candidates/<id>.json` and `.md`: pass-1 and pass-2 breakdowns, the
  options with links, `status: awaiting_pass3` (or `dropped` with a reason when even 10 what's-on
  points cannot reach the hit line).
- **FR-313** Pass 3 (`radar-daily`): Airbnb check by a Sonnet subagent (a price counts only from a
  concrete listing total with a link), research of what is on against `config/interests.yaml`,
  scored `uniqueness (0-3) x fit (0-1) x affordability`, capped at 10, cached 7 days in
  `data/research/<city>-<window>.json`. `final = pass-2 score + events`; hit at the class's
  `hit_threshold`. Written by `python -m radar.main finalize` to `hits/dry-run/` (learning-run
  hit), `hits/` (live hit) or `hits/near-miss/`.
- **FR-314** `config/interests.yaml` validated by the loader.
- **FR-315** Dashboard order: Hits (with the brief), Passed (every 70+ trip with its stage), Every
  city (best deal by score, ladder label, "typical for this route $X, exceptional under $Y", class
  label; expand: every weekend of both classes by score, price history), daily note; health and
  settings as before. "Would have fired" removed. Hits and Passed split "No day off needed" then
  "Needs a day off" with an accent per class.
- **FR-316** Settings: no per-city bar; read-only ladder per city; per-class switch and hit
  threshold; overall cap (off by default).
- **FR-317** `scripts/room_references.py` fills `rooms` for the 19 unresearched cities (Jan and Jul
  2027 lookups, median of the ten cheapest acceptable, good 0.75x, exceptional 0.57x, rounded to $5).
- **FR-318** Google Flights requests per scan stay at or under 688 planned; no new dependencies.

## Success criteria (the build plan's acceptance checks)

1. Vancouver worked example within 2 points of the research ladder (`$650` 83, exceptional 90).
2. Two above-typical trips in one window: the cheaper wins.
3. Basic fares present in a fresh YYC-YVR fixture.
4. No Ticketmaster reference in code, workflow or tests.
5. Flights at `good`, score 69: not a candidate; score 70: candidate.
6. Pass-2 fixture: central hotel $650 beats fringe rental $550 by score; both listed.
7. SerpApi cap honoured in a simulated month (no lookup past 200).
8. Dashboard: three sections in order, class grouping right, four data states, both widths and
   themes, clean console.
9. Offline scan writes `ladder`, `share`, `pass`, `final_score` on every row.
10. Dry-run query build plans at most 688 queries a day.

## Clarifications (answered from the plan, 2026-11-09)

- Q: Lodging estimate in pass 1? A: the season's `good` room rate (an optimistic placeholder that
  pass 2 replaces). With `typical`, an exceptional Vancouver fare in January scores 62 and no trip
  would ever reach pass 2.
- Q: Past share 1.30, flat or falling? A: falling at the same slope to -40, because flat ties the
  day-one Toronto case (shares 1.77 and 2.29) and check 2 requires the cheaper to win.
- Q: Where do learning-run hits go? A: `hits/dry-run/`, so `hits/*.json` keeps meaning "live hit"
  for the go-live trigger.
- Q: "Cheapest acceptable option" vs check 6? A: options are compared by score (price term plus
  the fringe penalty), then by total; when the price term saturates the central hotel wins.
- Q: Round-trip reprice? A: probed live on 2026-11-09; fast-flights 3.1.0 cannot price our exact
  leg pair (see the decisions log), so totals stay on one-way sums.
