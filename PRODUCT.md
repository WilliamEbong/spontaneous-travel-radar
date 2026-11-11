# Travel Radar: product truth

**What it is.** A deal radar for spontaneous weekend trips from Calgary for two adults. A collector scans Google
Flights every morning, scores every trip against what that route normally costs, checks real lodging for the few
candidates, and a daily Claude note researches what is on. The dashboard answers one question on William's phone:
is anything worth booking today?

**Who uses it.** William (and his partner), on a phone, most mornings, for about ten seconds; on a laptop when a
question needs the detail (why did Vancouver score 54, what did Toronto cost last week). Non-technical: the
settings panel exists so nothing ever needs a terminal.

**Surfaces.** `index.html` (the dashboard: verdict, hits, passed trips, every city, daily note, health sheet,
settings panel) and `table.html` (one scan day's scoring table). Static files on GitHub Pages, no build step, no
framework; JSON written by the collector and the routine.

**Mode.** Operate. The visitor completes a task: read the verdict, scan the best deals, open one trip's evidence.

**What must stay true.** Hits first, then every trip that scored 70+, then every city's best deal, then the daily
note. Two trip classes kept visibly distinct (no day off needed vs needs a day off), never by colour alone. Every
score opens its breakdown on hover, focus or tap. Prices are for two adults; the flights figure is per person. Quiet
is the system working: "Nothing worth booking today" is the normal state and must read as calm, not as failure.
Health and settings stay one tap away. Everything on the page is readable at phone width with no horizontal scroll.

**Brand commitments.** The visual world is William's archive-of-looking system (editorial design from the material
culture of knowledge: one fixed horizon, Perpetua / Franklin Gothic / Consolas with Cormorant Garamond / Libre
Franklin / IBM Plex Mono as web fallbacks, ivory paper, ink, rust accent, archival imagery, square corners, no
pills, badges, eyebrows or drop shadows). Chosen by William on 2026-11-11 ("archive of looking").

**Constraints.** $0 to run; the only external resources are the pinned js-yaml script (settings) and web fonts. No
analytics. Data text is always inserted as text, never HTML. Dark mode follows the system preference.
