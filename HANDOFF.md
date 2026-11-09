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
- Routines (month one on Opus 5.5, D-28; Gmail connector only):
  - `radar-daily` `trig_01VGioWFbgQxwEh1iZRypsCw`, Opus, cron `30 12 * * *` (05:30 Calgary),
    window 2026-11-10 to 2026-12-08, instructions in `routine/PROMPT-daily.md`. **Enabled**
    2026-11-09 16:10 UTC from the main session on William's say-so; first run 2026-11-10 12:36 UTC.
    Manage at https://claude.ai/code/routines/trig_01VGioWFbgQxwEh1iZRypsCw.
  - weekly digest `trig_01V9gJ6rL1sDuSsqDkE11oxo`, Opus, **disabled** 2026-11-09 16:10 UTC (folded into
    `radar-daily`, D-30; William does not want the separate email).
  - hit reviewer `trig_01TvveuLCRL8QwbwuF52yd9Y`, Sonnet, **disabled**, no schedule, no webhook.
  - `radar-tune` `trig_01E542toF6zwmddqDsjRGXeX`, Opus, one-shot `run_once_at` 2026-12-09T13:00:00Z
    (06:00 Calgary), **enabled**. Follows `routine/PROMPT-tune.md` and `docs/TUNING-PLAN.md`:
    backtest harness, rolling-percentile flight bands, a keep-or-revert config loop, then one PR
    `radar/tune-2026-12-09` for William to merge. Manage at
    https://claude.ai/code/routines/trig_01E542toF6zwmddqDsjRGXeX.
  - GitHub probe `trig_01NCvvPT6cUDiLLFkr7HN6tv`, Sonnet, done. The re-run at 15:43 UTC passed for push
    auth, PR open and comment read; Codex did not review the probe PR (D-37). Results in
    `routine/CAPABILITIES.md`.
  - first probe `trig_01XmaxqFZGSsnebpkB8VweMi`, done (read yes, push no, email yes).
- Codex review: William enabled automatic review on the repo (On PR open), but it did not review
  probe PR #1. Until a Codex review is seen on a `radar/iter-*` PR, assume the reviewer subagent
  fallback is doing the reviewing. Check the first PR's comments.
- Merged `radar/iter-*` branches stay on GitHub (the routine cannot delete branches). Turning on
  "Automatically delete head branches" in the repo settings would clean them up.
- Dashboard v2 merged to `main` (0ef0b69) and live on Pages, 2026-11-09. `index.html` and `site/` stay
  off-limits to the routine.
- Settings panel merged to `main` (897b491) and live, 2026-11-09 (D-43 to D-48): gear in the app bar;
  cities on/off and order, per-city `bar_cad`, days off (`config/days_off.yaml`, read by
  `generate_windows`), alert mode and threshold; Save writes through the GitHub Contents API with a
  fine-grained token William pastes once (steps in `README.md`, "Settings from the dashboard"). The
  token lives in the browser only. The routine may edit `config/scoring.yaml`; the panel retries on a
  sha conflict. William has not created the token yet as of this note.
- Window rule softened, 2026-11-09 evening (D-50, D-51): leave from 19:30 the evening before Day 1
  through 23:59 on Day 1 (was noon); home by 16:00 stays hard. Time score is linear from 10% to 70%
  of the window's best possible waking hours (`config/scoring.yaml: time_curve`), and trips under 10%
  are dropped. The request suggested 0.4/0.9; the data showed that would drop the trip that motivated
  the change, so 0.10/0.70 (details in D-51). The first scan with it is 2026-11-10.

## Enable procedure for `radar-daily` (done 2026-11-09; kept for a re-enable)

1. Re-arm the GitHub probe: `RemoteTrigger update trig_01NCvvPT6cUDiLLFkr7HN6tv` with
   `{"enabled": true, "run_once_at": "<now + 3 min, UTC>"}`. It reads `routine/PROMPT-probe-github.md`.
2. Read the result: `RemoteTrigger list_runs`, then `get_run_log` on the newest session. Record it in
   `routine/CAPABILITIES.md`. Check the probe PR is closed and its branch deleted.
3. If (a) push to main and (b) opening a PR both pass: keep the PR flow. If (b) fails but (a)
   passes: remove Phase A from `routine/PROMPT-daily.md`, make Phase C always use the fresh-context
   reviewer and commit to `main`, and say plainly here that Codex review is not in the loop. If (a)
   fails: do not enable; the routine could only email.
4. Enable `radar-daily` (`{"enabled": true}`), then disable the weekly digest
   (`trig_01V9gJ6rL1sDuSsqDkE11oxo`, `{"enabled": false}`). The hit routine stays disabled.

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
