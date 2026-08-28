# Design decisions

Why the site looks and behaves as it does. Written down because most of
these are trade-offs rather than right answers, and the reasoning is the
part that gets lost — the CSS only records what was chosen, never what was
tried and rejected.

`README.md` covers how to work on the site; this is why it is shaped the
way it is.

## The subject sets the palette

The archive is Kodachrome slides in card mounts, three children's diaries,
and a van. So: a dark room (`--ink #17130f`) with lit paper cards
(`--paper #efe3c8`), slides in mounts that echo the cardboard originals,
and Kodachrome red (`--kodachrome #c1432a`) as the single accent. Fraunces
for display, Lora for reading, IBM Plex Mono for anything that is data —
dates, photo ids, mileages.

The one thing to preserve if any of this is revisited: the page cards read
as paper under a lamp, and the accent is the red of the film stock, not a
brand colour.

## Text has a measure; photographs take the width

The shell is `min(1500px, 94vw)`. It used to be 1100px, which left ~250px
of dead margin down each side of a 1600px screen while the slides stayed
small.

Widening it alone would have made things worse: a 1500px shell gives
running text 112-character lines, nearly twice a comfortable measure. So
every text element is capped at **68 characters** — diary entries, stop
narratives, tag and index prose — and the width freed by widening goes
entirely to photographs, grids and the map, which want it.

This is the rule to apply to anything added later: **if it is read, cap it;
if it is looked at, let it run.**

## The diary: three shapes, decided by how many slides survive

A layout that suits thirteen photographs strands a page that has one, and
nearly half the diary has two slides or fewer.

| slides | treatment |
|---|---|
| 0 | text only |
| 1–2 | slides sit in the diary after the first entry, floating into the margin on wide screens |
| 3+ | a toggle: slides alongside the text (default), or below it |

**Why the margin for one or two.** A column layout on those days left the
right of the page empty for its whole height. Putting the slide in the
margin fills exactly the space the text was never going to use, and it
reads early, next to the entry it belongs with. It follows the treatment
the children's drawings already had.

**Wrapping the text around the photo was tried and rejected.** It works
mechanically, but only by removing the measure cap — which produced
112-character lines. The margin float gets the same "photo early, text
continues" effect with the measure intact.

## Why the slides float rather than sit in a grid

In the alongside layout the diary text floats left and the slides run in
normal flow beside it, continuing full width once the text ends.

The reason is that **how many slides fit beside the text depends on how
much the children wrote that day**, and no build step can know that. 24
November has three long entries and a drawing; 1 September has four lines.
A grid would need that number at build time. A float lets the browser
answer it.

The consequence: only inline-level content wraps around a float, so the
slide grid becomes a block of inline-blocks in this mode.

## The size cascade

Slide width steps down as the window narrows, so the column beside the text
always holds whole slides rather than one and a sliver:

| window | slides beside the text |
|---|---|
| ≥ 1460px | 2 × 300px |
| ≥ 1330px | 2 × 240px |
| ≥ 1100px | 1 × 300px |
| ≥ 1040px | 1 × 240px |
| below | none — everything under the diary |

**The breakpoints are measured, not derived.** They were checked by probing
rendered geometry at each width. They assume the 34rem text column; change
that and they drift, which is the main fragility here.

The cascade is deliberately **non-monotonic**: widening from 1300 to 1340
makes each slide *shrink*, because two smaller ones beat one larger. Anyone
dragging a window edge sees that as a glitch. Kept, because the end states
are what people experience.

## Rows are centred, not ranged left

A row of slides that does not fill the width centres, rather than sitting
against the left edge while the column above it sits right. Full rows are
unaffected. The section heading centres with them, or it hangs to the left
of the content it labels.

The photo grids use **flex, not grid**, for this: grid's track count is
fixed for the whole grid, so `justify-content` centres the tracks and
leaves a lone item in the first of them. A wrapping flex row centres
whatever is actually on each line.

## Slide sizes and the size budget

GitHub Pages caps a published site at **1 GB**, which is the constraint
behind every size decision.

| | |
|---|---|
| `thumb/` 600px | 55 MB — twice the 300px display size, for retina |
| `display/` 1200px | 165 MB — trimmed from 1600px to make room |
| `full/` native | 488 MB — the downloadable copy |
| `docs/` total | ~800 MB |

`display` was reduced from 1600px/q87 to 1200px/q82 specifically to afford
`full/`. At the old size the total would have been ~955 MB, with no room to
build on.

## The map: crosses, not dots

Stops are marked with a cross drawn in pen, not a circle. The route is
already a dashed Kodachrome line, so the marker should read as **a stop
marked by hand on a paper map**, not a UI pin.

- Each stop's slug seeds a small tilt and mirror, so no two crosses are
  identical — stable across reloads, varied across the map.
- Every stroke is drawn twice, a paper-coloured halo under the red, so the
  mark reads on the dark terrain tiles as well as the pale street ones.
- The strokes bow slightly. Straight ones read as a multiplication sign.

**U+2717 (✗) was considered and rejected.** None of the site's three
webfonts contain the glyph, so it would fall back to a different system
font on every platform — DejaVu renders it boldly, Gentium thinly. Bringing
the taper into the SVG was tried too; it loses at 22px, where the halo
collapses into a four-pointed star.

## Details worth keeping

- **Slide-by-slide navigation** runs date-first, then id — not id alone,
  because a roll can straddle a border (16.32–16.38 are India content on a
  Pakistan roll) and only the date orders those correctly. One unbroken
  walk from 01.01 at Cobham to 26.37 in Bangkok.
- **Static URLs carry `?v=<content hash>`**, so a returning visitor picks up
  changed CSS and JS immediately and unchanged files are not re-fetched.
- **The layout toggle appears only once JavaScript runs**, and is hidden
  below 1040px where it would do nothing. The alongside layout is what the
  CSS does on its own, so a visitor without JavaScript gets the default
  rather than a fallback.
- **`figure` carries a 40px browser margin.** It went unreset for a long
  time, quietly shrinking every slide mount and inflating the gaps. Worth
  remembering before adding another figure-based component.
