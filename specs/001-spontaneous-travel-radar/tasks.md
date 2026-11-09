# Tasks: Spontaneous Travel Radar

Each task maps to the same-numbered task in `BUILD-PLAN.md`, which holds the steps and tests.

## Phase 1: Setup
- [x] T000 Day-one fast-flights smoke test and Actions block test (`scripts/smoke_fast_flights.py`, `docs/notes/day-one-smoke.md`)
- [x] T001 Repo, Spec Kit, scaffolding (`pyproject.toml`, `.gitignore`, `.env.example`, `README.md`)

## Phase 2: Foundational
- [x] T002 Config files and loader (`config/*.yaml`, `radar/config.py`, `tests/test_config.py`)
- [x] T003 Window generator (`radar/windows.py`, `tests/test_windows.py`)
- [x] T004 Flight fetcher (`radar/flights.py`, `tests/test_flights.py`)
- [x] T005 Itineraries and trip-window filter (`radar/itineraries.py`, `tests/test_itineraries.py`)

## Phase 3: US2 scan pipeline (P1)
- [x] T006 Scoring (`radar/score.py`, `tests/test_score.py`)
- [x] T007 Events and weather (`radar/events.py`, `radar/weather.py`, `tests/test_events_weather.py`)
- [x] T008 Store and history percentile (`radar/store.py`, `tests/test_store.py`)
- [ ] T009 Hotel check and hits (`radar/hotels.py`, `radar/hits.py`, `tests/test_hotels_hits.py`)
- [ ] T010 Export and CLI, offline end-to-end (`radar/export.py`, `radar/main.py`, `tests/test_main_offline.py`)
- [ ] T011 GitHub Actions cron and PC fallback (`.github/workflows/scan.yml`, `scripts/run-scan.ps1`)

## Phase 4: US1 dashboard (P1)
- [ ] T012 Dashboard on GitHub Pages (`index.html`, `site/app.js`, `site/style.css`)

## Phase 5: US4 routines (P3)
- [ ] T013 Routine prompts, capability probe, routines (`routine/*.md`)

## Phase 6: Polish
- [ ] T014 Learning-run procedure and handover (`docs/LEARNING-RUN.md`, `README.md`)
