# Plan: Deal model v2 and three passes

Spec: `spec.md`. Constitution: `.specify/memory/constitution.md` (amended to v1.1 for William's v2
decisions). Python 3.12 (3.11 in the routine sandbox), fast-flights 3.1.0, pyyaml, httpx, tzdata;
vanilla JS dashboard, no build. $0, no new dependencies.

## Config

- `config/references.yaml` (new): top-level mapping city key to `{confidence, nonstop, flights:
  {typical, good, exceptional}, rooms: {winter: {typical, good, exceptional, source}, summer: {...}}}`.
  Flights from the research table. Rooms: Vancouver winter from research; every other season
  `source: estimate` from the old hotel tiers (cheap 160/120/90, mid 230/170/130, expensive
  330/250/190, summer +30%) until `scripts/room_references.py` replaces them.
- `config/scoring.yaml`: `weights {price 45, time 20, convenience 10, city 15, weather 10}`;
  `price_curve: {points: [[0.60, 45], [0.75, 25], [1.00, 0], [1.30, -10]], floor: -100}` (points on
  the price weight's scale); `cap_cad: null`; `serpapi_monthly_cap: 200`; `trip_classes.<class>`
  gains `enabled`, `candidate_threshold: 70`, `hit_threshold: 80` and loses `exclude_basic` and the
  weekend `gate_*`. Removed: `flight_bands`, `hotel_bands`, `score_threshold`, `weekend_trips`,
  `serpapi_per_candidate_cap`.
- `config/cities.yaml`: drop `flight_group`, `hotel_group`, `bar_cad`; optional `hotel_tax`
  (Vancouver 1.185).
- `config/interests.yaml` (new): `music_love`, `interests`, `dislikes`, `concert_price_cad
  {lesser_known: 60, famous: 100}`, `uniqueness_test`.

## Collector

- `radar/config.py`: `City.hotel_tax` (country default), `Ladder`/`Reference` dataclasses and
  `load_references` (all cities present, strict order), `load_interests`, new `Scoring` fields.
- `radar/score.py` (rewrite of the price half): `season`, `typical_trip_cad`, `price_points(share,
  curve)`, `ladder_label`, `lodging_estimate_cad` (season `good` room x nights x tax),
  `convenience(trip, city)` unchanged, `score_trip(trip, city, ref, s, *, weather_score, history_pct,
  lodging_cad=None)` returning `Scored` with `share`, `ladder`, `candidate`, `typical_cad`,
  `conv_pts`; `rescore(scored_dict, lodging_cad, fringe, s)` used by pass 2 and pass 3 so the
  arithmetic lives in one place; `is_candidate`.
- `radar/flights.py`: no `exclude_basic` anywhere; `exclude_basic_economy=False` on every query.
- `radar/events.py` deleted.
- `radar/hotels.py` (rewrite): `search(city, check_in, nights, kind, s, api_key, cache_dir, today)`
  for `kind` hotels or rentals (one SerpApi call each, counted first), `parse_options(payload, city,
  kind, nights)` with haversine distance, the 6 km cut, the fringe flag, after-tax total (pre-tax x
  tax as the fallback), Google's deal text; `check_lodging` runs both; `LodgingCheck(options,
  skipped)`.
- `radar/hits.py` (rewrite): `previous_candidate` (7-day dedupe, re-check only on a 15% fare drop),
  `pass2(...)` picks the best option by score, `write_candidate` (JSON + brief), `finalize(cand,
  research, s, interests)` for pass 3 (events points, Airbnb override, final score, `is_hit`, file
  placement), `render_brief`.
- `radar/main.py`: pass 1 over every trip, candidates, pass 2 for the top three (dedupe first),
  history rows and `latest.json` with the new fields, `finalize` subcommand.
- `radar/store.py`, `radar/export.py`: row fields `ladder`, `share`, `total_cad`, `nights`, `pass`,
  `final_score`, `candidate_id`; `latest.json` keeps its top-level keys, `best_by_city` becomes each
  city's top score, `cities` entries carry the ladder; `hits/index.json` indexes candidates, near
  misses and hits with their stage; weekly summary reports ladder spread and pass-3 outcomes.

## Routine

`routine/PROMPT-daily.md` gains a pass-3 section after the PR step: list today's `awaiting_pass3`
candidates, reuse a research file under 7 days old, otherwise research and write
`data/research/<city>-<window>.json` (schema in the prompt), run a Sonnet subagent for Airbnb,
then `python -m radar.main finalize <id> --research <path>`. The analysis section moves from bands
and bars to ladders and thresholds. `routine/PROMPT-hit.md` subjects get `[Weekend]` / `[Day off]`.

## Dashboard

`index.html`, `site/app.js`, `site/style.css`: sections Hits, Passed, Every city, Notes; class
grouping with an accent per class (`--cls-weekend`, `--cls-dayoff`), ladder pills, the stage of
each 70+ trip from `hits/index.json`. `site/settings.js`: per-class switch and hit threshold
(block-scoped YAML line edits inside `trip_classes`), overall cap, read-only ladders from
`config/references.yaml`, no bar stepper, no global score threshold. Four fixture states built by
`scripts/dashboard_fixtures.py` from a real offline scan plus `finalize` on fixture research.

## T9

`scripts/room_references.py`: per city and season one `search(kind="hotels")` (counted), median
nightly pre-tax of the ten cheapest acceptable, good 0.75x, exceptional 0.57x, round to $5, text
edit of the two `rooms` lines per city.

## Request budget

Unchanged query build (572 to 688 a day; check in tests). No round-trip reprice: fast-flights 3.1.0
cannot price an exact leg pair (probe evidence in the decisions log).
