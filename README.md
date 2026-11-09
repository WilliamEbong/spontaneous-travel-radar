# Spontaneous Travel Radar

A free tracker that watches fares for two from Calgary (YYC) to 20 North American cities, keeps only
trips that fit a one-vacation-day weekend (leave after 7:30pm the evening before, home by 4pm on the
last day off), scores complete trips (flights, nights, context), logs every quote, and shows the
best of them on a static dashboard. Month one (to about 2026-12-09) is a dry-run learning period:
no alerts. See `docs/LEARNING-RUN.md`.

- **Dashboard:** https://williamebong.github.io/spontaneous-travel-radar/
- **Daily scan:** GitHub Actions `scan` workflow, 10:17 UTC (03:17 MST / 04:17 MDT), about 80 minutes
- **Claude routines:** weekly digest, Mondays 07:00 Calgary, month one only:
  https://claude.ai/code/routines/trig_01V9gJ6rL1sDuSsqDkE11oxo · hit reviewer (disabled until go-live):
  https://claude.ai/code/routines/trig_01TvveuLCRL8QwbwuF52yd9Y · see `routine/CAPABILITIES.md`
- Design: `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md`
- Build plan: `BUILD-PLAN.md`; build decisions: `docs/notes/decisions.md`; day-one smoke test:
  `docs/notes/day-one-smoke.md`
- Config: `config/` (cities and bars, stat holidays, scoring bands and weights, airline surcharges)

## How it works

`radar/main.py scan` generates the trip windows 3 to 45 days ahead, queries Google Flights one-way
legs for two (CAD, carry-on priced in, basic fares excluded) through `fast-flights`' fetcher and our
own payload parser, keeps only itineraries inside the window, scores each complete trip 0 to 100,
and writes `data/latest.json`, `data/series.json`, `data/history/<date>.jsonl` and the weekly
summary. Candidates get a capped SerpApi Google Hotels check and a brief in `hits/dry-run/`.
Ticketmaster (events) and Open-Meteo (weather) add context. Everything runs without API keys too
(events empty, hotel check `skipped: no-key`).

## Run locally (Python 3.12)

```
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m radar.main scan --offline --today 2026-11-10
.venv\Scripts\python -m radar.main scan --cities vancouver,las_vegas --budget 60
```

Keys go in `.env` (see `.env.example`); `radar.main` reads it. In Actions they are repo secrets.

## Switching the collector host

If Google starts blocking GitHub's IPs (Health shows "Blocked by Google" or coverage collapses),
switch to the PC: follow the three steps at the top of `scripts/run-scan.ps1`.

## Defaulted questions for William (design section 11)

- [ ] 1. Public repo acceptable? Default yes (needed for free GitHub Pages).
- [ ] 2. Email alerts to your Gmail on live hits? Default yes, hits only, never digests.
- [ ] 3. Any three consecutive days off, or only weekend-anchored? Default weekend-anchored plus stat holidays.
- [ ] 4. Minimum lead time? Default 3 days.
- [ ] 5. Hotel floor? Default 4-star and up on Google's scale (no 3.5 exists), rating 4.3+/5, free cancellation requested.
- [ ] 6. Neighbourhoods per city? Seeded in `config/cities.yaml`; edit freely.
- [ ] 7. Scan from PC or GitHub? Decided by the day-one block test: GitHub Actions (not blocked).
- [ ] 8. Which stat-holiday calendar does your employer observe? Default `alberta`; switch `calendar:` in `config/holidays.yaml` to `ontario` or `federal`.
