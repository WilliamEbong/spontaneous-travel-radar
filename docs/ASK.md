# Answering William's questions about the radar

William's usual flow is the dashboard. When he has an actual question ("why did Vancouver score 54?",
"why is nothing worth booking?", "what would make Toronto a hit?", "is this scan healthy?"), he opens a
Claude Code session in this folder and asks. This file tells that session how to answer well.

## Where the answers live (read, never re-scan)

- `data/latest.json`: the current scan. `best_by_city` (one row per city, its top-scoring trip),
  `windows` (every city-weekend winner), `candidates`, `hits`, `cities` (each city's ladder:
  typical / good / exceptional flight price), `health` (coverage, requests, errors, blocked, lookups).
  Every trip row carries `breakdown`: each criterion with its `input` (the evidence in words), `points`
  and `max`. Quote those lines; they are the explanation.
- `data/history/YYYY-MM-DD.jsonl` and `.csv`: every logged trip for that scan with `components` and
  `inputs` (D-76). Use these for "what changed since yesterday" and for anything not on the page. The `.csv` is the scoring table
  (`table.html` on the site): one row per trip, the evidence line, points and score per criterion (D-77).
- `hits/candidates/`, `hits/near-miss/`, `hits/`: the three-pass files (pass 1 score, pass 2 real
  lodging with the options and links, pass 3 research with each find and its reason).
- `data/digests/<date>.md`: the daily routine's note (health, what changed, what it is watching).
- `config/references.yaml`: what each route normally costs (the ladders) and where the numbers came
  from; `docs/research/2026-11-09-fare-references.md` is the evidence behind them.
- `config/scoring.yaml`: weights, price anchors, thresholds, classes. `radar/score.py` is the formula.
- `docs/notes/decisions.md`: why things are the way they are, one entry per judgment call (D-01 to
  D-76+). When William asks "why", the decision entry is usually the honest answer.

## How to answer

- Plain words, numbers with their reasons: "Weather 9.7 of 10 because November normals are 19 °C
  highs with rain on 2 of 30 days." Lead with the one number that decided it.
- Say what is estimated and what is real (lodging is an estimate until pass 2 ran on that trip).
- If a field is missing because the scan predates a feature, say so and when it will exist.
- Never trigger a scan, change config, or spend lookups to answer a question. If the answer needs
  a change, say what the change would be and that it is his call.
- Compare against his own spot checks honestly: if Google shows a cheaper same-weekend trip inside
  the rules, that is a bug or a rule gap, and the answer is to find which.

## Useful commands

```
.venv\Scripts\python -c "import json; d=json.load(open('data/latest.json')); print([ (r['city'], r['score'], r['window_id']) for r in d['best_by_city'] ])"
.venv\Scripts\python -m radar.main export     # rebuild series, CSVs and indexes from what is on disk; no network
gh run list --workflow scan.yml --limit 3     # did the scan run, how long, did it fail
```
