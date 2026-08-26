"""Convert a leg's scanned slide photos into deduped, web-sized JPEGs.

Produces three derivatives per unique photo under docs/photos/<leg>/:
  thumb/<id>.jpg   - ~400px longest edge, for grids and map pins
  display/<id>.jpg - ~1200px longest edge, for the lightbox and photo page
  full/<id>.jpg    - native resolution, for the per-photo download link

The masters themselves live in the private archive repo and are never
opened for writing - see "Going public" in README.md. `full/` is the copy
that gets distributed, so it is the one that most needs embedded credit
and license metadata (see METADATA.md).

A source that is already JPEG is *copied* into full/ rather than
re-encoded: passing it back through Pillow costs a generation of loss and
inflates the total by ~40% for no gain. Only BMP sources get encoded.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

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
THUMB_MAX_EDGE, THUMB_QUALITY = 400, 87
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


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: process_photos.py <src_dir> <leg_slug> <out_root>")
        sys.exit(1)
    src, leg, out = sys.argv[1], sys.argv[2], sys.argv[3]
    result = process_leg(Path(src), leg, Path(out))
    print(result)
