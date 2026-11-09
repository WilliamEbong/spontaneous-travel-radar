# Tasks: Two trip classes

- [x] T201 Config: `dayoff_min_weeks`, `weekend_trips`, `trip_classes` in `config/scoring.yaml`; `air_time_min` on every city; `Scoring` and `City` fields (FR-204, FR-210)
- [x] T202 Windows: `Window.trip_class`, `weekend_windows`, `class_windows` (FR-201, FR-202)
- [x] T203 Queries: class-aware `LegQuery` and `build_queries`, weekend flags, crc32 mod 3 day-off rotation (FR-202, FR-205, FR-206)
- [x] T204 Trips, scoring, gates: `Trip.trip_class`, weekend candidate rule, per-class gates (FR-203)
- [x] T205 Scan loop: class-keyed legs, per-class percentile, `trip_class` on rows, latest and hits; day-off-only series and summary stats (FR-206, FR-207)
- [x] T206 Tests: window boundaries, city filter, gates, rotation count, offline scan with `trip_class` (SC-201, SC-202)
- [x] T207 Dashboard: class labels, weekend grouping, hero gates text, hint copy (FR-208)
- [x] T208 Settings panel: weeks slider and weekend switch (FR-209)
- [x] T209 Playwright check at 375 px and desktop width (SC-203)
- [x] T210 Docs: design doc, spec 001 FRs, decisions with budget numbers, HANDOFF, LEARNING-RUN, TUNING-PLAN, PROMPT-daily
