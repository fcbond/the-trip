"""Turn a leg's scanned slides into the site's photo derivatives, and write
the credit and licence into them.

One program rather than two, because the two steps must not be separated:
regenerating derivatives rewrites `full/` from the master, which discards
whatever metadata was written into the previous copy. Running them apart
means every change to a thumbnail size silently strips Monique's name and
the CC BY licence from all 903 distributed photographs until someone
remembers the second command. Now they are one command.

    uv run python scripts/photos.py                       # every leg
    uv run python scripts/photos.py --legs turkey iran     # some legs
    uv run python scripts/photos.py --only-metadata        # re-stamp, no re-encode
    uv run python scripts/photos.py --report-places        # data check, writes nothing

Produces three derivatives per unique photo under build/photos/<leg>/:
  thumb/<id>.jpg   - 600px longest edge, for grids and the diary
  display/<id>.jpg - 1200px longest edge, for the lightbox and photo page
  full/<id>.jpg    - native resolution, for the per-photo download link

The masters live in the private archive repo and are never opened for
writing - see "Going public" in README.md. Pass --source-root, or set
TRIP_ARCHIVE, to point at that checkout. Metadata needs exiftool; the
field spec and the reasoning behind each tag are in METADATA.md.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import (LEGS, LOCATION_ALIASES, TRANSIT_PREFIX_RE, build_photo_index,
                   leg_display_name, load_leg)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "build"
# The masters are not in this repo. Resolution order: --source-root, then
# $TRIP_ARCHIVE, then the pre-split in-repo location.
ENV_ROOT = os.environ.get("TRIP_ARCHIVE")
DEFAULT_SOURCE_ROOT = Path(ENV_ROOT) if ENV_ROOT else ROOT / "data" / "The Trip Photos _76"

# leg slug -> source folder name under the archive root.
# "Superceded" isn't a leg and is deliberately excluded.
LEG_FOLDERS = {
    "uk_greece": "1.1-2.12 UK-Greece",
    "turkey": "2.13 - 5.25 Turkey",
    "iran": "5.26-10.20 Iran",
    "afghanistan": "10.21-14.32 Afghanistan",
    "pakistan": "14.33 - 16.38 Pakistan",
    "india": "17.01 - 26.8 India",
    "bangkok": "26.9 - Bangkok",
}

SOURCE_SUFFIXES = {".jpg", ".jpeg", ".bmp", ".bm", ".png"}
KINDS = ("thumb", "display", "full")

JUNK_NAMES = {"Thumbs.db"}
JUNK_SUFFIXES = {".pe4", ".shw", ".db"}

# Roll is normally 2 digits, but a handful of Afghanistan sub-roll scans use
# a lettered roll ("13a") with a space instead of a dot before the slide
# number, e.g. "13a 1 River gorge...jpg" -> id "13a.1". Dot-separated ids
# (the common case) don't need a word-boundary check after the slide number
# - a Pakistan filename runs straight into the description with no space at
# all ("15.25Profile of figures...jpg") - but the space/no-separator forms
# do need one, to avoid over-consuming digits from an adjacent word/number.
ID_RE = re.compile(r"^(?:Copy of )?(?:(\d{2}a?)\.(\d{2})|(\d{2}a?)[ ]?(\d{1,2})\b)")

# Genuine archival numbering collisions: two different, real photos that
# happen to share a roll.slide number (not a re-scan of the same slide, so
# dedupe_by_id's "keep the bigger file" rule would wrongly discard one).
# Keyed by exact filename since that's the only unambiguous way to tell them
# apart; the second id must match whatever data/<leg>_photos.toml uses.
ID_OVERRIDES = {
    "20.22 Silhouette of Fatepur Sikri from valley,fort & ruined wall.jpg": "20.22b",
    "22.04 White bird in flight,query Ibis,egret.jpg": "22.04b",
}


def photo_id(filename: str) -> str:
    """The roll.slide number, or a slugified filename stem for the rare file
    that never got one (e.g. a scan named "pumpboy.jpg") - always a string,
    since data/<leg>_photos.json needs a stable id to key derivative files on.
    """
    if filename in ID_OVERRIDES:
        return ID_OVERRIDES[filename]
    m = ID_RE.match(filename)
    if m:
        roll = m.group(1) or m.group(3)
        slide = m.group(2) or m.group(4)
        return f"{roll}.{slide}"
    stem = Path(filename).stem.lower()
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-")


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def dedupe(files: list[Path]) -> list[Path]:
    """Drop byte-identical "Copy of ..." duplicates.

    This alone doesn't guarantee one file per photo id - two different scans
    of the same slide (e.g. an early low-res preview and the real scan) can
    share an id without being byte-identical. See dedupe_by_id for that case.
    """
    seen_hashes: dict[str, Path] = {}
    kept = []
    # Prefer the file WITHOUT "Copy of " prefix when both exist.
    files_sorted = sorted(files, key=lambda p: p.name.startswith("Copy of "))
    for f in files_sorted:
        h = file_hash(f)
        if h in seen_hashes:
            continue
        seen_hashes[h] = f
        kept.append(f)
    return kept


def dedupe_by_id(files: list[Path]) -> list[Path]:
    """Keep one file per photo id, preferring the largest (highest-res) file.

    Handles the same slide having been scanned more than once under the
    same roll.slide number - the derivative filenames are keyed by id alone,
    so two source files can't both survive.
    """
    by_id: dict[str, Path] = {}
    dropped = []
    for f in sorted(files, key=lambda p: p.stat().st_size, reverse=True):
        pid = photo_id(f.name)
        if pid in by_id:
            dropped.append(f.name)
            continue
        by_id[pid] = f
    if dropped:
        print(f"note: kept higher-res scan, dropped duplicate id for: {dropped}")
    return list(by_id.values())
# Longest-edge caps and JPEG quality per derivative. `display` is
# deliberately smaller than it once was (1600px/q87): a published GitHub
# Pages site is capped at 1GB, and shipping full/ alongside it at the old
# size would land ~955MB, with no room left. See README.md for the budget.
#
# thumb is 600px because the diary shows slides at up to 300px, and a
# retina screen wants twice the pixels it displays. It costs ~25MB across
# the archive, which the budget above has room for.
THUMB_MAX_EDGE, THUMB_QUALITY = 600, 85
DISPLAY_MAX_EDGE, DISPLAY_QUALITY = 1200, 82
FULL_QUALITY = 95


def make_derivative(src: Path, dest: Path, max_edge: int | None, quality: int = 87) -> None:
    """Resize and re-encode `src` into `dest`. `max_edge=None` keeps the
    source's own resolution (used for full/, which only downsizes nothing).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        if max_edge is not None:
            w, h = im.size
            scale = max_edge / max(w, h)
            if scale < 1:
                im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        # subsampling=0 keeps full chroma resolution, which matters at
        # full/'s quality level and costs little there; the web-sized
        # derivatives don't need it.
        im.save(dest, "JPEG", quality=quality, optimize=True,
                subsampling=0 if max_edge is None else 2)


def make_full(src: Path, dest: Path) -> None:
    """The distributable full-resolution copy.

    Byte-copies an already-JPEG source (no generation loss, no size
    inflation); encodes anything else - in practice the 285 uncompressed
    BMP scans from Turkey, Iran and Afghanistan - at FULL_QUALITY.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in {".jpg", ".jpeg"}:
        shutil.copyfile(src, dest)
    else:
        make_derivative(src, dest, None, FULL_QUALITY)
def process_leg(src_dir: Path, leg_slug: str, out_root: Path) -> dict:
    files = [
        f
        for f in src_dir.iterdir()
        if f.is_file()
        and f.name not in JUNK_NAMES
        and f.suffix.lower() not in JUNK_SUFFIXES
        # ".bm" covers a couple of files with a truncated ".bmp" extension
        # (a Windows short-filename artifact on the original scans) whose
        # content is verified BMP.
        and f.suffix.lower() in {".jpg", ".jpeg", ".bmp", ".bm", ".png"}
    ]
    unique = dedupe_by_id(dedupe(files))

    thumb_dir = out_root / "photos" / leg_slug / "thumb"
    display_dir = out_root / "photos" / leg_slug / "display"
    full_dir = out_root / "photos" / leg_slug / "full"

    report = {"total_files": len(files), "unique": len(unique), "skipped_dupes": len(files) - len(unique), "fallback_id": []}

    for f in unique:
        pid = photo_id(f.name)
        if not ID_RE.match(f.name):
            report["fallback_id"].append((f.name, pid))
        make_derivative(f, thumb_dir / f"{pid}.jpg", THUMB_MAX_EDGE, THUMB_QUALITY)
        make_derivative(f, display_dir / f"{pid}.jpg", DISPLAY_MAX_EDGE, DISPLAY_QUALITY)
        make_full(f, full_dir / f"{pid}.jpg")

    return report
CREATOR = "Monique Bond"
CREDIT = "Monique Bond, 1976 Trip"  # IPTC:Credit is capped at 32 bytes
IPTC_CITY_LIMIT = 32  # bytes, per the IPTC IIM spec
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
USAGE_TERMS = (
    "This work is licensed under the Creative Commons Attribution 4.0 "
    f"International License. To view a copy of this license, visit {LICENSE_URL}"
)
SITE = "https://fcbond.github.io/the-trip"
def rights_for(date: str) -> str:
    """Copyright line, carrying the year the photo was taken."""
    year = date[:4] if date else "1976"
    return f"© {year} {CREATOR}. Licensed CC BY 4.0."


def deg_ref(value: float, positive: str, negative: str) -> tuple[float, str]:
    return abs(value), positive if value >= 0 else negative


def tags_for(photo: dict, stop: dict | None) -> list[str]:
    """The exiftool -TAG=VALUE arguments for one photo."""
    pid = photo["id"]
    desc = photo.get("description") or ""
    date = photo.get("date") or ""
    page = f"{SITE}/photo/{pid}.html"
    rights = rights_for(date)

    args = [
        f"-XMP:Title={pid} - {desc}" if desc else f"-XMP:Title={pid}",
        f"-IPTC:ObjectName={pid}",
        f"-IPTC:Caption-Abstract={desc}",
        f"-XMP-dc:Description={desc}",
        f"-EXIF:ImageDescription={desc}",
        f"-EXIF:Artist={CREATOR}",
        f"-IPTC:By-line={CREATOR}",
        f"-XMP-dc:Creator={CREATOR}",
        f"-EXIF:Copyright={rights}",
        f"-IPTC:CopyrightNotice={rights}",
        f"-XMP-dc:Rights={rights}",
        "-XMP-xmpRights:Marked=True",
        f"-XMP-xmpRights:UsageTerms={USAGE_TERMS}",
        f"-XMP-xmpRights:WebStatement={LICENSE_URL}",
        f"-XMP-cc:License={LICENSE_URL}",
        f"-XMP-cc:AttributionName={CREATOR}",
        f"-XMP-cc:AttributionURL={page}",
        f"-IPTC:Credit={CREDIT}",
        f"-XMP-dc:Relation={page}",
        f"-XMP-dc:Identifier={pid}",
    ]

    if date:
        # No time of day was ever recorded; 00:00:00 is a placeholder, not
        # a claim about when the shutter fired.
        args += [
            f"-EXIF:DateTimeOriginal={date.replace('-', ':')} 00:00:00",
            f"-IPTC:DateCreated={date.replace('-', ':')}",
        ]

    # IPTC caps City at 32 bytes. A handful of photos have caption text
    # sitting in `place` rather than a place name (see --report-places);
    # those get skipped rather than silently truncated into a location
    # field, which would be wrong data, not just clipped data.
    place = photo.get("place") or ""
    if place and len(place.encode()) <= IPTC_CITY_LIMIT:
        args.append(f"-IPTC:City={place}")
        args.append(f"-XMP-photoshop:City={place}")
    if photo.get("country"):
        args.append(f"-IPTC:Country-PrimaryLocationName={photo['country']}")
        args.append(f"-XMP-photoshop:Country={photo['country']}")

    keywords = [leg_display_name(photo["leg"]), photo.get("country") or "",
                stop["name"] if stop else "", "1976", "Bond Trip"]
    for kw in dict.fromkeys(k for k in keywords if k):
        args.append(f"-IPTC:Keywords={kw}")
        args.append(f"-XMP-dc:Subject={kw}")

    if stop:
        # A landmark can sit a long way from the stop it hangs off - Opuzen
        # is 85km down the coast from Omiš, Pasargadae 39km from
        # Persepolis - so a landmark with its own lat/lon wins for both the
        # sub-location and the coordinates. Landmarks within their stop
        # (Badshahi Mosque in Lahore) declare none and inherit the stop's.
        landmark = next(
            (lm for lm in (stop.get("landmarks") or [])
             if lm.get("name") == photo.get("landmark")),
            None,
        )
        located = landmark if landmark and landmark.get("lat") is not None else stop
        args.append(f"-IPTC:Sub-location={located['name']}")
        args.append(f"-XMP-iptcCore:Location={located['name']}")
        # Not the exact spot the photo was taken from - close enough to
        # place it on a map, not a survey point.
        if located.get("lat") is not None and located.get("lon") is not None:
            lat, lat_ref = deg_ref(located["lat"], "N", "S")
            lon, lon_ref = deg_ref(located["lon"], "E", "W")
            args += [
                f"-EXIF:GPSLatitude={lat}", f"-EXIF:GPSLatitudeRef={lat_ref}",
                f"-EXIF:GPSLongitude={lon}", f"-EXIF:GPSLongitudeRef={lon_ref}",
            ]
    return args
def stamp_leg(photos, stop_by_photo, legs, out_root, kinds, dry_run):
    """Write the metadata block into each derivative that exists."""
    written = missing = 0
    for photo in photos:
        if photo["leg"] not in legs:
            continue
        stop = stop_by_photo.get(photo["id"])
        # image_leg differs from leg when a roll crossed a border mid-film
        # and the scan sits in the previous leg's folder.
        for kind in kinds:
            path = out_root / "photos" / photo["image_leg"] / kind / f"{photo['id']}.jpg"
            if not path.exists():
                missing += 1
                continue
            # IPTC IIM defaults to Latin-1, which can't hold the Turkish,
            # Persian and Indic characters in these captions and place
            # names. CodedCharacterSet=UTF8 is how IPTC declares otherwise.
            cmd = [
                "exiftool", "-charset", "iptc=UTF8",
                "-IPTC:CodedCharacterSet=UTF8",
                *tags_for(photo, stop), "-overwrite_original", "-q", str(path),
            ]
            if dry_run:
                print(f"{path}: {len(cmd) - 3} tags")
            else:
                subprocess.run(cmd, check=True)
            written += 1
    return written, missing


def report_places(photos, stops, legs):
    """Places that read like caption text rather than a place name.

    Length alone misses the short ones ("roof tent&Land Rover" is 20
    bytes), so a `place` is suspect when it matches no stop and no alias
    AND reads like prose - starts lowercase, strings clauses together with
    commas, or overruns the IPTC:City limit.
    """
    stop_names = {}
    for s in stops:
        stop_names.setdefault(s["leg"], set()).add(s["name"].lower())
    suspect = []
    for photo in photos:
        place = (photo.get("place") or "").strip()
        if not place or photo["leg"] not in legs:
            continue
        leg = photo["leg"]
        bare = TRANSIT_PREFIX_RE.sub("", place).strip().lower()
        aliases = {k.lower() for k in LOCATION_ALIASES.get(leg, {})}
        if bare in stop_names.get(leg, set()) or place.lower() in aliases or bare in aliases:
            continue
        why = []
        if place[0].islower():
            why.append("lowercase")
        if "," in place:
            why.append("comma")
        if len(place.encode()) > IPTC_CITY_LIMIT:
            why.append(f"{len(place.encode())}b")
        if why:
            suspect.append((leg, photo["id"], place, "+".join(why)))
    for leg, pid, place, why in sorted(suspect):
        print(f"{leg:12s} {pid:8s} {place!r}  [{why}]")
    print(f"\n{len(suspect)} suspect `place` value(s): match no stop or alias, and "
          f"read like caption text. Over {IPTC_CITY_LIMIT} bytes they also lose "
          "their IPTC:City tag.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--legs", nargs="+", choices=LEGS, default=LEGS,
                        help="Legs to process (default: all).")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT,
                        help="The archive's 'The Trip Photos _76' directory "
                             "(default: $TRIP_ARCHIVE, else the in-repo data/).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Output tree; photos land under <out>/photos/<leg>/.")
    parser.add_argument("--kinds", nargs="+", choices=KINDS, default=["full"],
                        help="Which derivatives to stamp with metadata (default: "
                             "full - the copy that gets downloaded and travels).")
    parser.add_argument("--only-metadata", action="store_true",
                        help="Re-stamp existing derivatives without re-encoding them.")
    parser.add_argument("--skip-metadata", action="store_true",
                        help="Generate derivatives but leave them unstamped. Only "
                             "useful mid-debugging: the published copies would carry "
                             "no credit or licence.")
    parser.add_argument("--report-places", action="store_true",
                        help="List photos whose `place` looks like caption text. "
                             "Writes nothing.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what metadata would be written, change nothing.")
    args = parser.parse_args()

    # Every leg is loaded whatever --legs says, so photo->stop matching sees
    # the same data build.py does; --legs filters what gets written.
    photos, stops = [], []
    for leg in LEGS:
        _, s, p, _ = load_leg(leg)
        photos += p
        stops += s

    if args.report_places:
        report_places(photos, stops, args.legs)
        return

    if not args.only_metadata:
        for leg in args.legs:
            src = args.source_root / LEG_FOLDERS[leg]
            if not src.is_dir():
                raise SystemExit(
                    f"No such source directory: {src}\n"
                    "The masters live in the private archive repo. Pass "
                    "--source-root <path to 'The Trip Photos _76'> or set "
                    "TRIP_ARCHIVE to point at it.")
            report = process_leg(src, leg, args.out)
            print(f"{leg}: {report}")

    if args.skip_metadata:
        print("--skip-metadata: derivatives carry no credit or licence")
        return

    if not args.dry_run and not shutil.which("exiftool"):
        raise SystemExit("exiftool not found - sudo apt install libimage-exiftool-perl")

    _, by_stop = build_photo_index(photos, stops)
    stop_by_photo = {p["id"]: next(s for s in stops if s["slug"] == slug)
                     for slug, plist in by_stop.items() for p in plist}
    written, missing = stamp_leg(photos, stop_by_photo, args.legs, args.out,
                                 args.kinds, args.dry_run)
    over = sum(1 for p in photos if p["leg"] in args.legs and p.get("place")
               and len(p["place"].encode()) > IPTC_CITY_LIMIT)
    print(f"{'would write' if args.dry_run else 'wrote'} metadata to {written} file(s)"
          + (f"; {missing} expected derivative(s) not found" if missing else "")
          + (f"; {over} photo(s) got no IPTC:City (place too long - run "
             "--report-places)" if over else ""))


if __name__ == "__main__":
    main()
