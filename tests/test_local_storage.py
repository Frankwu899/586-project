"""Library upgrades retain edits, originals and paid results without replacing data."""
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import local_storage as storage


def legacy_library(path):
    path.mkdir()
    with sqlite3.connect(path / "tasks.sqlite3") as db:
        db.execute("CREATE TABLE tasks (id TEXT, payload TEXT)")
        db.execute("INSERT INTO tasks VALUES ('task-1', '{\"edited\": true}')")
        db.execute("CREATE TABLE editor_drafts (scope TEXT, payload TEXT)")
        db.execute("INSERT INTO editor_drafts VALUES ('production', 'unsent draft')")
    (path / "media").mkdir()
    (path / "media" / "original.mp4").write_bytes(b"retained original media")
    (path / "provider-cache").mkdir()
    (path / "provider-cache" / "paid.json").write_text('{"paid_result": true}')
    return path


def test_platform_roots_are_outside_installation(tmp_path, monkeypatch):
    for name in ("VIDEO_ANATOMY_DATA_DIR", "VIDEO_ANATOMY_CACHE_DIR", "XDG_DATA_HOME", "XDG_CACHE_HOME", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)
    assert storage.default_data_dir(platform="darwin", home=tmp_path) == tmp_path / "Library/Application Support/Video Anatomy"
    assert storage.default_cache_dir(platform="darwin", home=tmp_path) == tmp_path / "Library/Caches/Video Anatomy"
    assert storage.default_data_dir(platform="linux", home=tmp_path) == tmp_path / ".local/share/video-anatomy"
    assert storage.default_data_dir(platform="win32", home=tmp_path) == tmp_path / "AppData/Local/Video Anatomy"


def test_migration_copies_verified_drafts_and_paid_results_and_retains_source(tmp_path):
    old = legacy_library(tmp_path / "old")
    new = tmp_path / "new"
    original = {p.relative_to(old): p.read_bytes() for p in old.rglob("*") if p.is_file()}
    with storage.library_lock(new):
        receipt = storage.prepare_library(new, old)
    assert receipt["status"] == "copied_and_verified"
    assert receipt["source_retained"]
    with sqlite3.connect(new / "tasks.sqlite3") as db:
        assert db.execute("SELECT * FROM editor_drafts").fetchall() == [("production", "unsent draft")]
    assert (new / "media/original.mp4").read_bytes() == original[Path("media/original.mp4")]
    assert json.loads((new / "provider-cache/paid.json").read_text())["paid_result"]
    assert all((old / name).read_bytes() == contents for name, contents in original.items())
    assert not list(tmp_path.glob(".new-import-*"))


def test_existing_store_never_merges_or_overwrites(tmp_path):
    old = legacy_library(tmp_path / "old")
    new = legacy_library(tmp_path / "new")
    (new / "media/original.mp4").write_bytes(b"new library edits")
    with storage.library_lock(new):
        assert storage.prepare_library(new, old)["status"] == "existing_library_preserved"
        with pytest.raises(ValueError, match="already exists"):
            storage.prepare_library(new, old, explicit_import=True)
    assert (new / "media/original.mp4").read_bytes() == b"new library edits"


def test_failed_copy_rolls_back_only_staging_and_keeps_source(tmp_path, monkeypatch):
    old = legacy_library(tmp_path / "old")
    new = tmp_path / "new"
    def corrupt_copy(source, target):
        Path(target).write_bytes(b"incorrect copied bytes")
    monkeypatch.setattr(storage.shutil, "copy2", corrupt_copy)
    with pytest.raises(ValueError, match="changed during import"):
        storage.migrate_library(old, new)
    assert not new.exists()
    assert (old / "media/original.mp4").read_bytes() == b"retained original media"
    assert not list(tmp_path.glob(".new-import-*"))


def test_symlinks_do_not_escape_the_library(tmp_path):
    old = legacy_library(tmp_path / "old")
    outside = tmp_path / "outside"
    outside.write_text("do not import")
    (old / "linked-file").symlink_to(outside)
    with pytest.raises(ValueError, match="symbolic link"):
        storage.migrate_library(old, tmp_path / "new")
    assert not (tmp_path / "new").exists()
    assert outside.read_text() == "do not import"


def test_same_library_is_noop_and_nested_destination_is_rejected(tmp_path):
    old = legacy_library(tmp_path / "old")
    assert storage.migrate_library(old, old)["status"] == "same_library"
    with pytest.raises(ValueError, match="separate folders"):
        storage.migrate_library(old, old / "new")


def test_active_library_lock_rejects_second_process_and_releases(tmp_path):
    target = tmp_path / "library"
    with storage.library_lock(target):
        with pytest.raises(ValueError, match="already open"):
            with storage.library_lock(target):
                pass
    with storage.library_lock(target):
        pass


def test_backup_includes_committed_wal_content(tmp_path):
    old = legacy_library(tmp_path / "old")
    with sqlite3.connect(old / "tasks.sqlite3") as active_db:
        active_db.execute("PRAGMA journal_mode=WAL")
        active_db.execute("INSERT INTO editor_drafts VALUES ('ideas', 'latest saved draft')")
        active_db.commit()
        storage.migrate_library(old, tmp_path / "new")
    with sqlite3.connect(tmp_path / "new/tasks.sqlite3") as copied:
        assert copied.execute("SELECT payload FROM editor_drafts WHERE scope='ideas'").fetchone() == ("latest saved draft",)


def test_missing_explicit_source_is_not_an_empty_success(tmp_path):
    with pytest.raises(ValueError, match="no tasks.sqlite3"):
        storage.prepare_library(tmp_path / "new", tmp_path / "missing", explicit_import=True)
    assert not (tmp_path / "new").exists()
