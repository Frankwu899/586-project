"""Stable local storage and verified, non-destructive imports of legacy bundles."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from uuid import uuid4

APP_NAME = "Video Anatomy"


def default_data_dir(*, platform: str | None = None, home: Path | None = None) -> Path:
    platform, home = platform or sys.platform, home or Path.home()
    configured = os.getenv("VIDEO_ANATOMY_DATA_DIR")
    if configured:
        return Path(configured).expanduser()
    if platform == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    if platform == "win32":
        return Path(os.getenv("LOCALAPPDATA", str(home / "AppData" / "Local"))) / APP_NAME
    return Path(os.getenv("XDG_DATA_HOME", str(home / ".local" / "share"))) / "video-anatomy"


def default_cache_dir(*, platform: str | None = None, home: Path | None = None) -> Path:
    platform, home = platform or sys.platform, home or Path.home()
    configured = os.getenv("VIDEO_ANATOMY_CACHE_DIR")
    if configured:
        return Path(configured).expanduser()
    if platform == "darwin":
        return home / "Library" / "Caches" / APP_NAME
    if platform == "win32":
        return Path(os.getenv("LOCALAPPDATA", str(home / "AppData" / "Local"))) / APP_NAME / "Cache"
    return Path(os.getenv("XDG_CACHE_HOME", str(home / ".cache"))) / "video-anatomy"


@contextmanager
def library_lock(data_dir: Path):
    """Hold one process per library; OS releases the lock after an unexpected exit."""
    data_dir = data_dir.expanduser().absolute()
    data_dir.parent.mkdir(parents=True, exist_ok=True)
    path = data_dir.parent / f".{data_dir.name}.lock"
    handle = path.open("a+b")
    try:
        try:
            if sys.platform == "win32":
                import msvcrt
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("This library is already open. Close the other Video Anatomy window or server first.") from exc
        yield
    finally:
        handle.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("The legacy library contains a symbolic link. Copy its files to a regular directory before importing.")
        if path.is_file() and path.name not in {"tasks.sqlite3", "tasks.sqlite3-wal", "tasks.sqlite3-shm", "tasks.sqlite3-journal"}:
            result[path.relative_to(root).as_posix()] = _sha256(path)
    return result


def migrate_library(source: Path, target: Path) -> dict:
    """Copy only into an absent target. Source survives success and every failure.

    Call while holding library_lock(target), with the old application stopped.
    SQLite backup includes WAL content, retains all tables, and is integrity-checked.
    Other files must have matching hashes before/after the copy. Installation of
    the fully checked staging folder is atomic within the destination filesystem.
    """
    source, target = source.expanduser().resolve(), target.expanduser().absolute()
    if source == target.resolve():
        return {"status": "same_library", "source": str(source)}
    if target.exists():
        raise ValueError("The destination library already exists. It was not changed. Use a new --data-dir to import another library.")
    if source in target.parents or target.resolve() in source.parents:
        raise ValueError("The source and destination libraries must be separate folders.")
    database = source / "tasks.sqlite3"
    if not database.is_file() or database.is_symlink():
        raise ValueError("No regular tasks.sqlite3 file was found in the legacy library.")
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}-import-", dir=target.parent))
    try:
        # No schema migration or user-state writes are made to the source.
        with sqlite3.connect(f"{database.as_uri()}?mode=rw", uri=True, timeout=2) as guard:
            guard.execute("BEGIN IMMEDIATE")
            before = _inventory(source)
            with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as read_db:
                with sqlite3.connect(stage / "tasks.sqlite3") as copied_db:
                    read_db.backup(copied_db)
                    if copied_db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                        raise ValueError("The copied database did not pass its integrity check. The old library is unchanged.")
                    if list(read_db.iterdump()) != list(copied_db.iterdump()):
                        raise ValueError("Database verification failed. The old library is unchanged.")
            for name, digest in before.items():
                destination = stage / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name, destination)
                if _sha256(destination) != digest:
                    raise ValueError("A file changed during import. Close the old application and retry.")
            if _inventory(source) != before:
                raise ValueError("The old library changed during import. Close the old application and retry.")
            receipt = {
                "status": "copied_and_verified", "source": str(source), "destination": str(target),
                "imported_at": datetime.now(timezone.utc).isoformat(), "source_retained": True,
                "file_sha256": before,
            }
            (stage / f"library-import-{uuid4().hex}.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            # Never replace an existing destination, including an empty folder.
            if target.exists():
                raise ValueError("The destination appeared during import; it was not overwritten.")
            stage.rename(target)
            return receipt
    except sqlite3.Error as exc:
        raise ValueError("The old database could not be copied safely. Stop the old application and retry; the source is unchanged.") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def prepare_library(target: Path, legacy: Path | None = None, *, explicit_import: bool = False) -> dict:
    target = target.expanduser().absolute()
    if legacy and (legacy.expanduser() / "tasks.sqlite3").is_file():
        if not target.exists() or explicit_import:
            return migrate_library(legacy, target)
        if legacy.expanduser().resolve() != target.resolve():
            return {"status": "existing_library_preserved", "legacy_source": str(legacy.resolve()),
                    "message": "An existing library is in use. The old bundle was not merged or deleted."}
    elif explicit_import:
        raise ValueError("The requested legacy folder has no tasks.sqlite3. Nothing was changed.")
    target.mkdir(parents=True, exist_ok=True)
    return {"status": "ready"}


def storage_info(data_dir: Path, cache_dir: Path, migration: dict | None = None) -> dict:
    # Originals, histories and paid result reuse remain persistent, even though
    # the historical directory is named provider-cache. There is no bulk-delete API.
    return {
        "data_dir": str(data_dir.resolve()), "derived_cache_dir": str(cache_dir.resolve()),
        "media_dir": str((data_dir / "media").resolve()),
        "provider_results_dir": str((data_dir / "provider-cache").resolve()),
        "storage_bytes": sum(p.stat().st_size for p in data_dir.rglob("*") if p.is_file() and not p.is_symlink()),
        "migration": migration or {"status": "ready"},
        "paid_results_are_persistent": True,
    }
