# Tuning plan for 2026-12-09 (end of month one)

Executed by the one-shot routine `radar-tune` (instructions: `routine/PROMPT-tune.md`). Written so a
fresh run with no other context can carry it out. Goal: stop hand-tuning route ladders. Make each route's
flight ladder follow its own prices, then test the price anchors and the few other knobs against a fixed,
offline metric. (Rewritten for the v2 deal model, D-57 to D-72; the v1 band version is in git history.)

## What exists on 2026-12-09

- `data/history/*.jsonl`: one file per scan day since 2026-11-09. Each row is one logged quote: the
  cheapest per airport per city-window plus each city-window's top scorer (`winner`, D-12). Fields include
  `city`, `airport`, `window_id`, `trip_class`, `out_dep`, `out_arr`, `back_dep`, `back_arr`, `stops_out`,
  `stops_back`, `flights_cad_2pax`, `price_pp`, `score`, `candidate`, `price_pts`, `history_pct`. From the
  first scan of the v2 branch they also carry `ladder`, `share`, `total_cad` (pass-1 complete trip),
  `nights`, `pass`, `final_score` (always null in history) and `candidate_id`. Older rows have `band`
  instead of `ladder` and no `share`: use them for fare percentiles only.
- `hits/candidates/*.json` (pass 2), `hits/near-miss/*.json` and `hits/dry-run/*.json` (pass 3): the
  month's candidates with their real lodging, what's-on points and final scores. `hits/index.json` lists
  them with their stage.
- `radar/score.py`: `price_points`, `price_component`, `typical_trip_cad`, `ladder_label`, `score_trip`,
  `is_candidate`, `rescore`. `radar/store.py: route_percentile`. `radar/hits.py: finalize`.
- `config/references.yaml` (route ladders), `config/scoring.yaml` (weights, `price_curve`, per-class
  `candidate_threshold` and `hit_threshold`, `cap_cad`). `docs/iteration-log.md` and
  `docs/notes/decisions.md` say what the daily loop changed during the month.

## Order of work

1. Count scan days: `ls data/history/*.jsonl | wc -l`. If under 21 (scans were missed), run anyway,
   say so in the PR and the note, and open the PR as a draft.
2. Build the backtest harness (a). Commit.
3. Implement rolling ladders (d), with tests. Commit.
4. Measure the baseline metric (b), then run the trial loop (c).
5. Open the PR and write the note (e).

## (a) Backtest harness: `scripts/backtest.py`

`python scripts/backtest.py [--config path/to/scoring.yaml] [--references path/to/references.yaml]
[--holdout-days 7] [--json]`. It reads every `data/history/*.jsonl` plus `config/cities.yaml`, no network,
under 10 seconds. It prints one line,
`metric=<float> mode=<labels|calibration> train=<float> holdout=<float> rows=<n> days=<n>`; with
`--json` the full breakdown per route.

For every v2 history row (it has `share` and `total_cad`), re-derive what the variant would have said that day:
- the ladder label from `price_pp` and the variant's flights ladder for that route (rolling ladders, (d),
  are computed from rows strictly before that row's `scan_date`, never from the future);
- the typical trip T from the variant's ladders and the row's `nights` (`typical_trip_cad` needs a
  check-in date for the season: use `out_arr`'s date);
- the new price points with `price_component(total_cad, T, s)`; `new_score = score - price_pts + new`;
- `candidate` = `is_candidate(price_pp, new_score, good, candidate_threshold[class])`.
Reuse the functions in `radar/score.py`; do not copy their logic. Holdout: the last `--holdout-days` scan
days are scored separately. `metric` is the train value, and the loop optimizes only that.

## (b) The metric (chosen at run time)

- **Labels mode**, if `data/labels.jsonl` exists with 30 or more rows
  (`{ts, city, window_id, price_pp, label: "book"|"skip"}`, a future dashboard tap): join each label to the
  history row with the same `city` and `window_id` from the latest scan day on or before `ts`. Metric =
  F0.5 on `book` (precision weighted twice recall), where a positive prediction is `candidate`. Higher is
  better.
- **Calibration mode** otherwise. Per route over all v2 rows, lower is better:
  - exceptional rate: penalty = distance outside [1%, 5%] of rows labelled `exceptional`;
  - good-or-better rate: penalty = distance outside [10%, 25%];
  - candidate rate: penalty = distance outside [0.5%, 3%] of winners (a few closer looks a week across
    all routes, never none and never a flood);
  - one-stop exceptional: share of `exceptional` rows with `stops_out + stops_back > 0`, weight 1.0;
  - flip rate: for each (city, window_id), consecutive scan days where the cheapest row's label changes
    while its `price_pp` moved under 5%, weight 0.5.
  Metric = mean over routes. Report each term with `--json`.
- Also report, not optimized: how the month's pass-3 results (hits and near misses) would score under the
  variant, so William sees whether a change would have turned a near miss into a hit or the reverse.

## (c) The trial loop (keep or revert)

A fixed harness, one editable surface, one scalar metric, a fixed budget per trial, keep or revert.
- Editable surface: `config/scoring.yaml` and the flights ladders in `config/references.yaml` (through the
  rolling settings of (d), not by hand). Harness, code and data are frozen once step 3 is committed.
- One parameter change per trial. 2-minute cap per trial; at most 60 trials; stop after 10 in a row
  without improvement. Keep a change only when the train metric improves (by 0.001 in calibration mode,
  0.01 in labels mode); otherwise revert the files (`git checkout -- config/`).
- Log every trial to `docs/tuning-log.md`: `| # | change | train | holdout | kept |`.
- Candidates, in rough order: the rolling percentiles for exceptional/good/typical, the rolling window
  (30 to 90 days), the price anchors in `price_curve.points` (each share moved by at most 0.05, points
  order kept; William's 60/75/100 are the start and must stay within 0.50-0.70, 0.65-0.85 and 0.95-1.05),
  `candidate_threshold` (65 to 80), the `price` weight (40 to 50, others rescaled to keep 100).
- Guardrails: never edit `config/cities.yaml`, `days_off.yaml`, `interests.yaml`, the room ladders, the
  trip classes' date ranges and hard rules, `enabled`, `hit_threshold` (William's line), `cap_cad`,
  `time_rule` (D-next), request volume, or anything outside `config/` during the loop. If the final
  holdout metric is worse than the baseline holdout, ship only (d) with the static ladders' best
  percentiles and say why.

## (d) Rolling ladders (collector change, with tests)

- New `config/scoring.yaml` keys: `ladder_mode: rolling` (or `static`), `rolling_ladder: {exceptional: 10,
  good: 25, typical: 50}` (percentiles of `price_pp`), `rolling_window_days: 60`, `rolling_min_days: 14`,
  `ladder_exclude_ranges: [[2026-12-18, 2027-01-04]]`. Add them to `Scoring` with defaults that reproduce
  today's behaviour (`static`).
- Percentiles are per route over both trip classes (both allow basic fares since v2), from history
  before today, excluding rows whose window starts inside an excluded range. Until a route has
  `rolling_min_days` scan days, use its static ladder from `config/references.yaml`. Enforce
  exceptional < good < typical with at least 1 CAD between them.
- Compute once per scan in `radar/main.py` and pass a `Reference` with the rolled flights ladder into
  `score_trip`; the room ladders stay static. Same code path in the backtest.
- Tests: fallback below 14 days; percentiles from known rows; never uses today's or future rows; ordering
  enforced; `static` mode unchanged (existing tests stay green).
- Stay out of `radar/windows.py`, `radar/flights.py`, `config/days_off.yaml`, `index.html` and `site/`.

The round-trip reprice of the v1 plan (d2) is dropped: fast-flights 3.1.0 cannot price an exact leg pair
(D-61).

## (e) Deliverable

- One branch and PR, `radar/tune-2026-12-09`, into `main`. Body: data span (scan days, rows), metric mode,
  baseline and final metric (train and holdout), the kept trials (table from `docs/tuning-log.md`), the
  config diff, how the month's hits and near misses would change, and how to undo (`ladder_mode: static`).
  Draft if under 21 scan days (step 1).
- Codex should review on PR open. In the same run, also start a fresh-context reviewer subagent on the
  full diff, fix what it confirms, and post its summary as a PR comment. William merges; no routine runs
  after it.
- Note `data/digests/2026-12-09.md` (`# Tuning run 2026-12-09`, at most 15 lines), the
  `data/digests/index.json` refresh, and one line in `docs/iteration-log.md`. Push those straight to
  `main`; if pushing fails, email the note to williamebong@gmail.com instead.

## Known bias: holiday fares

The month-one history covers trip windows from 3 days to 16 weeks ahead, so it includes Christmas and New
Year windows (2026-12-18 to 2027-01-04), when fares are inflated. Left in, they push ladder percentiles up,
so January fares look better than they are. Exclude them through `ladder_exclude_ranges`, and also report
the metric with them included, so the effect is visible. The 60-day rolling window works the remaining
bias out by mid-February.
