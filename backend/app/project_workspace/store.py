"""Transactional, project-owned SQLite records and recoverable local lifecycle."""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import tempfile
import threading

from ..workflow_errors import WorkflowError
from .models import Message, Project, now, uid

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,127}$")
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock(path: Path) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(path.absolute()), threading.RLock())


def _regular_tree(path: Path):
    if path.is_symlink():
        raise WorkflowError("unsafe_project_path", "Project files cannot be symbolic links.", 422)
    if path.exists():
        for entry in path.rglob("*"):
            if entry.is_symlink() or (not entry.is_file() and not entry.is_dir()):
                raise WorkflowError("unsafe_project_path", "The project contains an unsupported linked or special file.", 422)


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


class ProjectStore:
    """One process owns a library; SQLite transactions protect concurrent jobs/tabs.

    The catalog is a rebuildable index. Project databases remain authoritative,
    including lifecycle metadata. Staged imports never appear in list results.
    """

    def __init__(self, root: Path):
        self.migration_errors: list[str] = []
        self.library_errors: list[str] = []
        self.root = Path(root).expanduser().absolute()
        if self.root.is_symlink():
            raise WorkflowError("unsafe_project_path", "Choose a regular local library folder.", 422)
        self.root.mkdir(parents=True, exist_ok=True)
        self.projects = self.root / "projects"
        if self.projects.is_symlink():
            raise WorkflowError("unsafe_project_path", "The project folder cannot be a symbolic link.", 422)
        self.projects.mkdir(exist_ok=True)
        self.catalog_path = self.root / "library.sqlite3"
        if self.catalog_path.is_symlink():
            raise WorkflowError("unsafe_project_path", "The project catalog cannot be a symbolic link.", 422)
        with sqlite3.connect(self.catalog_path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, title TEXT NOT NULL, updated_at TEXT NOT NULL, trashed_at TEXT)")
        for project in self.list(include_trashed=True):
            # 1.8.1 retained failed messages but had no explicit turn identity.
            # Only the latest, unambiguously failed reply may gain a retry; a
            # completed or superseded historical request must never be replayed.
            latest_user = next((message for message in reversed(project.messages) if message.role == "user"), None)
            latest_reply = next((message for message in reversed(project.messages) if message.role == "assistant"), None)
            legacy_failed = (latest_user is not None and latest_reply is not None
                and latest_reply.status == "failed" and latest_reply.reply_to_message_id is None
                and project.messages.index(latest_reply) > project.messages.index(latest_user)
                and latest_user.id not in project.editor_drafts.get("conversation_turns", {})
                and not project.editor_drafts.get("conversation_requests"))
            if (any(job.status in {"queued", "running"} for job in project.jobs)
                    or any(resource.status == "processing" for resource in project.resources)
                    or project.editor_drafts.get("conversation_requests") or legacy_failed):
                def recover(state):
                    if legacy_failed:
                        user_id, reply_id = latest_user.id, latest_reply.id
                        reply = next(message for message in state.messages if message.id == reply_id)
                        reply.reply_to_message_id, reply.retryable = user_id, True
                        reply.diagnostics.update(outcome="failed", error_code="legacy_conversation_failure",
                                                 stage="upgrade_recovery", project_id=state.id, message_id=user_id)
                        state.editor_drafts.setdefault("conversation_turns", {})[user_id] = {
                            "status": "failed", "attempt_count": 1, "retryable": True,
                            "error_code": "legacy_conversation_failure"}
                    for job in state.jobs:
                        if job.status in {"queued", "running"}:
                            job.status = "failed"
                            job.progress = "Interrupted"
                            job.error = "The application stopped before this operation completed. Saved work is retained; retry explicitly."
                            job.error_code = "conversation_interrupted" if job.kind == "conversation" else "operation_interrupted"
                            job.updated_at = now()
                    for resource in state.resources:
                        if resource.status == "processing":
                            resource.status = "partial" if resource.evidence or resource.blocks else "failed"
                            resource.error = "Processing was interrupted. Completed evidence is retained; retry explicitly."
                    requests = state.editor_drafts.pop("conversation_requests", {})
                    for message_id, request in requests.items():
                        turns = state.editor_drafts.setdefault("conversation_turns", {})
                        turns[message_id] = {"status": "failed", "attempt_count": request.get("attempt_count", 1),
                                             "retryable": True, "error_code": "conversation_interrupted"}
                        state.messages.append(Message(role="assistant", status="failed", retryable=True,
                            reply_to_message_id=message_id,
                            diagnostics={"outcome": "failed", "error_code": "conversation_interrupted",
                                         "stage": "application_restart", "timestamp": now(), "project_id": state.id,
                                         "message_id": message_id},
                            text="Assistance was interrupted when the application stopped. Your message and saved work are retained; retry explicitly."))
                self._update(project.id, None, recover, include_trashed=True)

    def project_dir(self, project_id: str) -> Path:
        if not isinstance(project_id, str) or not _ID.fullmatch(project_id):
            raise WorkflowError("invalid_project_id", "The project identifier is invalid.", 422)
        path = self.projects / project_id
        if path.is_symlink() or path.resolve().parent != self.projects.resolve():
            raise WorkflowError("unsafe_project_path", "The project location is outside this library.", 422)
        return path

    def resolve_path(self, project_id: str, relative: str) -> Path:
        """Resolve a project-relative file, rejecting traversal and symlink ancestors."""
        folder = self.project_dir(project_id)
        pure = PurePosixPath(relative)
        if not relative or "\\" in relative or pure.is_absolute() or any(part in {"..", "."} for part in relative.split("/")):
            raise WorkflowError("unsafe_project_path", "This file does not have a valid project-relative path.", 422)
        target = folder.joinpath(*pure.parts)
        for current in [target, *target.parents]:
            if current == folder:
                break
            if current.is_symlink():
                raise WorkflowError("unsafe_project_path", "Project files cannot be symbolic links.", 422)
        if not target.resolve().is_relative_to(folder.resolve()):
            raise WorkflowError("unsafe_project_path", "This file is outside its project.", 422)
        return target

    def _connect(self, project_id: str):
        path = self.project_dir(project_id) / "project.sqlite3"
        if path.is_symlink():
            raise WorkflowError("unsafe_project_path", "The project database cannot be a symbolic link.", 422)
        if not path.is_file():
            raise WorkflowError("project_not_found", "This project does not exist.", 404)
        db = sqlite3.connect(path, timeout=15)
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def _validate(self, project: Project) -> Project:
        project = Project.model_validate(project.model_dump(mode="json"))
        if not project.title.strip() or len(project.title) > 250:
            raise WorkflowError("invalid_project_title", "Use a project title between 1 and 250 characters.", 422)
        self.project_dir(project.id)
        for resource in project.resources:
            for relative in (resource.original_path, resource.thumbnail_path, resource.playback_path):
                if relative:
                    self.resolve_path(project.id, relative)
        return project

    def _catalog(self, project: Project):
        with sqlite3.connect(self.catalog_path, timeout=15) as db:
            db.execute("INSERT INTO projects VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,updated_at=excluded.updated_at,trashed_at=excluded.trashed_at",
                       (project.id, project.title, project.updated_at, project.trashed_at))

    def _manifest(self, folder: Path, project: Project):
        manifest = {"schema_version": project.schema_version, "id": project.id, "title": project.title,
                    "created_at": project.created_at, "updated_at": project.updated_at}
        destination = folder / "project.json"
        if destination.is_symlink():
            raise WorkflowError("unsafe_project_path", "The project manifest cannot be a symbolic link.", 422)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder, prefix=".manifest-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)

    def _initialize(self, folder: Path, project: Project):
        for relative in ("sources/documents", "sources/media", "sources/assets", "outputs", "evidence", "cache", "staging"):
            (folder / relative).mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(folder / "project.sqlite3") as db:
            db.execute("CREATE TABLE project (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)")
            db.execute("INSERT INTO project VALUES (?,?,?)", (project.id, project.version, project.model_dump_json()))
        self._manifest(folder, project)

    def create(self, title: str) -> Project:
        project = self._validate(Project(title=title.strip()))
        return self.import_project(project)

    def import_project(self, project: Project, prepare: Callable[[Path], None] | None = None) -> Project:
        """Publish a validated, fully prepared project atomically, without replacement."""
        project = self._validate(project)
        destination = self.project_dir(project.id)
        with _lock(destination):
            if destination.exists():
                raise WorkflowError("project_exists", "The destination project already exists; it was not overwritten.", 409)
            stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=self.projects))
            try:
                if prepare:
                    prepare(stage)
                _regular_tree(stage)
                self._initialize(stage, project)
                if destination.exists():
                    raise WorkflowError("project_exists", "The destination project appeared during import.", 409)
                stage.rename(destination)
                self._catalog(project)
                return project
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

    def get(self, project_id: str, *, include_trashed: bool = False) -> Project:
        try:
            with self._connect(project_id) as db:
                row = db.execute("SELECT payload FROM project WHERE id=?", (project_id,)).fetchone()
        except (sqlite3.Error, OSError) as error:
            raise WorkflowError("project_unreadable", "This project's database could not be read. Its files were left unchanged; restore a verified backup or inspect the project folder.", 409) from error
        if row is None:
            raise WorkflowError("project_not_found", "This project does not exist.", 404)
        try:
            project = self._validate(Project.model_validate_json(row[0]))
        except ValueError as error:
            raise WorkflowError("project_unreadable", "This project's saved record could not be validated. Its files were left unchanged; restore a verified backup or inspect the project folder.", 409) from error
        if project.id != project_id:
            raise WorkflowError("project_unreadable", "The saved project identity does not match its folder. Its files were left unchanged.", 409)
        if project.trashed_at and not include_trashed:
            raise WorkflowError("project_trashed", "This project is in Trash. Restore it before continuing.", 410)
        return project

    def list(self, *, include_trashed: bool = False) -> list[Project]:
        projects = []
        errors = []
        for folder in sorted(self.projects.iterdir()):
            if folder.name.startswith(".") or not _ID.fullmatch(folder.name):
                continue
            if folder.is_symlink():
                errors.append(f"{folder.name}: this project location is a symbolic link and was not opened. Its files were left unchanged.")
                continue
            if not folder.is_dir():
                continue
            if not (folder / "project.sqlite3").is_file():
                errors.append(f"{folder.name}: the project database is missing or unreadable. Its folder was left unchanged; restore a verified backup.")
                continue
            try:
                project = self.get(folder.name, include_trashed=True)
            except (WorkflowError, OSError, ValueError, sqlite3.Error):
                errors.append(f"{folder.name}: this project could not be read. Its files were left unchanged; restore a verified backup or inspect its folder. Other projects remain available.")
                continue
            try:
                self._catalog(project)
            except (OSError, sqlite3.Error):
                errors.append(f"{folder.name}: the project index could not be refreshed. Its saved project remains available.")
            if include_trashed or project.trashed_at is None:
                projects.append(project)
        self.library_errors = errors
        return sorted(projects, key=lambda item: item.updated_at, reverse=True)

    def update(self, project_id: str, expected_version: int | None, change: Callable[[Project], object]) -> Project:
        return self._update(project_id, expected_version, change)

    def _update(self, project_id, expected_version, change, *, include_trashed=False, lifecycle_action=None):
        folder = self.project_dir(project_id)
        with _lock(folder), self._connect(project_id) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM project WHERE id=?", (project_id,)).fetchone()
            if row is None:
                raise WorkflowError("project_not_found", "This project does not exist.", 404)
            project = Project.model_validate_json(row[0])
            if lifecycle_action:
                db.execute("CREATE TABLE IF NOT EXISTS lifecycle_retry (id INTEGER PRIMARY KEY CHECK(id=1), action TEXT NOT NULL, expected_version INTEGER NOT NULL, result_version INTEGER NOT NULL)")
            if project.trashed_at and not include_trashed:
                raise WorkflowError("project_trashed", "This project is in Trash. Restore it before continuing.", 410)
            if expected_version is not None and project.version != expected_version:
                if lifecycle_action:
                    previous = db.execute("SELECT action,expected_version,result_version FROM lifecycle_retry WHERE id=1").fetchone()
                    if previous == (lifecycle_action, expected_version, project.version):
                        return project
                raise WorkflowError("project_version_conflict", "This project changed. Reload the latest saved state and retry.", 409)
            before = project.model_dump_json()
            brief_before = [fact.model_dump(mode="json") for fact in project.brief_draft]
            brief_version = project.brief_draft_version
            editor_before = json.loads(before)["editor_drafts"]
            editor_versions = dict(project.editor_draft_versions)
            result = change(project)
            if project.id != project_id:
                raise WorkflowError("immutable_project_id", "Project identity cannot be changed.", 422)
            brief_changed = [fact.model_dump(mode="json") for fact in project.brief_draft] != brief_before
            # The store owns this concurrency channel. Unrelated job/workspace
            # mutations cannot make a saved brief draft look newer, and a
            # callback cannot forge/reset its revision counter.
            project.brief_draft_version = brief_version + int(brief_changed)
            editor_after = project.model_dump(mode="json")["editor_drafts"]
            absent = object()
            project.editor_draft_versions = editor_versions
            for scope in editor_before.keys() | editor_after.keys():
                if editor_before.get(scope, absent) != editor_after.get(scope, absent):
                    project.editor_draft_versions[scope] = editor_versions.get(scope, 0) + 1
            if result is not False and project.model_dump_json() != before:
                project.version += 1
                project.updated_at = now()
                project = self._validate(project)
                db.execute("UPDATE project SET version=?,payload=? WHERE id=?", (project.version, project.model_dump_json(), project_id))
                if lifecycle_action:
                    db.execute("INSERT INTO lifecycle_retry VALUES (1,?,?,?) ON CONFLICT(id) DO UPDATE SET action=excluded.action,expected_version=excluded.expected_version,result_version=excluded.result_version",
                               (lifecycle_action, expected_version, project.version))
            else:
                project = Project.model_validate_json(before)
            db.commit()
            self._manifest(folder, project)
            self._catalog(project)
            return project

    @staticmethod
    def _idle(project):
        if (any(job.status in {"queued", "running"} for job in project.jobs)
                or any(resource.status == "processing" for resource in project.resources)
                or project.editor_drafts.get("conversation_requests")):
            raise WorkflowError("project_busy", "Wait for this project's active processing before changing its lifecycle.", 409)

    def trash(self, project_id: str, expected_version: int) -> Project:
        def change(project):
            if project.trashed_at:
                return False
            self._idle(project)
            project.trashed_at = now()
        return self._update(project_id, expected_version, change, include_trashed=True, lifecycle_action="trash")

    def restore(self, project_id: str, expected_version: int) -> Project:
        def change(project):
            if not project.trashed_at:
                return False
            project.trashed_at = None
        return self._update(project_id, expected_version, change, include_trashed=True, lifecycle_action="restore")

    def duplicate(self, project_id: str, expected_version: int) -> Project:
        source = self.project_dir(project_id)
        with _lock(source), self._connect(project_id) as db:
            db.execute("BEGIN IMMEDIATE")
            project = self.get(project_id)
            if project.version != expected_version:
                raise WorkflowError("project_version_conflict", "This project changed. Reload before duplicating it.", 409)
            self._idle(project)
            for resource in project.resources:
                original = self.resolve_path(project_id, resource.original_path)
                if not original.is_file() or (resource.sha256 and _digest(original) != resource.sha256):
                    raise WorkflowError("duplicate_missing_source", "Restore missing or changed originals before duplicating this project.", 409)
            copied = project.model_copy(deep=True)
            copied.id, copied.version = uid("project"), 1
            copied.title = f"{project.title[:243]} (copy)"
            copied.duplicated_from = project.id
            copied.legacy_task_id = None
            copied.created_at = copied.updated_at = now()
            copied.trashed_at = None
            copied.jobs = []
            copied.editor_drafts.pop("conversation_requests", None)
            for content in copied.contents:
                content.approved_direction_id = content.approved_direction_revision = None
                for direction in content.directions:
                    direction.approved = False
                    direction.approved_at = None
                    direction.needs_review = True
            for pack in copied.packs:
                pack.needs_review = True
            for resource in copied.resources:
                resource.thumbnail_path = None
                if resource.playback_path and resource.playback_path.startswith("cache/"):
                    resource.playback_path = None

            def prepare(stage):
                for name in ("sources", "outputs", "evidence", "legacy"):
                    origin = source / name
                    if origin.exists():
                        _regular_tree(origin)
                        shutil.copytree(origin, stage / name)
                evidence = stage / "evidence"
                evidence.mkdir(exist_ok=True)
                (evidence / "duplicated-project-snapshot.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")
                for resource in copied.resources:
                    if resource.sha256 and _digest(stage / resource.original_path) != resource.sha256:
                        raise WorkflowError("duplicate_source_changed", "A source changed while copying. The duplicate was not published.", 409)
            return self.import_project(copied, prepare)

    def clear_cache(self, project_id: str, expected_version: int | None = None) -> Project:
        folder = self.project_dir(project_id)
        with _lock(folder):
            def clear(project):
                self._idle(project)
                cache = folder / "cache"
                _regular_tree(cache)
                if cache.exists():
                    shutil.rmtree(cache)
                cache.mkdir()
                for resource in project.resources:
                    resource.thumbnail_path = None
                    if resource.playback_path and resource.playback_path.startswith("cache/"):
                        resource.playback_path = None
            return self.update(project_id, expected_version, clear)

    def migrate_legacy(self, legacy_service) -> list[Project]:
        from .migration import migrate_legacy
        return migrate_legacy(self, legacy_service)
