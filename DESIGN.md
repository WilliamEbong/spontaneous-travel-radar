# Travel Radar: the visual system

The dashboard and the scoring table use William's archive-of-looking system (his default for visual work, pinned for
this project on 2026-11-11): contemporary editorial design built from the material culture of knowledge. One fixed
horizon, paper below it, serif headlines, mono figures, ivory and ink with one payoff colour. The rules live in
`~/.claude/skills/archive-of-looking/SKILL.md`; this file records how they land in `site/style.css`.

## The one device

The first frame (`.frame`, `index.html`) is a title card: 100svh tall, night ground, the verdict in serif above the
horizon, the Earth's night limb (NASA, ISS, `site/art/`) landing on the horizon at 63.3% of the frame, the dark
planet with city lights below it, a mono plate caption at the foot. Everything after the frame is paper. No other
frame draws the axis; section rules are ordinary hairlines.

## Tokens (`:root` in `site/style.css`)

| Token | Light | Dark | Role |
|---|---|---|---|
| `--ground` | `#F3EFE4` ivory | `#2C2A27` charcoal | page |
| `--card` | `#E9E1CD` cream | `#363330` | slips, pages, the health sheet, the settings panel, the breakdown panel |
| `--ink` | `#1D1C1A` | `#F3EFE4` | text, numerals |
| `--graphite` | `#3C3A35` | ivory at 80% | secondary text |
| `--caption` | `#6B665C` | ivory at 70% | captions, mono meta (5.0:1 on ivory) |
| `--grey` | `#8B867B` | same | rules and the day-off class rule; never text |
| `--rust` / `--rust-ink` | `#A2573B` | `#B98A3E` / `#D1A458` | the payoff: hits, exceptional, the Save button, the sort underline |
| `--ochre` / `--ochre-text` | `#B98A3E` / `#8A6420` | `#B98A3E` / `#D1A458` | the no-day-off class rule and label |
| `--green`, `--blue` | `#4E6A58`, `#6E8496` | lighter | good (ladder), status ok |
| `--series` | `#236292` Prussian blue | `#7FA6C8` | the price line |
| `--night` | `#181417` | same | the first frame's ground, matched to the photograph |
| `--keyline`, `--hairline` | ink at 30%, 16% | ivory at 30%, 16% | card edges, table rules |

Status words: ok green, warn ochre-text, bad rust. Colour never carries meaning alone: every class, ladder rung and
status is printed as a word beside it.

## Type

- Display `--serif`: Perpetua, Cormorant Garamond (web), weight 500 requested so Cormorant renders at 500 and Perpetua
  at its one regular weight. Sentence case, no letter-spacing, line height 1.02 to 1.04. Hero `clamp(2.5rem, 9.2vw,
  6rem)`, section h2 2.125 / 2.75 rem, city names 1.875 rem, score numerals 2.5 rem (3.5 rem in drawers, 1.5 rem in
  tables), sheet titles 1.875 rem.
- Text `--sans`: Franklin Gothic Book, Libre Franklin; `--sans-m` Franklin Gothic Medium / Libre Franklin 500 for
  labels, item titles and buttons. Body 1 rem / 1.45, lead 1.1875 rem, hints 0.9375 rem.
- Data `--mono`: Consolas, IBM Plex Mono. Every figure, date, airport code, caption, meta line and status: 0.8125 rem
  (0.75 rem captions, 1.375 rem the trip total).
- The web faces load from Google Fonts with `display=swap`; the installed faces win on William's PC.

## Surfaces

- Trays (`.city`) and drawers (`.prow`): transparent on the paper, 1 px keyline, a 3 px rule on top in the class
  colour (ochre = no day off needed, grey = needs a day off). Hits and empty states are cream slips (`.slip`).
- The daily note is a page specimen: cream, keyline, a mono caption line, serif title.
- Dialogs: cream, keyline, no radius, no shadow; the backdrop is ink at 50%.
- Controls: square. Buttons keylined, the primary one rust with ivory text; the switch is a square slide (ink when
  on); the sort is plain mono words with a rust underline on the chosen one; inputs and the filter are keylined on the
  page ground.
- Grain: one fixed SVG `feTurbulence` layer over the page at 8% multiply (7% screen in dark), `body::after`.
- Corners square everywhere except the health dot, the chart's end dot and status dots.

## Motion

The hero headline rises 10 px over 0.6 s; the photograph pushes in 4.5% over 28 s; both `cubic-bezier(0.3, 0, 0.7, 1)`.
Transitions 150 to 300 ms. `prefers-reduced-motion` removes all of it. No parallax, bounce or springs.

## Not here

Pills, badges, eyebrows, uppercase labels, drop shadows, gradients as decoration, glass, rounded cards, coloured
side stripes, icons as glyphs or emoji. The icon set is the inline SVG sprite in each page (stroke 1.5).
