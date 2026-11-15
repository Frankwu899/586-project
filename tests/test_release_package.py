"""Integrity failures must be caught before an extracted release is executed."""
import hashlib
import json
from pathlib import PurePosixPath
import zipfile

import pytest

from scripts.check_release_package import verify_archive


def package(tmp_path, *, extra=None, corrupt=None, omit=None, manifest_commit=None):
    root = "video-anatomy-local"
    version, commit = "1.8.2", "a" * 40
    files = {name: b"synthetic package fixture" for name in (
        "backend/app/release.py", "scripts/local_server.py", "scripts/start-local.sh",
        "scripts/mac_launcher.py", "requirements.lock", "frontend/dist/index.html", "MAC_APP.md",
        "LOCAL_API.md", "docs/releases/1.8.2.md", "docs/handoff/project-workspace-1.8.2.md",
        "skills/video-anatomy-professional-generation/SKILL.md",
        *[f"skills/video-anatomy-professional-generation/references/{name}.md"
          for name in ("PROFESSIONAL_METHOD", "EDITORIAL", "QUALITY", "IDEAS", "STORYBOARD", "STRUCTURE")],
    )}
    if omit:
        del files[omit]
    manifest = {"application_version": version, "source_commit": manifest_commit or commit,
                "private_reference_included": False,
                "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(str(PurePosixPath(root) / name), b"tampered" if name == corrupt else content)
        archive.writestr(f"{root}/PACKAGE_MANIFEST.json", json.dumps(manifest))
        if extra:
            archive.writestr(*extra)
    return archive_path


def test_complete_manifest_verifies_hashes_and_exact_source(tmp_path):
    result = verify_archive(package(tmp_path), "1.8.2", "a" * 40)
    assert result["files_verified"] == 17
    assert result["source_commit"] == "a" * 40


def test_rejects_tampered_payload_before_smoke(tmp_path):
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_archive(package(tmp_path, corrupt="backend/app/release.py"), "1.8.2")


def test_rejects_unmanifested_application_file(tmp_path):
    with pytest.raises(ValueError, match="unmanifested"):
        verify_archive(package(tmp_path, extra=("video-anatomy-local/injected.py", b"untracked")), "1.8.2")


@pytest.mark.parametrize("name", ["../escaped.txt", "video-anatomy-local/.env",
                                  "video-anatomy-local/projects/library.sqlite3",
                                  "video-anatomy-local/private.wav"])
def test_rejects_unsafe_or_private_files(tmp_path, name):
    with pytest.raises(ValueError, match="unsafe path|excluded private/runtime"):
        verify_archive(package(tmp_path, extra=(name, b"private fixture")), "1.8.2")


def test_rejects_possible_key_without_printing_it(tmp_path):
    credential = b"sk-" + b"synthetic" * 8
    with pytest.raises(ValueError, match="possible credential") as failure:
        verify_archive(package(tmp_path, extra=("video-anatomy-local/config.txt", credential)), "1.8.2")
    assert credential.decode() not in str(failure.value)


def test_runtime_instructions_are_mandatory(tmp_path):
    with pytest.raises(ValueError, match="Missing runtime files"):
        verify_archive(package(tmp_path, omit="skills/video-anatomy-professional-generation/references/IDEAS.md"), "1.8.2")


def test_commit_must_match_the_delivered_build(tmp_path):
    with pytest.raises(ValueError, match="expected commit"):
        verify_archive(package(tmp_path), "1.8.2", "b" * 40)
