# Handoff: Spontaneous Travel Radar (v2 build of 2026-11-09)

Read this first if you are picking the build up in a fresh session. Then `SESSION-LOG.md`, the end of
`docs/notes/decisions.md` (D-57 to D-75) and `BUILD-PLAN-v2.md`.

## Where things stand

- **One time scale and convenience evidence (D-next) is built on branch `time-score`, not merged.** Worktree
  `.claude/worktrees/time-score`, from `main` d199e1b. Time = 20 × min(1, hours awake there ÷ 31), the same line for every
  class and window (4.5 h of airport overhead, 10 h a night; under 7.75 h the trip is dropped); `config/scoring.yaml: time_rule`
  replaces `time_curve`. The convenience breakdown line lists one evidence part per rule with its points. The first scan after
  the merge fills the new lines; the Toronto day-one pair now scores 19.0 and 6.8 on time. 103 tests. Screenshots in the
  side-session notes folder, `time-score-screens/`. Replayed over the 584 logged rows, the floor would drop 155 (29 of the 324
  winners, 15 of them weekend): William's call, `time_floor_share` is the knob.

- **Score breakdown (D-75) is built on branch `score-breakdown`, not merged.** Worktree
  `.claude/worktrees/score-breakdown`, from `main` f49df40. Every score on the page is a button whose panel lists each
  criterion with its input and points; the rows come from the collector (`breakdown` on `latest.json` rows, candidate
  and hit files and `hits/index.json`), so the first scan after the merge is what fills them: until then the page shows
  plain scores. 103 tests. Screenshots in the side-session notes folder, `score-breakdown-screens/`.

- **The v2 deal model is built on branch `v2-deal-model`, not merged.** Worktree:
  `C:\Users\Owner\OneDrive\Documents\Spontaneous Travel\.claude\worktrees\v2-deal-model` (the main
  checkout stays on `main`). Nothing pushed. The design session merges after review: merging deploys Pages
  (the push touches `index.html` and `site/`), the next 10:17 UTC scan runs the v2 collector, and
  `radar-daily` reads the v2 `routine/PROMPT-daily.md` the next morning (pass 3 included).
- Spec Kit: `specs/002-deal-model-and-passes/` (spec, plan, tasks; all ticked).
  Constitution amended to v1.1.0 for William's v2 decisions (D-71).
- `pytest -q`: 99 tests, all passing, no network. A fresh-context reviewer read the whole branch and found
  9 problems (one high: a hit could be declared on the pass-1 room estimate); all fixed with tests (D-73).
- What v2 does (design section 14): each trip is judged against its route's ladder
  (`config/references.yaml`); price is the complete trip for two as a share of the route's typical trip
  (45/25/0/-10 points at 0.60/0.75/1.00/1.30, then falling to -100); basic fares in both classes;
  Ticketmaster gone. Pass 1 scores every trip (lodging assumed at the season's good room rate). A fare at
  or under the route's good with a score of 70+ is a candidate; the top three a scan get pass 2 (Google
  Hotels and vacation rentals through SerpApi, within 6 km of the centre, best option by score) and a file
  in `hits/candidates/`. Pass 3 is the daily routine's: research of what is on against
  `config/interests.yaml`, Airbnb by a Sonnet subagent, then `python -m radar.main finalize`, which files
  a hit (final 80+, and only with real lodging) in `hits/dry-run/` (learning run) or `hits/` (live), or a
  near miss in `hits/near-miss/`.
- Dashboard: hits, Passed (every 70+ trip and the pass it reached), Every city (best deal, ladder,
  every weekend, price history), notes. Weekend trips ("No day off needed") are gold: border and label,
  both themes; day-off trips neutral. Settings: per-class switch and hit line, optional overall cap (off),
  read-only ladders; the per-city bar is gone.
- Room ladders came from Google Hotels for 19 cities (T9, 41 SerpApi lookups). The branch's
  `data/serpapi_usage.json` says 45 for 2026-11 (1 day one, 3 probes, 41 T9). `main` says 1 unless a
  scan used SerpApi since (v1 used it only for candidates, and there were none).
- Unchanged from v1 and still true: collector on GitHub Actions (`scan.yml`, cron 10:17 UTC), Pages
  from Actions, routines as listed below, learning run until about 2026-12-08, `radar-tune` on
  2026-12-09 (its plan, `docs/TUNING-PLAN.md`, is rewritten for ladders).

## Commits on the branch

`c7c2256` spec/plan/tasks and probe fixtures · `9ea2ba8` T2 basic fares · `88b5ab4` T1/T3/T4/T5 collector
(one commit: score, hotels and hits change shape together) · `b5e21d2` T6/T7 pass 3 and prompts ·
`49f4ede` session log · `bdee74e` T8 dashboard and settings · `2337364` T9 room ladders (this commit is red:
a YAML comment inside a flow mapping) · `7733b98` fix, green again · `d9c2a90` T10 docs · `eb64265` review
fixes (D-73) · then this hand-over.

## Merge notes for the design session

1. From the main checkout: `git merge --no-ff v2-deal-model` (or squash). Expected conflicts: only
   `data/serpapi_usage.json` if a scan on `main` used SerpApi meanwhile (add the two months' counts:
   the branch's 44 lookups are real), and the end of `docs/notes/decisions.md` if someone appended there.
   The daily routine writes `data/digests/` and `docs/iteration-log.md`, which the branch does not touch.
2. After the merge: the `TICKETMASTER_KEY` Actions secret is unused; William can delete it.
3. First v2 scan: history rows gain `ladder`, `share`, `total_cad`, `nights`, `pass`, `final_score`,
   `candidate_id` and drop `band`; `latest.json` gains `classes`; the old rows stay readable.
4. Check the first `radar-daily` run that has a candidate: it should write
   `data/research/<city>-<window>.json`, run `finalize`, and push `hits/` with its note.
5. Between the merge and the first v2 scan the page shows v1 `latest.json`: checked, it renders 20 cards with
   no broken numbers (the ladder line shows dashes until the scan).

## Open questions for William (each has a default already in place)

1. **D-60:** the research doc's "good trip about 74" is an arithmetic slip; the decided anchors give 70.6
   (still a candidate, not a hit). Default: anchors as decided, doc corrected.
2. **D-61:** the round-trip reprice is not built: fast-flights 3.1.0 cannot price our exact leg pair
   (probe evidence in the decision). Totals stay one-way sums, which run 3 to 15% above Google's headline.
3. **D-68:** New York's and Mexico City's lodging centres moved to Union Square and Roma Norte, and Los
   Angeles now searches Downtown first (Santa Monica is 22 km from the centre, outside the 6 km cut).
   New Orleans winter rooms stay an estimate (Google showed $620 a night on the sampled weekend).
4. Is the hit routine's stored prompt the repo file or inline text? `routine/PROMPT-hit.md` now asks for
   `[Weekend]` / `[Day off]` subjects; if the stored prompt is inline, update it at go-live.
5. Web search inside `radar-daily` was never probed. If it fails, pass 3 finalizes with no finds and the
   note says so; the trip can still be a hit on its pass-2 score.

## Acceptance checks (BUILD-PLAN-v2), as run on 2026-11-09/10

1. Vancouver worked example: $650 trip 83, exceptional 91 (doc: about 90), good trip 70.6 (doc: about 74,
   an arithmetic slip in the doc, D-60). `tests/test_score.py`.
2. Cheaper of two above-typical trips wins: Toronto day-one case and a far-past-2.2 case. `tests/test_score.py`.
3. Basic fares in a fresh YYC-YVR fetch: Flair $241 for two, WestJet 101 $343 vs $450 Standard
   (`tests/fixtures/ff_yyc_yvr_basic.json`, `tests/test_flights.py`).
4. No Ticketmaster in code, workflow or tests (grep; `scripts/run-scan.ps1` comment fixed too).
5. Candidate at good with 69 no, 70 yes. `tests/test_score.py`.
6. Central $650 hotel beats fringe $550 rental by score, both listed. `tests/test_hotels_hits.py`.
7. SerpApi cap: a simulated month stops at exactly 200. `tests/test_hotels_hits.py`.
8. Dashboard: Hits, Passed, Every city, Notes in order; class grouping right; four states x 375/1280 x
   light/dark; no horizontal scroll; 0 console messages; gold border on weekend cards. Screenshots in
   `C:\Users\Owner\OneDrive\Documents\.playwright-mcp\v2-shots\` (`final-*` after the review fixes).
9. Offline scan rows carry ladder, share, pass, final_score (`--today 2026-10-08`; `--today 2026-11-12`
   runs clean but the recorded fares cover none of its windows).
10. Query build plans 572 to 688 a day over six weeks. `tests/test_flights.py`.

## Later (not built)

"Would book / Not for me" taps writing `data/labels.jsonl`; interests editable in the panel; seasonal room
references finer than winter/summer and more than one sampled weekend per season; an exact-pair round-trip
price if fast-flights exposes Google's second page; the dashboard copy "next 6 weeks" for weekend trips is
fixed text (the range is config).

## Gotchas

- Python on Windows writes CRLF through `write_text`; the repo is mostly LF. Restore line endings before a
  commit (the run used a small script; `git diff --stat` showing whole files changed is the symptom).
- In this Windows Bash tool, backslashes inside heredocs get mangled: write scripts with the editor.
- Check pytest's exit code, not its last printed line, before committing (one red commit came from that).
- SerpApi responses are cached per scan day by city and dates, not by query text: after changing a city's
  first neighbourhood mid-day (or in `data/cache/rooms/` for the T9 script), delete those cache files.
- The token for the Settings panel lives in `localStorage` on `williamebong.github.io`, an origin every
  project page on that account shares (unchanged from v1; the reviewer noted it).
- Playwright MCP writes relative paths under `C:\Users\Owner\OneDrive\Documents\`; the v2 screenshots are in
  `C:\Users\Owner\OneDrive\Documents\.playwright-mcp\v2-shots\`. Use `localhost`, not `127.0.0.1`.
- An offline scan writes `data/`, `hits/` into the current folder: run it in a scratch copy (the tests do).
- `--today 2026-11-12` offline finds no trips: the recorded fixtures end 28 Nov and day-off windows then
  start 24 Dec. `--today 2026-10-08` exercises both classes.

## Routines (unchanged by this build; manage at https://claude.ai/code/routines)

- `radar-daily` `trig_01VGioWFbgQxwEh1iZRypsCw`, Opus, cron `30 14 * * *` (07:30 Calgary, after the 10:17 and 13:17 UTC scan slots, D-74), 2026-11-10 to 2026-12-08,
  instructions `routine/PROMPT-daily.md` (repo file, D-35). Enabled.
- `radar-tune` `trig_01E542toF6zwmddqDsjRGXeX`, Opus, one-shot 2026-12-09T13:00:00Z, follows
  `routine/PROMPT-tune.md` and `docs/TUNING-PLAN.md`. Enabled.
- Hit reviewer `trig_01TvveuLCRL8QwbwuF52yd9Y` disabled; weekly digest `trig_01V9gJ6rL1sDuSsqDkE11oxo`
  disabled; GitHub probe done.

## How to verify

```
.venv\Scripts\python -m pytest -q
python scripts\dashboard_fixtures.py <scratch dir>     (four data states through the real pipeline)
python -m http.server 8766 --directory <scratch dir>   then http://localhost:8766/hits/ (and empty, passed, live)
python scripts\room_references.py --dry-run             (lists the 39 lookups it would make)
```
Offline scan: copy `config/` and `tests/fixtures/offline/` into a scratch folder and run
`python -m radar.main scan --offline --today 2026-10-08` there.
