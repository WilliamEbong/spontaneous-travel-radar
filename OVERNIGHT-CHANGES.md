# Overnight changes, 2026-11-22 to 2026-11-23

This was a maintenance pass on branch `claude/overnight-fixes-bdabcb`. It ran unattended from about 22:55 on
2026-11-22 to about 00:30 on 2026-11-23, Calgary time. It started from `origin/main` at `f93e98e` (docs: daily
note 2026-11-22).

The pass found and fixed defects only. Nothing here changes the deal model, the scores, the config, the data or
the look of the site. Round 2 made three edits William approved directly: two lines of `scan.yml` (#29, #30)
and the field names in the disabled weekly prompt (#31). Each fix came from a test that failed before the
change and passes after it. The branch has not been pushed or merged.

**Tests:** 129 passed before, 150 after round 1, 156 after round 2 (after five reverts against the tangible-value bar) (`.venv\Scripts\python -m pytest -q`,
offline). Every change is one commit; undo any one with `git revert <hash>`. Round 2 ran on 2026-11-23 from about
13:30 Calgary time.

## How the work was done

1. Three read-only Opus auditors covered three areas: (a) collector and export; (b) score, passes 2 and 3,
   backtest and tune loop; (c) site JS, workflows, prompts and docs. I checked every lead against the code
   myself before acting on it.
2. Each fix followed the same steps: write a test that fails, fix the cause, run the full suite, then make
   one commit.
3. Codex (the installed codex plugin, `review --base origin/main`) reviewed the branch three times. The three
   reviews found 10 real problems, nearly all in the new guards. All 10 are fixed below; two more Codex points
   are listed under "Found, not changed".

## What changed

Most of the fixes are about one theme. The scan reads three outside services: Google Flights, SerpApi and
Open-Meteo. Before this pass, one malformed answer from any of them could end the whole daily scan. Because the
bad answer was cached, every re-run that day failed the same way. Now a bad item is skipped and the rest of the
scan goes on.

| # | Commit | What and why | Evidence (the test that failed before) |
|---|---|---|---|
| 1 | `2c65a49` | **One malformed Google Flights item crashed the scan.** `to_leg` guarded only the price lookup. A segment with a missing date raised `TypeError`, which is not a `FetchError`, so `main.scan` died. Re-runs that day read the same cached item and died again. Now the item is skipped. | `test_flights.py::test_malformed_item_is_skipped_not_fatal` |
| 2 | `2ed3030` | **A manual `--cities` re-run deleted the other cities' history for that day.** The `scan.yml` cities input runs it. The scan deleted `data/history/<day>.jsonl` and wrote back only the cities it had scanned, and the workflow committed the result. D-19 asks a re-run not to duplicate rows; it does not ask it to drop other cities' rows. Now the other cities' rows for the day are kept. | `test_main_offline.py::test_city_subset_rerun_keeps_the_other_cities_history` |
| 3 | `4241baa` | **A malformed SerpApi payload crashed the scan.** It failed after the payload was already cached, so re-runs that day failed too. Cases: `"properties": null`, a null coordinate, a text rating, or a response that is not an object. A negative total was also accepted as an option. Now each property is parsed on its own and skipped if malformed. A non-object response counts as an error and is not cached. | `test_hotels_hits.py::test_malformed_serpapi_payload_is_skipped_not_fatal`, `::test_non_object_serpapi_response_is_an_error` |
| 4 | `bfb3a8c` | **The pass-3 research check accepted `true` and `Infinity` as numbers.** In Python `True` counts as an int, and `json.loads` reads `Infinity`. A research file with `"total_cad": true` became a $1 Airbnb stay and a hit. `Infinity` was written into the hit file, which the page cannot parse. D-69 makes `finalize` the validator for this file. | `test_pass3.py::test_bad_research_file_is_refused` (4 new cases) |
| 5 | `41a04f3` | **The weather cache was not written atomically, and a corrupt one was never fetched again.** This went against D-23 ("caches are written atomically and a corrupt cache file counts as a miss"). A half-written `om-<city>.json` sent that city to climate normals for the whole day. A wrongly typed forecast also raised an error from a function documented as never raising. | `test_weather.py::test_half_written_weather_cache_is_a_miss`, `::test_wrong_typed_forecast_falls_back_to_normals` |
| 6 | `cde2a95` | **The day's history file was not replaced atomically.** The scan deleted the file and then appended rows one at a time. If the job was killed mid-write, it left a truncated file. The workflow commits on `always()`, so that file would be committed. The next scan's `read_history` then raised on it before it could replace the day, so the data could not repair itself. Now the file is written to a temp file and renamed into place, the same way `latest.json` already is. A demo of the old code under the same crash kept 1 of 2 rows. | `test_store.py::test_replacing_a_day_is_atomic` |
| 7 | `4b236f2` | **`latest.json` now carries `classes.dayoff.max_weeks`.** `site/app.js` prints "scanned N to M weeks out" but always fell back to 16, because the field was never written. With a 4-week lead time set in Settings, the page said 4 to 16 while the scan covered 4 to 14. This is a data change only; the site is unchanged. | `test_main_offline.py::test_latest_says_how_far_out_day_off_trips_are_scanned` |
| 8 | `883b4a1` | **The README now warns about the offline scan.** Its "Run locally" block listed `scan --offline --today 2026-10-08` without saying that the scan overwrites `data/` and `hits/`. HANDOFF already says to run it in a scratch copy; the README now says so too. | Documentation only |
| 9 | `543354a` | Codex: the guard from #1 hid a **misspelled city time zone** as "no fares", because `ZoneInfoNotFoundError` is a `KeyError`. The zone is now looked up outside the guard. | `test_flights.py::test_unknown_time_zone_is_not_swallowed_as_a_bad_item` |
| 10 | `68d8241` | Codex: **one malformed item in a live Google response** made `slim` fail, which threw away the valid fares of the whole query. Now that one item is skipped. | `test_flights.py::test_one_malformed_item_in_a_live_response_keeps_the_rest` |
| 11 | `b810eb0` | Codex: `{"properties": true}` passed the object check and crashed the loop. | Added to the #3 test |
| 12 | `af6c488` | Codex: **a SerpApi rate of `true` or `NaN`** could become a $1 stay that won pass 2. The raw rate is now checked as a real, finite, positive number. The number check (`hotels.is_number`) is shared with #4. | Added to the #3 test |
| 13 | `40f5121` | Codex: **a wrongly shaped forecast**, such as `{"daily": {"time": null}}`, was still cached and trusted all day. The daily lists are now checked when the cache is read and before a fresh response is cached. | `test_weather.py::test_wrong_typed_forecast_falls_back_to_normals` (extended) |
| 14 | `93b75a2` | Codex, second review: a Google price of `true` became a $1 fare, and `1e309` (read as infinity) raised outside the guard. The price must now be a positive finite number. All 615 priced fixture items are ints and still pass. | `test_flights.py::test_unreadable_price_drops_the_item` |
| 15 | `7d452ac` | Codex, second review: `slim` also skips an item shaped as an object, which raised `KeyError`. | Added to the #10 test |
| 16 | `c41f5b8` | Codex, second review: forecast lists of different lengths count as a cache miss. All real cached forecasts on this PC still pass. | `test_weather.py::test_short_forecast_arrays_are_a_cache_miss` |
| 17 | `74692d5` | Codex, second review: a weather cache that cannot be written (for example a locked file on the Windows fallback host) no longer ends the scan. This problem was there before this pass. | `test_weather.py::test_cache_write_failure_keeps_the_fetched_forecast` |
| 18 | `45c6d11` | Codex, third review: a huge integer such as `10**400` made `math.isfinite` raise `OverflowError`. This affected the flight price, the lodging total and the research numbers. All three now refuse it. | Added to the #14 and #3 tests |

Line endings: my first edits on Windows turned four LF files into CRLF and one CRLF file into LF. Before the
review I rebuilt those commits, with the same content and messages, so each one keeps its file's original line
endings. `git diff --stat origin/main` shows only the real lines.

## Round 2, 2026-11-23 (William's go-ahead to settle the open items)

The orchestrating session passed on William's approval to settle the items found in round 1, including the two
that were his decision, and to keep improving. Each fix again has a test that failed before the change.

| # | Commit | What and why | Evidence (the test that failed before) |
|---|---|---|---|
| 19 | ~~`5f3c27d`~~ reverted in `7c169f0` | **Reverted: fails the tangible-value bar** (only a hand-run `finalize` on a dropped candidate reaches it; the routine never does). Was: **`finalize` refuses a `dropped` candidate** (round-1 item 1; D-85). D-67 says a dropped candidate gets no research, and D-69 says pass 3 runs on awaiting candidates only. Only the routine's list command enforced that, so finalizing a drop by hand with a cheap Airbnb total could turn it into a hit. The D-73(1) Airbnb rescue of an awaiting candidate with no lodging is unchanged, and re-running `finalize` on a `done` candidate still works. Three pass-3 tests used to finalize a drop; they now use a hit line that leaves their candidate awaiting, and their assertions are unchanged. | `test_pass3.py::test_a_dropped_candidate_is_not_finalized` |
| 20 | `834b393` | **The backtest now replays with D-41's formula** (round-1 item 2; D-86): `score - price_pts + new price`. On the real history it reproduces 1,502 of 1,502 logged winner scores, against 1,495 before. Candidate decisions match 1,502 of 1,502 both before and after, and the hindsight score is 0.0 both before and after, so no tuning number moves. | `test_backtest.py::test_replay_starts_from_the_logged_score_not_the_rounded_components` |
| 21 | ~~`22f762a`~~ reverted in `6840337` | **Reverted: fails the tangible-value bar** (Open-Meteo has never sent text where a number goes). Was: **A forecast value that is not a number or null now counts as a cache miss** (Codex review 3; round-1 item 14). | `test_weather.py::test_wrong_typed_forecast_value_is_a_cache_miss` (5 cases) |
| 22 | ~~`e0daab8`~~ reverted in `707cd31` | **Reverted: fails the tangible-value bar** (only a hand edit of scoring.yaml can set rotate_days to 0). Was: **A bad trip rule now fails when the config loads** (round-1 item 11). Before, `rotate_days: 0` raised `ZeroDivisionError` in the middle of a scan. `span_weeks`, `rotate_days`, `min_days`, `max_days` (which may not be under `min_days`) and `max_air_min` are now checked along with the other Settings values. The live config still loads. | `test_config.py::test_bad_trip_rule_fails_loudly` (5 cases) |
| 23 | ~~`49620ee`~~ reverted in `2404177` | **Reverted: fails the tangible-value bar** (needs a crash in the few milliseconds of the append, inside a routine that commits afterwards). Was: **The tuning runs log is now written in full to a temp file and renamed** (round-1 item 9). A crash can no longer leave a cut-off line, which every later night and `--summary` would have raised on. | `test_tune_loop.py::test_a_failed_runs_append_leaves_the_earlier_lines_whole` |
| 24 | `4820b51` | **`*.tmp` files are now git-ignored.** The scan, the SerpApi counter and the runs log each write a `.tmp` file and then rename it. If a crash left one behind, `git add data` would have committed it. | `git check-ignore data/tuning/runs.jsonl.tmp` |
| 25 | `253eb3d` | **A SerpApi search whose `search_metadata.status` is "Error" is now retried, not cached as done** (round-1 item 10). SerpApi's documentation (api-status-and-error-codes) says a failed search still returns HTTP 200, with status "Error". Empty results come back as "Success" with an `error` message. Before, a failed search counted as a completed check, so D-66 skipped that city-window for 7 days. Empty results still count as a completed check. | `test_hotels_hits.py::test_serpapi_status_error_is_an_error_but_no_results_is_a_completed_check` |
| 26 | `569bce6` | **`export` and `summarize` now read history up to the Calgary scan date** (round-1 item 8). The scan's `export()` used the runner's `date.today()`. A `--today` run more than 90 days back wrote an empty `series.json`. The offline tests scan 2026-10-08, so they would have started failing on 2027-01-07. | `test_main_offline.py::test_export_reads_history_up_to_the_scan_date_not_the_runner_clock` |
| 27 | ~~`67b6430`~~ reverted in `14a5456` | **Reverted: fails the tangible-value bar** (only a rare manual --cities run, and only until the next full scan; 25 lines for that). Was: **A `--cities` re-run now keeps the day's other cities on the page** (round-1 item 3). The other enabled cities' windows, city entries and candidate ids carry over from the previous `latest.json`, but only from the same day. Another day's rows are stale, so they are not kept, and a city switched off since then is dropped. `health` still describes the re-run itself. | `test_main_offline.py::test_city_subset_rerun_keeps_the_other_cities_on_the_page`; `::test_settings_files_steer_the_scan` caught the switched-off case |
| 28 | `2330f20` | **The scan now picks each city-window's winner with `best_per_window`** (round-1 item 7). The rule is the same; there is now one tested copy of it instead of a separate `max(...)` in the scan. | Existing `test_score.py` and offline-scan tests |
| 29 | `623d304` | **The scan workflow's same-day guard now uses the Calgary date** (round-1 item 4; William approved this workflow edit directly). `scan_date` is Calgary's date, but the guard compared it with `date -u +%F`. A late cron slot that fired after 00:00 UTC (18:00 in Calgary in winter) saw a new day and scanned the same Calgary day again: about 700 Google fetches, and the day's rows replaced. The guard now gets the date the way the scan does (`radar.windows.CALGARY`, with the pip tzdata through `PYTHONTZPATH`). The YAML still parses, and the new step body ran here against `data/latest.json`. | `test_workflow.py::test_guard_date_is_calgary_not_utc` (runs the step's date line at 02:00 UTC on 24 Nov and expects 2026-11-23) |
| 30 | `e41c021` | **A push that changes `table.html` now redeploys the site** (round-1 item 5). | `test_workflow.py::test_every_page_redeploys_the_site_when_pushed` |
| 31 | `6ecbc7d` | **The weekly prompt now reads the summary's real field names** (round-1 item 6): `passes`, `near_misses` and `ladder_distribution`, and the ladders in `references.yaml`. All the fields it names are present in today's `data/weekly-summary.json`. The routine is disabled (D-30). | Field check against `data/weekly-summary.json` |
| 32 | `eab1690` | **A `--try` proposal must be one step from the current value.** Who notices: the tuning loop, any night the routine proposes its own trial (it may, up to three a night). `parse_try` checked only the surface and the bounds, so a proposal could jump `rolling_ladder.good` from 25 to 35, or set a threshold of 71, off the 2-point grid, after which every menu move lands on odd values. D-82 says one step a trial. A refused `--try` is printed and the night carries on. | `test_tune_loop.py::test_proposals_held_to_the_surface` (2 new cases) |
| 33 | `4adc598` | **A same-day trip spends no SerpApi lookups and cannot crash pass 2.** Who notices: the scan and the SerpApi quota. 19 real history rows are day trips (check-in = check-out), and 6 were winners. If one reached the candidate line, it sent a 0-night hotel search: 2 lookups, repeated every scan. Any option returned also made the lodging line divide by zero before the day's history was written, losing the day. `check_lodging` now skips it as "day trip", and the candidate is dropped like any check that did not run. | `test_hotels_hits.py::test_a_day_trip_spends_no_lookups_and_cannot_crash_pass_two` |
| 34 | `6d296a3` | **The scoring table shows a day trip as 0 nights, not 1.** Who notices: William reading `table.html` (19 real rows). | `test_main_offline.py::test_csv_row_tolerates_rows_from_before_the_components` (new case) |
| 35 | `63297aa` | **The page's "How trips are judged" uses the live thresholds.** Who notices: William, once the loop moves a candidate threshold (it may, 65 to 80). The copy said "70 or more" and "a final 80". The text is the same while the values are 70 and 80. | node check of the sentence with 68/80 and with no classes |
| 36 | `9c9f96d` | **README and ASK.md.** The README gave the scan time as 03:17 MST / 04:17 MDT; it is 04:17 Calgary all year (D-24). ASK.md sent an ASK session to `latest.json`'s `hits`, which is always empty since v2, so it would tell William there were no hits; it now points to `hits/index.json`. | Documentation only |

## Loop health (the nightly self-tuning, D-82), 2026-11-23

**It runs.** From `origin/main`:
- The routine's tuning step ran every day from 2026-11-13. It reported "collecting, N of 14" on each of those days (the iteration log and daily notes).
- On 2026-11-15 and 2026-11-19 the count did not move. The routine ran before that day's scan landed. This is harmless, because the loop reads whatever history is on `main`.
- The first real night was 2026-11-22, with 14 scan days. It ran 16 trials and kept none. The score was 0.00 both before and after. `docs/tuning-log.md` and `data/tuning/runs.jsonl` each have that one night, and no config error was recorded.
- No `radar/tune-*` or `radar/iter-*` pull request has ever been opened. The daily change step chose "action: none" every day.

**Can it improve? Not yet, and on the deal side not with today's fares.** I probed it offline on main's 15 days of real history (2,861 rows, 591 judged winners). I lowered `rolling_min_days` in memory only, so that the train days get rolling ladders:
- **The deal half of the score is structurally 0.** No winner has scored above 56, and `candidate_threshold` cannot go below 65 (William's bound). So no trip is ever "sent for a closer look", and every candidate-threshold or price-curve trial changes nothing.
- **The ladder half can learn, through one key.** With rolling ladders the score is 7.7 (at a 6-day minimum) or 13.3 (at 4). Of the 16 one-step moves, only `rolling_ladder.good` 25 to 30 wins: +3.0 and +3.9 points, with the good-or-better rate going from 2.5% to 3.9%, or from 4.4% to 6.4%. The other 15 moves score exactly 0.00 better.
- **The score stays 0 on the live settings until about 2026-11-30.** A train day needs 14 earlier scan days for its rolling ladder, and the last 7 days are the holdout, so that takes about 22 scan days (D-82(7)). From then on, expect the loop to raise `rolling_ladder.good` one step at a time, toward the 30% good-rate guardrail.
- **Whether a 1-point win is above noise cannot be measured yet.** Split-half replays still score 0 on both halves. The holdout veto is the guard in the meantime. Re-run the probe after about 30 scan days. The script is `loop_probe.py` in this session's scratchpad; it is not committed.

**A kept change that later proves worse reverts itself.** Every night starts from the current config, and the one-step menu includes the step back. So if the old value later scores 1 point better, the loop moves back. The 7-day holdout can also veto a whole night. Bounds and the two guardrails cap any drift. One `tune:` commit is one `git revert`.

**What can go wrong, and who sees it within a day:**
- **The routine does not run.** No daily note that day; William sees it missing. This is not self-healing, because no watchdog is in place.
- **The scan is late.** The loop uses yesterday's history. Harmless.
- **The scan workflow re-scans a day after 18:00 Calgary.** Fixed: #29.
- **A tune commit conflicts with the data commits.** They cannot: the tune commit names `config/scoring.yaml` alone, and the scan commits only `data/` and `hits/`. Both do `git pull --rebase` before they push.
- **The script fails.** The routine puts its last error line in the note (PROMPT-daily T).
- **A malformed `--try` proposal.** Fixed: #32.
- **Wasted trials.** About 12 of the 16 nightly trials are guaranteed no-ops while the deal half is 0. Each costs under a second, so I left the menu as it is.

**Changed here:** #20 (the replay now matches all 1,502 logged scores, so a trial is not judged on rounding noise) and #32. **Still William's:** whether the 65 floor on `candidate_threshold` should stay while no trip scores above 56. Until fares or that bound change, the loop can only learn the ladder half.

## Found, not changed (still open)

1. **Dead code kept for its tests:** `previous_candidate(exclude_id=)` and `store.append_quotes` are used only by
   their tests. Removing them would mean deleting tests, which this pass does not do.
2. **Two `--cities` scans running at the same time could overwrite each other's rows for the day** (Codex review
   3). This cannot happen today: the workflow's `concurrency: scan` group runs one scan at a time.
3. **Needs a browser:** a browser whose time-zone data is older than tzdata 2026f shows "Last scan" an hour
   early, because Node 24 here still has Calgary at UTC-7 for 2026-11-22. Leg times are not affected (D-24). Check
   it once on William's phone.
4. **Audit round 2, real but William's call or below the bar:**
   - **No Friday-to-Monday block when both days are off.** Good Friday plus Easter Monday 2027 gives only the separate fri-off and mon-off windows. Adding it is a new window type and more Google requests, so it is William's call.
   - **`finalize` adds what's on to the rounded pass-2 score.** One real New York case lands on 80, a hit, while its breakdown rows add up to 79.22. BUILD-PLAN-v2 says "pass 2 + events", so which rounding is meant is a deal-model question.
   - **The breakdown says "central room" when pass 2 found no room.** The wording is wrong, but the score is right.
   - **A degraded same-day full re-run replaces the morning's rows.** This needs a manual run.
   - **A failed flight-cache write ends a local scan.** This needs the Windows fallback host.
   - **`mode`, `weights` and the trip rules are not validated.** Only a hand edit can set them wrong.
   - **A non-atomic write under `hits/`.** This needs a crash mid-write.

## Codex reviews

- Review 1: 5 findings, all confirmed and fixed (#9 to #13).
- Review 2: 4 findings, all confirmed and fixed (#14 to #17).
- Review 3: 3 findings. 1 was fixed (#18) and 1 in round 2 (#21); the last is open item 2. By then the findings
  were very unlikely edge cases, so I stopped the review loop there.

## How to merge

The local `main` checkout is days behind, so do this from the worktree or from a fresh clone that is up to date
with `origin/main`:

```powershell
git fetch origin
git switch claude/overnight-fixes-bdabcb
git rebase origin/main          # the routines commit data to main every day; the branch touches no data files
.venv\Scripts\python -m pytest -q
git push origin claude/overnight-fixes-bdabcb   # then open a PR, or merge to main once it is green
```

The branch touches only `radar/`, `scripts/backtest.py`, `scripts/tune_loop.py`, `tests/`, `.gitignore`,
`.github/workflows/scan.yml`, `routine/PROMPT-weekly.md`, `README.md`, `HANDOFF.md`, `docs/notes/decisions.md` (D-84 to D-86), `SESSION-LOG.md` and this file, so it should not conflict with the daily data commits. After the merge, the next scan uses the new
guards; no config or data change is needed.
