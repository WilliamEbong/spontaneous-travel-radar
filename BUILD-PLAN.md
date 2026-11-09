# Spontaneous Travel Radar: Implementation Plan

> **For agentic workers:** This becomes a Spec Kit project (William's standing rule for new app builds). Task 1 runs the Spec Kit init; from then on execute through the speckit-* skills (constitution once, then specify → plan → tasks → implement → converge), feeding this document into `speckit-plan` and `speckit-tasks` as the plan content. Do **not** use superpowers `executing-plans` or `subagent-driven-development` here. Steps use checkbox (`- [ ]`) syntax for tracking. Ponytail applies throughout: stdlib and the named libraries first, no abstraction for a single use, one small runnable check per non-trivial module, shortest diff that works.

**Goal:** A free, mostly-deterministic tracker that scans round-trip fares for two from Calgary to 20 North American cities every day, scores complete weekend trips, logs everything to a public GitHub repo with a static dashboard, and (after a one-month learning run) wakes a cheap Claude routine only for exceptional deals.

**Architecture:** A Python collector (`radar/`) runs on a GitHub Actions cron, queries Google Flights through `fast-flights`, filters itineraries by the hard trip-window rule, scores them, appends every quote to daily JSONL, and commits `data/latest.json` for a vanilla HTML dashboard served by GitHub Pages. Candidate hits get a Google Hotels check through SerpApi's free tier (hard-capped in code) and a templated brief. A Claude cloud routine (Haiku/Sonnet) fires on a GitHub webhook only for live hits, plus a weekly digest during month one.

**Tech Stack:** Python 3.12, `fast-flights` pinned to the exact release `pip` resolves on day one (e.g. `==3.1.0`), `pyyaml`, `httpx`, `tzdata` (Windows has no system tz database), stdlib `zoneinfo`/`json`/`datetime`; `pytest` with recorded fixtures (no network in tests); GitHub Actions + GitHub Pages (public repo `WilliamEbong/spontaneous-travel-radar`); SerpApi Google Hotels (free tier, 250/month); Ticketmaster Discovery API (free); Open-Meteo (free); Claude cloud routines via the `RemoteTrigger` tool.

**Spec:** `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md` (read it first; this plan argues from it).

## Global Constraints

- **$0 new spend.** Only free tiers: SerpApi free (250 searches/month), Ticketmaster Discovery (5,000 calls/day), Open-Meteo (10,000 calls/day), GitHub Actions and Pages on a public repo. No proxies, no paid APIs, no hosting upgrades. If a step would cost money, stop and record it instead.
- **Claude usage is scarce.** No daily Claude runs. Routines: one weekly digest in month one (Haiku if the routine API allows a model choice, otherwise the cheapest offered) and a hit routine that is created but disabled until month one ends. Routine prompts read pre-computed JSON only; no browsing.
- **Two adults, always.** `Passengers(adults=2)`; every price stored is for two.
- **Prices in CAD**, taxes in, carry-on included: `currency="CAD"`, `carry_on_bags=1`, `exclude_basic_economy=True` on every flight query.
- **Hard trip-window rule** (spec §4), evaluated in `America/Edmonton`: depart from 19:30 the evening before Day 1 through 12:00 on Day 1; land from 17:00 on Day N−1 through 16:00 on Day N. Itineraries outside it are dropped before scoring. Two or more connections are dropped.
- **Lookahead:** windows whose Day 1 is 3 to 45 days from the scan date.
- **Request budget:** ≤ 900 Google Flights fetch *attempts* per scan, retries included, randomised 3 to 7 s apart; the full matrix (28 airports × 6 weekends × 6 dates = 1,008) exceeds it, so Task 4 rotates coverage deterministically and Task 10 reports coverage in health. SerpApi hard cap 3 searches per candidate and 60 per calendar month, counter persisted in the repo (not the cache), quota reserved before each request; Ticketmaster ≤ 1 call per city per window per day; Open-Meteo ≤ 1 call per city per day.
- **Pricing is one-way sums only.** A round-trip price cannot be attached to an independently chosen return leg; do not use round-trip queries for pricing in v1.
- **Git hygiene:** `git add <files>` explicitly, never `git commit -am`; commit and push a workflow before dispatching it; commit dashboard files before live verification.
- **Month one is a learning run:** `config/scoring.yaml: mode: dry-run`; candidates go to `hits/dry-run/`, nothing fires.
- **Secrets** only in `.env` (gitignored) locally and in Actions secrets: `SERPAPI_KEY`, `TICKETMASTER_KEY`. Never in code or committed data.
- **Library APIs:** before writing against `fast-flights`, SerpApi, Ticketmaster or Open-Meteo, fetch current docs with context7 (or the vendor page) in the build session. Signatures in this plan were verified on 2026-11-09 and may drift.

## Review Focus

Inputs the spec implies but no happy-path test exercises, most likely to bite first. Each has a test pinned to its owning task.

1. **Return leg lands after midnight Calgary time** (e.g. departs LAX 22:30 Sat, lands 01:40 Sun). It must count as a Day N−1 evening return, not be dropped or treated as Day N. Test in Task 5.
2. **Time-zone crossing on the outbound** (YYC 19:45 Thu → EWR 01:30 Fri local). Hours-on-ground must be computed in local wall time with correct dates; Day 1 arrival at 01:30 local counts as arriving Day 1. Test in Task 5.
3. **Google returns no flights or a blocked/garbled page** for one route. The scan must record the failure in `data/latest.json.health`, continue with the next route, and never write a partial `latest.json`. Test in Tasks 4 and 10.
4. **SerpApi cap reached mid-month.** The hotel check must return `skipped: "cap"` and the hit must still be written with the band estimate, not crash or exceed the cap. Test in Task 9.
5. **A 4-day stat block overlapping a weekend** (Family Day Monday 2027-02-15 → Sat–Mon 3-day with zero vacation days; Good Friday 2027-03-26 → Fri–Sun with zero vacation days; a Thursday stat such as Canada Day 2027-07-01 → Thu–Sun 4-day with one vacation day). The generator must emit the right windows with the right `vacation_days` and `nights`. Test in Task 3.

---

## File structure

```
spontaneous-travel-radar/
  README.md
  pyproject.toml                 deps: fast-flights (pinned), pyyaml, httpx; dev: pytest
  .gitignore                     .env, .venv, __pycache__, data/cache/
  .env.example                   SERPAPI_KEY=, TICKETMASTER_KEY=
  index.html                     dashboard page (GitHub Pages serves repo root)
  site/app.js, site/style.css    dashboard logic and styles (vanilla)
  config/cities.yaml             20 cities (spec §5) + logistics + bars + climate normals
  config/holidays.yaml           alberta / ontario / federal stats 2026–2027, calendar: alberta
  config/scoring.yaml            weights, flight bands, hotel bands, thresholds, usd_cad, mode
  config/airlines.yaml           fallback carry-on surcharges by airline code
  radar/__init__.py
  radar/config.py                load + validate YAML → dataclasses
  radar/windows.py               day-off blocks → Window objects
  radar/flights.py               fast-flights wrapper: LegQuery → list[Leg], pacing, cache
  radar/itineraries.py           pair legs into Trip per Window; hard-rule filter; hours on ground
  radar/score.py                 bands, components, worth-it score, candidate rule
  radar/events.py                Ticketmaster
  radar/weather.py               Open-Meteo + climate normals
  radar/hotels.py                SerpApi Google Hotels with caps
  radar/hits.py                  hit JSON + templated brief, dry-run routing
  radar/store.py                 JSONL append/read, history percentile
  radar/export.py                latest.json, series.json, weekly-summary.json
  radar/main.py                  CLI: scan | export | summarize, --offline
  scripts/run-scan.ps1           PC fallback (Task Scheduler)
  scripts/smoke_fast_flights.py  day-one smoke test
  tests/fixtures/                recorded fast-flights ResultList pickles/json, SerpApi/TM/OM json
  tests/test_*.py                one file per module
  data/latest.json, data/series.json, data/weekly-summary.json
  data/history/YYYY-MM-DD.jsonl  one line per quote
  data/digests/                  weekly digests (if the routine can commit)
  data/cache/                    per-day API cache (gitignored)
  hits/, hits/dry-run/
  routine/PROMPT-weekly.md, routine/PROMPT-hit.md, routine/CAPABILITIES.md
  docs/superpowers/specs/...     the design
  docs/notes/day-one-smoke.md    smoke-test findings
  docs/LEARNING-RUN.md           month-one procedure + exit checklist
  .github/workflows/scan.yml     daily cron + manual dispatch
```

---

### Task 0: Day-one smoke test of `fast-flights` (riskiest thing first)

**Files:**
- Create: `scripts/smoke_fast_flights.py`
- Create: `docs/notes/day-one-smoke.md`

**Interfaces:**
- Produces: a written record of (a) how much round-trip prices differ from one-way sums (information only; v1 sums one-ways regardless), (b) whether `carry_on_bags=1` changes Flair/WestJet UltraBasic prices (if prices are unchanged, bag coverage is *unverified*, not proven, and the airline surcharge fallback stays on for ULCCs), (c) whether GitHub Actions IPs are blocked, (d) the exact object shapes returned (used by Task 4). Known from upstream source on 2026-11-09: itineraries expose `.price`, `.airlines` (codes), `.flights` (segments) with `.from_airport.code`, `.to_airport.code`, `.departure`/`.arrival` as date/time **integer tuples**, `.duration`; the free parser does **not** populate flight numbers, so that field is optional everywhere.

- [ ] **Step 0: One repo root**

Run `git init` in the project folder (GitHub creation happens in Task 1). Every later commit, including this task's, lands in this root.

- [ ] **Step 1: Create a venv and install deps**

Run (PowerShell, from the project root):
```
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install fast-flights pyyaml httpx tzdata pytest; pip show fast-flights
```
Expected: installs without error; note the exact `Version:` and pin it in Task 1's `pyproject.toml`.

- [ ] **Step 2: Write `scripts/smoke_fast_flights.py`**

It must run, for a Friday 21 days out (`D`) and the following Sunday (`D+2`):
1. One-way YYC→YVR on D, `Passengers(adults=2)`, `currency="CAD"`, `carry_on_bags=1`, `exclude_basic_economy=True`, `max_stops=0`; print count, and for the first three results: `price`, `airlines`, each segment's `from_airport.code`, `departure`, `to_airport.code`, `arrival`, `duration`. Also dump the first result with `dataclasses.asdict` to `tests/fixtures/ff_yyc_yvr_oneway.json` (this is the real fixture Task 4 uses).
2. The same without `carry_on_bags`/`exclude_basic_economy`; print the cheapest price of each run side by side. Repeat both variants for YYC→YVR filtered to Flair (`airlines=["F8"]`) if Flair flies that day.
3. One-way YVR→YYC on D+2 with `latest_arrival_hour=16`; confirm every result arrives ≤ 16:00.
4. Round-trip YYC→YVR D / YVR→YYC D+2 and round-trip YYC→LAS D / LAS→YYC D+2, same flags; print each cheapest round-trip price next to (cheapest one-way out + cheapest one-way back). Information only.
5. One-way YYC→LAS on D with `max_stops=1`; print how many results have 1 stop and what the layover/segment gap looks like; dump a one-stop result to `tests/fixtures/ff_one_stop.json` and, if one appears, a two-stop result to `tests/fixtures/ff_two_stop.json` (otherwise hand-edit a copy of the one-stop fixture to three segments).
6. Repeat step 1 for YYC→MSY (no non-stop exists): confirm `max_stops=0` yields zero results or `FlightsNotFound`, and `max_stops=1` yields results.
Wrap each call in try/except, print the exception type and message, and sleep 4 s between calls.

- [ ] **Step 3: Run it locally and record findings**

Run: `python scripts/smoke_fast_flights.py`
Expected: prints for all six probes and writes the fixtures. Write `docs/notes/day-one-smoke.md` with: the real attribute names and tuple shapes seen; round-trip vs one-way-sum gap per route (for the record; v1 sums one-ways); whether the bag flag changed any price (unchanged ⇒ "unverified", keep ULCC surcharges on); `FlightsNotFound` behaviour; any block/captcha.

- [ ] **Step 4: Block test from GitHub Actions**

Only after Task 1 creates the repo: add a `workflow_dispatch` job that runs `scripts/smoke_fast_flights.py` on `ubuntu-latest`, trigger it with `gh workflow run`, read the log with `gh run view --log`. Record in the note: blocked / not blocked / partial. If blocked, Task 11 chooses the PC host.

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_fast_flights.py docs/notes/day-one-smoke.md tests/fixtures/
git commit -m "chore: day-one fast-flights smoke test, findings and fixtures"
```

---

### Task 1: Repo, Spec Kit, scaffolding

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`, `radar/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create the public repo**

Run: `gh repo create WilliamEbong/spontaneous-travel-radar --public --clone` (or `git init` + `gh repo create --source=. --public --push` inside the project folder). If `gh` is not authenticated, stop and report: William must run `gh auth login`.

- [ ] **Step 2: Spec Kit init (William's standing sequence)**

Run, in order, from the project root:
```
specify init . --integration claude --script ps --force
specify preset add lean
specify integration install codex --script ps
specify integration use codex
specify integration use claude
```
Then add to the project's `CLAUDE.md` and `AGENTS.md` (create if missing): "Spec Kit project: plan and build features with the speckit-* skills (constitution once; then specify → plan → tasks → implement → converge). Do not use superpowers brainstorming, writing-plans, executing-plans, or subagent-driven-development here; superpowers debugging, TDD, and verification skills are still fine."

Then run `speckit-constitution` (short: the Global Constraints above), `speckit-specify` from the design doc, `speckit-plan` and `speckit-tasks` pointing at this file as the plan content. Keep those artifacts thin; this file stays the source of truth.

- [ ] **Step 3: Scaffolding**

`pyproject.toml`: project `radar`, `requires-python = ">=3.12"`, dependencies `fast-flights==<exact version from Task 0>`, `pyyaml>=6`, `httpx>=0.27`, `tzdata`; optional `dev = ["pytest>=8"]`; `[tool.setuptools] packages = ["radar"]` (explicit discovery, so `tests/`, `site/`, `data/` are never packaged); `[tool.pytest.ini_options] testpaths = ["tests"]`.
`.gitignore`: `.venv/`, `__pycache__/`, `.env`, `data/cache/`, `.pytest_cache/`.
`.env.example`: `SERPAPI_KEY=` and `TICKETMASTER_KEY=`.
`README.md`: one paragraph on what it is, the dashboard URL placeholder, how to run `python -m radar.main scan --offline`, where config lives.

- [ ] **Step 4: Verify and commit**

Run: `pip install -e ".[dev]"; pytest` → "no tests ran" exit 5 is fine.
```bash
git add -A
git commit -m "chore: scaffold repo, Spec Kit, pyproject"
git push -u origin main
```

---

### Task 2: Config files and loader

**Files:**
- Create: `config/cities.yaml`, `config/holidays.yaml`, `config/scoring.yaml`, `config/airlines.yaml`
- Create: `radar/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class City:
      key: str; name: str; tier: int; rank: int
      airports: tuple[str, ...]          # first = preferred non-stop
      tz: str                            # IANA
      lat: float; lon: float
      airport_to_core_min: int; transfer_cost_cad_pp_each_way: int
      car_needed: bool
      neighbourhoods: tuple[str, ...]
      season_months: tuple[int, ...]     # empty = year-round
      flight_group: str                  # "yvr" | "sea_pdx" | "medium" | "yyz" | "yul_ord" | "nyc_tier2"
      hotel_group: str                   # "cheap" | "mid" | "expensive"
      hotel_currency: str                # "CAD" | "USD"
      bar_cad: int                       # complete-trip bar for two
      climate: dict[int, tuple[float, float, int]]  # month → (mean_high_c, mean_low_c, rain_days)
  @dataclass(frozen=True)
  class Scoring: weights: dict[str,int]; flight_bands: dict[str, dict[str,int]]; hotel_bands: dict[str, dict[str,int]]; usd_cad: float; mode: str; score_threshold: int; realert_drop_pct: int; lookahead_min_days: int; lookahead_max_days: int; serpapi_monthly_cap: int; serpapi_per_candidate_cap: int
  def load_cities(path="config/cities.yaml") -> list[City]
  def load_holidays(path="config/holidays.yaml") -> set[date]      # for the selected calendar
  def load_scoring(path="config/scoring.yaml") -> Scoring
  def load_airline_surcharges(path="config/airlines.yaml") -> dict[str,int]   # code → CAD per person round trip
  ```

- [ ] **Step 1: Write `config/cities.yaml`**

All 20 cities from spec §5 with the fields above. Values to seed:
- `flight_group`: YVR→`yvr`; SEA, PDX→`sea_pdx`; LAS, LAX, SFO, SAN, DEN, PSP→`medium`; YYZ→`yyz`; YUL, ORD, BNA, AUS→`yul_ord`; EWR/NYC and all Tier 2→`nyc_tier2`.
- `hotel_group`: cheap = DEN, YUL, SEA, PDX, YQB, LAS (weekday flag handled in Task 9); mid = ORD, YVR, YYZ, BOS, DC, BNA, AUS, MEX, MSY, LAX, SAN, PSP; expensive = NYC, SF.
- `bar_cad` = round up to 50 of `2 × amazing_threshold(flight_group) + hotel_good_mid_cad(hotel_group) + 4 × transfer_cost_cad_pp_each_way`, where hotel good midpoints are cheap 240, mid 380, expensive 550 in the city's hotel currency, converted at `usd_cad`.
- Airports: NYC `[EWR, JFK, LGA]`, Chicago `[ORD, MDW]`, LA `[LAX, BUR]`, SF `[SFO, OAK]`, Toronto `[YYZ, YTZ]`, DC `[DCA, IAD]`, Mexico City `[MEX, NLU]`, others single.
- `neighbourhoods`: 2 to 3 well-known central areas per city (e.g. Chicago: Loop, River North, West Loop).
- `climate`: 12 months of (mean high °C, mean low °C, rain days) from standard climate normals; approximate is fine, note the source in a comment.
- `season_months`: PSP `[11,12,1,2,3,4]`; BNA, AUS, SAN leave empty but add `seasonal_route: true` comment; others empty.

- [ ] **Step 2: Write `config/holidays.yaml`**

```yaml
calendar: alberta
alberta: [2026-11-11, 2026-12-25, 2026-12-26, 2027-01-01, 2027-02-15, 2027-03-26, 2027-05-24, 2027-07-01, 2027-08-02, 2027-09-06, 2027-10-11, 2027-11-11, 2027-12-25]
ontario: [2026-12-25, 2026-12-28, 2027-01-01, 2027-02-15, 2027-03-26, 2027-05-24, 2027-07-01, 2027-08-02, 2027-09-06, 2027-10-11, 2027-12-27, 2027-12-28]
federal: [2026-11-11, 2026-12-25, 2026-12-28, 2027-01-01, 2027-03-26, 2027-03-29, 2027-05-24, 2027-07-01, 2027-08-02, 2027-09-06, 2027-09-30, 2027-10-11, 2027-11-11, 2027-12-27, 2027-12-28]
```
Verify each date against an official 2027 calendar before committing (Boxing Day/Christmas observed-day shifts differ by employer; note which rule you used).

- [ ] **Step 3: Write `config/scoring.yaml`**

```yaml
mode: dry-run            # dry-run | live
usd_cad: 1.40
lookahead_min_days: 3
lookahead_max_days: 45
score_threshold: 80
realert_drop_pct: 15
serpapi_monthly_cap: 60
serpapi_per_candidate_cap: 3
weights: {price: 40, time: 15, convenience: 10, city: 15, events: 10, weather: 10}
flight_bands:            # per person, round trip, CAD, realistic; thresholds are upper bounds
  yvr:       {amazing: 120, good: 150, average: 190}
  sea_pdx:   {amazing: 200, good: 260, average: 330}
  medium:    {amazing: 220, good: 280, average: 350}
  yyz:       {amazing: 190, good: 240, average: 300}
  yul_ord:   {amazing: 250, good: 320, average: 400}
  nyc_tier2: {amazing: 320, good: 400, average: 500}
hotel_bands:             # 2 nights, 1 room, fees in, pre-tax, in the city's hotel currency
  cheap:     {amazing: 200, good: 280, average: 400}
  mid:       {amazing: 320, good: 440, average: 600}
  expensive: {amazing: 450, good: 650, average: 900}
```
Band semantics: price ≤ amazing → "amazing"; ≤ good → "good"; ≤ average → "average"; else "bad".

- [ ] **Step 4: Write `config/airlines.yaml`**

`{F8: 110, NK: 120, F9: 120}` (Flair, Spirit, Frontier), with a comment that this applies only if Task 0 found the bag flag ineffective for that airline; default behaviour is to trust Google's carry-on pricing.

- [ ] **Step 5: Write the failing test**

```python
def test_cities_load_and_are_consistent():
    cities = load_cities()
    assert len(cities) == 20
    keys = {c.key for c in cities}
    assert {"vancouver","new_york","mexico_city"} <= keys
    for c in cities:
        assert c.flight_group in {"yvr","sea_pdx","medium","yyz","yul_ord","nyc_tier2"}
        assert c.hotel_group in {"cheap","mid","expensive"}
        assert len(c.climate) == 12 and c.bar_cad % 50 == 0

def test_holidays_selected_calendar():
    hs = load_holidays()
    assert date(2027,2,15) in hs      # Family Day (alberta default)

def test_scoring_bands_monotonic():
    s = load_scoring()
    for g, b in s.flight_bands.items():
        assert b["amazing"] < b["good"] < b["average"], g
    assert s.mode == "dry-run" and sum(s.weights.values()) == 100
```

- [ ] **Step 6: Run to verify failure** — `pytest tests/test_config.py -v` → FAIL (ImportError).
- [ ] **Step 7: Implement `radar/config.py`** with the four loaders; `yaml.safe_load`; convert climate month keys to int; raise `ValueError` naming the city on any missing field.
- [ ] **Step 8: Run to verify pass** — `pytest tests/test_config.py -v` → PASS.
- [ ] **Step 9: Commit** — `git commit -am "feat: config files and validated loader"`.

---

### Task 3: Window generator

**Files:**
- Create: `radar/windows.py`
- Test: `tests/test_windows.py`

**Interfaces:**
- Consumes: `load_holidays()` from Task 2.
- Produces:
  ```python
  CALGARY = ZoneInfo("America/Edmonton")
  @dataclass(frozen=True)
  class Window:
      id: str                     # "<day1 ISO>_<pattern>" e.g. "2026-12-04_fri-off", "2027-07-01_stat-thu-4d"
      days_off: tuple[date, ...]  # consecutive, len 3 or 4
      window_nights: int          # len(days_off) - 1 (window length; hotel nights come from the itinerary, Task 5)
      vacation_days: int          # 0 or 1
      depart_from: datetime       # Calgary tz, 19:30 the evening before days_off[0]
      depart_to: datetime         # 12:00 on days_off[0]
      return_from: datetime       # 17:00 on days_off[-2]
      return_to: datetime         # 16:00 on days_off[-1]
      out_dates: tuple[date, date]    # (day before Day 1, Day 1)
      back_dates: tuple[date, date]   # (Day N-1, Day N)
  def generate_windows(today: date, holidays: set[date], min_days: int = 3, max_days: int = 45) -> list[Window]
  def scan_dates(windows: list[Window]) -> tuple[set[date], set[date]]   # (all outbound dates, all return dates)
  ```

Rules: enumerate Saturdays from `today` to `today + max_days + 7` (so a Day 1 inside the range is never missed because its Saturday falls outside), then for each weekend with Saturday `S` emit `fri-off` (Fri, Sat, Sun; vacation_days 1 unless Fri is a stat → 0) and `mon-off` (Sat, Sun, Mon; vacation_days 1 unless Mon is a stat → 0). If Thursday before is a stat, also emit `stat-thu-4d` (Thu..Sun, vacation 1 for Fri); if Tuesday after is a stat, emit `stat-tue-4d` (Sat..Tue, vacation 1 for Mon). A window is in range when `min_days ≤ (days_off[0] - today).days ≤ max_days`.

- [ ] **Step 1: Write failing tests**

```python
def test_plain_weekend_two_patterns():
    ws = generate_windows(date(2026,11,10), set())
    ids = {w.id for w in ws}
    assert "2026-11-20_fri-off" in ids and "2026-11-21_mon-off" in ids
    w = next(w for w in ws if w.id == "2026-11-20_fri-off")
    assert w.window_nights == 2 and w.vacation_days == 1
    assert w.depart_from == datetime(2026,11,19,19,30,tzinfo=CALGARY)
    assert w.depart_to   == datetime(2026,11,20,12,0,tzinfo=CALGARY)
    assert w.return_from == datetime(2026,11,21,17,0,tzinfo=CALGARY)
    assert w.return_to   == datetime(2026,11,22,16,0,tzinfo=CALGARY)

def test_monday_stat_costs_no_vacation_day():
    ws = generate_windows(date(2027,1,20), {date(2027,2,15)})
    w = next(w for w in ws if w.id == "2027-02-13_mon-off")
    assert w.vacation_days == 0

def test_thursday_stat_makes_four_day_block():
    ws = generate_windows(date(2027,6,10), {date(2027,7,1)})
    w = next(w for w in ws if w.id == "2027-07-01_stat-thu-4d")
    assert w.days_off == (date(2027,7,1),date(2027,7,2),date(2027,7,3),date(2027,7,4))
    assert w.window_nights == 3 and w.vacation_days == 1
    assert w.depart_from == datetime(2027,6,30,19,30,tzinfo=CALGARY)
    assert w.return_to == datetime(2027,7,4,16,0,tzinfo=CALGARY)

def test_lookahead_bounds():
    ws = generate_windows(date(2026,11,10), set(), 3, 45)
    assert all(3 <= (w.days_off[0]-date(2026,11,10)).days <= 45 for w in ws)

def test_scan_dates_shared():
    ws = generate_windows(date(2026,11,10), set())
    outs, backs = scan_dates([w for w in ws if w.days_off[0] in (date(2026,11,20),date(2026,11,21))])
    assert outs == {date(2026,11,19),date(2026,11,20),date(2026,11,21)}
    assert backs == {date(2026,11,21),date(2026,11,22),date(2026,11,23)}
```

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_windows.py -v` → FAIL.
- [ ] **Step 3: Implement `radar/windows.py`** per the Interfaces block.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: trip window generator with stat-holiday blocks"`.

---

### Task 4: Flight fetcher

**Files:**
- Create: `radar/flights.py`
- Create: `tests/fixtures/ff_yyc_yvr_oneway.json` (recorded from Task 0; serialise the returned objects to plain dicts with a small helper in the smoke script)
- Test: `tests/test_flights.py`

**Interfaces:**
- Consumes: `City` (Task 2), `scan_dates` (Task 3).
- Produces:
  ```python
  @dataclass(frozen=True)
  class LegQuery:
      origin: str; dest: str; day: date
      earliest_dep_hour: int | None = None; latest_dep_hour: int | None = None
      earliest_arr_hour: int | None = None; latest_arr_hour: int | None = None
      max_stops: int = 1
  @dataclass(frozen=True)
  class Leg:
      origin: str; dest: str
      dep: datetime; arr: datetime             # tz-aware, local to each airport
      airlines: tuple[str, ...]                # IATA codes
      flight_numbers: tuple[str, ...]          # usually empty: the free parser does not populate them
      stops: int; layover_min: int             # 0 when non-stop
      duration_min: int
      price_cad_2pax: int                      # carry-on included, 2 adults
  class FetchError(Exception): ...             # wraps blocks, parse failures, FlightsNotFound → empty list instead
  class Budget:                                # shared per-scan attempt budget
      def __init__(self, max_attempts: int = 900): ...
      def take(self) -> bool                   # False when exhausted
  def build_queries(cities: list[City], windows: list[Window], scan_date: date) -> list[LegQuery]
  def fetch_leg(q: LegQuery, budget: Budget, *, sleep_range=(3.0, 7.0), cache_dir="data/cache") -> list[Leg]
  def to_leg(raw_itinerary, origin: str, dest: str, origin_tz: str, dest_tz: str) -> Leg | None   # pure; None if 2+ stops or no price
  ```
  Query dates are **departure** dates. `build_queries` takes the windows (not bare date sets) so it knows each date's role, and emits per airport: outbound `(YYC→apt, day-before-Day-1, earliest_dep_hour=19)` and `(YYC→apt, Day 1, latest_dep_hour=12)`; return `(apt→YYC, Day N−1, no hour filter)` because a Day N−1 departure may land late Day N−1 or after midnight on Day N and both are in-window (the exact Calgary-time check happens in Task 5), and `(apt→YYC, Day N, latest_arr_hour=16)`. When one date plays several roles across windows, emit one query with the loosest filter. Dedupe. `max_stops=1` for every city (connections are scored, not banned).
  **Rotation to stay under 900 attempts:** primary airports (first in each city's list) are queried every scan for weekends 1 to 3; weekends 4 to 6 and all secondary airports (JFK, LGA, MDW, BUR, OAK, YTZ, IAD, NLU) are queried on alternating days, chosen by `(scan_date.toordinal() + hash(airport)) % 2`. Queries are ordered nearest weekend first so budget exhaustion drops far-out dates, not near ones. `fetch_leg` calls `budget.take()` before every attempt (retries included) and raises `FetchError("budget")` when it is exhausted.

- [ ] **Step 1: Write failing tests (fixture-based, no network)**

```python
def test_to_leg_parses_fixture_non_stop():
    raw = load_fixture("ff_yyc_yvr_oneway.json")[0]
    leg = to_leg(raw, "YYC", "YVR", "America/Edmonton", "America/Vancouver")
    assert leg.stops == 0 and leg.price_cad_2pax > 0
    assert leg.dep.tzinfo is not None and leg.arr < leg.dep + timedelta(hours=3)

def test_to_leg_drops_two_stop():
    raw = load_fixture("ff_two_stop.json")[0]
    assert to_leg(raw, "YYC", "MSY", "America/Edmonton", "America/Chicago") is None

def test_build_queries_roles_and_filters():
    cities = [c for c in load_cities() if c.key in ("vancouver","new_york")]
    ws = [w for w in generate_windows(date(2026,11,10), set()) if w.days_off[0] in (date(2026,11,20), date(2026,11,21))]
    qs = build_queries(cities, ws, scan_date=date(2026,11,10))
    sat = [q for q in qs if q.day == date(2026,11,21) and q.origin == "YVR"]      # Day N-1 for fri-off: unfiltered
    assert len(sat) == 1 and sat[0].earliest_arr_hour is None and sat[0].latest_arr_hour is None
    sun = [q for q in qs if q.day == date(2026,11,22) and q.origin == "YVR"]      # Day N (fri-off) and Day N-1 (mon-off): loosest = unfiltered
    assert len(sun) == 1 and sun[0].latest_arr_hour is None
    mon = [q for q in qs if q.day == date(2026,11,23) and q.origin == "YVR"]      # Day N only
    assert mon[0].latest_arr_hour == 16
    thu = [q for q in qs if q.day == date(2026,11,19) and q.dest == "YVR"]
    assert thu[0].earliest_dep_hour == 19
    assert all(q.max_stops == 1 for q in qs)

def test_budget_exhaustion_is_a_fetch_error(tmp_path):
    b = Budget(max_attempts=0)
    with pytest.raises(FetchError):
        fetch_leg(LegQuery("YYC","YVR",date(2026,12,4)), b, cache_dir=tmp_path)

def test_rotation_keeps_secondary_airports_alternating():
    cities = [c for c in load_cities() if c.key == "new_york"]
    ws = generate_windows(date(2026,11,10), set())
    a = {q.dest for q in build_queries(cities, ws, scan_date=date(2026,11,10)) if q.origin == "YYC"}
    b = {q.dest for q in build_queries(cities, ws, scan_date=date(2026,11,11)) if q.origin == "YYC"}
    assert "EWR" in a and "EWR" in b and (a ^ b) <= {"JFK","LGA"}
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement `radar/flights.py`**

`fetch_leg`: check `data/cache/<YYYY-MM-DD>/<origin>-<dest>-<day>-<filters>.json`; on miss, `budget.take()` (raise `FetchError("budget")` if False), sleep `random.uniform(*sleep_range)`, call `get_flights(create_query(flights=[FlightQuery(...)], trip="one-way", passengers=Passengers(adults=2), currency="CAD", max_stops=q.max_stops, carry_on_bags=1, exclude_basic_economy=True))`; retry once on a non-`FlightsNotFound` exception after 30 s (another `budget.take()`); cache the `dataclasses.asdict` serialisation; map through `to_leg`. `FlightsNotFound` → `[]` and cache the empty result. Any other failure after retry → raise `FetchError(str(q))`.
`to_leg`: use the shapes recorded in `docs/notes/day-one-smoke.md`: segments are `.flights`, departure/arrival are integer tuples (year, month, day[, hour, minute] as observed), build tz-aware datetimes with `ZoneInfo`; `stops = len(segments) - 1`; `layover_min` = sum of gaps between segments; `flight_numbers` empty when absent; return `None` when `stops >= 2` or `price is None`.

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: One live call as a check** — `python -c "from radar.flights import *; print(fetch_leg(LegQuery('YYC','YVR', date.today()+timedelta(21), latest_dep_hour=12), Budget(5))[:2])"` prints two `Leg`s.
- [ ] **Step 6: Commit** — `git commit -am "feat: fast-flights wrapper with pacing, cache and Leg model"`.

---

### Task 5: Itineraries, hard-rule filter, hours on ground

**Files:**
- Create: `radar/itineraries.py`
- Test: `tests/test_itineraries.py`

**Interfaces:**
- Consumes: `Window` (Task 3), `Leg` (Task 4), `City`.
- Produces:
  ```python
  @dataclass(frozen=True)
  class Trip:
      city_key: str; airport: str; window_id: str
      out: Leg; back: Leg
      flights_cad_2pax: int                 # out.price + back.price (one-way sums only)
      check_in: date; check_out: date       # hotel dates derived from the itinerary (destination-local)
      nights: int                           # (check_out - check_in).days; a Thu-evening arrival with a Sun departure is 3
      hours_on_ground: float                # waking hours, spec §7.1 formula
      best_possible_hours: float            # for the window
  def in_window(out: Leg, back: Leg, w: Window) -> bool
  def hotel_dates(out: Leg, back: Leg) -> tuple[date, date]            # check_in = out.arr local date, minus one day if out.arr local hour < 5; check_out = back.dep local date
  def hours_on_ground(out: Leg, back: Leg, nights: int) -> float      # (back.dep - out.arr) - 3h - 8h*nights, aware-datetime subtraction (UTC-correct across DST), hours, floor 0
  def best_possible_hours(w: Window) -> float                          # (return_to - depart_from) - 3h - 8h*w.window_nights
  def assemble(city: City, w: Window, outs: list[Leg], backs: list[Leg]) -> list[Trip]   # all in-window pairs
  ```
  `in_window` compares `out.dep.astimezone(CALGARY)` to `[w.depart_from, w.depart_to]` and `back.arr.astimezone(CALGARY)` to `[w.return_from, w.return_to]`, inclusive. Note the return leg's arrival is already Calgary-local since `dest == "YYC"`. Because Task 4's Day N−1 return query is unfiltered, this is where a Saturday 22:30 departure landing Sunday 01:40 is kept and a Saturday 14:00 departure landing 16:30 is dropped.

- [ ] **Step 1: Write failing tests (build `Leg`s by hand)**

```python
def leg(o, d, dep, arr, tz_o, tz_d, price=400, stops=0):
    return Leg(o, d, datetime.fromisoformat(dep).replace(tzinfo=ZoneInfo(tz_o)), datetime.fromisoformat(arr).replace(tzinfo=ZoneInfo(tz_d)), ("WS",), ("WS 1",), stops, 0, 90, price)
W = next(w for w in generate_windows(date(2026,11,10), set()) if w.id == "2026-11-20_fri-off")

def test_evening_out_and_after_midnight_return_are_in_window():
    out  = leg("YYC","LAX","2026-11-19T19:45","2026-11-19T22:00","America/Edmonton","America/Los_Angeles")
    back = leg("LAX","YYC","2026-11-21T22:30","2026-11-22T01:40","America/Los_Angeles","America/Edmonton")
    assert in_window(out, back, W)          # Review Focus 1

def test_return_after_4pm_day3_is_out():
    out  = leg("YYC","YVR","2026-11-20T08:00","2026-11-20T08:30","America/Edmonton","America/Vancouver")
    back = leg("YVR","YYC","2026-11-22T15:00","2026-11-22T17:20","America/Vancouver","America/Edmonton")
    assert not in_window(out, back, W)

def test_out_before_1930_is_out():
    out  = leg("YYC","YVR","2026-11-19T19:00","2026-11-19T19:30","America/Edmonton","America/Vancouver")
    back = leg("YVR","YYC","2026-11-22T10:00","2026-11-22T12:20","America/Vancouver","America/Edmonton")
    assert not in_window(out, back, W)

def test_hours_on_ground_crosses_time_zones():
    out  = leg("YYC","EWR","2026-11-19T19:45","2026-11-20T01:30","America/Edmonton","America/New_York")   # Review Focus 2
    back = leg("EWR","YYC","2026-11-22T07:00","2026-11-22T09:45","America/New_York","America/Edmonton")
    # 01:30 Fri → 07:00 Sun local = 53.5h; minus 3h overhead and 16h sleep = 34.5
    assert hours_on_ground(out, back, 2) == pytest.approx(34.5)

def test_hotel_dates_cover_the_arrival_night():
    out  = leg("YYC","EWR","2026-11-19T19:45","2026-11-20T01:30","America/Edmonton","America/New_York")
    back = leg("EWR","YYC","2026-11-22T07:00","2026-11-22T09:45","America/New_York","America/Edmonton")
    assert hotel_dates(out, back) == (date(2026,11,19), date(2026,11,22))      # 01:30 arrival needs Thursday night → 3 nights
    out2 = leg("YYC","LAX","2026-11-19T19:45","2026-11-19T22:00","America/Edmonton","America/Los_Angeles")
    back2 = leg("LAX","YYC","2026-11-22T06:30","2026-11-22T10:00","America/Los_Angeles","America/Edmonton")
    assert hotel_dates(out2, back2) == (date(2026,11,19), date(2026,11,22))    # also 3 nights

def test_best_possible_hours_fri_off():
    # 19:30 Thu → 16:00 Sun = 68.5h; minus 3 minus 16 = 49.5
    assert best_possible_hours(W) == pytest.approx(49.5)
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement `radar/itineraries.py`** per the Interfaces. `assemble` iterates all `outs × backs`, keeps `in_window`, sums the two one-way prices, derives `hotel_dates` and `nights`, drops pairs where `back.dep <= out.arr`.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: assemble trips and enforce the trip-window rule"`.

---

### Task 6: Scoring

**Files:**
- Create: `radar/score.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: `Trip` (Task 5), `City`, `Scoring` (Task 2), events/weather values (Tasks 7) as plain numbers, history percentile (Task 8) as `float | None`.
- Produces:
  ```python
  def flight_band(price_pp: int, group: str, bands: dict) -> str          # "amazing"|"good"|"average"|"bad"
  def hotel_band(total_2n: float, group: str, bands: dict) -> str
  @dataclass(frozen=True)
  class Components: price: float; time: float; convenience: float; city: float; events: float; weather: float
  @dataclass(frozen=True)
  class Scored:
      trip: Trip; band: str; price_pp: int; lodging_cad_est: float; total_cad: float
      components: Components; score: int; candidate: bool; hotel_spike: bool
  def lodging_estimate_cad(city: City, nights: int, s: Scoring) -> float   # good-band midpoint/2 * nights (trip.nights, from the itinerary), converted
  def score_trip(trip: Trip, city: City, s: Scoring, *, n_events: int, weather_score: float, history_pct: float | None, lodging_cad: float | None = None) -> Scored
      # lodging_cad None → use the estimate; a real hotel total (Task 9) re-scores with the same function
  def best_per_window(scored: list[Scored]) -> list[Scored]               # one winner per (city_key, window_id): highest score, then lowest total
  ```
  Component formulas (spec §7.1):
  - price (0–40): band anchors amazing 40, good 28, average 14, bad 0; linear within band on price between the thresholds (below amazing threshold stays 40). If `history_pct` is not None (≥14 days of data): `price = 0.5*band_score + 0.5*40*(1 - history_pct/100)`.
  - time (0–15): `15 * min(1, hours_on_ground / best_possible_hours)`.
  - convenience (0–10): start 10 if both legs non-stop; 5 if any leg has one connection with `layover_min ≤ 150`; 2 if longer. Then −2 if `airport_to_core_min > 45`; −3 if `car_needed`; −2 if `out.arr` local hour in 0..4. Floor 0.
  - city (0–15): `rank * 1.5`.
  - events (0–10): `min(10, 3 + 1.5 * n_events)`; `hotel_spike = n_events >= 6`.
  - weather (0–10): passed in from Task 7.
  - `score = round(sum)`; `total_cad = flights + lodging + 4*transfer`; `candidate = band == "amazing" or (band == "good" and history_pct is not None and history_pct <= 10)`. `candidate` only opens the gate to the hotel check; the hit decision (score ≥ threshold, total ≤ bar, re-alert rule) is made in Task 9's `finalize_hit` after real lodging is known.

- [ ] **Step 1: Write failing tests with spec values**

```python
def test_flight_band_thresholds():
    b = load_scoring().flight_bands
    assert flight_band(119, "yvr", b) == "amazing" and flight_band(120, "yvr", b) == "amazing"
    assert flight_band(121, "yvr", b) == "good" and flight_band(190, "yvr", b) == "average" and flight_band(191, "yvr", b) == "bad"
    assert flight_band(319, "nyc_tier2", b) == "amazing"

def test_hotel_band_expensive():
    b = load_scoring().hotel_bands
    assert hotel_band(449, "expensive", b) == "amazing" and hotel_band(901, "expensive", b) == "bad"

def test_score_amazing_nonstop_vancouver_is_candidate(vancouver_trip_fixture):
    s = score_trip(vancouver_trip_fixture, vancouver, load_scoring(), n_events=2, weather_score=8, history_pct=None)
    assert s.band == "amazing" and s.candidate
    assert s.components.price == 40 and s.components.city == 12
    assert s.score >= 80

def test_connection_costs_convenience(nyc_one_stop_trip):
    s = score_trip(nyc_one_stop_trip, new_york, load_scoring(), n_events=0, weather_score=5, history_pct=None)
    assert s.components.convenience <= 5

def test_history_percentile_blends(vancouver_trip_fixture):
    s = score_trip(vancouver_trip_fixture, vancouver, load_scoring(), n_events=0, weather_score=5, history_pct=50)
    assert s.components.price == pytest.approx(0.5*40 + 0.5*20)
```
Fixtures: build `Trip`s by hand in `conftest.py`: Vancouver non-stop both ways, `flights_cad_2pax=220` (110 pp), `hours_on_ground=35.0`, `best_possible_hours=49.5`, `nights=2` (expected components: price 40, time ≈10.6, convenience 10, city 12, events 6, weather 8 → score ≈ 87); and a one-stop EWR trip with `layover_min=90` on the outbound.

- [ ] **Step 2: Run to verify failure.** - [ ] **Step 3: Implement `radar/score.py`.** - [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: bands, worth-it score and candidate rule"`.

---

### Task 7: Events (Ticketmaster) and weather (Open-Meteo)

**Files:**
- Create: `radar/events.py`, `radar/weather.py`
- Create: `tests/fixtures/tm_chicago.json`, `tests/fixtures/om_chicago.json` (record once with real calls)
- Test: `tests/test_events_weather.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Event: name: str; date: date; segment: str; venue: str; url: str
  def fetch_events(city: City, start: date, end: date, *, api_key: str, cache_dir="data/cache") -> list[Event]
  def parse_events(payload: dict) -> list[Event]
  def weather_score(city: City, days: list[date], *, cache_dir="data/cache") -> tuple[float, str]   # (0..10, "forecast"|"normals")
  def score_from_daily(highs_c: list[float], precip_prob: list[float]) -> float
  ```
  Ticketmaster: `GET https://app.ticketmaster.com/discovery/v2/events.json` with `apikey`, `city=<city name>`, `countryCode=<US|CA|MX>` (the `latlong` parameter is deprecated; `geoPoint` needs a geohash, which `city`+`countryCode` avoids), `startDateTime` and `endDateTime` as the destination-local midnight boundaries **converted to UTC** with `ZoneInfo(city.tz)` and formatted `YYYY-MM-DDTHH:MM:SSZ`, `size=50`, `sort=date,asc`; events in `_embedded.events[]` with `name`, `dates.start.localDate`, `classifications[0].segment.name`, `_embedded.venues[0].name`, `url`. Add `city_tm_name` to `config/cities.yaml` where Ticketmaster's city differs (e.g. "New York" covers Manhattan only; use "New York" and accept it). Cache per `(city, start, end, scan date)`. Verify parameter names against the live docs before coding.
  Open-Meteo: `GET https://api.open-meteo.com/v1/forecast?latitude=&longitude=&daily=temperature_2m_max,precipitation_probability_max&forecast_days=16&timezone=auto`; if any requested day is beyond the forecast horizon, use `city.climate[month]` with `rain_days/30*100` as precip probability and return `"normals"`.
  `score_from_daily`: per day, start 10; subtract 1 per 3 °C the high sits outside 15–27 °C; subtract `precip_prob/20`; floor 0; average over days.

- [ ] **Step 1: Write failing tests**

```python
def test_parse_events_fixture():
    evs = parse_events(load_fixture("tm_chicago.json"))
    assert evs and all(e.segment for e in evs)

def test_event_bounds_are_utc_of_local_midnight():
    start, end = event_bounds(chicago, date(2026,12,4), date(2026,12,6))     # Chicago is UTC-6 in December
    assert start == "2026-12-04T06:00:00Z" and end == "2026-12-07T05:59:59Z"

def test_weather_formula():
    assert score_from_daily([20.0, 22.0], [10, 10]) == pytest.approx(9.5)
    assert score_from_daily([38.0], [0]) == pytest.approx(10 - 11/3)      # 11 °C over 27
    assert score_from_daily([-5.0], [80]) == 0

def test_weather_falls_back_to_normals(monkeypatch):
    far = [date.today() + timedelta(days=40)]
    score, source = weather_score(chicago, far)
    assert source == "normals" and 0 <= score <= 10
```

- [ ] **Step 2: Run to verify failure.** - [ ] **Step 3: Implement both modules with `httpx`, 10 s timeouts, per-day cache files, and `[]` / normals fallback on any HTTP error (log to stderr, never raise).** - [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: Ticketmaster events and Open-Meteo weather scoring"`.

---

### Task 8: Store and history percentile

**Files:**
- Create: `radar/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Produces:
  ```python
  def append_quotes(day: date, rows: list[dict], root="data/history") -> Path     # writes/append data/history/<day>.jsonl
  def read_history(days: int = 90, root="data/history") -> list[dict]
  def route_percentile(price_pp: int, city_key: str, history: list[dict], *, min_days: int = 14) -> float | None
      # % of historical in-window prices for this city that are <= price_pp; None if fewer than min_days distinct scan days
  ```
  Row schema (one per in-window `Trip`): `{scan_date, scan_ts, city, airport, window_id, out_dep, out_arr, back_dep, back_arr, airlines, stops_out, stops_back, flights_cad_2pax, price_pp, band, score, candidate}`; ISO strings, no nested objects.

- [ ] **Step 1: Write failing tests**

```python
def test_append_and_read_roundtrip(tmp_path):
    p = append_quotes(date(2026,11,20), [{"city":"vancouver","price_pp":150}], root=tmp_path)
    append_quotes(date(2026,11,20), [{"city":"vancouver","price_pp":130}], root=tmp_path)
    rows = read_history(90, root=tmp_path)
    assert len(rows) == 2 and p.name == "2026-11-20.jsonl"

def test_percentile_requires_min_days():
    hist = [{"scan_date":"2026-11-20","city":"vancouver","price_pp":150}]
    assert route_percentile(120, "vancouver", hist) is None
    hist = [{"scan_date":f"2026-11-{d:02d}","city":"vancouver","price_pp":100+d} for d in range(1,15)]
    assert route_percentile(105, "vancouver", hist) == pytest.approx(100*5/14)
```

- [ ] **Step 2–4: fail, implement, pass.** - [ ] **Step 5: Commit** — `git commit -am "feat: JSONL quote store and route percentile"`.

---

### Task 9: Hotel check and hits

**Files:**
- Create: `radar/hotels.py`, `radar/hits.py`
- Create: `tests/fixtures/serpapi_hotels_chicago.json` (record once; redact nothing sensitive, it has no key)
- Test: `tests/test_hotels_hits.py`

**Interfaces:**
- Consumes: `Scored` (Task 6), `City`, `Scoring`, events/weather values.
- Produces:
  ```python
  @dataclass(frozen=True)
  class HotelOption: name: str; neighbourhood: str; total_pre_tax: float; total_all_in: float | None; currency: str; rating: float; stars: int; free_cancel: bool | None; late_checkin: bool | None; check_in: str; check_out: str; link: str
      # free_cancel / late_checkin are None ("unknown") unless the response states them; never default to True
  @dataclass(frozen=True)
  class HotelCheck: options: tuple[HotelOption, ...]; band: str | None; skipped: str | None   # skipped: None | "cap" | "no-key" | "error"
  USAGE_PATH = "data/serpapi_usage.json"                       # committed, {"YYYY-MM": n}; NOT in data/cache (Actions runners start empty)
  def serpapi_reserve(month: str, s: Scoring, path=USAGE_PATH) -> bool   # atomically increments and returns False if that would exceed the monthly cap
  def check_hotels(city: City, check_in: date, nights: int, s: Scoring, *, api_key: str | None, cache_dir="data/cache") -> HotelCheck
  def finalize_hit(scored: Scored, city: City, hotels: HotelCheck, s: Scoring, previous: dict | None) -> tuple[Scored, bool, str]
      # re-scores with real lodging when available; returns (rescored, is_hit, reason) where is_hit requires score >= s.score_threshold AND total_cad <= city.bar_cad AND should_realert(...)
  def write_hit(scored: Scored, city: City, hotels: HotelCheck, events: list[Event], weather: tuple[float,str], s: Scoring, root="hits") -> tuple[Path, Path]   # (json, md); under <root>/dry-run/ when s.mode == "dry-run"
  def render_brief(hit: dict) -> str     # the templated markdown, spec §6.2 field list; shows all-in totals, labels pre-tax amounts as such
  def should_realert(hit: dict, previous: dict | None, drop_pct: int) -> bool
  def previous_hit(city_key: str, window_id: str, root="hits") -> dict | None    # last emitted hit for this city-window, live or dry-run
  ```
  `check_hotels`: refuse before calling when `api_key is None` (`skipped="no-key"`). Cache by `(city, check_in, nights, scan date)` so several itineraries on the same stay share one lookup. For each neighbourhood up to `s.serpapi_per_candidate_cap`: call `serpapi_reserve(month)` **before** the request (retries reserve again); if it returns False stop with `skipped="cap"` (keeping any options already fetched). Request: `GET https://serpapi.com/search.json?engine=google_hotels&q=<neighbourhood>, <city>&check_in_date=&check_out_date=&adults=2&currency=<hotel_currency>&hotel_class=4,5&rating=8&free_cancellation=true&sort_by=3&api_key=` (`rating=8` means 4.0+ on SerpApi's scale, so keep the `overall_rating >= 4.3` post-filter; `hotel_class=4,5` excludes 3-star since Google has no 3.5). From `properties[]` keep those with `overall_rating >= 4.3` and `extracted_hotel_class >= 4`; map `total_rate.extracted_before_taxes_fees` → `total_pre_tax` (band comparison, per spec), `total_rate.extracted_lowest` → `total_all_in` (display), `check_in_time`, `check_out_time`, `link`; set `free_cancel`/`late_checkin` only when the payload states them. Keep the 3 cheapest by `total_pre_tax`; band on the cheapest (3-night stays: thresholds × 1.5; Las Vegas uses `mid` when the stay includes a Friday or Saturday night, else `cheap`).
  Hit JSON: `{id, created, mode, city, window_id, dates:{check_in, check_out, nights}, flights:{out:{...},back:{...}}, price:{flights_cad_2pax, price_pp, band, lodging_cad, lodging_source:"estimate"|"serpapi", transfers_cad, total_cad, bar_cad}, hotels:{options:[...], band, skipped}, events:[...], weather:{score, source}, hours_on_ground, components:{...}, score, gate:{score_ok, bar_ok, realert_ok}, links:{google_flights, google_hotels}}`. `id = "<scan_date>_<city>_<window_id>"`. Google Flights link: `https://www.google.com/travel/flights?q=Flights%20to%20<APT>%20from%20YYC%20on%20<out>%20through%20<back>` (good enough; Google parses natural-language queries).

- [ ] **Step 1: Write failing tests**

```python
def test_cap_blocks_before_the_call(tmp_path, monkeypatch, fake_serpapi):
    (tmp_path/"usage.json").write_text(json.dumps({"2026-12": 60}))
    monkeypatch.setattr("radar.hotels.USAGE_PATH", tmp_path/"usage.json")
    hc = check_hotels(chicago, date(2026,12,4), 2, load_scoring(), api_key="x", cache_dir=tmp_path)
    assert hc.skipped == "cap" and hc.options == () and fake_serpapi.calls == 0          # Review Focus 4

def test_cap_at_59_allows_exactly_one_of_three_neighbourhoods(tmp_path, monkeypatch, fake_serpapi):
    (tmp_path/"usage.json").write_text(json.dumps({"2026-12": 59}))
    monkeypatch.setattr("radar.hotels.USAGE_PATH", tmp_path/"usage.json")
    hc = check_hotels(chicago, date(2026,12,4), 2, load_scoring(), api_key="x", cache_dir=tmp_path)   # chicago has 3 neighbourhoods
    assert fake_serpapi.calls == 1 and hc.skipped == "cap" and len(hc.options) >= 1
    assert json.loads((tmp_path/"usage.json").read_text())["2026-12"] == 60

def test_parse_fixture_filters_and_sorts():
    hc = parse_properties(load_fixture("serpapi_hotels_chicago.json"), chicago, 2, load_scoring())
    assert len(hc.options) <= 3 and hc.band in {"amazing","good","average","bad"}
    assert all(o.stars >= 4 and o.rating >= 4.3 for o in hc.options)
    assert hc.options == tuple(sorted(hc.options, key=lambda o: o.total_pre_tax))
    assert all(o.free_cancel in (True, False, None) for o in hc.options)

def test_finalize_hit_enforces_all_gates(scored_vancouver):
    s = load_scoring()
    ok, is_hit, _ = finalize_hit(scored_vancouver, vancouver, HotelCheck((), None, "no-key"), s, previous=None)
    assert is_hit == (ok.score >= s.score_threshold and ok.total_cad <= vancouver.bar_cad)
    _, again, reason = finalize_hit(scored_vancouver, vancouver, HotelCheck((), None, "no-key"), s, previous={"price":{"flights_cad_2pax": scored_vancouver.trip.flights_cad_2pax}})
    assert not again and reason == "realert"

def test_write_hit_goes_to_dry_run(tmp_path, scored_vancouver):
    s = replace(load_scoring(), mode="dry-run")
    j, m = write_hit(scored_vancouver, vancouver, HotelCheck((), None, "no-key"), [], (7.0,"forecast"), s, root=tmp_path)
    assert "dry-run" in str(j) and json.loads(j.read_text())["hotels"]["skipped"] == "no-key"
    assert "Google Flights" in m.read_text()

def test_realert_only_on_15pct_drop():
    assert not should_realert({"price":{"flights_cad_2pax":300}}, {"price":{"flights_cad_2pax":320}}, 15)
    assert should_realert({"price":{"flights_cad_2pax":250}}, {"price":{"flights_cad_2pax":320}}, 15)
```
`fake_serpapi` is a `conftest.py` fixture that monkeypatches `httpx.get` to return the Chicago fixture and counts calls.

- [ ] **Step 2–4: fail, implement, pass.**
- [ ] **Step 5: Commit** — `git commit -am "feat: capped SerpApi hotel check, hit JSON and templated brief"`.

---

### Task 10: Export and CLI (end-to-end offline)

**Files:**
- Create: `radar/export.py`, `radar/main.py`
- Test: `tests/test_main_offline.py`

**Interfaces:**
- Produces:
  ```python
  def write_latest(scored: list[Scored], cities, health: dict, path="data/latest.json") -> None
  def write_series(history: list[dict], path="data/series.json") -> None       # {city: [[scan_date, min price_pp], ...]} last 30 days
  def write_weekly_summary(history, hits_dir="hits/dry-run", path="data/weekly-summary.json") -> None
  # CLI
  python -m radar.main scan [--offline] [--today YYYY-MM-DD] [--cities a,b]   # full pipeline
  python -m radar.main export                                                   # rebuild latest/series from history
  python -m radar.main summarize                                                # weekly-summary.json
  ```
  `latest.json`: `{scan_date, scan_ts, mode, best_by_city:[{city, airport, window_id, dates, flights_cad_2pax, price_pp, band, history_pct, score, candidate, hours_on_ground, stops}], hits:[ids written this scan], candidates:[ids that reached the hotel check], health:{queries_planned, queries_attempted, budget_max, coverage_pct, cache_hits, fetch_errors:[{route, day, error}], no_nonstop:[city keys], serpapi_used_this_month, duration_s}}`. Write to a temp file and `os.replace` so a crash never leaves a partial file (Review Focus 3).
  `scan` order: load config → windows → `build_queries` (nearest weekend first) → fetch with one shared `Budget(900)` (each `FetchError` recorded, loop continues; `"budget"` errors are counted, not listed individually) → assemble → events/weather per (city, window) → score → `best_per_window` → candidates → hotel check → `finalize_hit` → write hits only when `is_hit` (dry-run writes to `hits/dry-run/`, with the gate results recorded even when not a hit so the digest can see near-misses) → append history → export → summarize if Monday. `--offline` makes fetch read only from `tests/fixtures/offline/` (a recorded scan subset for 3 cities) and skips Ticketmaster/Open-Meteo/SerpApi (returns `[]`, normals, `no-key`).

- [ ] **Step 1: Write failing test**

```python
def test_offline_scan_writes_latest_and_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); copy_fixture_tree("offline", tmp_path/"tests/fixtures/offline"); copy_config(tmp_path)
    rc = main(["scan","--offline","--today","2026-11-10","--cities","vancouver,las_vegas,new_orleans"])
    assert rc == 0
    latest = json.loads((tmp_path/"data/latest.json").read_text())
    assert latest["mode"] == "dry-run" and len(latest["best_by_city"]) >= 1
    assert "no_nonstop" in latest["health"] and 0 < latest["health"]["coverage_pct"] <= 100
    assert (tmp_path/"data/history/2026-11-10.jsonl").exists()
    ids = [(b["city"], b["window_id"]) for b in latest["best_by_city"]]
    assert len(ids) == len(set(ids))                                   # one winner per city-window

def test_fetch_error_is_recorded_not_fatal(tmp_path, monkeypatch):
    # make one route raise FetchError in offline mode
    ...
    assert latest["health"]["fetch_errors"] and rc == 0                 # Review Focus 3
```

- [ ] **Step 2–4: fail, implement, pass.** Record the offline fixture set from real calls for Vancouver, Las Vegas and New Orleans (6 dates each) once, with prices as returned.
- [ ] **Step 5: Live dry run** — `python -m radar.main scan --cities vancouver,las_vegas` (two cities, real network, ~70 requests). Inspect `data/latest.json` by eye; confirm prices look like Google's site for one route.
- [ ] **Step 6: Commit** — `git commit -am "feat: export, CLI and offline end-to-end scan"`.

---

### Task 11: GitHub Actions cron (+ PC fallback)

**Files:**
- Create: `.github/workflows/scan.yml`, `scripts/run-scan.ps1`

- [ ] **Step 1: Write the workflow**

Triggers: `schedule: - cron: "0 13 * * *"` (13:00 UTC = 06:00 MST / 07:00 MDT) and `workflow_dispatch`. Two jobs:
- `scan`: `permissions: contents: write`; `concurrency: {group: scan, cancel-in-progress: false}`; `timeout-minutes: 150`. Steps: checkout; `actions/setup-python@v5` with 3.12 and pip cache; `pip install -e .`; `python -m radar.main scan` with `env: SERPAPI_KEY: ${{ secrets.SERPAPI_KEY }}`, `TICKETMASTER_KEY: ${{ secrets.TICKETMASTER_KEY }}`; then `git config user.name "radar-bot"`, `git config user.email "radar-bot@users.noreply.github.com"`, `git add data hits`, `git commit -m "data: scan $(date -u +%F)" || echo "nothing to commit"`, `git pull --rebase`, `git push`; finally `actions/upload-pages-artifact@v3` with `path: .` (the whole repo is the site: `index.html`, `site/`, `data/`, `hits/`).
- `deploy`: `needs: scan`; `permissions: {pages: write, id-token: write}`; `environment: {name: github-pages, url: ${{ steps.deployment.outputs.page_url }}}`; one step `actions/deploy-pages@v4` with `id: deployment`.
Pushes made with `GITHUB_TOKEN` do **not** trigger a branch-based Pages build, so the site must be deployed as an artifact from this workflow; Task 12 configures Pages to "GitHub Actions" as the source.

- [ ] **Step 2: Add secrets** — `gh secret set SERPAPI_KEY` and `gh secret set TICKETMASTER_KEY` (values from William's `.env`; if absent, continue without them and report that William must create free accounts at serpapi.com and developer.ticketmaster.com; the scan runs with `no-key` and empty events).

- [ ] **Step 3: Commit and push the workflow, then run once manually** — `git add .github/workflows/scan.yml; git commit -m "ci: daily scan + Pages deploy"; git push; gh workflow run scan.yml; gh run watch`. Expected: both jobs green, a `data: scan …` commit on `main`. If `fetch_errors` in `data/latest.json` show blocks (HTTP 429/captcha text) for most routes, GitHub IPs are blocked → Step 4.

- [ ] **Step 4: PC fallback (only if blocked)** — `scripts/run-scan.ps1`: activate `.venv`, load `.env`, `python -m radar.main scan`, `git add data hits; git commit; git pull --rebase; git push`. Register with `schtasks /Create /SC DAILY /ST 06:00 /TN "SpontaneousTravelRadar" /TR "powershell -ExecutionPolicy Bypass -File <abs path>\scripts\run-scan.ps1"`. Change the workflow so the `scan` job is skipped on `schedule` (keep `workflow_dispatch`) and add a `push` trigger on `data/**` so a PC push still deploys Pages via the `deploy` job. Document the choice in `README.md`.

- [ ] **Step 5: Commit** — `git add .github/workflows/scan.yml scripts/run-scan.ps1 README.md; git commit -m "ci: daily scan workflow, Pages deploy and PC fallback"`.

---

### Task 12: Dashboard (GitHub Pages)

**Files:**
- Create: `index.html`, `site/app.js`, `site/style.css`

- [ ] **Step 1: Enable Pages with "GitHub Actions" as the source** — `gh api -X POST repos/WilliamEbong/spontaneous-travel-radar/pages -f build_type=workflow` (or repo Settings → Pages → Source: GitHub Actions). Not branch-based: bot pushes would never rebuild it. Record the URL in `README.md`.

- [ ] **Step 2: Build the page (vanilla, no framework, no build step)**

`index.html` loads `site/style.css`, `site/app.js`; `app.js` fetches `data/latest.json`, `data/series.json`, and lists `hits/` via a `hits/index.json` written by `export.py` (add `write_hits_index()` there: `[{id, path_json, path_md, mode, score, total_cad}]`). Sections per spec §6.3: Best right now (table: city, dates, fare for two, band pill, history %, score, 30-day inline-SVG sparkline from `series.json`), Hits (render each `.md` via a 20-line markdown-to-HTML helper or show the JSON fields directly), Would-have-fired (dry-run hits), Weekly digests (`data/digests/*.md` via `digests/index.json`), Health. Load the `dataviz` skill before writing the sparkline and band colours. Phone-first layout, 16 px gutters, dark mode via `prefers-color-scheme`. Last-scan timestamp at the top with a "stale" warning if older than 30 hours.

- [ ] **Step 3: Verify locally with Playwright (William's standing rule)** — serve locally (`python -m http.server 8000`), navigate with the playwright MCP tools, snapshot: table has 20 rows or fewer with band pills, Health shows the scan time and coverage %, no console errors; resize to 375 px and confirm no horizontal scroll.

- [ ] **Step 4: Commit, push, deploy, verify live** — `git add index.html site/; git commit -m "feat: static dashboard on GitHub Pages"; git push; gh workflow run scan.yml; gh run watch`, then open the live Pages URL with Playwright and repeat the snapshot.

---

### Task 13: Claude routines (capability probe, weekly digest, hit routine)

**Files:**
- Create: `routine/CAPABILITIES.md`, `routine/PROMPT-weekly.md`, `routine/PROMPT-hit.md`

The `RemoteTrigger` tool, its model selection, and webhook filtering are **unverified hypotheses**, not completion dependencies. If any of them is unavailable, write the prompts, record what was tried in `routine/CAPABILITIES.md`, and leave William a two-line note on how to create the routine himself in the claude.ai UI. Day one is still done.

- [ ] **Step 1: Discover the routine API shape** — `RemoteTrigger action: list`. Read one existing routine's JSON (if any) to learn field names (schedule, prompt, repository, model/effort, mcp_connections). If none exist, load the `schedule` skill and follow it.

- [ ] **Step 2: Capability probe (one cheap run)** — create a routine `radar-probe` (ad hoc, no schedule; cheapest model) on repo `WilliamEbong/spontaneous-travel-radar` whose prompt: reads `data/latest.json` and prints `scan_date`; tries to commit a one-line `routine/ping.txt`; tries to send a one-line email to williamebong@gmail.com via the Gmail connector if attached. `RemoteTrigger action: run`, then `list_runs` + `get_run_log`. Write `routine/CAPABILITIES.md`: read ✔/✘, commit ✔/✘, email ✔/✘. Delete or disable the probe.

- [ ] **Step 3: Write `routine/PROMPT-weekly.md`** (≤ 25 lines): "Read `data/weekly-summary.json` from the repo. Write a 15-line review for William: how many candidates would have fired and where; whether the flight bands look too loose or too tight per city (compare band distribution to percentiles); any city with zero non-stop found for 7+ days; request health; two concrete `config/scoring.yaml` changes to consider, with numbers. Do not browse. Do not fetch anything else." Delivery per CAPABILITIES: commit to `data/digests/<date>.md` and update `data/digests/index.json`, else email.

- [ ] **Step 4: Write `routine/PROMPT-hit.md`** (≤ 25 lines): "A file `hits/<id>.json` was just committed. Read it and only it. Write 8 to 10 lines: is this worth booking; which of the three hotels and why; what to watch (late check-in, resort fees, events that make the city loud or pricey, basic-fare smell, bad times); one-line verdict. Email the templated brief (`hits/<id>.md`) plus your lines to William. If you can commit, append your lines under `## Claude's take` in the `.md`. No browsing, no re-fetching."

- [ ] **Step 5: Create the routines** — weekly: `RemoteTrigger action: create` with cron Monday 07:00 America/Edmonton, cheapest model, repo bound, prompt from file; enabled; `docs/LEARNING-RUN.md` says to disable it after the fourth digest. Hit: create **disabled**. Attempt `create_webhook_trigger` with GitHub source on the repo, `push` events, filter: added files matching `hits/*.json` only (exclude `hits/dry-run/`, `hits/index.json`, any `.md`, and `data/**`, so the routine's own commits can never re-fire it). It stays disabled until month one ends **and** a test push of a dummy `hits/test.json` is seen to fire it exactly once (then delete the dummy). No daily polling routine and no enabled-but-prompt-guarded routine: both spend usage for nothing. If the webhook filter cannot express the path rule, leave the hit routine disabled and record it in `CAPABILITIES.md`; William can trigger it by hand from the dashboard's hit when one appears. Relay the server-parsed run time and routine URLs into `README.md`.

- [ ] **Step 6: Commit** — `git add routine/; git commit -m "feat: routine prompts and capability notes"`.

---

### Task 14: Learning-run procedure and handover

**Files:**
- Create: `docs/LEARNING-RUN.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/LEARNING-RUN.md`**: the weekly loop (Monday digest → 15-minute session: open dashboard, read digest, edit `config/scoring.yaml`, commit), the exit checklist from spec §8 (21+ days of history per city; dry-run false positives reviewed; bands and per-city `bar_cad` adjusted; hotel check ran on ≥ 3 dry-run candidates and totals checked by hand once against Google Hotels; `data/serpapi_usage.json` under cap; coverage % in health consistently above 80), the go-live steps (`mode: live`, enable the hit routine, confirm the webhook fires exactly once on a test `hits/test.json` then delete it), and the usage guard: disable the weekly digest routine after its fourth run.

- [ ] **Step 2: README**: dashboard URL, routine URLs, how to run locally, how to switch host, where the design and this plan live, the 8 defaulted questions from spec §11 as a checklist for William.

- [ ] **Step 3: Verify day-one "done"**: repo public and live; one real scan committed; dashboard shows data; `mode: dry-run`; weekly routine created; hit routine created but inert; all tests pass (`pytest -q`); `docs/notes/day-one-smoke.md` filled in.

- [ ] **Step 4: Commit and push** — `git add docs/LEARNING-RUN.md README.md; git commit -m "docs: learning-run procedure and handover"; git push`.

---

## Assumptions I made

- `fast-flights` 3.x keeps the `create_query`/`FlightQuery`/`get_flights` API and the `carry_on_bags`/`exclude_basic_economy` flags verified on 2026-11-09. Task 0 confirms.
- Google's bag-inclusive pricing covers Flair/WestJet UltraBasic; the airline surcharge table is a fallback only.
- GitHub Actions `ubuntu-latest` IPs may be blocked by Google; the PC fallback exists for that. Neither costs money.
- GitHub Pages requires a public repo on a free account; the repo contains fares and code only.
- Claude cloud routines can be bound to a GitHub repo and read files from it; whether they can commit or send Gmail is unknown until the Task 13 probe. The system is complete without either.
- Alberta stat calendar by default; William may switch to Ontario in `config/holidays.yaml`.
- Hotel bands compare SerpApi's pre-tax total (`total_rate.extracted_before_taxes_fees`) per the spec; the all-in total (`total_rate.extracted_lowest`) is stored and displayed separately. Task 9's fixture confirms both fields.
- Las Vegas hotel group flips to `mid` on Friday/Saturday nights; all other cities use one group.
- Climate normals and neighbourhood lists are approximate seeds; William edits.
- Ticketmaster's `city` parameter matches the city proper; suburbs and multi-city metros (New York boroughs, Bay Area) are under-counted. Acceptable for a 0–10 "things on" signal.
- Hotel nights come from the itinerary (a Thursday-evening arrival with a Sunday departure is 3 nights), so Thursday departures carry a real lodging cost and score accordingly.

## Codex review

Codex (GPT, via the codex-companion runtime, read-only) reviewed the first draft on 2026-11-09 against the design and upstream sources (fast-flights `querying.py`/`parser.py`, SerpApi Google Hotels docs, Ticketmaster Discovery v2 docs, GitHub Pages docs). Twelve findings; what changed:

| # | Finding | Action |
|---|---|---|
| 1 | A round-trip price cannot be attached to an independently chosen return leg; `fetch_roundtrip_price` could fabricate deals. | **Accepted.** Removed. v1 sums one-way prices; Task 0 records the round-trip gap for information only (now probes LAS too). |
| 2 | `candidate` gated only on flight band; nothing enforced score ≥ 80, the per-city bar, or re-alert suppression; multiple itineraries per city-window could all fire. | **Accepted.** Added `best_per_window` (Task 6) and `finalize_hit` (Task 9) that re-scores with real lodging and enforces all three gates; hit JSON records `gate`. |
| 3 | SerpApi counter lived in the gitignored cache, so fresh Actions runners reset the monthly quota; counter incremented after calls, retries uncounted. | **Accepted.** `data/serpapi_usage.json` committed to the repo; `serpapi_reserve` before every request incl. retries; test at 59 with three neighbourhoods; hotel lookups cached per stay. |
| 4 | Pushes made with `GITHUB_TOKEN` do not trigger branch-based Pages builds. | **Accepted.** Workflow deploys a Pages artifact after the scan (`upload-pages-artifact` + `deploy-pages`, `pages: write`, `id-token: write`, `github-pages` environment); Pages source set to "GitHub Actions". PC fallback keeps a `push` trigger on `data/**` for deploys. |
| 5 | Daily-poll fallback and prompt-guarded enabled routines burn usage; webhook could loop on the routine's own commits; weekly digest never stops. | **Accepted.** No polling routine; hit routine stays disabled until the webhook is proven to fire exactly once; filter excludes `dry-run/`, indexes, `.md` and `data/**`; weekly digest disabled after four runs; `RemoteTrigger` treated as an unverified hypothesis, not a completion dependency. |
| 6 | Bare date sets lose each date's window role; `earliest_arr_hour=17` on the Day N−1 return wrongly excluded a Saturday departure landing Sunday 01:40. | **Accepted.** `build_queries(cities, windows, scan_date)`; Day N−1 return queries unfiltered (exact Calgary-time check in Task 5); tests rewritten. |
| 7 | `nights = len(days_off) − 1` under-prices a Thursday-evening arrival with a Sunday departure (3 hotel nights); elapsed time must be UTC-correct across DST; Saturday enumeration could miss a Day 1 at the lookahead edge. | **Accepted.** `hotel_dates`/`nights` derived per itinerary (check-in moves to the previous day for arrivals before 05:00), `window_nights` kept for the best-possible normaliser; aware-datetime subtraction noted; Saturdays enumerated to `max_days + 7`. Codex confirmed the 34.5 h / 49.5 h test arithmetic. |
| 8 | Adapter contract: times are integer tuples, segments are `.flights`, the free parser does not populate flight numbers; unchanged prices do not prove bag coverage. | **Accepted.** Task 0 and Task 4 updated; `flight_numbers` optional; bag coverage recorded as "unverified" when prices are unchanged and the ULCC surcharge fallback stays on. |
| 9 | `rating=8` means 4.0+, not 8/10; `hotel_class=3,4,5` admits 3-star; pre-tax totals must not be shown as all-in; cancellation/late check-in must be "unknown" when absent. | **Accepted.** `hotel_class=4,5`, `extracted_hotel_class >= 4`, `overall_rating >= 4.3` post-filter; `total_pre_tax` (band) and `total_all_in` (display) stored separately; `free_cancel`/`late_checkin` tri-state. |
| 10 | Execution blockers: one repo root before Task 0's commit; `tzdata` on Windows; exact `fast-flights` pin; explicit package discovery; `git add` not `commit -am`; push workflows before dispatch; commit dashboard before live verification. | **Accepted.** All folded into Global Constraints, Task 0 Step 0, Task 1, Tasks 11–14. |
| 11 | 28 airports × 6 weekends × 6 dates = 1,008 queries exceeds the 900 budget; no shared budget or coverage reporting. | **Accepted.** Shared `Budget(900)` counting attempts incl. retries; deterministic rotation (weekends 4–6 and secondary airports on alternating days; nearest weekend first); `coverage_pct` in health. |
| 12 | `latlong` is deprecated in favour of `geoPoint`; date bounds must be destination-local converted to UTC, not local with a `Z` suffix. | **Accepted with a simpler fix.** `city` + `countryCode` parameters instead of a geohash (no new code); UTC conversion via `ZoneInfo` with a test. |

Nothing rejected.

## Self-review (writing-plans checklist)

- **Spec coverage:** §4 window rule → Task 3 + 5; §5 cities → Task 2; §6.1 config → Task 2; §6.2 collector incl. hotel check, JSONL, weekly summary → Tasks 4–10; §6.3 dashboard → Task 12; §6.4 routines → Task 13; §6.5 risks → Tasks 0, 4, 9, 11; §7 scoring, bands, candidate rule, realistic price, currency → Tasks 2, 6, 9; §8 learning run → Task 14; §9 layout → file structure; §10/§11 decisions and defaults → Tasks 2, 11, 13, 14.
- **Type consistency:** `Leg`, `Trip`, `Scored`, `Window`, `City`, `Scoring`, `HotelCheck` names and fields are used identically across Tasks 3–10.
- **Review Focus:** 1 and 2 → Task 5 tests; 3 → Tasks 4 (FetchError) and 10 (atomic write, error recorded); 4 → Task 9 cap test; 5 → Task 3 stat tests.
- **Proportion:** signatures and tests, not bodies; the one algorithm spelled out (score components) is the spec's own.
