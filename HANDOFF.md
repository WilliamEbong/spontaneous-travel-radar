# Handoff: Spontaneous Travel Radar (state as of 2026-11-10, 16:30 Calgary)

Read this first in a fresh session. Then `docs/notes/decisions.md` (D-01 to D-78, one entry per
judgment call), `docs/ASK.md` (how to answer William's questions from the data), and `SESSION-LOG.md`
(what happened, in order). `BUILD-PLAN-v2.md` and `docs/research/2026-11-09-fare-references.md` are the
design record for v2; `BUILD-PLAN.md` and the design doc in `docs/superpowers/specs/` are v1 background.

## What it is

A $0-to-run deal radar for spontaneous weekend trips from Calgary (YYC) for two adults. A Python
collector on GitHub Actions scans Google Flights daily, scores every trip, checks real lodging for
candidates, and publishes JSON to this public repo; GitHub Pages serves a static dashboard William
checks on his phone; a Claude routine runs once a day to research candidates, write a note and propose
at most one tuning change. William wants alerts only for deals so exceptional he books on sight; a quiet
dashboard is the system working. Month one (to about 2026-12-08) is a learning run: nothing alerts,
everything is logged and shown.

## Everything on `main` is live (nothing pending on branches)

Merged and deployed on 2026-11-09/10, newest last: dashboard v2 (D-36), settings panel (D-43 to D-48),
softened departure rule and time curve (D-50/51), two trip classes (D-52 to D-55), price below the bad
line (D-56), the v2 deal model and three passes (D-57 to D-73), schedule hardening (D-74), score
breakdown panel (D-75), components and inputs on every history row (D-76), scoring table and sky words
(D-77), one objective time scale and convenience evidence (D-78). `pytest -q`: 106 tests, no network.
Last commit `0ac2dd3`. The worktrees under `.claude/worktrees/` (`dashboard-v2`, `settings-panel`,
`v2-deal-model`, `score-breakdown`, `scoring-table`, `time-score`) are merged and can be removed.

Live: https://williamebong.github.io/spontaneous-travel-radar/ and `table.html` (scoring table).
Verified on the live site at 16:10 Calgary after the bonus scan: every score opens its breakdown with
the new time and convenience lines; `data/history/latest.csv` (296 trips, 135 KB) downloads.

## What runs, and when (Calgary time; the repo and logs use UTC)

- **04:17 daily**: the scan (`.github/workflows/scan.yml`, cron 10:17 UTC plus hourly backup slots to 16:17 UTC (D-79) that
  skips itself when today's scan exists, D-74; manual `gh workflow run scan.yml` always runs). About
  60 to 80 minutes, 572 to 688 Google Flights fetches, cap 900. Commits `data/` and `hits/`, redeploys
  Pages. GitHub's scheduler has been late (10 h on 11-09) and absent (11-10): hence the backup slot.
- **07:30 daily**: `radar-daily` (Opus 5.5, routine `trig_01VGioWFbgQxwEh1iZRypsCw`, cron 14:30 UTC,
  window 2026-11-10 to 2026-12-08, instructions in `routine/PROMPT-daily.md`): pass 2's Airbnb step and
  pass 3 research on today's candidates, a note to `data/digests/<date>.md` (shown on the page), at most
  one tuning PR a day on a `radar/iter-*` branch (Codex reviews on open; a reviewer subagent if Codex
  stays silent), merges yesterday's PR after reading its review. Its 12-08 run writes the month-one
  summary.
- **2026-12-09 06:00**: `radar-tune` (Opus, one-shot `trig_01E542toF6zwmddqDsjRGXeX`, 13:00 UTC,
  `routine/PROMPT-tune.md` + `docs/TUNING-PLAN.md`): backtest harness over the month's history, refit of
  the route ladders, keep-or-revert loop over `config/scoring.yaml`, one PR for William to merge.
- Disabled: hit reviewer `trig_01TvveuLCRL8QwbwuF52yd9Y` (live mode only), weekly digest
  `trig_01V9gJ6rL1sDuSsqDkE11oxo` (folded into the daily note). Manage all at https://claude.ai/code/routines.
- GitHub Apps installed by William on all his repos: Claude (routine push, PRs, webhooks) and the
  ChatGPT Codex Connector (automatic PR review is ON for this repo; it did not review probe PR #1, so
  the first real `radar/iter-*` PR shows whether it works).

## How a trip is judged (v2, D-57 onward; the formula is `radar/score.py`)

Two classes, kept distinct everywhere (gold border and label for "No day off needed"):
- **Needs a day off**: Fri off, Mon off, stat blocks; scanned 42 to 112 days out (approval lead time);
  departures from 19:30 the evening before through the end of day 1; home in Calgary by 16:00 on the
  last day off (hard).
- **No day off needed**: Fri from 17:30 or Sat morning out, home Sun by 16:00; 3 to 42 days out; near
  non-stop cities only (air time 3 h or less); basic fares allowed in both classes, carry-on priced in.

Pass 1, every trip, no AI. Score out of 100:
- **Price 45**: the complete trip for two (flights + room estimate at the season's good rate + transit)
  as a share of the route's *typical* trip from `config/references.yaml`: 45 points at 60% of typical
  or less, 25 at 75%, 0 at 100%, falling to −10 at 130% and on down (cheaper always ranks higher).
- **Time there 20**: hours awake = landing to take-off − 4.5 h airports − 10 h a night; 31 h = 20
  points for every class (the most a 3-day weekend can give); under 7.75 h the trip is dropped.
- **Convenience 10**: non-stop both ways 10; one stop 5 (layover ≤ 150 min) or 2; −2 airport > 45 min
  from downtown; −3 car needed; −2 outbound lands before 05:00; −3 fringe room after pass 2.
- **City 15**: rank/10 × 15. **Weather 10**: forecast within 15 days, else monthly normals; 10 minus
  1 per 3 °C outside 15–27 °C minus rain%/20, averaged over the days.
Candidate = flights at or under the route's *good* level and score ≥ 70 (per class in config).

Pass 2, candidates (max 3 a scan), SerpApi: Google Hotels and vacation rentals, 4–5 star, rating 4.3+,
listed neighbourhoods or within 6 km of the centre; cheapest acceptable option replaces the estimate;
price term recomputed. SerpApi self-cap 200 lookups a month (free tier 250); counter in
`data/serpapi_usage.json`. Pass 2b (routine): Sonnet subagent looks for Airbnb; a price counts only
with a concrete total and link.

Pass 3, survivors, Opus in `radar-daily`: what is on for those dates against `config/interests.yaml`
(hip-hop, R&B, jazz, Afrobeats; art, history, markets, nightlife, street festivals; concerts under $60
or $100 if famous; the "cannot get this in Calgary" test), each find scored uniqueness × fit ×
affordability, summed and capped at +10; cached 7 days in `data/research/`. Final ≥ 80 (per class)
and real lodging in hand = a hit: `hits/dry-run/` this month, `hits/` live; otherwise
`hits/near-miss/` with the whole breakdown.

## Data and storage (D-76, D-77; details in `docs/ASK.md`)

- `data/history/<date>.jsonl`: every logged trip (cheapest per airport pair plus the winner per
  city-weekend), with `components` and `inputs` behind the score. `<date>.csv`: the same, flat, one
  evidence line and points per criterion; `latest.csv`, `index.json`. About 0.5 MB a day in git.
- `data/latest.json`: what the page shows; every row carries `breakdown`. `data/series.json`: 30-day
  price lines per city and class. `data/weekly-summary.json`.
- `hits/candidates|near-miss|dry-run|`: one JSON per trip with all three passes, options and links.
- `config/references.yaml`: route ladders (typical / good / exceptional flights per person, rooms per
  night by season), with sources; `config/scoring.yaml`: weights, anchors, classes, thresholds, time
  rule; `config/cities.yaml`; `config/days_off.yaml` (from the panel); `config/interests.yaml`.
- Asking: open a Claude Code session in this folder and ask in plain words; `docs/ASK.md` guides it.

## Dashboard and panel

Order: Hits (with brief: flights link to Google Flights for the dates, Google Hotels link, one link per
lodging option, Airbnb link when found, what's on with reasons), Passed (every 70+ trip and the pass it
reached), Every city (best deal by score, the route's typical and exceptional, every weekend on tap,
price history per class), daily note; health behind the pulse button (coverage, requests of 900,
errors, blocked, candidates, lookups of 200); settings behind the gear (GitHub token once, cities on/off
and order, days-off calendar, trips: day-off lead weeks and weekend switch, per-class thresholds,
optional overall cap; Save commits to `config/`). Every score opens its breakdown on hover, focus or
tap. `table.html`: any day's scoring table, sort, filter, download.

## Open questions for William (defaults in place)

1. Weekend-only trips top out at 12.6 of 20 on time (20.5 h awake at best), so they need a
   near-exceptional price to reach 80; the per-class hit line in the panel is the knob if that feels too
   strict (D-78). Replayed over the 584 rows logged before D-78, the 7.75 h floor would drop 155
   trips (29 of 324 winners); `time_floor_share` is the knob.
2. Round-trip repricing is not built: fast-flights cannot price an exact leg pair, so totals are
   one-way sums, 3 to 15% above Google's headline for the same flights (D-61).
3. New Orleans stays on the list (no nonstop, no deal history, low confidence) by William's choice.
4. The 16-week upper bound for day-off trips is config, not in the panel.
5. `TICKETMASTER_KEY` secret is unused and can be deleted on GitHub.
6. Codex review on real PRs is unproven (probe PR got none); the reviewer-subagent fallback covers it.
7. "Would book / Not for me" taps for weight tuning: queued, not built (`data/labels.jsonl`).

## Gotchas

- Windows: `write_text` emits CRLF in a mostly-LF repo; check `git diff --stat` for whole-file changes.
  Backslashes in Bash heredocs get mangled; write scripts with the editor. Check pytest's exit code, not
  its last line.
- An offline scan (`python -m radar.main scan --offline --today 2026-10-08`) writes `data/` and `hits/`
  into the current folder: run it in a scratch copy with `config/` and `tests/fixtures/offline/`.
- The app sometimes says the folder is not a git repository and gives a side session no worktree; it is
  one: `git worktree add .claude/worktrees/<name> -b <name>` from the main checkout. Parallel sessions
  collide only on `docs/notes/decisions.md`, `HANDOFF.md`, `SESSION-LOG.md` (append-only, union-merge
  and renumber the D-entry).
- Playwright MCP is one shared instance (close it when done); its workspace root is
  `C:\Users\Owner\OneDrive\Documents\`, so screenshots land in `Documents\.playwright-mcp\`; open local
  servers as `localhost`, not `127.0.0.1`.
- The panel's GitHub token lives in `localStorage` on `williamebong.github.io`, shared by every project
  page on that account.
- SerpApi responses are cached per scan day by city and dates; after changing a city's neighbourhoods,
  delete that day's cache. The scan drops `data/cache/` before uploading the site.
- Give William times in Calgary local time; the logs and GitHub use UTC.

## How to verify

```
.venv\Scripts\python -m pytest -q                                   # 106, no network
gh run list -R WilliamEbong/spontaneous-travel-radar --limit 3       # scan ran? how long? failed?
python scripts\dashboard_fixtures.py <scratch>                       # four data states for the page
python -m http.server 8766 --directory <scratch>                     # then open localhost:8766
```
Then the live page: health (coverage ≥ 80%, no fetch errors, not blocked, scan under 30 h old), a
score panel on tap, the scoring table for today.

## Dates ahead

- Daily: 04:17 scan, 07:30 routine note. Mondays the note carries the week's summary.
- 2026-11-23 or so: first ladders refit may be proposed by the routine (needs 7+ scan days per city).
- 2026-12-08: `radar-daily`'s last run, month-one summary. 2026-12-09: `radar-tune` PR.
- After month one: switch the routine to Sonnet and a weekly cadence; decide live mode in the panel.
