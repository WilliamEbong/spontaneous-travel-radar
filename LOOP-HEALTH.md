# Loop health: live verification

This file checks that the radar's two self-improvement loops run on their own every day and stay running:
- **The nightly self-tuning step:** section T of `radar-daily`, `scripts/tune_loop.py` (D-82).
- **The daily improvement step:** section C of `radar-daily`, at most one `radar/iter-<date>` pull request a day.

A session cron checks the repo after each of the next three mornings' runs, after 09:15 Calgary. The verdict comes after day 3.

## Verdict (filled in after day 3)

| Question | Answer | Evidence |
|---|---|---|
| Does it run unattended? | The scheduler has started every run so far: `radar-scan-kick` and `radar-daily` ran on their own schedule every day from 2026-11-13 to 2026-11-23 (`docs/iteration-log.md`). The new behaviour (D-89, the backlog) ran once, at 04:46 UTC on 2026-11-24, started from this session; its first scheduled run is at 14:30 UTC the same day. The morning checks of 24 to 26 Nov record whether the scheduler runs it on its own. | iteration log; "Running now, 2026-11-24" |
| Is the tuning step running correctly? | Yes. It scores the real history (27.90), and its keep rule rejects no-ops and noise. | 2026-11-24 night; the placebo of 500 sham changes passed 0.6% |
| Can it improve anything yet? | Yes, since D-89 (2026-11-24). The train score is real (27.90), and every key is evaluated. On the 15 days available, three keys moved the score; the window and the other keys change no decision yet. A change is kept when the redraw rule says it is real. | "Running now, 2026-11-24", below |
| What can still stop it? | See "Continuity" | |

## Day 0: 2026-11-23, after the merge (PR 3, `b107ef9`)

| Step | Result | Evidence |
|---|---|---|
| Same-day guard on a real run | **ran and succeeded** | The 22:04 UTC scheduled backup run on `b107ef9` printed `latest scan_date=2026-11-23` and skipped the Scan step. The 23 Nov scan was not repeated. |
| `radar-scan-kick`, 04:17 Calgary | enabled; its 2026-11-23 run started that day's scan | Enabled, `17 10 * * *` UTC; next run 2026-11-24 10:17 UTC. |
| `radar-daily`, 08:30 Calgary | enabled; ran 2026-11-24 with the new behaviour (below) | Enabled, `30 14 * * *` UTC; next run 2026-11-24 14:30 UTC. Its stored prompt reads `routine/PROMPT-daily.md`, which has no end date (D-82). The name "month one" is a label only. |
| Tuning nights so far | ran and succeeded, kept nothing | 22 Nov and 23 Nov ran 16 trials each, 0 kept, train score 0.00. Holdout was 9.16 on the 23rd. |
| Daily improvement step | ran, chose "action: none" every day | No `radar/iter-*` pull request has been opened since the start. |

**What the loop could improve (as of day 0; superseded the next morning by D-89):** with the fixed 14-day replay ladder and 7-day holdout, every trial scored 0.00 until about 22 scan days, and the 65 floor sat above every trip (best 61). See "Running now, 2026-11-24" for what changed.

## Running now, 2026-11-24

Every row below is a real run on the live system, with its result and the commit it left.

| Loop step | Real run | Result | Commit |
|---|---|---|---|
| Daily scan | `scan` workflow, dispatched by `radar-scan-kick` at 10:18 UTC on 2026-11-23 | Ran and succeeded: 99.8% of 606 searches answered, not blocked. The repeat start at 22:04 UTC was skipped by the Calgary-date guard (`latest scan_date=2026-11-23`). | `285d0ad` (data scan 2026-11-23) |
| Daily routine `radar-daily` | Started from this session at 04:46 UTC with the new prompt and code (session `cse_01Gg7wybvq2ccKJ7eS677L6z`) | Ran and succeeded in about 2.5 minutes: sections A, P, B, T, C, D and E, then delivery | `28ed4b4` (daily note 2026-11-24) |
| Nightly tuning step (section T) | Run by that routine: `python scripts/tune_loop.py --date 2026-11-24` | Ran and succeeded with D-89. It started from a real train score of 27.90 (holdout 33.97, a 3-day holdout and 6-day replay ladders) and ran 16 trials. Three improved the score: the good-fare line 25 → 30 (+1.43), the day-off threshold 70 → 60 (+1.15) and the middle price step 0.75 → 0.85 (+1.15). The rule kept none of them: they won in 89.5%, 68% and 68% of the redraws, and 90% is needed. One trial made the score worse (good-fare line 25 → 20, −2.70), and 12 changed no decision. | `28ed4b4` (`docs/tuning-log.md`, `data/tuning/runs.jsonl`) |
| Daily improvement step (section C) | Run by that routine | Ran and succeeded: the top backlog item, as its first ever pull request. A same-day candidate no longer takes a lodging-check slot. Its test fails without the fix; all 184 tests pass on the branch (re-run here). | [WilliamEbong/spontaneous-travel-radar#6](https://github.com/WilliamEbong/spontaneous-travel-radar/pull/6), branch `radar/iter-2026-11-24` |

**Why nothing was kept tonight, and why that is the rule working**

These runs are on main's 15 days of history, using the merged code:
- **No-op:** a change that does nothing never wins a redraw (0%).
- **Noise:** 500 sham changes, each flipping as many random judgements as the good-fare move does, passed the keep rule 3 times (0.6%).
- **The good-fare move:** it lost the redraws only narrowly (89.5% against the 90% needed). Each new scan day adds evidence, so it may pass on a coming night. Whether it does is up to the rule.

**What happens next, with nothing for anyone to do**
- **Today's scan** at 10:17 UTC (04:17 Calgary) uses the same config, because nothing was kept.
- **The scheduled `radar-daily` run** at 14:30 UTC (08:30 Calgary) is the second run on this date:
  - Section A reviews pull request #6 and merges it if it is clean.
  - Section C is skipped, because a second run on the same date skips it.
  - Section T prints "already ran 2026-11-24".
  - It replaces the note with one that covers today's scan.
- **The watchdog** checks each scheduled scan run from today's 10:17 UTC slot on. It fails, and GitHub emails, if a day passes without a daily note or a tuning night.

## Continuity: what could stop a loop, and who would see it

| Way it could stop or go wrong | Self-healing? | Visible within a day? |
|---|---|---|
| `radar-scan-kick` fails or does not push | Yes. GitHub's scheduled backup slots (10:17 to 16:17 UTC, often late) start the scan. | The daily note says the scan was late. |
| A late backup slot fires after 18:00 Calgary | Yes. The same-day guard compares Calgary dates (fixed and proven on a real run, day 0). | The run log shows the Scan step skipped. |
| `radar-daily` does not run, fails before its note, or stops for good | No. | **New:** `scripts/watchdog.py` runs on every scheduled scan run. If yesterday has no daily note, or no tuning night once tuning was due, that run fails and GitHub emails it. Before, nothing would have shown. |
| `tune_loop.py` errors | No, but the next night tries again | The routine puts the last error line in the note (PROMPT-daily T), and the watchdog flags the missing night. |
| A `tune:` commit conflicts with a data commit | Cannot happen. The tune commit names `config/scoring.yaml` alone, the scan commits `data/` and `hits/`, and both rebase before they push. | |
| A kept change later proves worse | Yes. Each night starts from the current config and the menu includes the step back; the 7-day holdout can veto a night; bounds and guardrails cap drift. | `docs/tuning-log.md` and the note's tuning line |
| The routine pushes from a detached HEAD | The daily note has landed every day, and if a push fails the routine emails the note instead. | Yes, the email |
| The routine has an end date | None. D-82 removed the window from the prompt. | |
| A malformed `runs.jsonl` | No | The loop would raise each night; the note's error line and the watchdog show it. |

## Daily checks

(Day 1, 2 and 3 entries are added below by the morning checks.)
