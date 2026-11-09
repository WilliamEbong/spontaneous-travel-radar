# Build decisions

Decisions made during the unattended build (2026-11-09). Each says what was chosen, why, and how to undo it.
Items marked **check** are ones William should look at.

- **D-01** Python 3.12 via `uv venv --python 3.12` (the PC only has 3.14). Matches the Actions runtime. Undo: any 3.12+ venv works.
- **D-02** `radar/flights.py` uses `fast_flights.fetch_flights_html` and parses Google's payload itself (both the "best" and "other" lists). fast-flights 3.1.0's `get_flights` drops the "best" list, which held the cheapest fares in the smoke test (499 vs 583). Version pinned `==3.1.0`. Undo: switch back to `get_flights` if upstream fixes it.
- **D-03 (check)** `exclude_basic_economy=True` kept, as your hard constraint requires. The smoke test shows the carry-on flag alone already makes ULCC fares realistic (Flair +$43 per person per leg, priced by Google), and the no-basic flag is what doubles the cheapest YYC→YVR fare for two (245 → 499) by hiding Flair and WestJet UltraBasic. If you want ULCC fares with a bag counted, flip `EXCLUDE_BASIC` in `radar/flights.py` to `False`.
- **D-04 (check)** Flight bands kept as seeded, although realistic fares in the smoke test sat 2 to 3 times above the "bad" line (YVR 483 per person round trip vs 190). Retune from the first weeks of data via the weekly digest, not from one weekend.
- **D-05** Work is pushed straight to `main` of the public repo, as the task asks (the repo is the deploy target for the Actions scan and Pages). Commits are per task.
- **D-06** Rotation parity uses `zlib.crc32(airport)`, not `hash()` (Python salts string hashes per process, so `hash()` would rotate randomly). About 730 queries per scan, under the 900-attempt budget.
- **D-07** `LegQuery` carries `origin_tz`/`dest_tz` so `fetch_leg` can build tz-aware `Leg`s without a global airport table. The fetch cache directory is per scan day (`data/cache/<date>/`); `--offline` points it at `tests/fixtures/offline/`.
