# Spec: Two trip classes (day-off and weekend)

Approved by William on 2026-11-09. Base design: `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md`.

## Overview
Both William and his partner need time off approved, so a trip that uses a day off has to be at
least six weeks out. A weekend trip needs no approval. It can be close in, but it should only fire
when it is exceptional. The radar therefore scans two classes of trip, each with its own date range,
hard rules and gates, and every quote, card and hit says which class it belongs to.

## User scenarios
- **US1 (P1)** William sees day-off trips (Fri off, Mon off, stat blocks) 6 to 16 weeks out, early
  enough to ask for the time off.
- **US2 (P1)** William sees weekend-only trips (leave Friday after work, home Sunday) for the next six
  weeks, labelled "Weekend". One fires only when it is exceptional: an amazing fare, a very high
  score, and well under the city's bar.
- **US3 (P2)** William changes how far out day-off trips start (2 to 12 weeks) and turns weekend trips
  on or off from the dashboard's Settings panel.
- **US4 (P2)** The daily scan stays at or below today's request volume and under the 900 cap.

## Functional requirements
- **FR-201** Class "dayoff": the existing windows (fri-off, mon-off, stat-thu-4d, stat-tue-4d), Day 1
  from `min_weeks` x 7 to (`min_weeks` + `span_weeks`) x 7 days out (default 42 to 112). Window
  rules unchanged: leave from 19:30 the evening before Day 1 through 23:59 Day 1, home by 16:00 on the
  last day off. Basic fares excluded (`exclude_basic: true`). Gates unchanged.
- **FR-202** Class "weekend": one window per weekend, its Friday 3 to 42 days out. Leave Friday from
  17:30 through Saturday 12:00, home in Calgary by Sunday 16:00. Non-stop only, only cities with
  `air_time_min` of 180 or less, the city's first airport only, basic fares allowed
  (`exclude_basic: false`).
- **FR-203** Weekend gates: the band must be `gate_band` (amazing) to become a candidate, the score at
  least `gate_min_score` (88), and the complete trip at most `gate_max_bar_share` (0.70) x `bar_cad`.
  The scoring formula is unchanged.
- **FR-204** Each city gets `air_time_min` in `config/cities.yaml` (non-stop air time from the design
  table; door-to-door time for one-stop cities).
- **FR-205** Request volume: weekend queries every day; day-off city-weekends rotated over
  `rotate_days` (3) per city-airport-weekend, `(crc32(city:airport) + weekend number - scan day) mod 3`, so each
  day carries an even share; secondary airports every 9 days (D-54). Planned queries per day are at or below today's
  volume (702) and under the 900 cap, confirmed by a dry-run query build.
- **FR-206** Queries, cache keys and legs keep the classes apart: one class's legs never pair with the
  other's windows.
- **FR-207** `trip_class` (`dayoff` or `weekend`) is on every history row, every `latest.json` row
  and every hit. The route percentile compares a quote only with earlier quotes of the same class.
- **FR-208** Dashboard cards show the window's label ("Fri off", "Mon off", "Weekend", "Thu stat",
  "Tue stat") next to the dates. The expanded per-city list puts weekend trips under their own
  heading. The hero count covers hits of both classes. The `data/digests/index.json` contract is
  unchanged.
- **FR-209** Settings panel: "Day-off trips at least N weeks out" (whole number 2 to 12, default 6)
  and a "Weekend trips" on/off switch, both saved to `config/scoring.yaml` with the panel's existing
  validation and look.
- **FR-210** All class settings live in `config/scoring.yaml` under `trip_classes`, replacing
  `lookahead_min_days` and `lookahead_max_days`.

## Success criteria
- **SC-201** Tests cover: window generation at the boundaries (day-off 42 and 112 days, weekend 3
  and 42 days), the weekend city filter, the weekend gates, the rotation count, and an offline scan
  whose output carries `trip_class`.
- **SC-202** A dry-run query build for 2026-11-10 to 2026-11-12 plans at most 702 queries on each day.
- **SC-203** The dashboard shows class labels and the weekend grouping at 375 px and desktop width
  with no console errors (Playwright).

## Defaults taken
- Weekend departure starts at 17:30 Friday: the planning session's reading of William's "leave friday
  after work". Undo: one number in config.
- Allowing basic fares for weekend trips is the planning session's call. Undo: `exclude_basic: true`.
- Palm Springs qualifies for weekend trips (air time 2.7 h). Los Angeles and San Diego (3.2 h) do not.
- Day-off windows with no vacation day (a stat Friday or Monday) stay in the day-off range. Scanning
  them closer in is a question for William.
