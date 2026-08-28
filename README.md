# The Trip — 1976

> **Edit this in [the-trip-archive](https://github.com/fcbond/the-trip-archive), not here.**
> This repository is a deploy target: `docs/`, `metadata/`, `web/` and
> `scripts/` are copied in by `scripts/deploy.py` from the private archive
> repo, which also holds the original scans the site is built from. Changes
> made directly here will be overwritten by the next deploy.

A family's overland journey from London to Bombay by van in 1976, rebuilt
from their slides, diaries and letters as a browsable site: a map of every
stop, the diary day by day, and 903 photographs.

Photographs are © 1976 Monique Bond, released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

**Other documents in this repo**

- `TODO.md` — outstanding work, and what blocks publication.
- `METADATA.md` — the EXIF/IPTC/XMP written into every distributed photo.
- `INITIAL.md` — how the archive was first built. Historical; nothing in it
  needs running again.

## Quick start

```bash
uv run python scripts/build.py            # -> build/ (plain, local preview)
uv run python -m http.server 8000 --directory build
# open http://localhost:8000/index.html

STATICRYPT_PASSWORD=... uv run python scripts/apply_password.py  # -> docs/ (committed, served by GitHub Pages at fcbond.github.io/the-trip)
```

The full pipeline, when the photos themselves have changed:

```bash
uv run python scripts/photos.py          # derivatives + embedded credit, all legs
uv run python scripts/build.py
STATICRYPT_PASSWORD=... uv run python scripts/apply_password.py
uv run python scripts/deploy.py -m "what changed"
```

`photos.py` is only needed when a leg's source scans change, or when a
derivative size changes - it is by far the slowest step, about ten minutes
for all seven legs. It writes the derivatives *and* the embedded credit in
one pass, deliberately: regenerating rewrites `full/` from the master and
discards whatever metadata the previous copy carried, so the two steps
were never safe to run apart. `--only-metadata` re-stamps without
re-encoding; `--report-places` is the caption check and writes nothing.

Editing a caption or a place in `metadata/*.toml` still needs
`photos.py --only-metadata`, because those values are embedded in the
distributed copies as well as shown on the page - then rebuild and deploy.

CSS and JS URLs carry a cache-busting `?v=<hash>` suffix, generated in
`build.py` by `asset_versions()` from each file's own bytes - so a
returning visitor picks up changed assets immediately, and unchanged ones
aren't re-downloaded. Templates must reference static files through the
`asset()` helper (`{{ root }}{{ asset('css/style.css') }}`) to get it.

`build/` is gitignored and gets wiped/regenerated on every build. `docs/`
is the only encrypted, committed, deployed output — never hand-edit it.

**Careful: parts of `docs/` are hardlinked to other trees**, so writing
to one path silently rewrites another. Two known cases:

- `build/photos/**` and `docs/photos/**` share inodes, so re-running
  `photos.py` into `build/` rewrites the committed `docs/` images
  in place. A `git status` full of modified `docs/photos/**` right after a
  photo rebuild is this, not a bug.
- `web/static/**` and `docs/static/**` share inodes, which is the worse
  one: editing the *source* CSS edits the deployed file directly, with no
  build step in between.

Check with `stat -c '%i %h %n' <path>` - a link count above 1 means the
file is shared. `apply_password.py` deletes `docs/` and moves a fresh
staticrypt output into place, so a full build resets `docs/` and breaks
the links - verified: link counts drop back to 1 afterwards. Until you have
run it, don't read a clean `docs/` diff as proof that a build- or
source-side change didn't touch deployed output.

## Directory map

```
data/                            original source material, never hand-edited by any script
  raw_docs/                        original diaries/letters/xlsx (docx, xlsx)
  The Trip Photos _76/             original scanned slides, one folder per leg,
                                    plus slide-metadata.xlsx (see INITIAL.md)
  DB|FB|HB 1976-77 Diary pix/      Denise/Francis/Helena's own drawings & diary pages
  The Bond Trip Book/              the family's own 2022 book - the richest single
                                    source for place+date+narrative+photo captions
  Scans of Letters etc/            PDF scans backing some of raw_docs/'s transcriptions
metadata/                        the hand-maintained/generated data this site is built from
web/templates/, web/static/      Jinja2 templates + CSS/JS
scripts/                         the build pipeline (see below)
build/                           gitignored plain HTML output (local preview)
docs/                            committed, password-gated output (for GitHub Pages)
```

## Data files (`metadata/`)

One leg = one country/section of the trip (`turkey`, `iran`, `afghanistan`,
...). Each leg has:

- **`<leg>_days.json`** — the diary, verbatim. One entry per day:
  `{"date", "weekday", "place_label", "entries": [{"speaker", "text"}]}`.
  `speaker` is `D`/`F`/`H` (Denise/Francis/Helena) or `G/M` (Graham/Monique,
  usually mileage logs). This is a straight transcription with little need
  for hand-editing, so it stays JSON.

- **`<leg>_stops.toml`** — the itinerary. One `[[stop]]` per place:
  `slug, name, date_start, date_end, narrative_excerpt, mileage_note, lat,
  lon, wikidata, wikipedia`. **Hand-maintained** — this is where you fix a
  wrong coordinate or split a new stop out of an existing one (see
  "Editing metadata" below). Not regenerated by any script once it exists.
  `wikidata`/`wikipedia` are both optional and render only if set - Stonegate
  has a Wikidata item but no English Wikipedia article, so its `wikipedia`
  is empty.

  A stop can optionally carry `[[stop.landmarks]]` - one per linkable site
  within it (e.g. Agra's Taj Mahal and Agra Fort): `name, wikidata,
  wikipedia`, and no dates of their own since they share the parent stop's
  page and diary days.

  A landmark may also declare `lat`/`lon`. Without them it inherits the
  stop's position, which is right for a site actually inside the stop
  (Badshahi Mosque is in Lahore). Declare them when the landmark is a
  distance away: Opuzen is 85km down the coast from the Omiš stop,
  Pasargadae 39km from Persepolis, Senj 150km from Postojna. The
  coordinates a photo gets embedded - and the `IPTC:Sub-location` it
  carries - come from the landmark when it has its own, otherwise from the
  stop. A photo opts in with a
  `landmark` field matching the landmark's `name` - **and must already
  resolve to the parent stop**, since landmarks only group photos that
  stop already has. Where a place has no stop of its own, that usually
  means adding a `LOCATION_ALIASES` entry alongside the landmark.

  Both stops and landmarks also accept `links` for anything that isn't
  Wikipedia - a bare URL, a list of URLs, or a list of `{ url, label }`
  tables. A missing label falls back to the hostname. Craignano uses this:
  it has no Wikidata entry at all, only a Himachal tourism page.

- **`<leg>_photos.toml`** — one `[[photo]]` per processed slide:
  `id` (the `roll.slide` number from the original slide mounts, e.g.
  `"14.31"` - globally unique across the whole trip), `filename` (source
  file in `data/The Trip Photos _76/<leg folder>/`), `description`, `place`
  (specific location, for the caption), `country`, `date`, `quality`,
  `notes` (free text, e.g. "worth a look" flags left by the xlsx merge -
  see `TODO.md`),
  an optional `stop` (explicit slug override - see below), and an optional
  `landmark` (matches one of the parent stop's `landmarks` by name exactly -
  see above).
  **Hand-maintained.**

- **`<leg>_tags.json`** — recurring-motif index (frogs, Fred, punctures,
  ...), built by keyword search over that leg's diary text. `{tag_key:
  [{"date", "speaker", "excerpt"}]}`.

- **`<leg>_places.json`** — the *raw* book-chapter extraction (place names +
  date ranges + narrative, before geocoding/splitting). Kept only as a
  historical record of where `<leg>_stops.toml` first came from; **not read
  by the build**.

- **`metadata/diary_pix.toml`** — one file, not per-leg (person's drawings
  span the whole trip regardless of which legs are built yet). One `[[pix]]`
  per drawing: `id, person (D/F/H), date, title, filename`.

## How a photo finds its stop page

`build.py`'s `build_photo_index` resolves each photo to a stop, in order:

1. **Explicit `stop` field on the photo** (if set) — always wins. Use this
   for one-off cases a name can't express, e.g. `09.35` in Iran is pinned
   to `stop = "safi-abad-palace"` even though its `place` field and dates
   would otherwise put it under the broader Caspian Sea stop.
2. **`LOCATION_ALIASES[leg]`** in `build.py` — maps a photo's `place` value
   to a stop name by substring match, for compound one-day-two-places cases
   like Turkey's `"Side / Alanya"`, and for sites with no stop of their own
   (`"Amber Fort" -> ["jaipur"]`). The lookup is **case-insensitive**, so
   `"Pinjore gardens"` still finds the `"Pinjore Gardens"` entry.
3. **The `place` naming a stop outright** — `"Ellora Caves"`, `"Ghazni"`.
   Matched against stop names by containment, so a stop renamed
   `"Bombay (Mumbai)"` still answers to `"Bombay"`. A modifier is stripped
   first, so a photo taken on the way somewhere lands on the place it was
   heading for: `toward`, `towards`, `near`, `nr`, `en route to`,
   `on the way to`, `approaching`, `outside` (see `TRANSIT_PREFIX_RE`).
   Where two stops share a name, the photo's date picks between them.
4. **Date-range fallback** — the stop whose `date_start`..`date_end`
   contains the photo's `date`. This is the last resort, and it is only as
   good as the stop ranges: where two stops cover the same day, file order
   decides, which is arbitrary. A photo landing on the wrong stop usually
   means its `place` is caption text rather than a place name — see
   `photos.py --report-places`.

Steps 2 and 3 only ever match stops **within the photo's own leg**, so a
photo whose roll crossed a border mid-film needs moving to the other leg's
`<leg>_photos.toml` with an `image_leg` field pointing back at the folder
its scan physically lives in (as rolls `16.32`-`16.38` do).

## Common tasks

Everything here is an edit to a `.toml` file followed by a rebuild. No
script re-runs and no re-extraction - the TOML files are the source of
truth, not a cache of something else.

### Fixing a photo that lands on the wrong stop

Nearly always its `place` is caption text rather than a place name, or
names a place no stop or alias knows. Find out which:

```bash
uv run python scripts/photos.py --report-places   # caption-ish places
uv run python scripts/build.py                            # warns about unmatched photos
```

Then, in order of preference:

1. **The `place` is caption text** - move it into `description` and put a
   real place name in `place`. This is the common case and the one worth
   doing properly, since `place` is embedded as `IPTC:City` in every
   distributed copy of the photo.
2. **The place is real but has no stop** - if the family stayed there, add
   a stop (below). If they passed through or visited for a day, add a
   `LOCATION_ALIASES` entry in `build.py` pointing at the stop that should
   own it, and consider a landmark so it gets its own links.
3. **The place is real and the stop exists, but the photo still misses** -
   check capitalisation is irrelevant (it is; the lookup is
   case-insensitive) and that the stop is in the *same leg*. A photo whose
   roll crossed a border mid-film has to move to the other leg's
   `<leg>_photos.toml`, keeping `image_leg` pointing at the folder its scan
   physically sits in.
4. **Nothing else fits** - set `stop = "<slug>"` on the photo. This always
   wins and is the escape hatch for one-offs.

### Adding a stop

1. Find the place on Wikidata and **check the result by hand**. Searching
   `Meteora` returns the Linkin Park album first; `Akdamar` returns two
   villages nowhere near Lake Van. Take the `Q` id, its coordinates, and
   its English Wikipedia URL if it has one:
   ```bash
   curl -s -A "the-trip/1.0" \
     "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Meteora&language=en&format=json&limit=5" \
     | python3 -m json.tool
   ```
2. Add a `[[stop]]` to `metadata/<leg>_stops.toml`, **in date order** - the
   date fallback walks stops in file order, so position matters when two
   stops share a day.
3. `wikipedia` may be empty if there's no article (Stonegate has a Wikidata
   item but no English page); both links render only when set.
4. Rebuild and check the unmatched warning is still empty.

### Adding a landmark

For a linkable site inside a stop rather than a stop of its own - Elephanta
Island within Bombay, Shalimar Gardens within Lahore.

```toml
[[stop.landmarks]]
name = "Shalimar Gardens"
wikidata = "Q499527"
wikipedia = "https://en.wikipedia.org/wiki/Shalamar_Gardens,_Lahore"
```

Then tag each photo with `landmark = "Shalimar Gardens"`.

**The photo must already resolve to the parent stop** - landmarks only
group photos the stop already has, they don't attract new ones. If the
photos are landing elsewhere, add a `LOCATION_ALIASES` entry as well; that
is what pins Pinjore Gardens to Chandigarh.

For a site with no Wikipedia entry, use `links` instead - a bare URL, a
list of URLs, or `{ url, label }` tables. A missing label falls back to the
hostname:

```toml
links = [{ url = "https://hpshimla.nic.in/tourist-place/craignano-nature-park/", label = "Himachal Tourism" }]
```

### Adding or replacing photos

Only needed when the source scans change; it is by far the slowest step.
The masters live in the private archive repo, so point the script at them:

```bash
uv run python scripts/photos.py "$TRIP_ARCHIVE/<leg folder>" <leg> build
uv run python scripts/photos.py --legs <leg>
uv run python scripts/build.py
```

`photos.py` writes `thumb/`, `display/` and `full/` for every
unique photo. `publish_full_res.py` and `process_diary_pix.py` take
`--source-root` (or `$TRIP_ARCHIVE`) for the same reason.

### Other fixes worth knowing

- **Wrong coordinates.** The Caspian Sea stop was pinned to the sea's
  Wikidata centroid rather than where the family actually camped: edit
  `lat`/`lon` in `metadata/<leg>_stops.toml` directly.
- **One date range covering more than one place.** Shahr-e Zohak and
  Mazar-i Sharif both spanned `1976-11-02`-`1976-11-05` because Ajar
  Valley, visited in between, had no stop of its own. Tighten both ranges
  to their real days, add the new `[[stop]]` between them, and check no
  alias depended on the old wider range. Once ranges stop overlapping,
  date matching is often enough on its own.
- **Overlapping ranges are legal.** Bharatpur (9-10 Dec) overlaps Fatehpur
  Sikri (8-9 Dec) because they really did spend the 9th at both. Name
  matching beats the date fallback, so photos still land correctly - it is
  only the fallback that gets ambiguous, and then file order decides.

After any edit: `uv run python scripts/build.py`, check the relevant page,
then re-run `apply_password.py` before committing.

## Photo pages

Every photo gets its own page at `photo/<id>.html` (e.g. `photo/12.34.html`)
- the display-size image, place/date, and links out to its stop page (if it
resolved to one - see above), its diary day (if that day's built), and the
map (`index.html?stop=<slug>#map`, which `map.js` reads to pan/zoom to that
stop and open its popup on load).

A caption that mentions another photo by id (a real pattern in this
archive - e.g. `"6 streams & water mill below natural lake of 12.30"`)
gets that id turned into a link to `photo/12.30.html` automatically.
`build.py`'s `linkify_photo_refs` does this against the set of ids actually
built, trying a couple of zero-padding variants (a caption might say
`"11.6"` where the stored id is `"11.06"`) so it doesn't depend on prose
matching the stored format exactly. The `.slide-id` label on every gallery
thumbnail (stop/diary pages) links to the same pages.

## Verifying a build

```bash
uv run python -c "
import re
from pathlib import Path
from urllib.parse import urlsplit, unquote
build = Path('build')
broken = []
for f in build.rglob('*.html'):
    text = f.read_text()
    for m in re.finditer(r'(?:href|src|data-full)=\"([^\"]+)\"', text):
        url = m.group(1)
        if url.startswith(('http', '#', 'mailto:', 'data:')):
            continue
        # Strip ?query and #fragment before resolving: the map links are
        # index.html?stop=<slug>#map, which is a real file plus state.
        path = unquote(urlsplit(url).path)
        if not path:
            continue
        if not (f.parent / path).resolve().exists():
            broken.append((str(f), url))
print(len(broken), 'broken links')
for b in broken: print(b)
"
```

Also worth checking after processing any leg's photos: every id in
`<leg>_photos.toml` has a matching file in each of
`build/photos/<leg>/{thumb,display,full}/`
(a mismatch usually means a filename convention `photos.py`'s
`ID_RE` doesn't recognize yet — it's already been extended twice for
leg-specific quirks, see its docstring).

## Going public

**Decided.** Francis's siblings have agreed to release everything (August
2026), and Monique - who took the slides and holds the copyright - has
agreed to release them under [CC BY
4.0](https://creativecommons.org/licenses/by/4.0/). The site (slides, diary
entries, and the interface tying them together) goes public; the raw source
documents stay private. Full-resolution photos are downloadable per photo,
from the photo's own page.

What remains is a family check of the captions, dates, and photo selection,
after which the password comes off. The check gates *removing the gate*, not
creating the public repo - see "What the password gate actually is" below,
and the one-way-door note at the end.

### The two repos

| | `fcbond/the-trip` (public, new) | `fcbond/the-trip-archive` (private) |
|---|---|---|
| **Holds** | `metadata/`, `scripts/`, `web/`, `docs/`, `README.md`, `METADATA.md`, build config | everything now in `data/` |
| **Photos** | web derivatives + full-res JPEG, in `docs/photos/` | the 1002 masters, incl. the 285 uncompressed BMPs |
| **Diaries** | transcribed text in `metadata/*_days.json`, rendered to `docs/diary/` | source `.docx` in `raw_docs/`, diary-pix PDFs |
| **Also** | - | `The Bond Trip Book/`, `Scans of Letters etc/` |
| **Served** | GitHub Pages from `docs/` on `main` | not served |

The private repo is the **archive**, not a set of withheld secrets. The
diary text is published in full; the `.docx` originals are kept back so
there's always something to check the transcription against if a
transformation ever loses something. The book is held back because parts of
its introduction aren't for release, and the Woman's Day article isn't ours
to republish.

### Why not split the photos across several repos

The archive is 1546 MB, but not because there are too many photos - because
three legs were digitised to uncompressed BMP:

| leg | source size | why |
|---|---|---|
| Iran | 656 MB | 148 BMPs |
| Turkey | 519 MB | 120 BMPs |
| Afghanistan | 133 MB | 17 BMPs |
| other four legs, combined | 238 MB | all JPEG |

Splitting by leg would still leave Iran at 656 MB, now with several
checkouts to keep in sync and a build that needs all of them at once. The
fix is format, not repo count: the 285 BMPs re-encode to JPEG q95 at **5.2x
smaller** with no visible loss, taking the whole archive to ~543 MB. The
masters stay in the private archive repo, so nothing is lost in the
transformation.

(`xz` was considered and rejected: it gets a 4.6 MB BMP to 2.6 MB, while
PNG gets it to 2.4 MB *and* leaves it a viewable image. Lossless PNG for
the whole archive lands at ~1032 MB vs JPEG q95's ~543 MB - not worth 2x
for scans this size.)

### Full-res per photo, and the size budget that shapes it

Full-res is served **from Pages**, not from Release assets. A release asset
downloads as an attachment and can't be viewed in the browser, and a
per-leg zip would make "click this photo" hand you 150 photos. So each
photo gets a third derivative next to `thumb/` and `display/`.

GitHub Pages caps a **published site at 1 GB** (and soft-limits bandwidth to
100 GB/month), which is the real constraint. Measured and projected over
1014 photos:

| | current | planned |
|---|---|---|
| `thumb/` | 27 MB @ 400 px | **55 MB @ 600 px q85** |
| `display/` | 277 MB @ 1600 px q87 | **165 MB @ 1200 px q82** |
| `full/` native res | - | **488 MB** |
| diary-pix `cropped/` | 37 MB | 37 MB |
| HTML (photo/diary/stops/tags) | 57 MB | 57 MB |
| **total `docs/`** | **401 MB** | **792 MB** |

That leaves ~23% headroom under the cap. Shrinking `display` is what buys
it - at the current 1600 px/q87 the total would be ~955 MB, too close to
the ceiling to build on. If more headroom is wanted later, `display` at
1400 px/q85 is 219 MB and 1200 px/q82 is 153 MB; those are measured, not
guessed.

**Note on what "full-res" means per leg.** The BMP legs were scanned at
1532x980; the JPEG legs at 2043x1307. So for Turkey, Iran, and Afghanistan
the full-res file is *smaller than the current 1600 px display derivative* -
the full-res link there gains almost nothing. Only the 713 JPEG-sourced
photos get a real step up, and it's 1.6x the pixels. If those slides still
exist physically, rescanning is the only thing that would make a full-res
link meaningful for those three legs.

### Which repo to work in

**Work here, in the archive repo.** It has the photo masters, so it is the
only place a photo can be reprocessed, and it holds the full history. The
public repo is a deploy target: everything in it is copied there by
`scripts/deploy.py`, and edits made directly in it are overwritten by the
next deploy. Its README says so at the top - the banner is injected during
the copy, so it cannot be lost to a sync.

```bash
uv run python scripts/build.py
STATICRYPT_PASSWORD=... uv run python scripts/apply_password.py
uv run python scripts/deploy.py --dry-run              # see what would change
uv run python scripts/deploy.py -m "fix a caption"     # sync, commit, push
```

`deploy.py` refuses to run when:

- **anything it would deploy is uncommitted here** - it publishes the
  working tree, not a commit, so an uncommitted change would go live with
  nothing in the archive to explain it (`--allow-dirty` overrides);
- **`docs/` is older than `metadata/` or `web/`**, so a forgotten rebuild
  cannot publish the previous version (`--force` overrides);
- **an archive-only path** (`data/`, `INITIAL.md`, the one-time scripts)
  has appeared on the public side.

It also warns about unpushed archive commits, and records which one each
deploy came from in the public commit message
(`Deployed from the-trip-archive@<sha>`), so any published state can be
traced back. `--public` or `$TRIP_PUBLIC` points it at the checkout;
`--no-push` stops after committing.

### Doing the split

Nothing here is destructive to the current repo - it gets **renamed, not
deleted**, so no "did everything transfer?" moment is needed.

```bash
# 0. Back up off-machine first. The current .git is 1.9 GB and holds the
#    only copy of the full history.
git clone --mirror . /media/<drive>/the-trip-mirror.git

# 1. Rename on GitHub: Settings -> General -> Repository name,
#    the-trip -> the-trip-archive. It stays private, keeps all history
#    and all of data/. Then repoint this checkout:
git remote set-url origin https://github.com/fcbond/the-trip-archive.git

# 2. Build the public repo as a fresh tree. Not a filtered clone: docs/ is
#    regenerated build output, and filtering would still drag along
#    hundreds of MB of superseded derivatives from every past rebuild.
mkdir ../the-trip && cd ../the-trip && git init -b main
cp -r ../Trip_1976/{metadata,scripts,web,pyproject.toml,uv.lock,README.md,METADATA.md,.gitignore} .
# docs/ is NOT copied - regenerate it with the new derivative sizes.

# 3. Create it public. This can happen before the family check finishes -
#    see "What the password gate actually is" below.
gh repo create fcbond/the-trip --public --source=. --remote=origin
```

Keep the public repo named `the-trip`: the Pages URL
`https://fcbond.github.io/the-trip/` is already baked into the per-photo
metadata as the attribution link (see `METADATA.md`).

### What the split needs from the code — done

All of it is in place; recorded here so the reasoning survives.

- **`photos.py`** writes a third derivative, `full/`, at native
  resolution, and `display` dropped to 1200px/q82 to make room under the
  Pages cap. An already-JPEG source is **byte-copied** into `full/` rather
  than re-encoded: passing it through Pillow at q95 inflated 306 MB of
  sources to ~430 MB and cost a generation of loss for nothing. Only the
  BMP scans get encoded.
- **`publish_full_res.py`, `process_diary_pix.py`** take `--source-root`,
  falling back to `$TRIP_ARCHIVE`, then the pre-split in-repo `data/`.
  `photos.py` already took its source as an argument. So no script
  in the public repo needs a `data/` directory that isn't there.
- **`photo.html`** links the display image to `full/`, with a separate
  `<a download>` beside the caption, so a visitor can both view and save.
- **`photos.py`** stamps the CC BY credit block into `full/`, the
  copy most likely to travel. See `METADATA.md`.

**Still to move when the public repo is built:** the one-time scripts and
their inputs belong in the archive, not the public tree — `build_stops.py`,
`migrate_to_toml.py`, `xlsx_metadata.py`, `metadata/*_places.json`,
`metadata/*_photos.json`. Nothing in the build reads any of them; see
`INITIAL.md`.

### What the password gate actually is

`apply_password.py` runs staticrypt over `build/`, which encrypts **HTML
only**. `docs/photos/**/*.jpg` are plain JPEG files, and
`metadata/*_days.json` holds the diary text in plain JSON. So once the
public repo exists, the photos and the diary text are readable by anyone
willing to look at the repo, gate or no gate. What the gate buys is that
the *site* - captions in context, the map, the day-by-day narrative - isn't
casually browsable or indexable yet.

That's the intended arrangement, not a gap: the gate is a courtesy lock
while the family checks captions and selection, and it comes off once that's
done. It does mean the public repo can be created before the check
finishes - the check is about getting the presentation right, not about
keeping the photos back.

**Don't publish the password with the site it gates.** The quick-start
above used to carry the literal password inline; it's now `...`, because
`README.md` goes into the public repo. Share the password out of
band, or keep it in the private archive repo's notes. (The salt in
`.staticrypt.json` is fine to publish - it's a salt, not a secret.)

### One-way door

Creating the public repo is not practically reversible. CC BY is
irrevocable for copies already distributed, and anything fetched while the
repo is public stays fetched. The family check is the last point at which a
photo can quietly be pulled.
