"""Wrap build/ (plain HTML) with a staticrypt password gate, writing docs/.

docs/ is what GitHub Pages actually serves, so it's the only place the
password-protected output should live; build/ stays a local, gitignored
preview of the plain site. staticrypt encrypts each HTML page's body
client-side (decrypted via a password prompt using the Web Crypto API) but
does not touch linked binary assets (photos, css, js) - those are copied
through unchanged, so this is a light deterrent against casual/search
discovery, not real access control.

Password comes from the STATICRYPT_PASSWORD env var so it's never
hardcoded here or passed as a visible CLI argument in shell history.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DOCS = ROOT / "docs"
TEMPLATE = ROOT / "web" / "templates" / "password_template.html"


def main():
    password = os.environ.get("STATICRYPT_PASSWORD")
    if not password:
        raise SystemExit("Set STATICRYPT_PASSWORD in the environment before running this script.")
    if not BUILD.exists():
        raise SystemExit("build/ doesn't exist - run scripts/build.py first.")

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [
                "npx",
                "--yes",
                "staticrypt",
                str(BUILD),
                "-r",
                "-d",
                tmp,
                "-p",
                password,
                "--short",
                "--remember",
                "30",
                "--template-title",
                "The Trip · 1976",
                "--template-instructions",
                "Family archive - ask Francis for the password.",
                "--template-color-primary",
                "#c1432a",
                "--template-color-secondary",
                "#17130f",
                "--template",
                str(TEMPLATE),
            ],
            check=True,
            cwd=ROOT,
        )
        # staticrypt nests output under a copy of the input dir's basename;
        # flatten that back out into docs/.
        nested = Path(tmp) / BUILD.name
        if DOCS.exists():
            shutil.rmtree(DOCS)
        shutil.move(str(nested), str(DOCS))

    print(f"wrote password-protected site to {DOCS}")


if __name__ == "__main__":
    main()
