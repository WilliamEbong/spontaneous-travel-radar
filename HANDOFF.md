# Handoff: Spontaneous Travel Radar (build of 2026-11-09)

Read this first if you are picking the build up in a fresh session. Then read `SESSION-LOG.md` and
`docs/notes/decisions.md`.

## Where things stand

- Repo `WilliamEbong/spontaneous-travel-radar` is public and on `main`. All BUILD-PLAN tasks 0 to 14
  are implemented; Spec Kit artifacts are in `specs/001-spontaneous-travel-radar/` (tasks.md has a
  Phase 7 "Convergence" with the last open items).
- `pytest -q`: 58 tests, all passing, no network.
- Collector host: GitHub Actions (`.github/workflows/scan.yml`, cron 10:17 UTC). The day-one block
  test showed Google does not block Actions IPs. PC fallback: `scripts/run-scan.ps1` (not registered).
- Dashboard: https://williamebong.github.io/spontaneous-travel-radar/ (Pages source = GitHub Actions).
- Secrets `SERPAPI_KEY` and `TICKETMASTER_KEY` are set as Actions secrets (William set them) and
  are in the local `.env` (gitignored).
- Routines (Sonnet 5.5 since 2026-11-09, D-27; Gmail connector only):
  - weekly digest `trig_01V9gJ6rL1sDuSsqDkE11oxo`, Mondays 14:00 UTC (07:00 Calgary), real work only
    2026-11-16 to 2026-12-07; emails the digest because routines cannot push yet.
  - hit reviewer `trig_01TvveuLCRL8QwbwuF52yd9Y`, **disabled**, no schedule, no webhook.
  - probe `trig_01XmaxqFZGSsnebpkB8VweMi`, one-shot, done (read yes, push no, email yes).

## Open threads

1. Done 2026-11-09 08:50 UTC: the first full scan (run 42580547763) committed `data/latest.json`
   (702/702 queries, 0 errors, 66 min) and the live dashboard was verified with Playwright.
   Next check: the scheduled scan of 2026-11-10 10:17 UTC is the first to ship D-25 (cheapest per city).
2. Webhook for the hit routine is blocked until William installs the Claude GitHub App on the repo
   (https://github.com/apps/claude/installations/select_target). That also lets routines commit
   digests. Not needed until go-live (`docs/LEARNING-RUN.md`).
3. T017: FR-006 says every quote is logged; D-12 logs the cheapest per airport plus the winner.
   William to confirm.
4. Bands sit far below realistic carry-on, no-basic fares (D-03, D-04, D-26): all 119 city-windows
   on day one band "bad", so there are no candidates and no hotel checks until the bands move.
   Decided 2026-11-09: William keeps basic fares excluded (`EXCLUDE_BASIC` stays `True`). Retune
   `config/scoring.yaml` from the project's own data after two weeks of scans (target: the digest of
   2026-11-23): per city, amazing/good/average at about p10/p25/p50 of `price_pp` from
   `data/weekly-summary.json`.

## Gotchas

- fast-flights 3.1.0's `get_flights` drops Google's "best flights" list; we parse the page
  ourselves (`radar/flights.py: parse_items`). It also imports `typing_extensions` undeclared.
- tzdata 2026f has Alberta and BC on permanent daylight time from November 2026; the workflow sets
  `PYTHONTZPATH=""` so Python uses the pip `tzdata` package.
- In this Windows Bash tool, backslashes inside heredocs get mangled: write files with the editor.
- Playwright MCP can only write inside the project folder (`.playwright-mcp/`, gitignored).

## How to verify

```
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m radar.main scan --offline --today 2026-11-10
gh run list --workflow scan.yml --limit 3
```
Then open the dashboard URL and check Health: coverage, fetch errors, blocked, SerpApi used.
