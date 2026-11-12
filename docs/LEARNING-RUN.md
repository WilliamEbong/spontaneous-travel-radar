# The learning run

Since 2026-11-09 the radar collects, scores and logs every day, but sends no alerts
(`config/scoring.yaml: mode: dry-run`). It has no end date (D-82): it keeps running, and from about
2026-11-22 it tunes its own price judgment every night (below). Going live with email stays your
decision. The goal is to tune the scoring on real data before anything is allowed to interrupt you.

Since v2 (D-57 to D-72) every trip is judged against what its own route normally costs
(`config/references.yaml`), and the month also exercises the two closer looks on real candidates:
pass 2 (real hotels and rentals within about 20 minutes of the centre, at most three a day, 2 SerpApi
lookups each) and pass 3 (the daily routine researches what is on for those dates against
`config/interests.yaml`). Learning-run hits land in `hits/dry-run/`, near misses in `hits/near-miss/`;
nothing is emailed. Expect most days to have no candidate at all: quiet is correct.

## Every day (automatic)

- The `scan` workflow runs at 10:17 UTC (03:17 MST), commits `data/` and `hits/dry-run/`, and
  redeploys the dashboard: https://williamebong.github.io/spontaneous-travel-radar/
- The `radar-daily` routine (Opus 5.5) runs at 14:30 UTC (07:30 Calgary) every day, with no end
  date. It merges or drops yesterday's change after reading Codex's review, runs pass 3 on today's
  candidates, checks the data, runs the nightly self-tuning step, makes at
  most one change as a pull request, writes a short note to `data/digests/<date>.md` (shown on the
  dashboard), and logs one line in `docs/iteration-log.md`. Most days it changes nothing.
  Prompt and rules: `routine/PROMPT-daily.md`.
- Check the Health panel now and then: coverage above 80%, no "Blocked by Google", SerpApi under 200.
- Two kinds of trip are scanned (D-52). Day-off trips start 6 weeks out (change it in Settings, 2 to
  12 weeks) so you can both get the time approved. Weekend-only trips run the next 6 weeks, leave
  Friday after 5:30 pm, come home Sunday by 4 pm, non-stop and short hops only. Both classes use the
  same lines (70 for a closer look, 80 for a hit), each with its own switch and hit line in Settings.
  Weekend trips are the gold ones on the page ("No day off needed").

## Every Monday (15 minutes)

1. The Monday note from `radar-daily` is the weekly digest: up to 20 lines with the week's summary
   and two config changes to consider.
2. Open the dashboard and the digest side by side. Look at the hits and the Passed list: would you
   really have booked those? Open a brief: are the lodging and the what's-on finds the kind you would
   pick? Look at the ladder pills on the city cards: is everything "above typical" (ladders too low) or
   everything "exceptional" (too high)?
3. Look over the week's pull requests and `docs/iteration-log.md`. To undo a merged change, revert
   its commit; each PR body says how. You can still edit `config/scoring.yaml` or
   `config/cities.yaml` yourself; the routine reads the decisions log before changing anything.

## Exit checklist (all must hold before going live)

- [ ] 21+ days of history for every city (`data/history/` has 21+ files; each city's price
      history on the dashboard has 21+ points).
- [ ] Dry-run hits and near misses reviewed: false positives understood and fixed by tuning.
- [ ] Route ladders checked against the data (they roll from each route's own fares since D-82).
- [ ] Pass 2 ran on at least 3 candidates, and one total was checked by hand against Google Hotels.
- [ ] Pass 3 ran on at least 3 candidates, and its what's-on finds looked right to you.
- [ ] `data/serpapi_usage.json` stayed under the cap (200) every month.
- [ ] Coverage in Health consistently above 80%.

## Going live

1. Set `mode: live` in `config/scoring.yaml` and commit.
2. Enable the hit routine (`radar-hit`, link in `README.md`) at https://claude.ai/code/routines.
3. Test the trigger once: commit a dummy `hits/test.json` copied from any dry-run hit, confirm the
   routine fires exactly once (its run list), then delete the dummy file. If the webhook could not
   be created (see `routine/CAPABILITIES.md`), run the routine by hand when the dashboard shows a hit.

## Self-tuning (every night, permanent, D-82)

This replaces the one-time tune of 2026-12-09. Rules: `docs/TUNING-PLAN.md`.
- 2026-12-08: `radar-daily` writes a one-time month-one summary. It ends nothing: everything carries on.
- Every route's flight ladder follows its own last 60 days of fares once it has 14 scan days
  (`ladder_mode: rolling`; the static ladders stay until then; Christmas and New Year weekends,
  2026-12-18 to 2027-01-04, never feed a ladder). `ladder_mode: static` undoes it.
- Each night, once 14 scan days exist (until then the note says "collecting, N of 14 days"), the routine
  runs `scripts/tune_loop.py`: 16 small changes to the price judgment, each replayed offline over the
  whole history. One number decides: how often the radar's "good" and "closer look" calls landed near
  the lowest fare each weekend went on to show, scored on everything but the last 7 scan days, which are
  kept aside as a check. A change is kept only if it wins by a clear margin without calling far more or
  far fewer trips good; otherwise it is reverted.
- Kept changes go live on their own as one `tune:` commit a night on `main` (`auto_apply: true` in
  `config/tuning.yaml`; `false` turns them into pull requests for you). Every trial is in
  `docs/tuning-log.md`. To undo one, revert its commit and list its key under `frozen` in
  `config/tuning.yaml` so it is not learned again.
- What it may change: what counts as a good and a normal fare (ladder percentiles and look-back), the
  price curve's three steps, and each class's closer-look line. Never your hit line, the time rule,
  the cap, `mode`, the trip rules, cities or interests. The other weights (time there, city,
  convenience, weather) stay frozen until your "book / skip" taps reach 30 (`data/labels.jsonl`, a
  future dashboard button); then the taps count for half of the number.
- Mondays: the weekly digest says in plain words what was kept that week and how the number moved.

## Usage guard

- One Opus run a day (`radar-daily`), told to stop as soon as there is nothing to do; no end date
  (D-82). The self-tuning inside it is plain Python, a few seconds of compute.
- The old weekly digest routine is disabled once `radar-daily` is on (its Monday note replaces it).
- The hit routine stays disabled until you go live.
- Superseded by D-82: the old plan to switch `radar-daily` to Sonnet and a weekly cadence, or disable
  it, after month one. It stays daily so the self-tuning gets a night every day.
