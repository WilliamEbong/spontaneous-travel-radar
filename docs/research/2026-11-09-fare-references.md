# Fare references from Calgary: what a deal is, per route (research of 2026-11-09)

Purpose: seed `config/references.yaml` with a per-route ladder (typical / good / exceptional) so the
price score is relative to what each route normally costs, not to a fixed budget. The scan's own
history refines these numbers; the Dec 9 tuning run re-fits them.

All prices CAD, per person, round trip, **carry-on included**, any fare family (basic allowed).

## Method

Three independent sources per city, then a judgment call:

1. **Google Flights "usually costs" range** (history-based, read from the live results page for a
   Friday–Sunday weekend, 1 adult, 12–14 Feb 2027 and 16–18 Jul 2027). Its floor is the anchor for
   *typical*. Where the floor is a Flair no-bag fare, $45–90 was added for bags; where only
   connections were cheap, the nonstop level was used because the scoring prefers nonstop.
2. **YYC Deals posts** (Chris Myden's Calgary deal blog, which posts only fares well below normal).
   Across the 20 cities the posted prices sit 30–45% under Google's typical floor, consistently.
   That level is *good*. The best posts of the last few years, +15% for fare inflation since 2019,
   give *exceptional*: about 55–60% of typical.
3. **Our day-one scan floor** (3–45 days out, Standard fares only, carry-on, inside the time rules).
   It runs 1.5–3× the typical level everywhere, which measures the Standard-only filter, not the
   market. Recorded for the comparison only.

Sanity anchor: William's own Calgary–Vancouver trips in Jan–Feb 2026, AC or WestJet with a carry-on,
were under $200 round trip. On this ladder that is "good, not exceptional", which matches his view
that $200 to Vancouver does not move him.

## Table

| City | Deal posts (recent; older) | Google typical floor Feb / Jul | Our floor | Typical | Good | Exceptional | Confidence |
|---|---|---|---|---|---|---|---|
| Vancouver | none since 2022; $100–135 (2018–22) | 182 / 364 | 484 | 200 | 150 | 120 | high |
| Seattle | $197 (2024); $166–201 | scrape failed | 603 | 280 | 200 | 160 | medium |
| Portland | $189 (2022) only | 543 (1-stop) / 700 | 778 | 450 | 300 | 200 | low |
| Denver | $174–240 (2023–24); $158–231 | 545–616 / 700 | 949 | 500 | 300 | 220 | high |
| Las Vegas | $188 (2023); $132–230 (2022–23); "normal ~$325–350" | 329 / 510 | 1,056 | 340 | 230 | 170 | high |
| Toronto | $254 (2023); $190–310 (2019–22) | 351 / 554 | 820 | 400 | 280 | 200 | high |
| Montreal | $215–336 (2024–26); $116–138 (2022) | 547 / 598 | 668 | 520 | 330 | 240 | high |
| Quebec City | $195–399 (2025–26, seasonal nonstop) | 779 / 707 (stops) | 1,106 | 720 | 450 | 330 | medium |
| Boston | $258–381 (2023–25) | 630 / ~800 (stops) | 1,431 | 700 | 420 | 300 | medium |
| New York | $334 (2025); $265–348 | 592 (stops), 863 nonstop / 766 | 828 | 650 | 420 | 320 | high |
| Washington DC | $249–356 (2023–25) | 586 (stops) / unreliable | 986 | 650 | 420 | 300 | medium |
| Nashville | $260 (2025) | 525 (stops) / 875 nonstop | 702 | 620 | 400 | 280 | medium |
| Austin | $176–361 (2024–25) | 599 (stops) / 1,014 | 716 | 650 | 400 | 280 | medium |
| New Orleans | none, ever | 903 / 895 (stops) | 1,292 | 900 | 550 | 380 | low |
| Mexico City | $479 (2025 launch); $280–361 (2018–19) | 755–936 / 870 | 1,024 | 850 | 550 | 400 | medium |
| Los Angeles | $223 (2024), $220 (2023) | 435 / 417 | 859 | 480 | 300 | 220 | high |
| San Francisco | $196 (2024), $176 (2022) | 424 / 567 | 628 | 480 | 300 | 210 | high |
| San Diego | $207–246 (2023), $284 (2024) | 516 (stops) / 819 | 1,007 | 600 | 380 | 260 | medium |
| Palm Springs | $220–278 (2022–23, winter) | no data | 741 | 450 (winter) | 300 | 230 | low |
| Chicago | $263–279 (2024–25); $204 record | 498 (stops), 656 nonstop / 562 | 685 | 550 | 350 | 260 | high |

Route facts that matter: no nonstop at all to New Orleans; seasonal or limited nonstop to Portland,
Quebec City, Boston, Nashville, Austin, San Diego (winter), Palm Springs (winter only). New Orleans
stays on the list (William's call: it is the strongest city for the "cannot get this in Calgary"
test) with low confidence and day-off trips only.

## Hotels

Only Vancouver was researched to depth. Downtown Vancouver, 15–17 Jan 2027, 2 adults, 4–5 star,
rating 4.0+, Google Hotels, per night before ~18.5% tax and fees: Quality Inn Downtown $118 (not a
real 4-star), Hotel Belmont $170, Georgian Court $177, Grand Park $179, Level Yaletown (5-star) $203
"Deal", Sheraton Wall Centre $219 "Deal", Hilton $244, Sutton Place (5-star) $249 "Deal", Hyatt
Regency $262 "Deal". Market: Vancouver has Canada's highest rates; citywide ADR $284 (2025), $330
July 2025, $373 Sept 2026; January–March are the cheapest months, January citywide ≈ $203.

Ladder for a room you would be happy in (Sheraton, Hyatt, Sutton Place, Level tier), Vancouver,
winter, per night pre-tax: typical 230, good 170, exceptional 130. Google's per-hotel "Deal" flag
("X% less than usual") is a free history signal and should be stored with every lookup.

The other 19 cities need the same pass (one Google Hotels lookup per city per season, about 40
lookups, inside the SerpApi quota). Until then their room references are estimates and must be
marked `source: estimate` in the config.

## Complete-trip ladder, worked example (Vancouver, January, two people, 2 nights, transit $40)

- Typical: 2×200 + 2×230×1.185 + 40 ≈ 985
- Good: 2×150 + 2×170×1.185 + 40 ≈ 743
- Exceptional: 2×120 + 2×130×1.185 + 40 ≈ 588 (about 40% below typical)

Price score anchors chosen from this: 45 points at 60% of the route's typical complete trip or
less, about 25 at 75%, 0 at 100%, a gentle negative slope beyond so cheaper still ranks higher among
non-deals. With January weather (4/10), full time (20), convenience (10) and city (12), the "good"
trip scores about 74 (a near-miss), $650 scores about 83 (a hit), the exceptional trip about 90.

## Weak spots

Seattle's Google scrape failed; Palm Springs returned nothing (winter-only route; retry needed);
Washington's July figure was USD; several Google typical floors equal the current cheapest fare,
meaning a thin range for that search. YYC Deals post dates came from search snippets, so months are
approximate. These widen the error bars on five cities; they do not change the shape.

## Sources

Google Flights results pages (live, 2026-11-09, via Firecrawl); yycdeals.com tag pages and post
titles; Business in Vancouver and Daily Hive on Vancouver hotel rates (CoStar data); Airbnb newsroom
(CoStar July 2025 ADR); Gokanada (2023 downtown average); Ratepunk, Momondo, Skyscanner, Expedia,
Priceline route pages for monthly medians and booking windows; Google Hotels via SerpApi (live).
