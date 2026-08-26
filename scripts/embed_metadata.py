"""Write EXIF/IPTC/XMP metadata into the built photo derivatives.

Reads the curated data in metadata/*.toml + *_stops.toml and stamps each
derivative under build/photos/<leg>/ with its caption, creator, CC BY
licence, date, location, and a link back to its page on the site - so a
photo that leaves the site still says what it is and who made it. See
METADATA.md for the field spec and the reasoning behind each tag.

Run after process_photos.py and before build.py/apply_password.py:

    uv run python scripts/embed_metadata.py                  # all legs, full/ only
    uv run python scripts/embed_metadata.py --kinds full display thumb
    uv run python scripts/embed_metadata.py --legs turkey --dry-run

Requires exiftool (`sudo apt install libimage-exiftool-perl`). Derivatives
are regenerated from the masters on every run of process_photos.py, so
re-running this is always safe - it never touches the masters themselves.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import (LEGS, LOCATION_ALIASES, TRANSIT_PREFIX_RE, build_photo_index,
                   leg_display_name, load_leg)

ROOT = Path(__file__).resolve().parents[1]
BUILD_PHOTOS = ROOT / "build" / "photos"

CREATOR = "Monique Bond"
CREDIT = "Monique Bond, 1976 Trip"  # IPTC:Credit is capped at 32 bytes
IPTC_CITY_LIMIT = 32  # bytes, per the IPTC IIM spec
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
USAGE_TERMS = (
    "This work is licensed under the Creative Commons Attribution 4.0 "
    f"International License. To view a copy of this license, visit {LICENSE_URL}"
)
SITE = "https://fcbond.github.io/the-trip"
KINDS = ("thumb", "display", "full")


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legs", nargs="+", choices=LEGS, default=LEGS)
    parser.add_argument(
        "--kinds", nargs="+", choices=KINDS, default=["full"],
        help="Which derivatives to stamp (default: full - the copy that "
             "actually gets downloaded and travels).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written, change nothing.")
    parser.add_argument(
        "--report-places", action="store_true",
        help="List photos whose `place` looks like caption text rather than a "
             "place name. Writes nothing.",
    )
    args = parser.parse_args()

    if not args.dry_run and not subprocess.run(["which", "exiftool"], capture_output=True).stdout:
        raise SystemExit("exiftool not found - sudo apt install libimage-exiftool-perl")

    suspect = []
    photos, stops = [], []
    for leg in LEGS:  # every leg, so photo->stop matching sees the same data as build.py
        d, s, p, t = load_leg(leg)
        photos += p
        stops += s
    _, by_stop = build_photo_index(photos, stops)
    stop_by_photo = {p["id"]: next(s for s in stops if s["slug"] == slug)
                     for slug, plist in by_stop.items() for p in plist}

    if args.report_places:
        # Length alone misses the short ones ("roof tent&Land Rover" is 20
        # bytes). A `place` is suspect when it matches no stop and no alias
        # AND reads like prose - starts lowercase, or strings clauses
        # together with commas, or overruns the IPTC:City limit.
        stop_names = {}
        for s in stops:
            stop_names.setdefault(s["leg"], set()).add(s["name"].lower())
        for photo in photos:
            place = (photo.get("place") or "").strip()
            if not place or photo["leg"] not in args.legs:
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
        print(f"\n{len(suspect)} suspect `place` value(s): match no stop or alias, "
              "and read like caption text. Over "
              f"{IPTC_CITY_LIMIT} bytes they also lose their IPTC:City tag.")
        return

    written = missing = skipped_city = 0
    for photo in photos:
        if photo["leg"] not in args.legs:
            continue
        stop = stop_by_photo.get(photo["id"])
        image_leg = photo["image_leg"]  # set by load_leg; differs when a scan sits in another leg's folder
        for kind in args.kinds:
            path = BUILD_PHOTOS / image_leg / kind / f"{photo['id']}.jpg"
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
            if args.dry_run:
                print(f"{path}: {len(cmd) - 3} tags")
            else:
                subprocess.run(cmd, check=True)
            written += 1

    over = sum(1 for p in photos if p["leg"] in args.legs and p.get("place")
               and len(p["place"].encode()) > IPTC_CITY_LIMIT)
    print(f"{'would write' if args.dry_run else 'wrote'} metadata to {written} file(s)"
          + (f"; {missing} expected derivative(s) not found" if missing else "")
          + (f"; {over} photo(s) got no IPTC:City (place too long - run "
             "--report-places)" if over else ""))


if __name__ == "__main__":
    main()
