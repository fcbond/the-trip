"""Bundle each leg's full-resolution photos into a zip and publish them as
GitHub Release assets, for anyone who wants a whole leg at once rather
than clicking through the site's per-photo full-res links.

Source photos live in the private archive repo, not here - pass
--source-root, or set TRIP_ARCHIVE, to point at that checkout's
"The Trip Photos _76" directory. See "Going public" in README.md.

Building archives (the default) only writes zips under build/full_res/
(gitignored) - safe to run any time. Publishing requires --publish and a
`gh` CLI authenticated against fcbond/the-trip.

Note that release assets inherit repo permissions: on a private repo their
download URLs return 404 to anyone without access, so publishing there
distributes nothing publicly.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from photos import (JUNK_NAMES, JUNK_SUFFIXES, LEG_FOLDERS, SOURCE_SUFFIXES,
                    dedupe, dedupe_by_id, photo_id)

ROOT = Path(__file__).resolve().parents[1]
# The masters are not in this repo. Resolution order: --source-root, then
# $TRIP_ARCHIVE, then the pre-split in-repo location (kept so the script
# still works from an archive-repo checkout that has both).
ENV_ROOT = os.environ.get("TRIP_ARCHIVE")
DEFAULT_RAW_ROOT = Path(ENV_ROOT) if ENV_ROOT else ROOT / "data" / "The Trip Photos _76"
DEFAULT_OUT = ROOT / "build" / "full_res"
DEFAULT_TAG = "full-res-photos"



def leg_files(leg_slug: str, raw_root: Path) -> list[Path]:
    """Same source-file selection/dedupe as photos.py, so the
    archive matches exactly the photos that made it onto the site.
    """
    src_dir = raw_root / LEG_FOLDERS[leg_slug]
    if not src_dir.is_dir():
        raise SystemExit(
            f"No such source directory: {src_dir}\n"
            "The full-resolution masters live in the private archive repo. "
            "Pass --source-root <path to 'The Trip Photos _76'> or set "
            "TRIP_ARCHIVE to point at it."
        )
    files = [
        f
        for f in src_dir.iterdir()
        if f.is_file()
        and f.name not in JUNK_NAMES
        and f.suffix.lower() not in JUNK_SUFFIXES
        and f.suffix.lower() in SOURCE_SUFFIXES
    ]
    return dedupe_by_id(dedupe(files))


def build_archive(leg_slug: str, out_dir: Path, raw_root: Path) -> Path:
    """Zip a leg's unique full-res source photos, named by photo id."""
    files = leg_files(leg_slug, raw_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / f"{leg_slug}-full-res.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(files, key=lambda p: photo_id(p.name)):
            zf.write(f, arcname=f"{photo_id(f.name)}{f.suffix.lower()}")
    return archive_path


def publish(tag: str, archives: list[Path]) -> None:
    """Create the release if it doesn't exist yet, then upload/replace assets."""
    exists = subprocess.run(["gh", "release", "view", tag], capture_output=True).returncode == 0
    if not exists:
        subprocess.run(
            [
                "gh", "release", "create", tag,
                "--title", tag,
                "--notes", "Full-resolution originals, one zip per leg.",
            ],
            check=True,
        )
    subprocess.run(
        ["gh", "release", "upload", tag, "--clobber", *(str(a) for a in archives)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--legs", nargs="+", choices=sorted(LEG_FOLDERS), default=sorted(LEG_FOLDERS),
        help="Legs to archive (default: all).",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Local output directory for zips.")
    parser.add_argument(
        "--source-root", type=Path, default=DEFAULT_RAW_ROOT,
        help="Path to 'The Trip Photos _76' in the private archive checkout "
             "(default: $TRIP_ARCHIVE, else the pre-split in-repo location).",
    )
    parser.add_argument("--tag", default=DEFAULT_TAG, help="GitHub Release tag to publish under.")
    parser.add_argument(
        "--publish", action="store_true",
        help="Upload the built archives as GitHub Release assets. Without this "
             "flag the script only writes zips locally.",
    )
    args = parser.parse_args()

    archives = []
    for leg in args.legs:
        path = build_archive(leg, args.out, args.source_root)
        size_mb = path.stat().st_size / 1_000_000
        print(f"{leg}: {path} ({size_mb:.0f} MB)")
        archives.append(path)

    if args.publish:
        publish(args.tag, archives)
        print(f"Published {len(archives)} asset(s) to release '{args.tag}'.")
    else:
        print("Local build only - rerun with --publish to upload to GitHub Releases.")


if __name__ == "__main__":
    main()
