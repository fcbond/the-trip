"""Parse and process the DB/FB/HB "Diary pix" folders: Denise, Francis and
Helena's own drawings and diary pages, scanned as one PDF or image per item
and named "YYYY-MM-DD <initials> <title>.ext".

Writes metadata/diary_pix.toml (one [[pix]] per item), a whitespace-cropped
full-resolution master per item under build/photos/diary_pix/cropped/ (the
scanned pages have wide blank margins around the actual drawing), and
thumb/display JPEGs derived from that crop.
"""

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

import tomlkit
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "metadata"

# The scans live in the private archive repo, not here. Resolution order:
# --source-root, then $TRIP_ARCHIVE, then the pre-split in-repo location -
# the same order publish_full_res.py uses.
ENV_ROOT = os.environ.get("TRIP_ARCHIVE")
DEFAULT_SOURCE_ROOT = Path(ENV_ROOT) if ENV_ROOT else ROOT / "data"

FOLDER_NAMES = {
    "D": "DB 1976-77 Diary pix",
    "F": "FB 1976-77 Diary pix",
    "H": "HB 1976-77 Diary pix",
}


def folders(source_root: Path) -> dict[str, Path]:
    """Per-person scan directories under `source_root`."""
    found = {p: source_root / name for p, name in FOLDER_NAMES.items()}
    missing = [str(d) for d in found.values() if not d.is_dir()]
    if missing:
        raise SystemExit(
            "No such source directory:\n  " + "\n  ".join(missing) + "\n"
            "The diary-pix scans live in the private archive repo. Pass "
            "--source-root <path to the dir holding the 'Diary pix' folders> "
            "or set TRIP_ARCHIVE to point at it."
        )
    return found

NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) [A-Z]{2} (.+)\.(pdf|jpg|jpeg|png)$", re.IGNORECASE)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


_FORMAT_PRIORITY = {"pdf": 0, "jpg": 1, "jpeg": 1, "png": 2}


def parse_folder(person: str, folder: Path) -> list[dict]:
    by_key: dict[str, dict] = {}
    skipped = []
    for f in sorted(folder.iterdir()):
        m = NAME_RE.match(f.name)
        if not m:
            skipped.append(f.name)  # e.g. undated "1976 HB Watercolour scene.pdf"
            continue
        date, title, ext = m.groups()
        title = title.strip()
        if title == "_":
            title = ""
        # The same drawing occasionally got scanned into more than one
        # format (e.g. "Bangles.jpg" and "Bangles.png") - keep one.
        key = (date, slugify(title)).__repr__()
        item = {"person": person, "date": date, "title": title, "filename": f.name}
        existing = by_key.get(key)
        if existing is None or _FORMAT_PRIORITY.get(ext.lower(), 9) < _FORMAT_PRIORITY.get(
            existing["filename"].rsplit(".", 1)[-1].lower(), 9
        ):
            by_key[key] = item
    if skipped:
        print(f"note: {person} - skipped (no parseable date): {skipped}")
    return list(by_key.values())


def autocrop_whitespace(im: Image.Image, threshold: int = 240) -> Image.Image:
    """Crop to the bounding box of non-near-white content, with a small margin.

    These are scans of a drawing on a much larger sheet of paper, so the
    raw render is mostly blank margin - this trims it down to the actual
    artwork.
    """
    gray = im.convert("L")
    mask = gray.point(lambda p: 255 if p < threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return im
    padding = max(15, round(0.02 * max(im.width, im.height)))
    left = max(0, bbox[0] - padding)
    top = max(0, bbox[1] - padding)
    right = min(im.width, bbox[2] + padding)
    bottom = min(im.height, bbox[3] + padding)
    return im.crop((left, top, right, bottom))


def make_derivative(src: Path, dest: Path, max_edge: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        scale = max_edge / max(w, h)
        if scale < 1:
            im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        im.save(dest, "JPEG", quality=87, optimize=True)


def render_source(src: Path, tmp_dir: Path) -> Path:
    """Return a raster image path for a source file, converting PDFs via pdftoppm."""
    if src.suffix.lower() != ".pdf":
        return src
    out_stem = tmp_dir / src.stem
    subprocess.run(
        ["pdftoppm", "-jpeg", "-r", "200", "-singlefile", str(src), str(out_stem)],
        check=True,
    )
    return out_stem.with_suffix(".jpg")


def main(source_root=DEFAULT_SOURCE_ROOT):
    FOLDERS = folders(source_root)
    all_items = []
    for person, folder in FOLDERS.items():
        all_items += parse_folder(person, folder)

    doc = tomlkit.document()
    doc.add(tomlkit.comment("Denise/Francis/Helena's own diary drawings & pages, by date."))
    doc.add(tomlkit.comment("See README.md for field meanings."))
    doc.add(tomlkit.nl())
    array = tomlkit.aot()

    cropped_dir = ROOT / "build" / "photos" / "diary_pix" / "cropped"
    thumb_dir = ROOT / "build" / "photos" / "diary_pix" / "thumb"
    display_dir = ROOT / "build" / "photos" / "diary_pix" / "display"
    cropped_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for item in all_items:
            person_lower = item["person"].lower()
            title_slug = slugify(item["title"]) or "untitled"
            pid = f"{person_lower}-{item['date']}-{title_slug}"
            src = FOLDERS[item["person"]] / item["filename"]
            raster = render_source(src, tmp_dir)

            cropped_path = cropped_dir / f"{pid}.jpg"
            with Image.open(raster) as im:
                autocrop_whitespace(im.convert("RGB")).save(cropped_path, "JPEG", quality=92)

            make_derivative(cropped_path, thumb_dir / f"{pid}.jpg", 400)
            make_derivative(cropped_path, display_dir / f"{pid}.jpg", 1600)

            table = tomlkit.table()
            table["id"] = pid
            table["person"] = item["person"]
            table["date"] = item["date"]
            table["title"] = item["title"]
            table["filename"] = item["filename"]
            array.append(table)

    doc["pix"] = array
    (DATA / "diary_pix.toml").write_text(tomlkit.dumps(doc))
    print(f"wrote {len(all_items)} diary-pix entries to metadata/diary_pix.toml")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--source-root", type=Path, default=DEFAULT_SOURCE_ROOT,
        help="Directory holding the 'DB/FB/HB 1976-77 Diary pix' folders "
             "(default: $TRIP_ARCHIVE, else the pre-split in-repo data/).",
    )
    main(parser.parse_args().source_root)
