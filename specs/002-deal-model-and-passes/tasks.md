# Tasks: Deal model v2 and three passes

Each task ends with `pytest -q` green and its own commit. IDs follow `BUILD-PLAN-v2.md`.

## Setup
- [x] T300 Spec Kit artifacts, constitution v1.1, live probes (basic fares, round trip, SerpApi shapes) with fixtures

## Foundational (price model)
- [x] T301 `config/references.yaml`, `hotel_tax`, `load_references`; price term, ladder label, weights; drop bands and bars (`radar/config.py`, `radar/score.py`, `config/*.yaml`, tests) (FR-301 to FR-305, check 1, 2)
- [x] T302 Basic fares in both classes (`radar/flights.py`, `config/scoring.yaml`, tests, fixture) (FR-306, check 3)
- [x] T303 Remove Ticketmaster (`radar/events.py`, workflow, `.env.example`, tests, footer) (FR-307, check 4)
- [x] T304 Candidate rule and per-class thresholds; history and latest fields (`radar/score.py`, `radar/store.py`, `radar/export.py`, `radar/main.py`) (FR-308, FR-309, checks 5, 9, 10)

## Passes
- [x] T305 Pass 2: lodging search, distance filter, best-by-score, cap, candidate files (`radar/hotels.py`, `radar/hits.py`, `radar/main.py`) (FR-310 to FR-312, checks 6, 7)
- [x] T306 Pass 3: `finalize`, research schema, `routine/PROMPT-daily.md`, `routine/PROMPT-hit.md` (FR-313)
- [x] T307 `config/interests.yaml` and loader (FR-314)

## Dashboard
- [x] T308 Page: Hits, Passed, Every city, notes; class grouping; ladders; settings panel changes; fixture states; Playwright at 375/1280, light/dark (FR-315, FR-316, check 8)

## Data
- [x] T309 `scripts/room_references.py` and the live run for 19 cities (FR-317)

## Polish
- [x] T310 Docs: design doc v2 section, decisions D-57 onward, LEARNING-RUN, TUNING-PLAN, PROMPT-tune, CAPABILITIES, README
- [x] T311 Finish: tests, offline scan at `--today 2026-11-12`, Playwright evidence, fresh-context review and fixes, HANDOFF, report
