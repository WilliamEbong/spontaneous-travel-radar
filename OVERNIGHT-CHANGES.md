# Overnight changes, 2026-11-22 to 2026-11-23

This was a maintenance pass on branch `claude/overnight-fixes-bdabcb`. It ran unattended from about 22:55 on
2026-11-22 to about 00:30 on 2026-11-23, Calgary time. It started from `origin/main` at `f93e98e` (docs: daily
note 2026-11-22).

The pass found and fixed defects only. Nothing here changes the deal model, the scores, the config, the data,
the workflows, the routine prompts or the look of the site. Each fix came from a test that failed before the
change and passes after it. The branch has not been pushed or merged.

**Tests:** 129 passed before, 150 passed after (`.venv\Scripts\python -m pytest -q`, offline). Every change is
one commit; undo any one with `git revert <hash>`.

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

## Found, not changed (below the bar, off-limits, or the owner's call)

1. **`finalize` will run pass 3 on a candidate marked `dropped`** (radar/hits.py `finalize`). D-69 says "pass 3
   runs on today's awaiting candidates only", but only the routine's list command enforces that. A candidate
   dropped for quota can still become a hit if it is finalized by hand with an Airbnb total. I started a fix and
   then reverted it: three existing tests deliberately finalize D-67-dropped candidates to test the Airbnb
   rescue, so refusing them changes tested behaviour. **Recommendation:** decide whether pass 3 may rescue a
   D-67 drop. If it may not, refuse `status == "dropped"` in `finalize` and update those three tests. If it may,
   refuse only the "pass 2 did not run" drops (D-73(1)).
2. **The backtest replay drifts 1 point from D-41's formula** (scripts/backtest.py `judge`). It rounds
   `price + sum of components` instead of using `score - price_pts + new price`. On the real history, 7 of
   1,502 winners replay 1 point off; D-82 noted 2. Candidate decisions still match 1,502 of 1,502. I did not
   change it because it would shift the tune loop's numbers. **Recommendation:** switch to the D-41 formula in a
   tune-loop iteration, with its own before and after.
3. **A `--cities` re-run still shrinks `latest.json` to the scanned cities** until the next full scan. History is
   kept (fix #2), but the dashboard shows only those cities for the rest of the day. **Recommendation:** merge
   the other cities' `windows` and `best_by_city` from the previous `latest.json`, or document that `--cities`
   is for testing.
4. **Workflow, not edited: the same-day guard compares Calgary's `scan_date` with the UTC date**
   (`.github/workflows/scan.yml`, "Already scanned today?", `date -u +%F`). GitHub has run cron slots 7.5 to 10
   hours late (D-79, D-83). A 16:17 UTC slot that fires after 00:00 UTC lands on the next UTC day while Calgary
   still has the same date, so the guard says "not done" and the day is scanned again: about 700 Google fetches,
   and the day's rows are replaced. **Fix:** compute the date in Calgary, for example
   `python -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('America/Edmonton')).date())"`
   with `PYTHONTZPATH=""`, as the Scan step already does.
5. **Workflow, not edited: the Pages push filter leaves out `table.html`** (`scan.yml` `paths:`). A push that
   changes only `table.html` waits for the next scan to deploy. **Fix:** add `"table.html"`.
6. **Routine prompt, not edited: `routine/PROMPT-weekly.md` reads `would_have_fired` and `band_distribution`.**
   Neither exists in `data/weekly-summary.json`, whose keys are now `ladder_distribution` and others. The
   prompt also says the bands are in `scoring.yaml`. The routine is disabled (D-30), so this only matters if it
   is turned back on. **Fix:** retire the file or rename the fields.
7. **Dead code: `score.best_per_window` and `previous_candidate(exclude_id=)` are used only by tests.**
   `main.scan` picks the winner with its own `max(...)`, so the tested rule and the live rule can drift apart.
   Removing them would mean deleting tests, so I left them. `store.append_quotes` is now also used only by its
   test, since #6.
8. **`export()` and `summarize` use `date.today()` on the runner (UTC), not the Calgary scan date.** This only
   moves the 90-day and 7-day edges by a day. Low.
9. **`tune_loop.append_run` appends a line without an atomic write.** A crash mid-append would leave a
   truncated `data/tuning/runs.jsonl`, and every later night and `--summary` would raise on it. This is unlikely,
   because the routine commits only after the run. Not proven.
10. **A SerpApi HTTP 200 response that carries an `"error"` key** is cached as a completed check with no
    options. D-66 would then skip that city-window for 7 days. Proving it needs a real 200 error response that is
    not "no results".
11. **`trip_classes` values (`rotate_days`, `span_weeks`, `min_days`, `max_days`) are not validated.**
    `rotate_days: 0` would raise `ZeroDivisionError` mid-scan. Only a hand edit can set these; the tune loop
    cannot.
12. **Needs a browser (none was used tonight):** a browser with time-zone data older than tzdata 2026f shows
    "Last scan" an hour early, because Node 24 here still has Calgary at UTC-7 for 2026-11-22. Leg times are not
    affected (D-24). Check it once on William's phone.
13. **Doc drift:** HANDOFF.md says "129 tests"; the branch now has 150. I left it, because the count changes
    with every merge.

14. **Codex, review 3: forecast value types are not checked.** A forecast with a text value where a high should
    be passes the list checks of #13 and #16. It is cached, and that city falls back to normals for the day
    without a retry. The scan does not crash, and Open-Meteo has never sent such values, so I stopped here.
    **Recommendation:** check that each high is a number or null before caching.
15. **Codex, review 3: two `--cities` scans running at the same time could overwrite each other's rows for the
    day.** Not reachable today: the workflow's `concurrency: scan` group with `cancel-in-progress: false` runs
    one scan at a time. It would matter only for two manual local runs at once.

## Codex reviews

- Review 1: 5 findings, all confirmed and fixed (#9 to #13).
- Review 2: 4 findings, all confirmed and fixed (#14 to #17).
- Review 3: 3 findings. 1 was fixed (#18). The other 2 are listed as items 14 and 15 above. By then the findings
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

The branch touches only `radar/`, `tests/`, `README.md`, `docs/notes/decisions.md` (D-84), `SESSION-LOG.md`
and this file, so it should not conflict with the daily data commits. After the merge, the next scan uses the new
guards; no config or data change is needed.
