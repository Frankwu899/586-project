"""Integrity failures must be caught before an extracted release is executed."""
import hashlib
import json
from pathlib import PurePosixPath
import subprocess
import zipfile

import pytest

from backend.app.release import VERSION
from scripts import package_demo
from scripts.check_release_package import verify_archive
from scripts.mac_app_bundle import bundle_entries


def package(tmp_path, *, extra=None, corrupt=None, omit=None, manifest_commit=None,
            manifest_clean=True, mac=False, omit_wrapper=None, corrupt_readme=False,
            launcher_mode=0o755, corrupt_launcher=False):
    root = "Video Anatomy.app/Contents/Resources/app" if mac else "video-anatomy-local"
    commit = "a" * 40
    files = {name: b"synthetic package fixture" for name in (
        "backend/app/release.py", "scripts/local_server.py", "scripts/start-local.sh",
        "scripts/mac_launcher.py", "requirements.lock", "frontend/dist/index.html", "MAC_APP.md",
        "LOCAL_API.md", f"docs/releases/{VERSION}.md", f"docs/handoff/project-workspace-{VERSION}.md",
        "skills/video-anatomy-professional-generation/SKILL.md",
        *[f"skills/video-anatomy-professional-generation/references/{name}.md"
          for name in ("PROFESSIONAL_METHOD", "EDITORIAL", "QUALITY", "IDEAS", "STORYBOARD", "STRUCTURE")],
    )}
    if omit:
        del files[omit]
    manifest = {"application_version": VERSION, "source_commit": manifest_commit or commit,
                "source_tree_clean": manifest_clean, "private_reference_included": False,
                "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
                "wrapper_files": {}}
    archive_path = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, content in files.items():
            archive.writestr(str(PurePosixPath(root) / name), b"tampered" if name == corrupt else content)
        if mac:
            for relative, (content, mode) in bundle_entries().items():
                name = "Video Anatomy.app/" + relative
                manifest["wrapper_files"][name] = hashlib.sha256(content).hexdigest()
                if name == omit_wrapper:
                    continue
                entry = zipfile.ZipInfo(name)
                entry.create_system = 3
                if relative == "Contents/MacOS/VideoAnatomy":
                    mode = launcher_mode
                    if corrupt_launcher:
                        content = b"#!/bin/bash\necho 'Synthetic changed wrapper'\n"
                entry.external_attr = (0o100000 | mode) << 16
                archive.writestr(entry, content)
            if omit_wrapper != "README.txt":
                archive.writestr("README.txt", b"tampered" if corrupt_readme else files["MAC_APP.md"])
            manifest["wrapper_files"]["README.txt"] = hashlib.sha256(files["MAC_APP.md"]).hexdigest()
        archive.writestr(f"{root}/PACKAGE_MANIFEST.json", json.dumps(manifest))
        if extra:
            archive.writestr(*extra)
    return archive_path


def test_complete_manifest_verifies_hashes_and_exact_source(tmp_path):
    result = verify_archive(package(tmp_path), VERSION, "a" * 40)
    assert result["files_verified"] == 17
    assert result["source_commit"] == "a" * 40
    assert result["source_tree_clean"] is True


def test_rejects_tampered_payload_before_smoke(tmp_path):
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_archive(package(tmp_path, corrupt="backend/app/release.py"), VERSION)


def test_rejects_unmanifested_application_file(tmp_path):
    with pytest.raises(ValueError, match="unmanifested"):
        verify_archive(package(tmp_path, extra=("video-anatomy-local/injected.py", b"untracked")), VERSION)


@pytest.mark.parametrize("name", ["../escaped.txt", "video-anatomy-local/.env",
                                  "video-anatomy-local/projects/library.sqlite3",
                                  "video-anatomy-local/private.wav", "video-anatomy-local/private.m4v"])
def test_rejects_unsafe_or_private_files(tmp_path, name):
    with pytest.raises(ValueError, match="unsafe path|excluded private/runtime"):
        verify_archive(package(tmp_path, extra=(name, b"private fixture")), VERSION)


def test_rejects_possible_key_without_printing_it(tmp_path):
    credential = b"sk-" + b"synthetic" * 8
    with pytest.raises(ValueError, match="possible credential") as failure:
        verify_archive(package(tmp_path, extra=("video-anatomy-local/config.txt", credential)), VERSION)
    assert credential.decode() not in str(failure.value)


def test_runtime_instructions_are_mandatory(tmp_path):
    with pytest.raises(ValueError, match="Missing runtime files"):
        verify_archive(package(tmp_path, omit="skills/video-anatomy-professional-generation/references/IDEAS.md"), VERSION)


def test_commit_must_match_the_delivered_build(tmp_path):
    with pytest.raises(ValueError, match="expected commit"):
        verify_archive(package(tmp_path), VERSION, "b" * 40)


@pytest.mark.parametrize("clean", [False, None, "true"])
def test_development_snapshot_is_not_a_reviewed_team_package(tmp_path, clean):
    with pytest.raises(ValueError, match="verified clean source tree"):
        verify_archive(package(tmp_path, manifest_clean=clean), VERSION)


def test_mac_bundle_opens_as_exactly_readme_and_app_with_notes_inside(tmp_path):
    archive = package(tmp_path, mac=True)
    report = verify_archive(archive, VERSION, "a" * 40)
    assert report["variant"] == "mac-launcher"
    with zipfile.ZipFile(archive) as opened:
        assert {PurePosixPath(name).parts[0] for name in opened.namelist()} == {"README.txt", "Video Anatomy.app"}
        assert f"Video Anatomy.app/Contents/Resources/app/docs/releases/{VERSION}.md" in opened.namelist()


@pytest.mark.parametrize("extra", ["RELEASE NOTES.md", "READ ME FIRST.md", "extras/"])
def test_mac_rejects_any_third_top_level_item_including_empty_directory(tmp_path, extra):
    with pytest.raises(ValueError, match="only README.txt and Video Anatomy.app"):
        verify_archive(package(tmp_path, mac=True, extra=(extra, b"")), VERSION)


def test_mac_requires_the_readme(tmp_path):
    with pytest.raises(ValueError, match="only README.txt and Video Anatomy.app"):
        verify_archive(package(tmp_path, mac=True, omit_wrapper="README.txt"), VERSION)


def test_mac_readme_must_match_the_manifested_instructions(tmp_path):
    with pytest.raises(ValueError, match="launch instructions differ"):
        verify_archive(package(tmp_path, mac=True, corrupt_readme=True), VERSION)


def test_mac_wrapper_must_retain_executable_permission(tmp_path):
    with pytest.raises(ValueError, match="not executable"):
        verify_archive(package(tmp_path, mac=True, launcher_mode=0o644), VERSION)


def test_mac_wrapper_bytes_are_hashed_as_well_as_payload(tmp_path):
    with pytest.raises(ValueError, match="Wrapper hash mismatch"):
        verify_archive(package(tmp_path, mac=True, corrupt_launcher=True), VERSION)


@pytest.fixture
def source_checkout(tmp_path, monkeypatch):
    """Exercise provenance in a disposable repo, without committing the real worktree."""
    root = tmp_path / "source"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "--initial-branch=package-fixture"], cwd=root, check=True)
    (root / "source.py").write_text("# Synthetic committed packaging input.\n")
    (root / ".gitignore").write_text("dist/\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Package fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "Synthetic packaging provenance fixture"], cwd=root, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    built = root / "frontend/dist"
    built.mkdir(parents=True)
    (built / "index.html").write_text("<!doctype html><title>Synthetic package UI</title>")
    monkeypatch.setattr(package_demo, "ROOT", root)
    return root, commit


def test_reviewed_commit_requires_exact_full_sha_and_clean_tree(source_checkout):
    _, commit = source_checkout
    assert package_demo.source_identity(commit) == (commit, True)
    with pytest.raises(ValueError, match="full 40-character"):
        package_demo.source_identity(commit[:7])
    with pytest.raises(ValueError, match="differs"):
        package_demo.source_identity("0" * 40)


@pytest.mark.parametrize("change", ["unstaged", "staged", "untracked"])
def test_rejects_uncommitted_input_before_packaging(source_checkout, change):
    root, commit = source_checkout
    if change == "untracked":
        (root / "new-source.py").write_text("# Unreviewed synthetic input.\n")
    else:
        (root / "source.py").write_text("# Changed synthetic input.\n")
        if change == "staged":
            subprocess.run(["git", "add", "source.py"], cwd=root, check=True)
    with pytest.raises(ValueError, match="clean working tree"):
        package_demo.source_identity(commit)
    assert package_demo.source_identity(include_working_tree=True) == (commit, False)


def test_mac_packager_requires_a_reviewed_commit(source_checkout, tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["package_demo.py", str(tmp_path / "candidate.zip"), "--mac-app"])
    with pytest.raises(SystemExit) as failure:
        package_demo.main()
    assert failure.value.code == 2
    assert not (tmp_path / "candidate.zip").exists()


def test_packager_refuses_dirty_source_without_creating_archive(source_checkout, tmp_path, monkeypatch):
    root, commit = source_checkout
    (root / "source.py").write_text("# Changed after reviewed commit.\n")
    output = tmp_path / "candidate.zip"
    monkeypatch.setattr("sys.argv", ["package_demo.py", str(output), "--mac-app", "--expected-commit", commit])
    with pytest.raises(SystemExit) as failure:
        package_demo.main()
    assert failure.value.code == 2
    assert not output.exists()


def test_changes_during_packaging_do_not_replace_previous_output(source_checkout, tmp_path, monkeypatch):
    root, commit = source_checkout
    output = tmp_path / "candidate.zip"
    output.write_bytes(b"Previous synthetic output must survive failure.")
    monkeypatch.setattr("sys.argv", ["package_demo.py", str(output), "--local-api", "--expected-commit", commit])
    distribute = package_demo.distributable

    def change_source(path, *, local_api):
        (root / "source.py").write_text("# Changed during packaging.\n")
        return distribute(path, local_api=local_api)

    monkeypatch.setattr(package_demo, "distributable", change_source)
    with pytest.raises(SystemExit) as failure:
        package_demo.main()
    assert failure.value.code == 2
    assert output.read_bytes() == b"Previous synthetic output must survive failure."
    assert not list(tmp_path.glob(".video-anatomy-package-*.tmp"))


def test_builder_packages_only_committed_payload_with_two_top_level_items(source_checkout, tmp_path, monkeypatch):
    root, _ = source_checkout
    inventory_dir = tmp_path / "inventory"
    inventory_dir.mkdir()
    with zipfile.ZipFile(package(inventory_dir)) as fixture:
        for entry in fixture.infolist():
            relative = PurePosixPath(entry.filename).relative_to("video-anatomy-local")
            if relative.name == "PACKAGE_MANIFEST.json":
                continue
            destination = root / str(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(fixture.read(entry))
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Package fixture", "-c", "user.email=fixture@example.invalid",
                    "commit", "-qm", "Synthetic complete package inputs"], cwd=root, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    output = tmp_path / "candidate.zip"
    monkeypatch.setattr("sys.argv", ["package_demo.py", str(output), "--mac-app", "--expected-commit", commit])
    package_demo.main()
    assert verify_archive(output, VERSION, commit)["source_tree_clean"] is True
    with zipfile.ZipFile(output) as archive:
        assert {PurePosixPath(name).parts[0] for name in archive.namelist()} == {"README.txt", "Video Anatomy.app"}
