# Travel Radar: the visual system

The dashboard and the scoring table use William's archive-of-looking system (his default for visual work, pinned for
this project on 2026-11-11): contemporary editorial design built from the material culture of knowledge. One fixed
horizon, paper below it, serif headlines, mono figures, ivory and ink with one payoff colour. The rules live in
`~/.claude/skills/archive-of-looking/SKILL.md`; this file records how they land in `site/style.css`.

## The one device

The first frame (`.frame`, `index.html`) is a title card: 100svh tall, the photograph filling it, the verdict in serif
above the horizon, the Earth's night limb (NASA, ISS, `site/art/`) landing on the horizon at 63.3% of the frame, and
under the horizon one line in ivory (mono kicker, serif city, mono figures): today's best deal or the top hit, a link
to its card. The photograph's credit sits in the footer. Everything after the frame is paper. No other frame draws
the axis; section rules are ordinary hairlines.

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
| `--control-line` | ink at 55% | ivory at 55% | boundaries of switches, buttons, inputs (3.6:1) |
| `--caption-card`, `--rust-card`, `--ochre-card` | `#5F5A50`, `#8E4A2E`, `#7A5818` | ivory at 72%, `#D1A458` | the three text colours on cream, where the ivory values fall under 4.5:1 |

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

- Trays (`article.city`) and drawers (`.prow`): transparent on the paper, 1 px keyline, a 3 px rule on top in the class
  colour (ochre = no day off needed, grey = needs a day off). A hit is a tray on cream with a rust keyline and a rust
  numeral. Empty states and the daily note are cream slips (`.slip`).
- The daily note is a page specimen: cream, keyline, a mono caption line, serif title.
- Dialogs: cream, keyline, no radius, no shadow; the backdrop is ink at 50%.
- Controls: square. Buttons bounded at 55% ink, the primary one rust with ivory text; the switch is a square slide
  (ink when on); the sort is plain mono words with a rust underline on the chosen one; inputs and the filter are
  bounded on the page ground. Links are rust in Franklin Gothic Medium with no underline, ink on hover. Hover washes
  only on devices with a pointer (`@media (hover: hover)`).
- Grain: one fixed SVG `feTurbulence` layer over the page at 8% multiply (7% screen in dark), `body::after`.
- Corners square everywhere except the health dot, the chart's end dot and status dots.

## Motion (D-81)

Motion is state and reveal, never decoration. One easing everywhere, `--ease: cubic-bezier(0.3, 0, 0.7, 1)`, near-linear;
only transform, opacity, clip and a dash offset move, with one exception named below. William reads this page for ten
seconds a day, so nothing loops, bounces or springs, and nothing waits for a choreography.

- **The one authored moment: the handover.** The first frame is `position: sticky` under the paper (`.paper`, opaque, at
  least a viewport tall), so the paper slides up over the Earth's limb as the visitor scrolls. Scrubbed by the scroll
  itself (`animation-timeline: scroll(root)`): the headline and the deal line lift 20 px and fade over the first 36% of
  a viewport, so they are gone when the paper reaches the horizon (at 36.7%) and the words leave with the limb; the
  plate pushes in 4% and a night overlay darkens it to 50% over the first viewport. The bar turns to paper 64 px
  before the paper reaches it, and the frame stops painting once covered (`.gone`), both from IntersectionObservers on
  a sentinel the height of the frame ending at the paper's top edge (pixel margins, rebuilt on resize; a jump straight
  past it still changes its state). Engines that cannot read the scroll get `.frame.past`, a 0.4 s fade once the paper
  is half way up.
- **Arrival.** The headline rises 10 px over 0.6 s, the deal line 0.15 s later; the photograph pushes in 4.5% over 28 s.
  Six empty keyline trays and one caption ("Reading today's scan…") sit in the markup until the JSON lands; nothing
  loops. Trays, drawers and hit cards fade up 10 px over 0.5 s the first time they come into view, the ones arriving
  together 60 ms apart (300 at most); the classes come from JS and come off again after the card's own transition (a
  focused card shows regardless).
- **Open and close.** Every `<details>` opens through `::details-content` with `interpolate-size: allow-keywords`: the
  height eases over 0.35 s and the body fades in over 0.45 s; closing runs the same in reverse. This is the one layout
  animation on the page, one card at a time; engines without it cut. The chevron turns over 0.25 s. The breakdown slip
  fades and settles 6 px over 0.3 s and fades out before it goes (`@starting-style`, `display` with `allow-discrete`).
  When a tray opens its price line draws itself over 0.8 s (a dash offset on a path with `pathLength="1"`) and the end
  dot lands at the end. Tray bodies and briefs are built or fetched at the first sign of interest (hover, focus, touch)
  so the height eases in one movement.
- **Feedback.** Hover washes and keyline darkening on devices with a pointer; a press (`:active`) washes every summary,
  sort word and calendar day; buttons settle 1 px; links turn ink; 150 ms. Sorting slides each tray from where it was to
  where it lands over 0.4 s (FLIP, transform only; a tray coming from more than a viewport away fades in instead).
  Dialogs rise 12 px (the panel 24) and fade over 0.3 to 0.35 s. A breakdown opened while its card is still moving
  finishes the card's motion first, so the fixed slip is placed against the viewport.
- **Reduced motion.** `prefers-reduced-motion: reduce` turns off every transition and animation, pseudo-elements, the
  scroll-driven ones and `::details-content` included; the reveal classes are never added; the Web Animations are
  skipped, and cancelled if the preference changes mid-visit; the page cuts straight.

## Not here

Pills, badges, eyebrows, uppercase labels, drop shadows, gradients as decoration, glass, rounded cards, coloured
side stripes, icons as glyphs or emoji. The icon set is the inline SVG sprite in each page (stroke 1.5).
