# Improvement backlog

These are the daily routine's improvements (`routine/PROMPT-daily.md`, section C), most valuable first. When the day's data turns up nothing more urgent, C does the top open item as that day's one change. It works on a `radar/iter-<date>` branch, adds a test where the item says so, and in the same pull request marks the item `done (iter <date>)`.

Each item lists:
- **Who notices:** who sees the problem, and how often.
- **Where:** the files to change.
- **Done when:** the check that proves it is finished.

Every item stays inside section C's allowed files; none touches anything on C's "Never" list. Add a new item only when it is real, with its "who notices" line, and keep the list ranked.

## 1. Same-day trips must not take a lodging-check slot (done (iter 2026-11-24))

**Who notices:** the scan, on any day a same-day trip qualifies as a candidate. That is now possible, because D-89 lets the candidate thresholds come down towards 60, and the history has 19 same-day trips, 6 of which were their weekend's best. `check_lodging` skips such a trip ("day trip", no lookups). But `scan` has already counted it as one of the 3 lodging checks of the day (`MAX_CANDIDATES_PER_SCAN`). D-66 does not count a skipped check as done, so it takes a slot again on every scan and can crowd out a real overnight candidate.

**Where:** `radar/main.py`, the pass-2 loop. Leave out `x.trip.nights < 1` before the slot is counted, and print why to stderr.

**Done when:** a test in `tests/test_main_offline.py` shows a same-day candidate takes no slot, while an overnight candidate still gets its check. `python -m pytest -q` passes.

## 2. The breakdown says "central room" when pass 2 found no room (done (iter 2026-11-25))

**Who notices:** William, reading a candidate's brief on a day when pass 2 found nothing acceptable within 6 km. The convenience line then ends "… · central room", while the lodging line says "nothing acceptable within 6 km" (D-78: the room part is added only once pass 2 has found one).

**Where:** `radar/score.py` (`convenience_line` and `breakdown`) and `radar/hits.py` (`pass2`, and `finalize`'s estimate path). Pass `room=` only when a room was chosen. The score itself does not change.

**Done when:** a test in `tests/test_hotels_hits.py` shows the line has no "central room" when `LodgingCheck((), None, 2)` finds nothing, and keeps it when a room is chosen.

## 3. `docs/ASK.md`: the storage numbers are out of date (open)

**Who notices:** an ASK session telling William how big the history is. ASK.md says each day is "about 300 rows, ~250 KB". Recent days are 65 to 227 rows and 87 to 378 KB.

**Where:** `docs/ASK.md`, "Storage plan". Measure the last 7 days of `data/history/` and write the range.

**Done when:** the numbers match the files, stated as a range with the date measured.

## 4. README: the local commands have no macOS or Linux form (open)

**Who notices:** anyone setting the project up outside Windows. The "Run locally" commands use `.venv\Scripts\python` only.

**Where:** `README.md`, "Run locally". Add one line with the `.venv/bin/python` form.

**Done when:** both forms are shown and no other README line changes.
