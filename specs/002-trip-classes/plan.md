# Plan: Two trip classes

Spec: `spec.md`. Constitution: `.specify/memory/constitution.md`. This is $0, with no new dependencies
and no new Claude runs. The window rule stays the only hard filter, now one rule per class. The
weekend class's non-stop and air-time limits are part of its rule.

## Config (`config/scoring.yaml`)
- Top level, edited by the Settings panel (one line each, like `mode`):
  `dayoff_min_weeks: 6` (2 to 12) and `weekend_trips: true`.
- `trip_classes:` block, routine-tunable gates and fixed rules:
  - `dayoff: {span_weeks: 10, exclude_basic: true, rotate_days: 3}`
  - `weekend: {min_days: 3, max_days: 42, depart_from: "17:30", depart_to: "12:00",
    exclude_basic: false, max_air_min: 180, gate_band: amazing, gate_min_score: 88,
    gate_max_bar_share: 0.70}`
- `lookahead_min_days` / `lookahead_max_days` removed. `Scoring` gets `dayoff_min_weeks`,
  `weekend_trips`, `trip_classes`.
- `config/cities.yaml`: `air_time_min` on every city (design section 5 table; one-stop cities get
  their door-to-door time). `City.air_time_min: int`.

## Collector
- `radar/windows.py`: `Window.trip_class` (`"dayoff"` default). `generate_windows` is unchanged
  apart from the field. New `weekend_windows(today, min_days, max_days, depart_from, depart_to,
  blocked)` returns one window per Friday in range, with id `<Fri>_weekend`, `days_off` = (Sat, Sun),
  leave Fri `depart_from` to Sat `depart_to`, home Sat 17:00 to Sun 16:00, out (Fri, Sat), back
  (Sat, Sun), and dropped if Fri, Sat or Sun is blocked. `class_windows(today, s, holidays, extra,
  blocked)` builds both lists from config.
- `radar/flights.py`: `LegQuery` gets `trip_class`. `key()` appends `-weekend` for that class only,
  so existing cache and fixture names stay valid. Weekend queries use `max_stops=0` and
  `exclude_basic=False` and the city's first airport only. `build_queries` groups roles by class too,
  so classes never merge. Day-off rotation: a city-weekend is in today's plan when
  `crc32(f"{city}:{weekend}") % rotate_days == today.toordinal() % rotate_days`, all its airports
  together, so out and back legs land on the same day. Weekend: every day. `EXCLUDE_BASIC` becomes
  the class flag.
- `radar/itineraries.py`: `Trip.trip_class` from the window.
- `radar/score.py`: weekend candidate = band at least `gate_band`; day-off rule unchanged.
- `radar/hits.py: gates`: per-class score threshold and bar share.
- `radar/main.py`: legs keyed by `(trip_class, origin, dest, day)`; windows from `class_windows`.
  Percentile history keyed by (city, class); rows without `trip_class` count as `dayoff`.
- `radar/store.py`, `radar/export.py`, `radar/hits.py`: `trip_class` on history rows, `latest.json`
  rows and hits. Series and weekly-summary price stats use day-off rows only, so basic weekend fares
  do not distort the band fit the daily routine reads.

## Dashboard
- `site/app.js`: `PATTERN.weekend = "Weekend"`; stat labels stay. The per-city table splits
  weekend rows under a "Weekend trips" heading. The hero text mentions the weekend gates. Hits
  already count both classes. The hint in `index.html` describes both classes.
- `site/settings.js`: a new "Trips" section with a slider "Day-off trips at least N weeks out"
  (2 to 12) and an on/off switch "Weekend trips", in the existing styles. Both go through the existing
  scoring.yaml line editor, validation and read-back.

## Budget
Measured with a dry-run query build for 2026-11-10 to 2026-11-12, all 20 cities. Numbers go in the
decision log.

## Tests
Window boundaries for both classes; the weekend city filter, non-stop and basic flags; the weekend
gates; the rotation count (each city-weekend exactly once in 3 days; daily total at most 702); an
offline scan with `trip_class` on rows. Playwright on the dashboard and the Settings panel.
