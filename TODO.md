# Outstanding work

For whoever picks this up next, human or Claude. Ordered by what blocks
publication, then what improves it.

Counts are as of 2026-08-26 and go stale; each item says how to recount.

The caption pass is finished: 0 suspect places and 0 review notes across
all 903 photos, with none unmatched to a stop.

## Before making the repo public

- [x] **Caption pass — done.** All seven legs. `place` no longer holds
      caption text anywhere, and every "worth a look" note is resolved.
      Recheck any time with:

      ```bash
      uv run python scripts/photos.py --report-places
      grep -c "worth a look" metadata/*_photos.toml
      ```

- [x] **Naming private individuals — decided: the names stay.** The
      diaries name people who hosted the family in 1976 — Mrs Nargis
      Engineer, Mrs Pai, Mr Fudge, Mr and Mrs Ashley, Dr Mercimer, Sarah
      Woodam — and one address, a Munich doctor's surgery at
      `uk_greece_days.json` 1976-08-05. The family's decision is to publish
      them as written: it is a fifty-year-old memoir and the children's own
      words. A scan for addresses, postcodes, phone numbers, emails and
      bank details found nothing else.

- [ ] **Build the public repo and publish.** Steps are in "The two repos"
      in `README.md`. Creating it is the one-way door: CC BY is irrevocable
      for copies already distributed.

## Improvements, not blockers

- [ ] **Link what is still unlinked.** Most places now resolve to a stop
      or a landmark with real Wikipedia/Wikidata links. What remains are
      minor spots with no Wikidata entry of their own (Craignano has only a
      tourism page) and a few that reach their stop by alias rather than by
      name. Always verify an id by hand before adding it: searching
      `Meteora` returns the Linkin Park album first, `Hierapolis` returns a
      Syrian city, `Akdamar` returns two villages nowhere near Lake Van, and
      the Asclepieion of Pergamon does not come back at all under that
      name — it was found by looking up the Wikipedia title.

- [ ] **Rescan the BMP legs, if the slides still exist.** Turkey, Iran and
      Afghanistan were digitised at 1532x980; every other leg at 2043x1307.
      So for those three the "full size" link on a photo page offers
      essentially what is already on screen. Nothing in the code needs
      changing - re-run `photos.py` on better scans.

- [ ] **Vendor Leaflet**, if the site should survive unpkg going away. It
      is BSD-2-Clause, so copying `leaflet.js`/`leaflet.css` into
      `web/static/vendor/` is fine provided the `/* @preserve */`
      copyright banner stays and the `LICENSE` file ships alongside.
      `leaflet.css` also expects `images/layers.png` and friends. Note this
      does not make the map self-contained: tiles still come from
      OpenStreetMap and OpenTopoMap on every pan.

- [ ] **Consider a stop for Craignano.** It has 10 photos and currently
      hangs off Shimla as a landmark with a tourism link, because it has no
      Wikidata entry at all.

## Known small oddities

Not worth blocking on, recorded so nobody re-derives them:

- **`17.05` and `17.07`** are dated 23 Nov but placed *Pinjore Gardens*,
  which the diary puts on the 24th. Their captions are too generic ("2
  bullocks & farmer irrigating", "V beautiful sunset") to tell whether the
  date or the place is off. They reach the right stop by name either way.
- **`16.04`** ("Sheep, people, tent in street scene", 17 Nov) has an empty
  `place`: the diary has them driving round Islamabad, back to Rawalpindi
  and on to Lahore, so the street could be either. It carries no
  `IPTC:City` rather than a guess.
- **Stops with no photos** — `bhakra-dam`, `chandigarh`, `london`. Each
  holds diary days that belong to it; the photos taken those days belong to
  a neighbouring stop. Harmless.
- **Overlapping stop ranges are normal**, and mean "based here, went there
  that day" — Bamiyan/Band-e Amir, Kabul/Ghazni, Meteora/Thessaloniki. A
  range that swallows a *later* stop's days entirely is the thing to check
  after adding a stop.

## When building the public repo

These 15 files are archive-only — nothing in the live build reads any of
them (verified). They document provenance, so move them to
`the-trip-archive` rather than deleting:

```
scripts/build_stops.py          scripts/migrate_to_toml.py
scripts/xlsx_metadata.py        INITIAL.md
metadata/*_places.json          (7 files)
metadata/*_photos.json          (4 files: bangkok, india, pakistan, uk_greece)
```

184 KB in total. What's left is the live pipeline: `build.py`,
`apply_password.py`, `photos.py`,
`publish_full_res.py`, `process_diary_pix.py` — none of which needs a
`data/` directory, since the last three take `--source-root`.

## Watch items

- **Pages size.** GitHub caps a published site at 1 GB. `docs/` is at
  770 MB, and roughly 490 MB of that is the `full/` derivatives. Better
  scans would push it up; `display` is already trimmed to 1200px/q82 to
  make room. Check with `du -sm docs`.

- **The hardlink trap.** `build/photos` and `docs/photos`, and
  `web/static` and `docs/static`, have been found sharing inodes - writing
  one silently rewrote the other. A full build resets it. Check with
  `stat -c '%i %h %n' <path>`; a link count above 1 means shared.
