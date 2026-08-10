#!/usr/bin/env python3
"""Verify release versions and the HACS archive layout."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "cover_control" / "manifest.json"
VERSION_FILE = ROOT / "version.txt"
ARCHIVE = ROOT / "cover_control.zip"


def version() -> str:
    """Return and validate the source-controlled release version."""

    manifest_version = json.loads(MANIFEST.read_text(encoding="utf-8")).get("version")
    file_version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not isinstance(manifest_version, str) or not manifest_version:
        raise SystemExit("manifest.json version is missing or invalid")
    if file_version != manifest_version:
        raise SystemExit(
            f"Version mismatch: version.txt={file_version}, "
            f"manifest.json={manifest_version}"
        )
    return manifest_version


def verify_tag(expected_version: str) -> None:
    """Check a tag ref when running for a published release."""

    ref_type = os.environ.get("GITHUB_REF_TYPE", "")
    ref_name = os.environ.get("GITHUB_REF_NAME", "")
    is_tag = ref_type == "tag" or os.environ.get("GITHUB_REF", "").startswith(
        "refs/tags/"
    )
    if is_tag and ref_name != expected_version:
        raise SystemExit(
            f"Tag/version mismatch: tag={ref_name}, expected={expected_version}"
        )


def verify_archive(expected_version: str) -> None:
    """Check that HACS can extract the integration directly from the archive."""

    if not ARCHIVE.is_file():
        raise SystemExit(f"{ARCHIVE.name} is missing")
    try:
        with ZipFile(ARCHIVE) as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names or "__init__.py" not in names:
                raise SystemExit(
                    "Archive root must contain manifest.json and __init__.py"
                )
            if any("__pycache__" in name or name.endswith(".pyc") for name in names):
                raise SystemExit("Archive contains Python cache files")
            archived_manifest = json.loads(archive.read("manifest.json"))
    except BadZipFile as error:
        raise SystemExit(f"Invalid release archive: {error}") from error

    if archived_manifest.get("version") != expected_version:
        raise SystemExit("Archive manifest version does not match version.txt")


def main() -> None:
    """Run source and optional archive verification."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", action="store_true", help="verify the ZIP")
    parser.add_argument("--skip-tag", action="store_true", help="skip tag validation")
    args = parser.parse_args()

    expected_version = version()
    if not args.skip_tag:
        verify_tag(expected_version)
    if args.archive:
        verify_archive(expected_version)
    print(f"Release verification passed: {expected_version}")


if __name__ == "__main__":
    main()
