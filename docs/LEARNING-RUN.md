# Month one: the learning run

From 2026-11-09 to about 2026-12-09 the radar collects, scores and logs every day, but sends no
alerts (`config/scoring.yaml: mode: dry-run`). The goal is to tune the scoring on real data before
anything is allowed to interrupt you.

## Every day (automatic)

- The `scan` workflow runs at 10:17 UTC (03:17 MST), commits `data/` and `hits/dry-run/`, and
  redeploys the dashboard: https://williamebong.github.io/spontaneous-travel-radar/
- The `radar-daily` routine (Opus 5.5) runs at 12:30 UTC (05:30 Calgary), 2026-11-10 to 2026-12-08.
  It merges or drops yesterday's change after reading Codex's review, checks today's data, makes at
  most one change as a pull request, writes a short note to `data/digests/<date>.md` (shown on the
  dashboard), and logs one line in `docs/iteration-log.md`. Most days it changes nothing.
  Prompt and rules: `routine/PROMPT-daily.md`.
- Check the Health panel now and then: coverage above 80%, no "Blocked by Google", SerpApi under 60.

## Every Monday (15 minutes)

1. The Monday note from `radar-daily` is the weekly digest: up to 20 lines with the week's summary
   and two config changes to consider.
2. Open the dashboard and the digest side by side. Look at "Would have fired": would you really have
   booked those? Look at the band pills in "Best right now": is everything "bad" (bands too tight)
   or everything "amazing" (too loose)?
3. Look over the week's pull requests and `docs/iteration-log.md`. To undo a merged change, revert
   its commit; each PR body says how. You can still edit `config/scoring.yaml` or
   `config/cities.yaml` yourself; the routine reads the decisions log before changing anything.

## Exit checklist (all must hold before going live)

- [ ] 21+ days of history for every city (`data/history/` has 21+ files; the dashboard's
      "vs history" column shows percentiles instead of "building").
- [ ] Dry-run hits reviewed: false positives understood and fixed by tuning.
- [ ] Flight bands and per-city `bar_cad` adjusted from the data.
- [ ] The hotel check ran on at least 3 dry-run candidates, and one total was checked by hand
      against Google Hotels.
- [ ] `data/serpapi_usage.json` stayed under the cap every month.
- [ ] Coverage in Health consistently above 80%.

## Going live

1. Set `mode: live` in `config/scoring.yaml` and commit.
2. Enable the hit routine (`radar-hit`, link in `README.md`) at https://claude.ai/code/routines.
3. Test the trigger once: commit a dummy `hits/test.json` copied from any dry-run hit, confirm the
   routine fires exactly once (its run list), then delete the dummy file. If the webhook could not
   be created (see `routine/CAPABILITIES.md`), run the routine by hand when the dashboard shows a hit.

## Usage guard

- One Opus run a day (`radar-daily`), told to stop as soon as there is nothing to do. Outside
  2026-11-10 to 2026-12-08 it only replies "out of window".
- The old weekly digest routine is disabled once `radar-daily` is on (its Monday note replaces it).
- The hit routine stays disabled until you go live.
- End of month one (about 2026-12-08): switch `radar-daily` to Sonnet 5.5 (`claude-sonnet-5-5`)
  and a weekly cadence (cron `30 12 * * 1`, Mondays only), and move its window dates forward, or
  disable it.
