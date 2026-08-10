#!/usr/bin/env python3
"""Build the HACS release archive for Cover Control."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = ROOT / "custom_components" / "cover_control"
ARCHIVE = ROOT / "cover_control.zip"


def main() -> None:
    """Create an archive whose root is the integration directory."""

    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(INTEGRATION_DIR.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            archive.write(path, path.relative_to(INTEGRATION_DIR))

    print(f"Built {ARCHIVE.name}")


if __name__ == "__main__":
    main()
