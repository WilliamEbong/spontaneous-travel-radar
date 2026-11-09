# Month one: the learning run

From 2026-11-09 to about 2026-12-09 the radar collects, scores and logs every day, but sends no
alerts (`config/scoring.yaml: mode: dry-run`). The goal is to tune the scoring on real data before
anything is allowed to interrupt you.

## Every day (automatic, no Claude)

- The `scan` workflow runs at 10:17 UTC (03:17 MST), commits `data/` and `hits/dry-run/`, and
  redeploys the dashboard: https://williamebong.github.io/spontaneous-travel-radar/
- Check the Health panel now and then: coverage above 80%, no "Blocked by Google", SerpApi under 60.

## Every Monday (15 minutes)

1. The weekly digest routine runs at 07:00 Calgary time and writes a 15-line review
   (see `routine/CAPABILITIES.md` for where it lands: `data/digests/` or your inbox).
2. Open the dashboard and the digest side by side. Look at "Would have fired": would you really have
   booked those? Look at the band pills in "Best right now": is everything "bad" (bands too tight)
   or everything "amazing" (too loose)?
3. Edit `config/scoring.yaml` (bands, weights, `score_threshold`) and, if a city is too easy or too
   hard to trigger, its `bar_cad` in `config/cities.yaml`. Commit with a one-line reason.
   Optional: open a Claude session in this folder for the edit; it costs one short session.

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

- Disable the weekly digest routine after its fourth run (it also stops itself: from the fifth
  Monday it only replies "month one is over").
- No daily Claude runs exist. The hit routine stays disabled until you go live.
