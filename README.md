# Spontaneous Travel Radar

A free tracker that watches fares for two from Calgary (YYC) to 20 North American cities, keeps only
trips that fit a one-vacation-day weekend (leave after 7:30pm the evening before, home by 4pm on the
last day off), judges each complete trip for two against what its route normally costs, takes a
closer look at the few exceptional ones (real lodging, then what is on), logs every quote, and shows
the best of them on a static dashboard. Month one (to about 2026-12-09) is a dry-run learning period:
no alerts. See `docs/LEARNING-RUN.md`.

- **Dashboard:** https://williamebong.github.io/spontaneous-travel-radar/
- **Daily scan:** GitHub Actions `scan` workflow, 10:17 UTC (03:17 MST / 04:17 MDT), about 80 minutes
- **Claude routines:** `radar-daily` (pass 3, the daily note, at most one change a day):
  https://claude.ai/code/routines/trig_01VGioWFbgQxwEh1iZRypsCw · hit reviewer (disabled until go-live):
  https://claude.ai/code/routines/trig_01TvveuLCRL8QwbwuF52yd9Y · see `routine/CAPABILITIES.md`
- Design: `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md`
- Build plans: `BUILD-PLAN.md` (v1), `BUILD-PLAN-v2.md` (deal model and passes); build decisions: `docs/notes/decisions.md`; day-one smoke test:
  `docs/notes/day-one-smoke.md`
- Config: `config/` (cities, route ladders in `references.yaml`, stat holidays, days off, scoring weights
  and thresholds, the interests profile for pass 3, airline surcharges). Everything the Settings panel on the dashboard changes lives here too, as plain YAML.

## Settings from the dashboard

The gear button on the dashboard opens Settings: which cities the scan covers and in what order,
each route's ladder (read-only), extra days off and blocked dates, each trip class's switch and hit
line, the alert mode, an optional cap, and a "Run scan now" button. Everything is live to look at without signing in. Saving writes the config
files to `main` as a normal commit (`chore: settings from dashboard`), and the change applies at the
next scan, 04:17 Calgary. No terminal, no YAML by hand.

Saving needs a GitHub token that can write to this one repository. You create it once (about two
minutes) and paste it into the panel; it stays in your browser only.

1. Open https://github.com/settings/personal-access-tokens/new (a fine-grained token).
2. Token name: Radar dashboard. Expiration: as long as you like; when it runs out, make a new one
   and paste it again.
3. Repository access: Only select repositories, then pick `spontaneous-travel-radar`.
4. Permissions, Repository permissions: Contents, Read and write. Optional: Actions, Read and
   write, which makes "Run scan now" work. Leave everything else at No access.
5. Generate token, copy it, paste it into the panel's GitHub field and tap Connect.

What the controls do:

- Cities: the switch turns a city off (the scan skips it and spends no requests on it). Drag a row,
  or use the arrows, to set the order the dashboard's "Mine" sort uses. Under each city is its route
  ladder (typical, good, exceptional fare per person), which trips are judged against; edit
  `config/references.yaml` to change it.
- Days off: tap a weekday once for an extra day off (it counts like a stat holiday, so a Thursday or
  Tuesday off makes a 4-day long weekend and a Friday or Monday off costs no vacation day), again to
  block it (no trips touching that date), again to clear. Weekends and stat holidays only block.
  Stored in `config/days_off.yaml`.
- Trips: "Needs a day off" and "No day off needed" (weekend) each have a switch and a hit line (the
  final score a trip needs, 60 to 100); day-off trips also have their lead time (2 to 12 weeks).
- Alerts: learning run (hits and near misses show on the page, nothing is emailed) or live; an optional
  cap on a hit's complete trip for two (off by default); how much further a fare must drop before a city
  and weekend checked this week gets a fresh lodging check.
- Scan: "Run scan now" starts the GitHub Actions scan (two taps, about an hour, around 700 Google
  requests, so at most once a day).

Saving touches only the files whose values changed and only the lines you changed, so comments
and the daily routine's own edits survive. If GitHub answers 401 the token was rejected (Disconnect
and paste a new one); 403 on save means the token lacks Contents write, or the API limit for the
hour is used up; if the daily routine committed in the same minute, the panel re-reads the file and
retries once. Disconnect clears the token from the browser.

## How it works

`radar/main.py scan` generates the windows of both trip classes, queries Google Flights one-way legs
for two (CAD, carry-on priced in, basic fares allowed) through `fast-flights`' fetcher and our own
payload parser, keeps only itineraries inside the window, and scores each complete trip against its
route's typical trip (pass 1). Candidates (a fare at or under the route's good and a score of 70+) get
real lodging, Google Hotels and vacation rentals through SerpApi, at most three a scan (pass 2), written
to `hits/candidates/`. The daily routine researches what is on for those dates and runs
`python -m radar.main finalize` (pass 3), which files hits and near misses. Open-Meteo adds weather.
The scan writes `data/latest.json`, `data/series.json`, `data/history/<date>.jsonl` and the weekly
summary, and runs without API keys too (lodging check `skipped: no-key`).

## Run locally (Python 3.12)

```
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m radar.main scan --offline --today 2026-10-08
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
