# Tuning plan for 2026-12-09 (end of month one)

Executed by the one-shot routine `radar-tune` (instructions: `routine/PROMPT-tune.md`). Written so a
fresh run with no other context can carry it out. Goal: stop hand-tuning flight bands. Make them
follow each route's own prices, then tune the few remaining knobs against a fixed, offline metric.

## What exists on 2026-12-09

- `data/history/*.jsonl`: one file per scan day since 2026-11-09. Each row is one logged quote: the
  cheapest per airport per city-window plus each city-window's top scorer (D-12). Fields include
  `city`, `airport`, `window_id`, `out_dep`, `out_arr`, `back_dep`, `back_arr`, `stops_out`,
  `stops_back`, `flights_cad_2pax`, `price_pp`, `band`, `score`, `candidate`, `winner`. From
  2026-11-10 they also include `price_pts` (the price component of `score`) and `history_pct`. Rows
  from 2026-11-09 lack them: use those rows for band calibration only.
- `radar/score.py`: `flight_band`, `band_price_score`, `score_trip`, and the candidate rule.
  `radar/store.py: route_percentile` is the route percentile (14 scan days minimum).
  `radar/hits.py: gates` decides firing: score at or above `score_threshold`, `total_cad` within
  the city's `bar_cad`, plus re-alert checks.
- `config/scoring.yaml`: static `flight_bands` per group (`cities.yaml: flight_group`), `weights`,
  `score_threshold`, `hotel_bands`. `docs/iteration-log.md` and `docs/notes/decisions.md` say what
  the daily loop changed during the month.

## Order of work

1. Count scan days: `ls data/history/*.jsonl | wc -l`. If under 21 (scans were missed), run anyway,
   say so in the PR and the note, and open the PR as a draft.
2. Build the backtest harness (a). Commit.
3. Implement rolling-percentile bands (d), with tests. Commit.
4. Measure the baseline metric (b), then run the trial loop (c).
5. Open the PR and write the note (e).

## (a) Backtest harness: `scripts/backtest.py`

`python scripts/backtest.py [--config path/to/scoring.yaml] [--holdout-days 7] [--json]`. It reads
every `data/history/*.jsonl` plus `config/cities.yaml`, and the scoring config from `--config`
(default `config/scoring.yaml`). No network, under 10 seconds. It prints one line,
`metric=<float> mode=<labels|calibration> train=<float> holdout=<float> rows=<n> days=<n>`; with
`--json` it prints the full breakdown per route.

For every history row, re-derive what the variant config would have said that day:
- `band` from `price_pp` and the variant's bands for that route. With rolling bands (d), compute them
  from the rows of the trailing window strictly before that row's `scan_date`, never from the future.
- `history_pct` with `route_percentile` over prior scan days only, as the collector does.
- the price points with `band_price_score` and the history blend from `score_trip`;
  `new_score = score - price_pts + new_price_pts` (rows that have `price_pts`).
- `total_cad = flights_cad_2pax + lodging estimate (score.lodging_estimate_cad, nights from the
  out_arr/back_dep local dates) + 4 x transfer_cost_cad_pp_each_way`.
- `fires` = candidate rule and `new_score >= score_threshold` and `total_cad <= bar_cad`. Ignore
  re-alert in the backtest.

Reuse the functions in `radar/score.py` and `radar/store.py`; do not copy their logic. Holdout: the
last `--holdout-days` scan days are scored separately. `metric` is the train value, and the loop
optimizes only that.

## (b) The metric (chosen at run time)

- **Labels mode**, if `data/labels.jsonl` exists with 30 or more rows
  (`{ts, city, window_id, price_pp, label: "book"|"skip"}`, written by a future dashboard tap): join
  each label to the history row with the same `city` and `window_id` from the latest scan day on or
  before `ts`. Metric = F0.5 on `book` (precision weighted twice recall), where a positive
  prediction is `fires`. Higher is better.
- **Calibration mode** otherwise. Per route (city) over all rows, lower is better:
  - amazing rate: penalty = distance outside [1%, 5%] of rows;
  - good rate: penalty = distance outside [10%, 20%] of rows. The lower edges stop the loop from
    "winning" by making nothing fire, which is the day-one state;
  - one-stop amazing: share of `amazing` rows with `stops_out + stops_back > 0`, weight 1.0;
  - flip rate: for each (city, window_id), consecutive scan days where the cheapest row's band
    changes while its `price_pp` moved under 5%, weight 0.5.

  Metric = mean over routes of the four terms (the last two weighted). Report each term with
  `--json`.

## (c) The trial loop (keep or revert)

This follows the autoresearch pattern: a fixed harness, one editable surface, one scalar metric, a
fixed budget per trial, and keep or revert.
- Editable surface: `config/scoring.yaml` only. Harness, code and data are frozen once step 3 is
  committed.
- One parameter change per trial. 2-minute cap per trial (backtest run plus your reasoning); at most
  60 trials; stop early after 10 trials in a row without improvement.
- Keep a change only when the train metric improves (by 0.001 or more in calibration mode, 0.01 in
  labels mode). Otherwise revert the file (`git checkout -- config/scoring.yaml`).
- Log every trial to `docs/tuning-log.md`:
  `| # | change | train | holdout | kept |`.
- Candidates, in rough order: the rolling percentiles (amazing/good/average), the rolling window
  length (30 to 90 days), the history blend weight in the price score (once (d) makes it a config
  value), `score_threshold` (70 to 90), the `price` weight (30 to 50, others rescaled to keep the
  total 100).
- Guardrails: never edit `config/cities.yaml`, `days_off.yaml`, the window rule (leave 19:30 the
  evening before Day 1 to 23:59 Day 1, home by 16:00), `time_curve` (William's floor, D-51), request volume,
  or anything outside `config/scoring.yaml` during the loop. If the final holdout metric is worse
  than the baseline holdout, ship only (d) with the static seeds' best percentiles and say why.

## (d) Rolling-percentile flight bands (collector change, with tests)

- New `config/scoring.yaml` keys: `flight_band_mode: rolling` (or `static`),
  `rolling_bands: {amazing: 10, good: 25, average: 50}` (percentiles), `rolling_window_days: 60`,
  `rolling_min_days: 14`, `history_blend: 0.5` (the weight `score_trip` gives `history_pct`).
  Add them to `Scoring` in `radar/config.py`, with defaults that reproduce today's behaviour.
- A route's bands = those percentiles of its own `price_pp` over the trailing
  `rolling_window_days`, from history before today. Until a route has `rolling_min_days` scan days,
  use its static `flight_bands` group (the seeds stay as the fallback). Enforce
  amazing < good < average with at least 1 CAD between them.
- Compute once per scan in `radar/main.py` next to `route_percentile`, and pass the per-route bands
  into `score_trip` so `flight_band` and `band_price_score` use them. Same code path in the backtest.
- Tests: fallback below 14 days; percentiles from known rows; never uses today's or future rows;
  ordering enforced; `static` mode unchanged (existing tests stay green).
- Stay out of `radar/windows.py`, `radar/flights.py`, `config/days_off.yaml`, `index.html` and
  `site/` unless they are already merged on `main` and the change truly needs them.

## (d2) Round-trip reprice for candidates only (if `radar-daily` has not shipped it)

The one-way sums we scan with run above what William sees in Google. Evidence (2026-11-09):
- YYC-YYZ, Air Canada, Nov 27 out, Dec 6 back, 1 adult, carry-on, no basic: one-way sum
  417 + 402 = 819, round-trip query 793 (3% lower). Google's own headline for those flights was 708
  (Standard fare, carry-on included).
- LAS (day-one smoke test, two adults): round trip 1,778 vs one-way sum 2,050 (13% lower).
- So the sums run about 10 to 15% above Google's headline.

Check `docs/iteration-log.md`. If no `radar/iter-*` PR shipped this, add it on the tune branch as its
own commit after (d) and before the loop: for candidates only, before the hotel check, one
fast-flights round-trip query for the same flights, counted inside the existing scan budget. Use the
lower of the two prices in the brief and the trip total; keep one-way sums for scanning, bands,
scores and history, so the backtest is unaffected. Test with a fixture round-trip payload. If
`radar/flights.py` has unmerged work from another session, skip this and say so in the PR.

## (e) Deliverable

- One branch and PR, `radar/tune-2026-12-09`, into `main`. Body: data span (scan days, rows),
  metric mode, baseline and final metric (train and holdout), the kept trials (table from
  `docs/tuning-log.md`), the `config/scoring.yaml` diff, the band change and how to undo
  (`flight_band_mode: static`). Draft if under 21 scan days (step 1).
- Codex should review on PR open. In the same run, also start a fresh-context reviewer subagent on
  the full diff, fix what it confirms, and post its summary as a PR comment (the same fallback
  `radar-daily` uses). William merges; no other routine runs after it.
- Note `data/digests/2026-12-09.md` (`# Tuning run 2026-12-09`, at most 15 lines), the
  `data/digests/index.json` refresh, and one line in `docs/iteration-log.md`. Push those straight
  to `main`; if pushing fails, email the note to williamebong@gmail.com instead.

## Known bias: holiday fares

The month-one history covers trip windows up to 45 days ahead, so it includes Christmas and New
Year windows (departures 2026-12-18 to 2027-01-04), when fares are inflated. Left in, they push
percentile bands up, so January fares look better than they are. In the backtest and in the
rolling-band computation, exclude rows whose `window_id` date falls in 2026-12-18 to 2027-01-04
(make the excluded date range a config list, `band_exclude_ranges`, so next year can reuse it).
Also report the metric with them included, so the effect is visible. The 60-day rolling window
works the remaining bias out by mid-February.
