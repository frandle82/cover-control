"""Tests for commit and release helper scripts."""

from __future__ import annotations

import json

import pytest

from scripts import set_version, validate_commit, verify_release


@pytest.mark.parametrize(
    "subject",
    [
        "feat: add adaptive positioning",
        "fix(config): preserve manual override",
        "feat!: change configuration schema",
        "feat(runtime)!: change shading behavior",
        "docs: document release workflow",
        "build: update release tooling",
        "Merge pull request #1 from example/branch",
    ],
)
def test_conventional_commit_subjects_are_accepted(subject):
    """Valid Conventional Commit subjects pass validation."""

    assert validate_commit.is_valid(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "update files",
        "Feat: add adaptive positioning",
        "fix: trailing period.",
        "fix(Config): uppercase scope",
        "fix: ",
    ],
)
def test_invalid_commit_subjects_are_rejected(subject):
    """Non-conforming commit subjects fail validation."""

    assert not validate_commit.is_valid(subject)


@pytest.mark.parametrize(
    ("version", "release_type"),
    [
        ("0.8.0", "draft"),
        ("1.0.0", "release"),
        ("1.0.0-rc.1", "prerelease"),
    ],
)
def test_release_versions_are_accepted(version, release_type):
    """Valid version and release-state combinations pass validation."""

    set_version.validate_version(version, release_type)


@pytest.mark.parametrize(
    ("version", "release_type"),
    [
        ("v1.0.0", "release"),
        ("1.0", "release"),
        ("1.0.0-rc.1", "release"),
        ("1.0.0", "prerelease"),
        ("1.0.0", "unsupported"),
    ],
)
def test_invalid_release_versions_are_rejected(version, release_type):
    """Invalid version and release-state combinations fail validation."""

    with pytest.raises(ValueError):
        set_version.validate_version(version, release_type)


def test_manifest_version_is_updated(tmp_path):
    """Only the manifest version changes during a release update."""

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"domain": "cover_control", "version": "0.7.6"}),
        encoding="utf-8",
    )

    set_version.update_manifest(manifest_path, "0.8.0")

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
        "domain": "cover_control",
        "version": "0.8.0",
    }


def test_release_version_comes_from_manifest(tmp_path, monkeypatch):
    """Release verification uses manifest.json as the single version source."""

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"version": "0.8.0"}', encoding="utf-8")
    monkeypatch.setattr(verify_release, "MANIFEST", manifest_path)

    assert verify_release.version() == "0.8.0"


def test_release_verification_rejects_invalid_manifest_version(tmp_path, monkeypatch):
    """Release verification rejects non-SemVer manifest versions."""

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"version": "v0.8.0"}', encoding="utf-8")
    monkeypatch.setattr(verify_release, "MANIFEST", manifest_path)

    with pytest.raises(SystemExit, match="version is missing or invalid"):
        verify_release.version()
