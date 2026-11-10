# Spec: Spontaneous Travel Radar

Full design: `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md` (source of truth).

## Overview
A free daily collector that scans one-way fares for two from Calgary (YYC) to 20 North American
cities, keeps only itineraries inside the trip window, scores complete weekend trips, logs every
quote, and publishes a static dashboard. During month one it runs in dry-run mode: no alerts.

## User scenarios
- **US1 (P1)** William opens the dashboard on his phone and sees, per city, the best in-window trip
  for two right now: dates, fare, band, score, a 30-day sparkline, and scan health.
- **US2 (P1)** Every morning a scan runs unattended on GitHub Actions and commits fresh data.
- **US3 (P2)** An exceptional trip gets a capped hotel check and a templated brief in `hits/dry-run/`.
- **US4 (P3)** Each Monday of month one, a cheap Claude routine writes a short tuning digest.

## Functional requirements
- **FR-001** Generate trip windows from weekends and the selected stat calendar, per trip class
  (`specs/002-trip-classes/spec.md`): day-off windows 42 to 112 days ahead, weekend-only windows 3 to
  42 days ahead.
- **FR-002** Query Google Flights one-way legs for 2 adults in CAD with carry-on, no basic fares on
  day-off trips (weekend-only trips allow them, D-52),
  within a budget of 900 fetch attempts per scan, with rotation and caching.
- **FR-003** Drop itineraries outside the trip window (design §4: leave from 19:30 the evening before
  Day 1 through 23:59 on Day 1, home in Calgary by 16:00 on the last day off), with 2+ connections,
  or with under `time_rule.time_floor_share` (25%) of `time_rule.time_max_hours` (31 h) awake there (D-50, D-78).
- **FR-004** Score trips 0 to 100 per design §7; one winner per city-window.
- **FR-005** Run the SerpApi hotel check only for candidates, hard-capped (3 per candidate, 60 per month).
- **FR-006** Append every in-window quote to `data/history/YYYY-MM-DD.jsonl`; write `data/latest.json`
  atomically with a health block; write `data/series.json` and a weekly summary.
- **FR-007** Serve a static dashboard on GitHub Pages: best by city, hits, would-have-fired, digests, health.
- **FR-008** Work without API keys: hotel check reports `skipped: no-key`, events return empty.

## Success criteria
- **SC-001** `pytest -q` passes with no network.
- **SC-002** One real scan committed by the workflow, `data/latest.json` present, `mode: dry-run`.
- **SC-003** Dashboard live, verified with Playwright at desktop and 375 px, no console errors.
- **SC-004** Weekly digest routine created; hit routine created but inert.

## Edge cases
See BUILD-PLAN.md "Review Focus": after-midnight returns, time-zone crossings, blocked routes,
SerpApi cap mid-month, 4-day stat blocks.
