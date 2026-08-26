"""Render every leg's metadata/ JSON into a single continuous site in build/.

Legs are merged (not siloed): the diary, map, and tags all span the whole
trip, so prev/next diary-day and prev/next stop links flow naturally across
a leg boundary once all legs' days/stops are sorted together by date.
"""

import json
import hashlib
import re
import shutil
from pathlib import Path

import tomlkit
from jinja2 import Environment, FileSystemLoader
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "metadata"
TEMPLATES = ROOT / "web" / "templates"
# Unencrypted build output, used for local preview. `docs/` (served by
# GitHub Pages) only ever holds the staticrypt-encrypted output produced by
# apply_password.py from this directory - see that script for why the two
# are kept separate.
DOCS = ROOT / "build"

LEGS = ["uk_greece", "turkey", "iran", "afghanistan", "pakistan", "india", "bangkok"]

# leg.title() mangles underscored slugs ("uk_greece" -> "Uk_Greece"); only
# legs whose display name isn't just the capitalized slug need an entry here.
LEG_DISPLAY_NAMES = {"uk_greece": "UK & Greece"}


def leg_display_name(leg):
    return LEG_DISPLAY_NAMES.get(leg, leg.title())

# A `place` written as a journey rather than a destination: "toward Van",
# "near Malatya", "en route to Kabul". The photo was taken on the way to a
# stop, so it belongs with that stop - strip the modifier and match on what
# remains. Checked only after an exact LOCATION_ALIASES hit fails, so an
# explicit mapping always wins.
TRANSIT_PREFIX_RE = re.compile(
    r"^(?:towards?|near|nr\.?|en route to|on the way to|approaching|outside)\s+", re.I
)

# Free-text `place` values found in each leg's <leg>_photos.toml, mapped to
# stop slugs within that same leg. Multi-place strings ("A / B") are matched
# left-to-right. A photo's own explicit `stop` field (set by hand for
# one-off cases the aliases below can't express, e.g. Safi Abad Palace)
# always wins over this; anything matched by neither falls back to a
# date-range match against that leg's own stops.
LOCATION_ALIASES = {
    "uk_greece": {
        "Pindos": ["metsovo"],
        "Senj": ["postojna"],
    },
    "turkey": {
        # Sites within a stop that have no stop of their own. Hoşap Castle
        # and Akdamar are landmarks of Van; the Asclepeion is the healing
        # sanctuary below the Pergamon acropolis.
        "Asclepeion": ["pergamon"],
        "Hierapolis": ["pamukkale"],
        "Hoşap Castle": ["van"],
        "Alanya": ["alanya"],
        "Anamur / Narlikuyu": ["anamur", "narlıkuyu"],
        "Aspendos": ["aspendos"],
        "Bursa": ["bursa"],
        "Goreme": ["göreme"],
        "Istanbul": ["istanbul"],
        "Izmir": ["i̇zmir", "izmir"],
        "Kusadasi": ["kuşadası"],
        "Lake Van": ["van"],
        "Nevsehir": ["nevşehir"],
        "Ortahisar / Zelve": ["ortahisar", "zelve"],
        "Pammukale": ["pamukkale"],
        "Pergamon": ["pergamon"],
        "Side / Alanya": ["side", "alanya"],
        "Troy": ["troy"],
        "Van to Iran border": ["van"],
        # Waypoints on the two-day Kayseri -> Van drive (14-15 Sep), which
        # no stop's date range covers. Both point at the destination.
        "Gurun": ["van"],
        "Malatya": ["van"],
    },
    "india": {
        "Simla": ["shimla"],
        # Day sites and sanctuaries that aren't stops of their own: Amber
        # Fort is the fort above Jaipur, Ranthambore the park the Sawai
        # Madhopur stop exists for. Bharatpur IS a stop (they stayed two
        # nights) - the alias just makes the match explicit rather than
        # leaving it to the date fallback, which would hand 9 Dec to
        # Fatehpur Sikri.
        "Amber Fort": ["jaipur"],
        # A compound place, like Turkey's "Side / Alanya": the drive
        # between the two, so it belongs on both stops.
        "Hoshiarpur to Nangal": ["hoshiarpur", "nangal"],
        "Anandpur": ["nangal"],   # Anandpur Sahib, ~10km from Nangal
        "Bhakra Dam": ["bhakra dam"],
        "Bharatpur": ["bharatpur"],
        "Ranthambore National Park": ["sawai madhopur"],
        "Sariska Tiger Reserve": ["sariska"],
    },
    "iran": {
        # Same-day excursions with no stop of their own: Cyrus's tomb at
        # Pasargadae (80km north, visited on the way in on 30 Sep) and the
        # Safavid dam at Fariman, an afternoon out from Mashhad.
        "Pasargadae": ["persepolis"],
        "Fariman": ["mashhad"],
        "Golestan": ["golestan national park"],
        "Caspian Sea": ["caspian"],
        "Safi Abad Palace": ["safi"],
    },
    "afghanistan": {
        "Shar-e Zuhak": ["shahr-e zohak"],
        "Herat": ["herat"],
        "Lashkargah": ["lashkar"],
        "Qala-e-Bost": ["lashkar"],
        "Kandahar": ["kandahar"],
        "Kabul": ["kabul"],
        "Bamyan": ["bamiyan"],
        "Djellalabad": ["jalalabad"],
        "Hadda to Khyber Pass": ["hadda", "khyber"],
    },
    # Pakistan's stops have several same-day date-range overlaps (Taxila
    # 14-16 Nov overlaps Rawalpindi/Islamabad on the 16th, Islamabad overlaps
    # Lahore on the 17th) since they were a continuous journey through
    # adjacent places - date-fallback alone would silently pick whichever
    # stop sorts first, so anything with an unambiguous place name is routed
    # explicitly instead.
    "pakistan": {
        # 14 Nov: Darra, back to Peshawar, then east to Taxila, following
        # the Kabul river to where it meets the Indus at Attock. The
        # date fallback would otherwise leave these on the Darra stop.
        "Attock": ["taxila"],
        "Attock Fort": ["taxila"],
        "Wah Gardens": ["taxila"],
        "Darra": ["darra adam khel"],
        "Taxila museum": ["taxila"],
        "Rawalpindi": ["rawalpindi"],
    },
}


def load_json(name):
    """Load and parse a JSON file from data/."""
    return json.loads((DATA / name).read_text())


def _plain(value):
    """Recursively convert tomlkit's container types to plain dict/list, so
    nested tables (e.g. a stop's [[landmarks]]) come out Jinja-friendly
    instead of as tomlkit's own Table/AoT wrapper types."""
    if hasattr(value, "items"):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def load_toml_array(name, key):
    """Load a [[key]] array-of-tables from a TOML file in data/, as plain dicts."""
    doc = tomlkit.parse((DATA / name).read_text())
    return [_plain(item) for item in doc[key]]


def landmark_links(value):
    """Normalise a landmark's `links` into [{"url", "label"}, ...].

    Accepts a bare URL string, a list of URL strings, or a list of
    {url, label} tables - so a landmark with nothing on Wikipedia (a
    tourism-board page, a local heritage listing) can still be linked, and
    can carry more than one. A missing label falls back to the hostname,
    which reads better than a bare URL and doesn't claim to be Wikipedia.
    """
    if not value:
        return []
    if isinstance(value, str):
        value = [value]
    out = []
    for item in value:
        if isinstance(item, str):
            item = {"url": item}
        url = item.get("url")
        if not url:
            continue
        label = item.get("label")
        if not label:
            label = urlsplit(url).netloc.removeprefix("www.")
        out.append({"url": url, "label": label})
    return out


def asset_versions(static_dir):
    """Short content hash per static file, for cache-busting URLs.

    Browsers cache static/css/style.css and static/js/*.js indefinitely, so
    a returning visitor keeps the old copies after a rebuild until their
    cache happens to expire. Suffixing each URL with a hash of the file's
    own bytes means the URL changes exactly when the file does - and stays
    identical when it doesn't, so nothing is re-downloaded needlessly.
    """
    versions = {}
    for f in sorted(static_dir.rglob("*")):
        if f.is_file():
            digest = hashlib.sha256(f.read_bytes()).hexdigest()[:8]
            versions[f.relative_to(static_dir).as_posix()] = digest
    return versions


def load_leg(leg):
    """Load one leg's days/stops/photos/tags, tagging each record with its leg.

    A photo's `leg` (used for stop/tag matching) always matches the file
    it's listed in, but its `image_leg` (used only to build the thumb/
    display URL) can be set explicitly to a different leg when the source
    scan physically sits in another leg's photo folder because the film
    roll crossed a border mid-roll. See README's India setup note.
    """
    days = load_json(f"{leg}_days.json")
    stops = load_toml_array(f"{leg}_stops.toml", "stop")
    photos = load_toml_array(f"{leg}_photos.toml", "photo")
    tags = load_json(f"{leg}_tags.json")
    for d in days:
        d["leg"] = leg
    for s in stops:
        s["leg"] = leg
        s["links"] = landmark_links(s.get("links"))
        for lm in s.get("landmarks") or []:
            lm["links"] = landmark_links(lm.get("links"))
    for p in photos:
        p["leg"] = leg
        if not p.get("image_leg"):
            p["image_leg"] = leg
    return days, stops, photos, tags


def date_in_range(date, start, end):
    """True if start <= date <= end (all ISO date strings)."""
    return start <= date <= end


def stop_for_date(stops, date):
    """First stop (in list order) whose date range contains date, or None."""
    for s in stops:
        if date_in_range(date, s["date_start"], s["date_end"]):
            return s
    return None


def _stop_index(leg_stops):
    """Stops of one leg, grouped by lower-cased name.

    A name can belong to more than one stop (Kabul and Isfahan were each
    visited twice), so every stop is kept under its name and the photo's
    own date picks between them later.
    """
    by_name = {}
    for s in leg_stops:
        by_name.setdefault(s["name"].lower(), []).append(s)
    return by_name


def _match_name(key, stops_by_name, date):
    """Slug of the stop whose name contains `key`, or is contained by it.

    Containment rather than equality so a stop renamed "Bombay (Mumbai)"
    still answers to "Bombay". Where several stops share a name, the date
    disambiguates; failing that the first declared one wins.
    """
    key = key.lower()
    for name_lower, candidates in stops_by_name.items():
        if key in name_lower or name_lower in key:
            return (stop_for_date(candidates, date) or candidates[0])["slug"]
    return None


def _match_place(place, aliases, stops_by_name, date):
    """Every stop slug a photo's `place` resolves to, best route first.

    1. LOCATION_ALIASES, which can name several stops for one compound
       place ("Side / Alanya"), and so returns a list.
    2. The place naming a stop outright ("Ellora Caves", "Ghazni").
    3. Either of those again, after stripping a leading modifier, so a
       photo taken on the way somewhere lands on the place it was heading
       for ("toward Van" -> Van).

    Returns [] when none of them match, leaving the caller to fall back to
    the date range.
    """
    for candidate in dict.fromkeys([place, TRANSIT_PREFIX_RE.sub("", place).strip()]):
        if not candidate:
            continue
        slugs = []
        for token in aliases.get(candidate.lower(), []):
            slug = _match_name(token, stops_by_name, date)
            if slug:
                slugs.append(slug)
        if slugs:
            return slugs
        slug = _match_name(candidate, stops_by_name, date)
        if slug:
            return [slug]
    return []


def build_photo_index(photos, stops):
    """Group photos by date and by containing stop slug.

    Each photo is matched against stops from its own leg only: an explicit
    `stop` field wins outright, then its `place` via _match_place, then a
    date-range fallback. The fallback is the weakest of the three - where
    two stops cover the same day it picks whichever was declared first -
    so a photo landing oddly usually means its `place` is caption text
    rather than a place name.
    """
    stops_by_leg = {}
    for s in stops:
        stops_by_leg.setdefault(s["leg"], []).append(s)
    # Built once per leg rather than once per photo: both are pure
    # functions of the leg's stops.
    names_by_leg = {leg: _stop_index(ss) for leg, ss in stops_by_leg.items()}
    aliases_by_leg = {
        leg: {k.lower(): v for k, v in LOCATION_ALIASES.get(leg, {}).items()}
        for leg in stops_by_leg
    }

    by_date = {}
    by_stop_slug = {s["slug"]: [] for s in stops}
    unmatched = []

    for p in photos:
        by_date.setdefault(p["date"], []).append(p)
        leg = p["leg"]
        leg_stops = stops_by_leg.get(leg, [])

        if p.get("stop"):
            by_stop_slug[p["stop"]].append(p)
            continue

        slugs = []
        if p["place"]:
            slugs = _match_place(
                p["place"], aliases_by_leg.get(leg, {}), names_by_leg.get(leg, {}), p["date"]
            )
        if not slugs:
            s = stop_for_date(leg_stops, p["date"])
            if s:
                slugs = [s["slug"]]
            else:
                unmatched.append(p["id"])
        for slug in dict.fromkeys(slugs):  # de-dupe, keep order
            by_stop_slug[slug].append(p)

    for date in by_date:
        by_date[date].sort(key=lambda p: p["id"])
    for slug in by_stop_slug:
        by_stop_slug[slug].sort(key=lambda p: p["id"])

    if unmatched:
        print(f"warning: {len(unmatched)} photos matched to no stop: {unmatched}")
    return by_date, by_stop_slug


def group_photos_by_landmark(photos, stop):
    """Group a stop's photos under its declared landmarks (e.g. Agra's Taj
    Mahal, Agra Fort), for stops big enough to have more than one linkable
    site. A photo opts in via a `landmark` field matching a landmark's
    `name` exactly; anything else - including every photo on a stop with no
    landmarks declared at all - lands in one landmark-less group, so this is
    a no-op for the common case. Returns a list of {"landmark", "photos"}
    dicts, landmark-less photos first, then landmarks in declared order.
    """
    landmarks = stop.get("landmarks") or []
    by_name = {lm["name"]: [] for lm in landmarks}
    unassigned = []
    for p in photos:
        bucket = by_name.get(p.get("landmark"))
        (bucket if bucket is not None else unassigned).append(p)
    groups = []
    if unassigned:
        groups.append({"landmark": None, "photos": unassigned})
    for lm in landmarks:
        if by_name[lm["name"]]:
            groups.append({"landmark": lm, "photos": by_name[lm["name"]]})
    return groups


def tag_label(key):
    """Turn a tag key like 'puncture_tyre_breakdown' into 'Puncture / Tyre / Breakdown'."""
    return key.replace("_", " / ").title()


def merge_tags(tag_dicts):
    """Combine each leg's tag-occurrence dict into one, summing occurrence lists."""
    merged = {}
    for tags in tag_dicts:
        for key, occs in tags.items():
            merged.setdefault(key, []).extend(occs)
    return merged


def pix_by_date_person(pix):
    """Group diary-pix entries by (date, person initial)."""
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in pix:
        by_key.setdefault((p["date"], p["person"]), []).append(p)
    return by_key


def pix_after_entry(day, pix_index):
    """{entry index: [pix,...]} - each speaker's drawings attach after their
    LAST entry that day, so they read as "next to" that child's diary text
    rather than a separate section."""
    last_index_for_speaker = {}
    for i, entry in enumerate(day["entries"]):
        last_index_for_speaker[entry["speaker"]] = i
    result: dict[int, list[dict]] = {}
    for speaker, idx in last_index_for_speaker.items():
        matches = pix_index.get((day["date"], speaker))
        if matches:
            result[idx] = matches
    return result


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_NAMES_FULL = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def add_month_fields(days):
    """Set day["month"] (sortable "1976-08") and day["month_label"]
    ("August 1976") in place, for grouping the diary index by month."""
    for d in days:
        year, month = d["date"][:4], int(d["date"][5:7])
        d["month"] = d["date"][:7]
        d["month_label"] = f"{MONTH_NAMES_FULL[month - 1]} {year}"


MILES_RE = re.compile(r"\(([\d,]+)\s*miles travelled\)")


def add_tag_sizes(tag_list):
    """Set tag["size"] to a 1-5 bucket scaled by count, so the tag cloud on
    the index page reads at a glance which themes recur most."""
    if not tag_list:
        return
    counts = [t["count"] for t in tag_list]
    lo, hi = min(counts), max(counts)
    for t in tag_list:
        t["size"] = 1 if hi == lo else 1 + round(4 * (t["count"] - lo) / (hi - lo))


def add_miles_so_far(days):
    """Set day["miles_so_far"] to the cumulative trip mileage as of that day,
    carried forward from the last "(N miles travelled)" the G/M mileage log
    happened to mention - most days don't log one themselves."""
    last_known = None
    for d in days:
        for e in d["entries"]:
            for m in MILES_RE.finditer(e["text"]):
                last_known = int(m.group(1).replace(",", ""))
        d["miles_so_far"] = f"{last_known:,} mi" if last_known is not None else ""


PHOTO_REF_RE = re.compile(r"\b(\d{1,2}a?)\.(\d{1,2})\b")


def linkify_photo_refs(text, known_ids, self_id):
    """Turn a mention of another photo's id in caption text (e.g. "...below
    natural lake of 12.30") into a link to that photo's page.

    Ids in prose aren't always written the same way they're stored (e.g.
    "11.6" in a caption vs the stored id "11.06"), so a few zero-padding
    variants are tried against the known id set rather than assuming one
    convention. Assumes it's only ever rendered from a page one directory
    below the site root (stops/, diary/, photo/), which is true today.
    """

    def replace(m):
        roll, slide = m.group(1), m.group(2)
        for candidate in (
            f"{roll}.{slide}",
            f"{roll.zfill(2)}.{slide.zfill(2)}",
            f"{roll}.{slide.zfill(2)}",
            f"{roll.zfill(2)}.{slide}",
        ):
            if candidate in known_ids and candidate != self_id:
                return f'<a href="../photo/{candidate}.html">{m.group(0)}</a>'
        return m.group(0)

    return PHOTO_REF_RE.sub(replace, text)


def add_diary_place(days, stops):
    """Set day["diary_place"] to a consistent "Stop - Country" string for the
    diary index, resolved from the stop table rather than the diary's own
    (inconsistently formatted, often blank) place_label header text."""
    for d in days:
        stop = stop_for_date(stops, d["date"])
        country = leg_display_name(d["leg"])
        d["diary_place"] = f"{stop['name']} - {country}" if stop else country


def leg_summary(days):
    """'Turkey (26 Aug - 20 Sep), Iran (21 Sep - 19 Oct)' - one range per leg, in trip order."""
    ranges = {}
    for d in days:
        r = ranges.setdefault(d["leg"], [d["date"], d["date"]])
        r[0], r[1] = min(r[0], d["date"]), max(r[1], d["date"])

    def fmt(iso):
        return f"{int(iso[8:10])} {MONTH_NAMES[int(iso[5:7]) - 1]}"

    parts = [f"{leg_display_name(leg)} ({fmt(start)} - {fmt(end)})" for leg, (start, end) in ranges.items()]
    return ", ".join(parts)


# The diary's real first/last dated entries - used only to detect whether
# every leg has been built yet, for the homepage's "still being added" vs
# "complete" copy.
FULL_TRIP_START = "1976-07-29"
FULL_TRIP_END = "1977-01-22"


def main():
    days, stops, photos, tag_dicts = [], [], [], []
    for leg in LEGS:
        d, s, p, t = load_leg(leg)
        days += d
        stops += s
        photos += p
        tag_dicts.append(t)
    tags = merge_tags(tag_dicts)

    days.sort(key=lambda d: d["date"])
    stops.sort(key=lambda s: s["date_start"])
    add_month_fields(days)
    add_miles_so_far(days)
    add_diary_place(days, stops)
    photos_by_date, photos_by_stop = build_photo_index(photos, stops)
    pix_index = pix_by_date_person(load_toml_array("diary_pix.toml", "pix"))

    known_photo_ids = {p["id"] for p in photos}
    for p in photos:
        p["description_html"] = linkify_photo_refs(p["description"], known_photo_ids, p["id"])
    photo_stop_slug = {p["id"]: slug for slug, plist in photos_by_stop.items() for p in plist}
    stops_by_slug = {s["slug"]: s for s in stops}
    day_dates = {d["date"] for d in days}

    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=False)

    if DOCS.exists():
        for item in DOCS.iterdir():
            if item.name in ("photos",):  # already built by process_photos.py
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    DOCS.mkdir(exist_ok=True)

    # static assets + data
    shutil.copytree(ROOT / "web" / "static", DOCS / "static", dirs_exist_ok=True)
    (DOCS / "data").mkdir(exist_ok=True)
    (DOCS / "data" / "stops.json").write_text(json.dumps(stops, ensure_ascii=False))

    is_complete = bool(days) and days[0]["date"] == FULL_TRIP_START and days[-1]["date"] == FULL_TRIP_END
    versions = asset_versions(ROOT / "web" / "static")

    def asset(path):
        """static/<path> with a cache-busting suffix, for use in templates."""
        v = versions.get(path)
        return f"static/{path}?v={v}" if v else f"static/{path}"

    env.globals["asset"] = asset
    base_ctx = {"leg_summary": leg_summary(days), "days_count": len(days), "is_complete": is_complete}

    def render(template_name, out_path, **ctx):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(env.get_template(template_name).render(**base_ctx, **ctx))

    # Home / map
    render("index.html", DOCS / "index.html", root="", stops=stops)

    # Diary index + per-day pages
    render("diary_index.html", DOCS / "diary" / "index.html", root="../", days=days)
    for i, day in enumerate(days):
        prev_day = days[i - 1]["date"] if i > 0 else None
        next_day = days[i + 1]["date"] if i < len(days) - 1 else None
        render(
            "day.html",
            DOCS / "diary" / f"{day['date']}.html",
            root="../",
            day=day,
            prev_day=prev_day,
            next_day=next_day,
            photos=photos_by_date.get(day["date"], []),
            stop=stop_for_date(stops, day["date"]),
            pix_after=pix_after_entry(day, pix_index),
        )

    # Stop pages
    for i, stop in enumerate(stops):
        stop_days = [d for d in days if date_in_range(d["date"], stop["date_start"], stop["date_end"])]
        render(
            "stop.html",
            DOCS / "stops" / f"{stop['slug']}.html",
            root="../",
            stop=stop,
            photo_groups=group_photos_by_landmark(photos_by_stop.get(stop["slug"], []), stop),
            days=stop_days,
            prev_stop=stops[i - 1] if i > 0 else None,
            next_stop=stops[i + 1] if i < len(stops) - 1 else None,
        )

    # Tags
    tag_list = [
        {"slug": key.replace("_", "-"), "label": tag_label(key), "count": len(occs)}
        for key, occs in sorted(tags.items(), key=lambda kv: -len(kv[1]))
    ]
    add_tag_sizes(tag_list)
    render("tags_index.html", DOCS / "tags" / "index.html", root="../", tags=tag_list)
    for key, occs in tags.items():
        render(
            "tag.html",
            DOCS / "tags" / f"{key.replace('_', '-')}.html",
            root="../",
            tag_name=key,
            tag_label=tag_label(key),
            occurrences=sorted(occs, key=lambda o: o["date"]),
        )

    # Photo pages - one per id, so a caption's cross-reference to another
    # photo (see linkify_photo_refs) and a "photo/<id>.html" URL both have
    # somewhere to land.
    for p in photos:
        stop = stops_by_slug.get(photo_stop_slug.get(p["id"]))
        render(
            "photo.html",
            DOCS / "photo" / f"{p['id']}.html",
            root="../",
            photo=p,
            stop=stop,
            has_day=p["date"] in day_dates,
        )

    print(f"built {len(days)} diary days, {len(stops)} stops, {len(tag_list)} tags, {len(photos)} photo pages into {DOCS}")


if __name__ == "__main__":
    main()
