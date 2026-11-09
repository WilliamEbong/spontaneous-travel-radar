# Build plan v2: deal model, three passes, dashboard (2026-11-09)

> **Build status (branch `v2-deal-model`, 2026-11-10).** T1 to T11 done, reviewed, not merged; per-task
> state in `specs/002-deal-model-and-passes/tasks.md`, judgment calls D-57 to D-73 in
> `docs/notes/decisions.md` (review fixes D-73), run log in `SESSION-LOG.md`, hand-over in `HANDOFF.md`.
> Changed with evidence: the price line keeps falling past 1.30 (D-59); pass 1 assumes a good room
> (D-58); the round-trip reprice is not built (D-61); three lodging centres moved (D-68).

Owner: William. Written by the design session after a day of running v1 and a long design discussion.
Executor: a fresh Opus session running `/build-continuously`. Read, in this order: `HANDOFF.md`,
`docs/notes/decisions.md`, `docs/research/2026-11-09-fare-references.md`, then this plan. The
original design and v1 plan (`docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md`,
`BUILD-PLAN.md`) are background; where they conflict with this plan, this plan wins.

Spec Kit project: run `speckit-specify`, `speckit-plan`, `speckit-tasks` for this feature
(`specs/002-deal-model-and-passes/`), then implement. Ponytail governs every line.

## Why v2

Day one showed: (1) the price score went to zero for every fare above a seeded "bad" line, so the
cards picked the dearest itinerary; (2) the seeded bands and per-city bars described weekends that
do not exist (headline basic fares, and a $700 Vancouver bar against a $380 room); (3) "exclude
basic" threw away Air Canada and WestJet Basic fares that include a carry-on, the fares William
actually flies; (4) Ticketmaster event counts measured crowds, not interest; (5) William wants a
system that finds deals so exceptional he books on sight, not trips under a budget.

## What William decided (final, do not re-open)

1. No fixed price limit anywhere in scoring. "Good" is relative to what each route normally costs.
2. Price is one thing: the complete trip for two (flights + lodging + transit). Flights alone decide
   only who gets a closer look.
3. Three passes. Pass 1 scores every trip (free). Pass 2 finds real lodging for candidates and
   rescores the same price term. Pass 3 researches what is on for survivors and adds up to 10.
4. Basic fares allowed in both trip classes; carry-on always priced in.
5. Ticketmaster removed entirely. Events are judged by the "cannot get this in Calgary" test against
   William's interests profile, by the AI pass, on candidates only.
6. Lodging search restricted to each city's listed neighbourhoods or within ~20 minutes of the
   centre; location affects the convenience score; outskirts are discarded, not scored.
7. Two trip classes stay distinct everywhere: "No day off needed" (weekend) and "Needs a day off"
   (fri-off, mon-off, stat blocks), each with its own switch and threshold.
8. Dashboard order: Hits, then Passed (every trip scoring 70+), then every city's best deal.
9. All 20 cities stay. New Orleans is low-confidence, day-off trips only (no nonstop).
10. Hit line 80 for both classes (default; per-class in config). Price anchors 60/75/100 (see §T1).

## Global constraints

- $0: no paid APIs, no new paid services. No new pip or npm dependencies. Static dashboard, no build.
- Google Flights requests per scan stay at or under today's level (572–688; hard cap 900).
- SerpApi (Google Hotels): self-cap rises from 60 to 200 lookups a month (free tier 250). A
  candidate costs 2 lookups (hotels + vacation rentals). At most 3 candidates a day get pass 2/3.
- Claude usage: pass 3 is Opus, candidates only, cached 7 days per city-window; the Sonnet Airbnb
  step is a subagent inside the same routine run. No new routines; `radar-daily` (Opus, 12:30 UTC)
  carries passes 2 and 3. Do not touch `radar-tune` or the hit routine.
- Work on a branch in a worktree; commit per task; **do not merge or push to `main`**. Merging to
  `main` deploys Pages and changes what `radar-daily` runs the next morning; the design session
  merges after review.
- Keep `data/digests/index.json`, `data/latest.json` top-level keys and `hits/` layout readable by the
  current dashboard until the new dashboard lands in the same branch (T8).
- Secrets never in the repo. `.env` is gitignored. Never print key values.
- Playwright MCP is one shared instance: close it when done. Verify every UI change with it.
- Docs: decisions continue the D-numbering after the highest present; HANDOFF and SESSION-LOG as
  `build-continuously` requires.

## Tasks (in order; each ends green)

### T1 References and the price model
- New `config/references.yaml`: per city `flights: {typical, good, exceptional}` (CAD pp round trip,
  carry-on included) from the research table; `rooms: {winter: {typical, good, exceptional},
  summer: {...}}` per night pre-tax in the city's hotel currency, Vancouver from research
  (230/170/130 winter), all others `source: estimate` seeded from the current hotel tiers (cheap
  160/120/90, mid 230/170/130, expensive 330/250/190; summer +30%), to be replaced by T9. Each city
  carries `confidence: high|medium|low` and `nonstop: year-round|seasonal|none`.
- `radar/config.py` loads and validates it (every city present, exceptional < good < typical).
- Price term, `radar/score.py`: typical complete trip T = 2×flights.typical + nights×rooms[season].typical×tax
  + 4×transfer; `share = total / T`; points = 45 at share ≤ 0.60, 25 at 0.75, 0 at 1.00, straight
  lines, then −10 at 1.30 and flat (ordering among non-deals). Season = winter for Nov–Mar,
  summer otherwise (one line; tune later). Tax factor per city in `cities.yaml` (`hotel_tax: 1.185`
  for Vancouver; defaults 1.15 CA, 1.16 US, 1.19 MX).
- Weights: `{price: 45, time: 20, convenience: 10, city: 15, weather: 10}`. Remove `events`.
- Remove `flight_bands`, `hotel_bands`, `bar_cad` from scoring and gates. `bar_cad` may remain in
  `cities.yaml` as an optional personal cap used only if `settings.cap_cad` is set (off by default).
- Band label on cards becomes a ladder label: `exceptional` (flights ≤ exceptional), `good`,
  `typical`, `above` — computed from flights pp vs the route ladder. Keep the text-label pills.
- Tests: ladder validation; price points at share 0.5/0.6/0.75/1.0/1.3; Vancouver worked example from
  the research doc (good trip ≈ 74, $650 ≈ 83, exceptional ≈ 90 with weather 4, time 20,
  convenience 10, city 12).

### T2 Fares
- Remove `EXCLUDE_BASIC` (`radar/flights.py`): `exclude_basic_economy=False` for both classes;
  `carry_on_bags=1` stays. Update fixtures/tests that assumed Standard-only. Note in decisions that AC
  Basic and WestJet Basic include a carry-on and Flair/UltraBasic get the bag priced by Google.

### T3 Remove Ticketmaster
- Delete `radar/events.py`, its tests, the `TICKETMASTER_KEY` use in `.github/workflows/scan.yml`
  and `.env.example` if present, `hotel_spike`, and the events component. The secret itself can stay
  in GitHub; say so in HANDOFF so William can delete it.
- `n_events` parameters removed from `score_trip`; offline fixtures updated.

### T4 Candidate rule and history
- Candidate (goes to pass 2) = flights pp ≤ route `good` **and** pass-1 score ≥ `candidate_threshold`
  (70) for its class. Replaces the band/history-percentile rule.
- Per class in `config/scoring.yaml`: `classes: {dayoff: {enabled, candidate_threshold: 70,
  hit_threshold: 80}, weekend: {same}}`. The existing weekend hard rules (nonstop, air time ≤ 3 h)
  stay.
- History rows and `latest.json` rows gain `ladder` (label), `share` (total / typical trip),
  `pass` (1|2|3) and `final_score` (null until pass 3). `winner` and cheapest-per-pair logging as now.

### T5 Pass 2, deterministic part (collector)
- For each candidate (max 3 per scan, highest pass-1 score first): Google Hotels lookup (4–5 star,
  rating ≥ 4.3, 2 adults, the window's nights) **and** a vacation-rentals lookup (SerpApi
  `vacation_rentals=true`, same dates), both constrained to the city's `neighbourhoods` (query text)
  and then filtered by distance to the city centre ≤ 6 km as a stand-in for 20 minutes
  (`gps_coordinates` in SerpApi results; `lat`/`lon` in `cities.yaml`). Store Google's per-property
  `deal`/`deal_description` text.
- Cheapest acceptable option becomes `lodging_cad` (all-in total); price term recomputed with it;
  convenience −3 if the chosen option is 3–6 km out ("fringe"); pass-2 score written.
- Round-trip reprice (already a permitted change class): one fast-flights round-trip query for the
  candidate's exact legs; use the lower of round-trip and one-way-sum in the total. Counts against the
  request budget; cap 3 a day by construction.
- SerpApi counter: `serpapi_monthly_cap: 200`; errors not retried; `skipped: quota` recorded.
- Output: `hits/candidates/<date>-<city>-<window>.json` with pass-1 and pass-2 breakdowns, options
  list with links, and `status: awaiting_pass3`.
- Tests with fixtures: filtering by distance, cheapest-acceptable choice, rescoring, cap behaviour.

### T6 Pass 2 (Airbnb) and pass 3 in `routine/PROMPT-daily.md`
- After the scan's candidates are read: for each `awaiting_pass3` candidate (max 3), (a) a Sonnet
  subagent searches Airbnb for the dates, 2 guests, entire place or private room, inside the listed
  neighbourhoods; it returns a price only when it reads a concrete listing total for those dates
  with a link, otherwise `hint` text; if a concrete price beats the current lodging, the total and
  score are recomputed and the brief shows both. (b) Pass 3: research what is on for those exact
  dates (official city and tourism calendars, festival listings, museum and gallery programmes, local
  press, venue calendars), judge each find against `config/interests.yaml` and score
  `uniqueness (0–3) × fit (0–1) × affordability (free 1.0, ≤$30 0.8, ≤$60 0.6, ≤$100 and famous
  0.3, else 0)`, sum, cap 10, with a one-line reason per item; note negatives (closures, strikes,
  weather warnings, big crowd events that inflate prices) as text; cache in
  `data/research/<city>-<window>.json` for 7 days. (c) `final_score = pass2 + events`; `is_hit =
  final ≥ hit_threshold[class]`; write `hits/<id>.json` (hit) or `hits/near-miss/<id>.json` with the
  full three-pass breakdown; dry-run: never email, show on the page.
- Keep the routine's existing jobs (daily note, one change PR a day, iteration log). Routine prompts
  remain the only source of routine instructions; no RemoteTrigger changes needed.

### T7 Interests profile
- `config/interests.yaml`: music genres (hip-hop, R&B, jazz, Afrobeats, Black music broadly), art,
  history, markets, nightlife, street and neighbourhood festivals; concert price lines $60 (lesser
  known) / $100 (famous); dislikes (country, big-ticket arena shows); the uniqueness test in one
  sentence ("would this be possible in Calgary? then it is worth 0"). Validated by the loader.

### T8 Dashboard and panel
- Page order: (1) **Hits** with the brief (flights, lodging options with links, what is on with
  reasons, three-pass breakdown); (2) **Passed**: one row per trip with pass-1 score ≥ 70, columns:
  class label, city, dates, flights pp, score so far, stage reached (lodging checked → real total;
  what's-on → +N; final), sorted hits first then score; (3) **Every city**: 20 cards, best deal
  (highest score; show price and flights), ladder label, "typical for this route $X · exceptional
  under $Y" line, class label; expand → every weekend for both classes sorted by score, plus price
  history; (4) daily note; health and settings as now. Remove "Would have fired".
- Both lists split "No day off needed" then "Needs a day off", with a visible accent per class and
  the class label on cards. Email subjects (live mode) prefixed `[Weekend]` / `[Day off]`.
- Panel: remove per-city bar steppers; show the read-only ladder per city; per-class switch and
  hit threshold; optional overall cap (off); interests editable later (not this build).
- Empty states for every section with the day-one-style data (no candidates yet).
- Playwright at 375 and 1280, light and dark, with fixture data for: no candidates; two passed, no
  hit; one hit in each class. Screenshots in the report. Console clean.

### T9 Hotel reference pass
- `scripts/room_references.py`: for each of the 19 unresearched cities, one Google Hotels lookup for
  15–17 Jan 2027 and one for 16–18 Jul 2027 (2 adults, 4–5 star, rating ≥ 4.3, central
  neighbourhoods, sorted by price). `typical` = median nightly rate of the ten cheapest acceptable;
  `good` = 0.75×typical; `exceptional` = 0.57×typical, rounded to $5. Writes into
  `config/references.yaml` with `source: google-hotels 2026-11-xx` and keeps the Vancouver numbers.
  About 38 lookups; counts against the 200 cap; record the count in the SerpApi counter.

### T10 Docs
- Design doc: new section "v2 deal model" (ladder, price term, passes, classes on the page) marking
  superseded parts. Decisions D-56 onward, one per judgment call. HANDOFF (full rewrite of the
  status section), LEARNING-RUN (month one now observes passes 2 and 3 on dry-run candidates),
  TUNING-PLAN (Dec 9 refits the ladders from history and tests the 60/75/100 anchors against the
  month's near-misses and hits), CAPABILITIES (SerpApi cap), README (settings section updated).

### T11 Finish
- `pytest -q` green; `python -m radar.main scan --offline --today 2026-11-12` produces latest.json
  with the new fields and the dashboard renders it; Playwright evidence; fresh-context review
  subagent on the branch and fixes applied; HANDOFF written; report in the `build-continuously`
  format with the branch name. Do not merge.

## Acceptance checks (definition of done)

1. Vancouver worked example reproduces within ±2 points (research doc §complete-trip ladder).
2. Two all-above-typical trips in one window: the cheaper one wins (regression of the day-one bug).
3. Basic fares present in a fresh fixture fetch for YYC–YVR (AC/WestJet Basic or Flair appear).
4. No reference to Ticketmaster remains in code, workflow or tests.
5. Candidate rule: flights at `good` with score 69 → not a candidate; score 70 → candidate.
6. Pass 2 fixture: a central hotel at $650 beats a fringe rental at $550 by score; both appear in
   the options list.
7. SerpApi cap honoured in a simulated month (no lookup past 200).
8. Dashboard shows the three sections in order with correct class grouping in all four fixture
   states, both widths, both themes, console clean.
9. Offline scan writes `ladder`, `share`, `pass`, `final_score` on every row.
10. Request budget unchanged: dry-run query build reports ≤ 688 queries.

## Judgment calls already made (change only with evidence)

- Price anchors 60/75/100 and the −10 at 130% ordering slope.
- Hit 80, candidate 70, both classes.
- Winter = Nov–Mar for room references.
- 6 km as the proxy for "20 minutes from the centre".
- Room estimates for 19 cities until T9 runs.
- Sonnet Airbnb prices count only when concrete.

## Later (not this build)

"Would book / Not for me" tap on cards writing `data/labels.jsonl`; interests editable in the panel;
labels-driven weight tuning on Dec 9; seasonal room references finer than winter/summer.
