# Self-tuning: the permanent loop (D-82)

William, 2026-11-12: the radar must never stop, and it should keep improving itself the way Karpathy's
autoresearch does: a fixed harness, one editable surface, one number to improve, a fixed budget per experiment,
keep the change if the number improves and revert it if not, forever, with the human editing only the
instructions. He will not look at travel until February, so the loop runs unattended. This replaces the one-time
2026-12-09 retune (`radar-tune`, whose prompt is now a stub that stops) and the 2026-12-08 stop of `radar-daily`.
The one-time plan is in git history (this file before D-82).

## Where it runs, and why

Inside the daily routine `radar-daily` (section T of `routine/PROMPT-daily.md`), as one deterministic command:
`python scripts/tune_loop.py --date <date>`. Not as a step after the scan in Actions, because:
- the scan stays isolated: a tuning bug can never cost a day's scan, and `.github/workflows/` stays untouched;
- the routine already pushes to `main`, opens pull requests and writes the note that reports the loop;
- the routine can propose up to three trials of its own (`--try key=value`), autoresearch's agent step, while the
  arithmetic, the keep-or-revert rule and the file edits stay in code (constitution II). Its proposals may draw only
  on the train columns of `docs/tuning-log.md`, never on the last 7 scan days it reads for its analysis, since those
  are the holdout;
- GitHub's scheduler starts the scan 7 to 10 hours late (D-74, D-79), so the routine often runs before today's scan.
  That does not matter: the loop replays whatever history is on `main` and never assumes today's scan exists.
The harness is plain Python with no network, so moving it into Actions later is one workflow step.

## What it learns from

`data/history/<day>.jsonl`, one file per scan day: the cheapest trip per airport per city-weekend plus each
city-weekend's top scorer (`winner`), with `components` and `inputs` since D-76 and `share`, `total_cad` since v2.
The 2026-11-09 rows are v1 (no `share`): they feed the ladders and the lows, not the judgements.
Day-off weekends are priced every third day while they are 112 to 42 days out (secondary airports every ninth);
weekend-only trips every day while they are 42 to 3 days out. So a weekend's "eventual low" is the lowest fare the
radar saw while it was scanning that weekend, not the fare on the day of departure.

## (a) The harness: `scripts/backtest.py`

`python scripts/backtest.py [--config config/scoring.yaml] [--references config/references.yaml]
[--until YYYY-MM-DD] [--holdout-days 7] [--json]`. Offline, deterministic, no network. For every logged winner it
re-derives what the given config would have said that day, reusing `radar/score.py` and `radar/store.py`:
- the route's flights ladder: `rolling_flights` over the rows before that row's scan day (never its own day or
  later), or the static ladder in `config/references.yaml`;
- the typical trip from that ladder, the row's nights and the season of its check-in (`typical_trip_cad`), then the
  price component of the logged complete trip (`price_component`); the other four components are the logged ones
  (scaled if a weight changed), so the replayed score is `price + the rest`;
- called good: flights per person at or under the ladder's `good`; sent for a closer look: `is_candidate` with the
  class's `candidate_threshold`.
Under the live config it reproduces the logged winners' scores: 412 of 414 exactly on the four scan days to
2026-11-12, the other two one point off at a .5 rounding edge (components are stored to two decimals), and every
logged candidate decision. It prints one line,
`score=<train> mode=<hindsight|blend> train=… holdout=… rows=… days=…`, and one line per set with the parts;
`--json` prints everything. `--until` replays the history as it stood on that day. Under a second on 3 days of data.

## (b) The number: the hindsight price score

One judgement = one logged winner (the trip the radar shows for a city-weekend on a scan day), judged again as above.

- **Near the eventual low**: the winner's flights per person are at most 1.10 x the lowest winner fare that weekend
  showed on any scan day in the data being scored.
- **Unfinished weekends**: a weekend still being scanned counts with its low so far, once it has been priced on 3 or
  more scan days; with fewer it is left out. Every night scores from scratch, so a later, lower fare turns an earlier
  "right" call into a "wrong" one for every config alike: configs are only ever compared on the same data the same
  night, never across nights.
- **Two terms, each F0.5** = 1.25 TP / (1.25 TP + 0.25 FN + FP), where TP = flagged and near the low, FP = flagged
  but not near it, FN = near the low but not flagged:
  - *deal*: the flag is "sent for a closer look" (the trips that can become hits);
  - *ladder*: the flag is "called good or better".
  F0.5 leans on precision: a flag that proved wrong costs four times a low that was missed, because William wants
  rare calls he can trust.
- **Score** = 50 x (deal + ladder), 0 to 100, higher is better.
- **Holdout**: the most recent 7 scan days. **Train**: every earlier scan day, scored as if the history ended on the
  last train day (its lows and its 3-day rule use train rows only). Nothing from the holdout days, neither their
  judgements nor their fares, reaches the train score. The holdout score judges the last 7 days against the lows of
  all data. Trials are kept or reverted on the train score alone; the holdout can only veto a whole night (c).
- **Guardrails** (train): the share of judged trips called good or better must stay within 5% to 30%, the share sent
  for a closer look within 0.5% to 3% (a few a week across all routes). A trial may not move either share further
  outside its band than the current config has it, so it cannot win by flagging everything or nothing; a config
  already outside a band may only move toward it.
- **Noise margin**: a trial is kept only when it beats the current train score by 1.0 point or more. Smaller moves
  are a few judgements flipping, which the data cannot tell from noise.
- **Labels** (once `data/labels.jsonl`, `{ts, city, window_id, price_pp, label: "book"|"skip"}` from a future
  dashboard tap, has 30 or more rows): a labels term, F0.5 on "book" with "sent for a closer look" as the
  prediction, each tap joined to the winner judged for its city and window on the latest scan day on or before the
  tap; it falls in train or holdout by that day. The score becomes the mean of the hindsight score and the labels
  term, and the taste weights unlock (c).
- **Stored with its inputs and parts**: `data/tuning/runs.jsonl`, one line a night: the data span (scan days, first
  and last day, train and holdout spans, rows, labels), the rules (1.10, 3 days, F0.5, 7 days), the start and final
  settings with their score and every part for train and holdout (TP, FP, FN, precision, recall, F, the two shares,
  judgements, lows), and every trial's move, the value it replaced, the parts before and after, kept or not and why.
  A re-run scan replaces its day's file, so each line also stores fingerprints: the code's git commit and hashes of
  `config/references.yaml` (static ladders, rooms), `config/cities.yaml` and the history files read. When they match,
  `scripts/backtest.py --until <span end>` with a config holding those settings reproduces the stored score without
  fetching anything.

## (c) The nightly trial loop: `scripts/tune_loop.py`

- **Start guard**: fewer than 14 scan days in `data/history/` (about 2026-11-22 if every scan lands): it prints
  `collecting, N of 14 days` and writes nothing. Expect the score to sit at 0 for about a week after that: the rolling
  ladders need 14 days before a judgement's own day and the train set excludes the last 7, so train judgements use the
  static ladders, which call nothing good today, until about 22 scan days (around 2026-11-30). Every trial is
  reverted until then; that is correct.
- **The editable surface** (`python scripts/tune_loop.py --surface` prints it with the current values), one key one
  step per trial, within William's bounds:

  | key | bounds | step |
  |---|---|---|
  | `rolling_ladder.good` (percentile) | 15 to 35 | 5 |
  | `rolling_ladder.typical` (percentile) | 40 to 60 | 5 |
  | `rolling_window_days` | 30 to 90 | 15 |
  | `price_curve.share_0` (full points at or under) | 0.50 to 0.70 | 0.05 |
  | `price_curve.share_1` (the middle step) | 0.65 to 0.85 | 0.05 |
  | `price_curve.share_2` (no points) | 0.95 to 1.05 | 0.05 |
  | `dayoff.candidate_threshold`, `weekend.candidate_threshold` | 65 to 80 | 2 |
  | the five `weights`, only once 30 labels exist: two traded by 2 points, the total stays 100 | price 40-50, time 15-25, convenience 5-15, city 10-20, weather 5-15 | 2 |

  The price-curve shares stay in rising order and the ladder percentiles above `exceptional`. A key William set
  outside its bounds by hand is left alone, as is any key listed under `frozen` in `config/tuning.yaml`. Never on the
  surface: `hit_threshold` (William's line), `cap_cad`, `mode`, `time_rule`, the price curve's points, fourth pair
  and `floor`, `rolling_ladder.exceptional` (a label on the page; it changes no closer look), `rolling_min_days`,
  `ladder_exclude_ranges`, `ladder_mode` (William's undo), the trip classes' ranges and rules,
  `config/references.yaml`, `cities.yaml`, `interests.yaml`, `days_off.yaml`, code.
- **A night**: `trials_per_night` (16 in `config/tuning.yaml`, 10 to 20) trials. The routine's `--try` proposals go
  first (refused if off the surface or out of bounds); then one-step moves from the current config, the least-tried
  key first, rotated by the date. Each trial replays the whole history and is kept when the train score is at least
  1.0 above the current one with both guardrails holding and the replay under 2 minutes; otherwise it is reverted.
  The next trial starts from the current config (hill climbing). A trial over 2 minutes ends the night.
- **Holdout veto**: if the night's final holdout score is more than 1.0 below its starting one, the whole night is
  undone and nothing changes. This is the only use of the holdout.
- **Writes**: one row per trial and one per night in `docs/tuning-log.md` (change, score before and after, holdout
  before and after, the parts, kept or reverted and why); one line in `data/tuning/runs.jsonl`; and, when something
  was kept, only the changed lines of `config/scoring.yaml`, comments kept, written through a temp file and read
  back before it counts; on any failure (for example a line rewritten by hand into a shape it cannot edit) the old
  bytes go back, the night is still logged with the error, and nothing changes. `--date` makes a second run the
  same day a no-op (`already ran`).
- **Going live** (`auto_apply` in `config/tuning.yaml`): `true` (William's choice) makes the routine commit
  `config/scoring.yaml` alone on `main` as `tune: <date>: <changes> (score a → b)`; one `git revert` undoes the
  night. A night's kept changes share one commit because two can touch the same line, and one commit is what one
  revert can always undo. `false` puts the same commit on `radar/tune-<date>` and opens a PR for William; the routine
  skips the loop while one is open.
- **Undo and stop**: revert the `tune:` commit, then add its key to `frozen` so the loop does not learn it again.
  Freezing every key stops the loop without touching anything else; `ladder_mode: static` drops the rolling ladders.
- **Monday note**: `python scripts/tune_loop.py --summary --date <date>` prints the week in plain words (what was
  kept, the score at the start and end of the week, on train and on the holdout); the routine copies it in.

## (d) Rolling ladders (built, D-82)

- `config/scoring.yaml`: `ladder_mode: rolling`, `rolling_ladder: {exceptional: 10, good: 25, typical: 50}`
  (percentiles of `price_pp`), `rolling_window_days: 60`, `rolling_min_days: 14`,
  `ladder_exclude_ranges: [[2026-12-18, 2027-01-04]]`. The `Scoring` defaults reproduce `static`.
- Per route, both trip classes, every logged row in the window before the scan day, excluding rows whose weekend
  starts inside an excluded range; nearest-rank percentiles (the weekly summary's); exceptional < good < typical with
  at least 1 CAD between them. Until a route has 14 scan days in the window, its static ladder is used.
- `radar/store.py: rolling_flights` is the one function: the scan rolls the refs once per scan in `radar/main.py`
  (pass 1, pass 2, the page's ladder), the backtest per row's scan day. Rooms stay static. Every trip's `inputs`
  carry the `flights_ladder` it was judged by, since that ladder now moves daily.
- Tests: `tests/test_rolling_ladders.py` (static mode, the 14-day fallback, known percentiles, never today or later,
  the window bound, excluded windows, rung order, config validation).

## Known bias: holiday fares

The history includes Christmas and New Year windows, when fares are inflated; left in, they would push the ladders
up so that January fares look better than they are. `ladder_exclude_ranges` keeps 2026-12-18 to 2027-01-04 out of
the ladders; add next year's range each December. Those weekends are still judged and scored like any other.

## Not built

- The variant does not re-pick each weekend's winner: the logged winner is fixed and only its judgement moves.
- The one-time plan's report of how the month's hits and near misses would score under a variant.
