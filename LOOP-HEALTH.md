# Loop health: live verification

This file checks that the radar's two self-improvement loops run on their own every day and stay running:
- **The nightly self-tuning step:** section T of `radar-daily`, `scripts/tune_loop.py` (D-82).
- **The daily improvement step:** section C of `radar-daily`, at most one `radar/iter-<date>` pull request a day.

A session cron checks the repo after each of the next three mornings' runs, after 09:15 Calgary. The verdict comes after day 3.

## Verdict (filled in after day 3)

| Question | Answer | Evidence |
|---|---|---|
| Does it run unattended? | pending | |
| Is the tuning step running correctly? | pending | |
| Can it improve anything yet? | Not before about 2026-11-30, and only the "good fare" line | Day 0, below |
| What can still stop it? | See "Continuity" | |

## Day 0: 2026-11-23, after the merge (PR 3, `b107ef9`)

| Step | Result | Evidence |
|---|---|---|
| Same-day guard on a real run | **ran and succeeded** | The 22:04 UTC scheduled backup run on `b107ef9` printed `latest scan_date=2026-11-23` and skipped the Scan step. The 23 Nov scan was not repeated. |
| `radar-scan-kick`, 04:17 Calgary | not due yet | Enabled, `17 10 * * *` UTC; next run 2026-11-24 10:17 UTC. |
| `radar-daily`, 08:30 Calgary | not due yet | Enabled, `30 14 * * *` UTC; next run 2026-11-24 14:30 UTC. Its stored prompt reads `routine/PROMPT-daily.md`, which has no end date (D-82). The name "month one" is a label only. |
| Tuning nights so far | ran and succeeded, kept nothing | 22 Nov and 23 Nov ran 16 trials each, 0 kept, train score 0.00. Holdout was 9.16 on the 23rd. |
| Daily improvement step | ran, chose "action: none" every day | No `radar/iter-*` pull request has been opened since the start. |

**What the loop can improve in the next two weeks:**
- **Until about 2026-11-30, nothing.** A train day needs 14 earlier scan days for its rolling ladder, and the last 7 days are held out. That takes about 22 scan days, and there are 15. Until then every trial scores 0.00 and nothing can be kept. This is correct behaviour, not a fault.
- **From about 30 Nov, only `rolling_ladder.good`.** An offline probe on the real history (in `OVERNIGHT-CHANGES.md`, Loop health) found that raising it from 25 to 30 is the one move that scores better. The 23 Nov holdout agrees: lowering it to 20 scored worse (9.16 to 7.36).
- **The "send for a closer look" half stays at 0.** No trip has ever scored 65 (D-87 keeps that floor). The best was 56 until the rolling ladders took effect; on 23 Nov it was 61 (San Francisco). If scores keep rising, the floor comes into reach.
- **The noise test needs more days.** Whether a 1-point win is above noise cannot be tested yet: a split-half replay still scores 0 on both halves. Re-test once the train score is non-zero, about 7 Dec. Until then the holdout veto is the guard.

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
