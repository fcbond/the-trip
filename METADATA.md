# Embedded photo metadata

Spec for writing EXIF/IPTC/XMP metadata directly into the photo files
themselves (thumb, display, and full), so captions/credit/location
survive once a photo is downloaded and leaves the site. Implemented as
`scripts/embed_metadata.py`; this document is the field spec it follows
and the reasoning behind each choice.

## Why embed metadata at all

The site's captions/dates/coordinates currently only exist as rows in
`metadata/<leg>_photos.toml` / `<leg>_stops.toml`. A photo saved off the
site by someone else carries none of that. Standard IPTC/XMP/EXIF fields
are read by Wikimedia Commons' upload tooling, most photo viewers/DAM
software, and reverse-image-search context - writing them once, from data
we've already curated, makes every copy of a photo self-describing.

## Non-destructive strategy

The masters live in the private archive repo (`the-trip-archive`, see
"Going public" in `README.md`) and are documented as never hand-edited by
any script - that stays true. Metadata gets written to *derivatives and
copies*, never the masters:

- **thumb/display/full** - all three are regenerated from scratch on every
  run of `process_photos.py`; metadata-writing becomes one more step in
  `make_derivative()`, right after Pillow saves the JPEG (Pillow's
  re-encode strips any pre-existing EXIF, so this has to happen after the
  save, not before).
- **`full/` needs this most.** It's the copy a re-user downloads and takes
  elsewhere, so it's the one that has to carry its own credit and license.
  Note that for already-JPEG sources `full/` is a *byte copy* rather than a
  Pillow re-encode (see `README.md`) - so for those files exiftool is
  writing into a copy that still holds whatever EXIF the scanner left, and
  should overwrite rather than assume an empty slate.
- **per-leg zips** - `publish_full_res.py` bundles source files for bulk
  download. Since `full/` derivatives now carry the metadata, the zips
  should be built from those rather than from the raw masters, so a photo
  says the same thing however it was obtained.

## Character encoding

IPTC IIM defaults to Latin-1, which silently mangles the Turkish, Persian
and Indic characters in these captions and place names. `embed_metadata.py`
passes `-charset iptc=UTF8` and sets `IPTC:CodedCharacterSet=UTF8`, which
is how IPTC declares otherwise. XMP and EXIF are UTF-8 natively and need
no such handling. Drop those flags and the damage is quiet - exiftool
warns once per file and writes the mangled bytes anyway.

## Tool

[`exiftool`](https://exiftool.org/) - handles EXIF, IPTC, and XMP in one
pass with a consistent CLI, unlike Pillow (EXIF-only) or piexif
(EXIF-only, no IPTC/XMP). Installed at `/usr/bin/exiftool`
(`sudo apt install libimage-exiftool-perl` elsewhere).
`embed_metadata.py` shells out to it once per file. If that gets slow
across 1000 files, exiftool's `-json` batch input or `-stay_open` would
cut the per-invocation startup cost - not worth the complexity until the
runtime actually hurts.

## Fields

All values are pulled from existing `metadata/*.toml` data - no new data
entry required.

| Purpose | Tag(s) written | Source |
|---|---|---|
| Title | `XMP:Title`, `IPTC:ObjectName` | `"{id} — {description}"` |
| Caption | `IPTC:Caption-Abstract`, `XMP-dc:Description`, `EXIF:ImageDescription` | photo `description` |
| Creator | `EXIF:Artist`, `IPTC:By-line`, `XMP-dc:Creator` | `Monique Bond` |
| Copyright | `EXIF:Copyright`, `IPTC:CopyrightNotice`, `XMP-dc:Rights` | `"© {year} Monique Bond. Licensed CC BY 4.0."` |
| Rights marked | `XMP-xmpRights:Marked` | `True` (the photos are under copyright, and licensed — not public domain) |
| Usage terms | `XMP-xmpRights:UsageTerms` | `"This work is licensed under the Creative Commons Attribution 4.0 International License. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0/"` |
| License URL | `XMP-cc:License`, `XMP-xmpRights:WebStatement` | `https://creativecommons.org/licenses/by/4.0/` |
| Attribution | `XMP-cc:AttributionName`, `XMP-cc:AttributionURL` | `Monique Bond` / the photo's page on this site (how a re-user is asked to give credit) - keep the public repo named `the-trip` so this URL stays valid |
| Credit line | `IPTC:Credit` | `"Monique Bond, 1976 Trip"` - IPTC caps this field at 32 bytes, so it is deliberately terser than the copyright line |
| Date | `EXIF:DateTimeOriginal`, `IPTC:DateCreated` | photo `date` (the 1976 date the photo was taken - **not** the ~2005 file mtime left over from scanning) |
| Location | `IPTC:Sub-location`, `IPTC:City`, `IPTC:Country-PrimaryLocationName`, plus `XMP-iptcCore:Location`, `XMP-photoshop:City`, `XMP-photoshop:Country` | parent stop `name` / photo `place` / photo `country`. IPTC caps City at 32 bytes; over that it is skipped rather than truncated, since the overruns are caption text, not long place names. The XMP equivalents have no such limit |
| GPS | `EXIF:GPSLatitude(Ref)`, `EXIF:GPSLongitude(Ref)` | the photo's landmark `lat`/`lon` when it declares them, else the parent stop's - approximate either way: it is where the *place* is, not the exact spot the photo was taken from. A landmark declares its own only when it sits well away from its stop (Opuzen is 85km from Omiš) |
| Keywords | `IPTC:Keywords`, `XMP-dc:Subject` | `[leg display name, country, stop name, "1976", "Bond Trip"]` |
| More-info link | `XMP-dc:Relation` | `https://fcbond.github.io/the-trip/photo/{id}.html` - dead link until the repo goes public (per-photo pages already exist at this path). Kept out of `WebStatement`, which by convention points at the *rights* statement (the license deed) |
| Photo id | `XMP-dc:Identifier` | the `roll.slide` id itself, e.g. `"03.07"`, so provenance survives even if a downstream copy gets renamed |

**Rights (settled):** Monique Bond took the slides, holds the copyright,
and has agreed to release them under [CC BY
4.0](https://creativecommons.org/licenses/by/4.0/). So the creator,
copyright, and license fields above are no longer provisional - they name
her and the license outright, in every derivative we distribute.

Two things to keep in mind when implementing:

- **A license declaration is not reversible in practice.** CC BY is
  irrevocable for copies already distributed, and embedded metadata travels
  with the file. Nothing is lost by writing it into the thumb/display
  derivatives now (they're regenerated every build), but the moment full-res
  zips are published under it, that grant stands for those copies.
- **Authorship and ownership are settled, by two separate routes.** As far
  as the family knows Monique took every slide, so `Monique Bond` as
  creator is accurate on the face of it. And if a few turn out to be
  Graham's, it changes nothing that matters: Graham has died and left
  everything to Monique, so she holds the copyright in those too. The
  licence grant is therefore valid across the whole archive regardless of
  who pressed the shutter - which is the part that had to be right before
  publishing.

  The one thing inheritance doesn't transfer is *authorship* as a matter of
  fact. So if a specific photo is ever identified as Graham's, the
  `Creator`/`Artist` field would be the thing to correct, not the licence.
  That stays cheap: derivatives are regenerated from the TOML on every
  build, so it's a per-photo `creator` field plus a branch in `tags_for()`,
  not a re-issue.

## Worked example: photo `03.07` (Pamukkale, Turkey)

Source data (`metadata/turkey_photos.toml` + `turkey_stops.toml`):

```toml
[[photo]]
id = "03.07"
filename = "0307 Pammukale, shallow water basins.bmp"
description = "Pammukale, shallow water basins"
place = "Pamukkale"
country = "Turkey"
date = "1976-09-03"

[[stop]]
slug = "pamukkale"
name = "Pamukkale"
lat = 37.9236
lon = 29.1223
wikidata = "Q105893254"
wikipedia = "https://en.wikipedia.org/wiki/Pamukkale"
```

Resulting metadata values:

| Field | Value |
|---|---|
| Title | `03.07 — Pammukale, shallow water basins` |
| Caption | `Pammukale, shallow water basins` |
| Creator | `Monique Bond` |
| Copyright | `© 1976 Monique Bond. Licensed CC BY 4.0.` |
| Rights marked | `True` |
| Usage terms | `This work is licensed under the Creative Commons Attribution 4.0 International License. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0/` |
| License URL | `https://creativecommons.org/licenses/by/4.0/` |
| Attribution | `Monique Bond` / `https://fcbond.github.io/the-trip/photo/03.07.html` |
| Credit | `Monique Bond, 1976 Trip` |
| Date | `1976:09:03 00:00:00` (no time-of-day recorded, so `00:00:00` is a placeholder, not a claim) |
| City | `Pamukkale` (standardised to the stop's spelling; the caption keeps the family's "Pammukale") |
| Sub-location | `Pamukkale` |
| Country | `Turkey` |
| GPS | `37.9236 N, 29.1223 E` |
| Keywords | `Turkey, Pamukkale, 1976, Bond Trip` |
| More-info link | `https://fcbond.github.io/the-trip/photo/03.07.html` |
| Photo id | `03.07` |

Equivalent `exiftool` invocation (what the script will generate/run per file):

```bash
exiftool \
  -Title="03.07 — Pammukale, shallow water basins" \
  -Caption-Abstract="Pammukale, shallow water basins" \
  -XMP-dc:Description="Pammukale, shallow water basins" \
  -ImageDescription="Pammukale, shallow water basins" \
  -Artist="Monique Bond" \
  -By-line="Monique Bond" \
  -XMP-dc:Creator="Monique Bond" \
  -Copyright="© 1976 Monique Bond. Licensed CC BY 4.0." \
  -CopyrightNotice="© 1976 Monique Bond. Licensed CC BY 4.0." \
  -XMP-dc:Rights="© 1976 Monique Bond. Licensed CC BY 4.0." \
  -XMP-xmpRights:Marked=True \
  -XMP-xmpRights:UsageTerms="This work is licensed under the Creative Commons Attribution 4.0 International License. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0/" \
  -XMP-xmpRights:WebStatement="https://creativecommons.org/licenses/by/4.0/" \
  -XMP-cc:License="https://creativecommons.org/licenses/by/4.0/" \
  -XMP-cc:AttributionName="Monique Bond" \
  -XMP-cc:AttributionURL="https://fcbond.github.io/the-trip/photo/03.07.html" \
  -Credit="Monique Bond, 1976 Trip" \
  -DateTimeOriginal="1976:09:03 00:00:00" \
  -IPTC:DateCreated="1976:09:03" \
  -City="Pamukkale" \
  -Sub-location="Pamukkale" \
  -Country-PrimaryLocationName="Turkey" \
  -GPSLatitude="37.9236" -GPSLatitudeRef="N" \
  -GPSLongitude="29.1223" -GPSLongitudeRef="E" \
  -Keywords="Turkey" -Keywords="Pamukkale" -Keywords="1976" -Keywords="Bond Trip" \
  -XMP-dc:Subject="Turkey" -XMP-dc:Subject="Pamukkale" -XMP-dc:Subject="1976" -XMP-dc:Subject="Bond Trip" \
  -XMP-dc:Relation="https://fcbond.github.io/the-trip/photo/03.07.html" \
  -XMP-dc:Identifier="03.07" \
  -overwrite_original \
  03.07.jpg
```

## Running it

`embed_metadata.py` runs *after* `process_photos.py` (which regenerates
the derivatives from scratch, wiping any previous metadata) and *before*
`build.py`/`apply_password.py`:

```bash
uv run python scripts/process_photos.py "<src>" <leg> build   # per leg
uv run python scripts/embed_metadata.py                       # stamps full/
uv run python scripts/build.py
STATICRYPT_PASSWORD=... uv run python scripts/apply_password.py
```

By default it stamps only `full/` - the copy that actually gets
downloaded and travels. `--kinds full display thumb` covers all three;
`--dry-run` shows what would be written without touching anything.

## Checked

- **Creator.** Settled - see "Authorship and ownership" above. All 903
  photos carry `Monique Bond`.
- **Spot-checked** with `exiftool` across the awkward cases: `03.07`
  (matches the worked example below, GPS included), `04.06` (non-ASCII
  caption), and `25.01` (one of the 18 photos that match no stop, so
  correctly carries no GPS or sub-location).
- **Two IPTC limits found the hard way.** `Credit` is capped at 32 bytes,
  and IPTC IIM defaults to Latin-1 - which silently mangled the Turkish
  and Persian captions until `CodedCharacterSet=UTF8` was set. Both are
  handled in the script; the field table above reflects the shorter
  credit line.
- **Caption text in the `place` field** is the standing data fault, and it
  matters here because `place` becomes `IPTC:City` in every distributed
  copy. `--report-places` flags any `place` matching no stop and no alias
  that also reads like prose - lowercase start, comma-joined clauses, or
  over the 32-byte `IPTC:City` limit. A length-only check missed most of
  them: `"shield on back,sword"` is plainly a caption at 20 bytes. Values
  over the limit get no City tag at all rather than a truncated wrong one.
  See "Known review items" in `README.md` for the current count.
