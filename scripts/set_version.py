#!/usr/bin/env python3
"""Validate and update the Cover Control integration version."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

MANIFEST_PATH = Path("custom_components/cover_control/manifest.json")
VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
RELEASE_TYPES = ("draft", "prerelease", "release")


def validate_version(version: str, release_type: str) -> None:
    """Validate a requested version and release state."""

    if release_type not in RELEASE_TYPES:
        raise ValueError(f"unsupported release type: {release_type}")
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError("version must use SemVer without a leading 'v'")
    if release_type == "release" and match.group("prerelease"):
        raise ValueError("a final release cannot use a prerelease version")
    if release_type == "prerelease" and not match.group("prerelease"):
        raise ValueError(
            "a prerelease requires a suffix such as '-beta.1' or '-rc.1'"
        )


def update_manifest(path: Path, version: str) -> None:
    """Write the requested version to an integration manifest."""

    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = version
    path.write_text(
        f"{json.dumps(manifest, indent=2, ensure_ascii=False)}\n",
        encoding="utf-8",
    )


def main() -> int:
    """Validate the requested version and optionally write it to the manifest."""

    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument(
        "--release-type",
        choices=RELEASE_TYPES,
        default="draft",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate without updating manifest.json",
    )
    args = parser.parse_args()

    try:
        validate_version(args.version, args.release_type)
    except ValueError as error:
        parser.error(str(error))

    if not args.check:
        update_manifest(MANIFEST_PATH, args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
