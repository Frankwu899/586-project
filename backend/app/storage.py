"""Small transactional storage boundary; one validated task aggregate per row."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Callable

from .frame_migration import migrate_v02_task
from .contract_migration import migrate_v03_task
from .models import TaskState, utc_now, validate_state
from .m2_migration import migrate_v04_task
from .m2_storage import M2StoreMixin
from .editor_storage import EditorStoreMixin
from .workspace_migration import migrate_v05_task
from .workflow_errors import WorkflowError


class TaskStore(M2StoreMixin, EditorStoreMixin):
    def __init__(self, root: Path):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self.media_root = root / "media"
        self.path = root / "tasks.sqlite3"
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS task_lifecycle (
                task_id TEXT PRIMARY KEY REFERENCES tasks(id), trashed_at TEXT,
                last_action TEXT NOT NULL, last_expected_version INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS task_migration_archive (
                task_id TEXT NOT NULL, source_schema_version TEXT NOT NULL,
                target_schema_version TEXT NOT NULL, original_task_version INTEGER NOT NULL,
                migrated_task_version INTEGER NOT NULL, original_payload TEXT NOT NULL,
                original_sha256 TEXT NOT NULL, migrated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, source_schema_version, original_sha256))""")
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS m2_drafts (task_id TEXT PRIMARY KEY REFERENCES tasks(id), version INTEGER NOT NULL, payload TEXT NOT NULL, last_apply_request TEXT)")
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS editor_drafts (task_id TEXT NOT NULL REFERENCES tasks(id), scope TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(task_id,scope))")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for task_id, payload in db.execute("SELECT id, payload FROM tasks").fetchall():
                self._read_state(db, task_id, payload)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def _read_state(self, db: sqlite3.Connection, task_id: str, payload: str) -> TaskState:
        data = json.loads(payload)
        source_version = data.get("task", {}).get("schema_version")
        if source_version not in ("0.2.0", "0.3.0", "0.4.0", "0.5.0"):
            return validate_state(TaskState.model_validate(data))
        state = (migrate_v02_task(data, self.media_root) if source_version == "0.2.0"
                 else migrate_v03_task(data) if source_version == "0.3.0"
                 else migrate_v04_task(data) if source_version == "0.4.0" else migrate_v05_task(data))
        if state.task.task_id != task_id:
            raise ValueError("stored task identity does not match its payload")
        db.execute("""INSERT INTO task_migration_archive
            (task_id, source_schema_version, target_schema_version, original_task_version,
             migrated_task_version, original_payload, original_sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                   (task_id, source_version, state.task.schema_version, data["task"]["version"], state.task.version,
                    payload, hashlib.sha256(payload.encode()).hexdigest()))
        db.execute("UPDATE tasks SET version = ?, payload = ? WHERE id = ?",
                   (state.task.version, state.model_dump_json(), task_id))
        self._m2_draft(db, state)
        return state

    def create(self, state: TaskState) -> TaskState:
        state = validate_state(state)
        with self._connect() as db:
            db.execute("INSERT INTO tasks VALUES (?, ?, ?)", (state.task.task_id, state.task.version, state.model_dump_json()))
        return state

    def _require_active(self, db, task_id):
        if db.execute("SELECT 1 FROM task_lifecycle WHERE task_id=? AND trashed_at IS NOT NULL", (task_id,)).fetchone():
            raise WorkflowError("task_trashed", "This project is in Trash. Restore it before continuing.", 410)

    def _m2_state(self, db, task_id):
        # Draft writes have independent versions and bypass get/update. Check
        # their lifecycle inside the same transaction, including stale tabs.
        self._require_active(db, task_id)
        return super()._m2_state(db, task_id)

    def get(self, task_id: str, *, include_trashed: bool = False) -> TaskState:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not include_trashed:
                self._require_active(db, task_id)
            row = db.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise WorkflowError("task_not_found", "This task does not exist.", 404)
            return self._read_state(db, task_id, row[0])

    def list(self, *, include_trashed: bool = False) -> list[TaskState]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            condition = "" if include_trashed else "WHERE NOT EXISTS (SELECT 1 FROM task_lifecycle WHERE task_id=tasks.id AND trashed_at IS NOT NULL)"
            rows = db.execute(f"SELECT id, payload FROM tasks {condition} ORDER BY rowid DESC").fetchall()
            return [self._read_state(db, task_id, payload) for task_id, payload in rows]

    def list_trash(self) -> list[TaskState]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("""SELECT tasks.id, tasks.payload FROM tasks
                JOIN task_lifecycle ON task_lifecycle.task_id=tasks.id
                WHERE trashed_at IS NOT NULL ORDER BY trashed_at DESC, tasks.rowid DESC""").fetchall()
            return [self._read_state(db, task_id, payload) for task_id, payload in rows]

    def rename(self, task_id: str, expected_version: int, title: str) -> TaskState:
        def change(state):
            if state.task.title == title:
                return False
            state.task.title = title
            state.task.updated_at = utc_now()
        return self.update(task_id, expected_version, change)

    def _require_idle(self, db, state):
        busy = any(job.status in ("pending", "running") for job in state.jobs)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "background_operations" in tables:
            busy = busy or bool(db.execute("""SELECT 1 FROM background_operations
                WHERE task_id=? AND status IN ('queued','running') LIMIT 1""", (state.task.task_id,)).fetchone())
        if "structure_runs" in tables:
            for row in db.execute("SELECT payload FROM structure_runs WHERE task_id=?", (state.task.task_id,)):
                workspace = json.loads(row[0])
                busy = busy or workspace.get("status") in ("analyzing", "researching") or workspace.get("feedback_status") == "running"
        if busy:
            raise WorkflowError("task_busy", "Wait for this project's current work to finish before moving it to Trash.", retryable=True)

    def set_trashed(self, task_id: str, expected_version: int, trashed: bool) -> TaskState:
        """Reversible list membership only: never remove media, drafts or history."""
        action = "trash" if trashed else "restore"
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM tasks WHERE id=?", (task_id,)).fetchone()
            if row is None:
                raise WorkflowError("task_not_found", "This task does not exist.", 404)
            state = self._read_state(db, task_id, row[0])
            lifecycle = db.execute("SELECT trashed_at,last_action,last_expected_version FROM task_lifecycle WHERE task_id=?", (task_id,)).fetchone()
            currently_trashed = lifecycle is not None and lifecycle[0] is not None
            if state.task.version != expected_version:
                # An exact retry after a lost response must not toggle twice.
                if lifecycle and lifecycle[1:] == (action, expected_version) and currently_trashed == trashed and state.task.version == expected_version + 1:
                    return state
                raise WorkflowError("version_conflict", "This project changed. Reopen it and retry your action.")
            if currently_trashed == trashed:
                return state
            if trashed:
                self._require_idle(db, state)
            state.task.version += 1
            state.task.updated_at = utc_now()
            state = validate_state(state)
            db.execute("UPDATE tasks SET version=?,payload=? WHERE id=?", (state.task.version, state.model_dump_json(), task_id))
            db.execute("""INSERT INTO task_lifecycle VALUES (?,?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET trashed_at=excluded.trashed_at,
                last_action=excluded.last_action,last_expected_version=excluded.last_expected_version""",
                (task_id, state.task.updated_at.isoformat() if trashed else None, action, expected_version))
            return state

    def update(self, task_id: str, expected_version: int | None, change: Callable[[TaskState], None], *, require_m2_ready: bool = False, preserve_m2_inputs: bool = False, require_editors_clear=(), editor_checkpoint=None, capture_editor_versions=None, expected_editor_versions=None) -> TaskState:
        """Lock, compare, validate and commit together; callers never mutate stored objects."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_active(db, task_id)
            row = db.execute("SELECT version, payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise WorkflowError("task_not_found", "This task does not exist.", 404)
            state = self._read_state(db, task_id, row[1])
            if expected_version is not None and state.task.version != expected_version:
                raise WorkflowError("version_conflict", "This task changed. Reopen it and retry your edit.")
            if require_m2_ready:
                self._require_m2_ready(db, state)
            self._require_editors_clear(db, state, require_editors_clear, capture_editor_versions)
            if expected_editor_versions is not None:
                for scope, expected in expected_editor_versions.items():
                    if self._editor_draft(db, state, scope).draft_version != expected:
                        raise WorkflowError("editor_input_changed", "An editor draft changed while this operation ran. Its result was discarded; saved edits are intact.")
            checkpoint = self._editor_commit_before(db, state, *editor_checkpoint) if editor_checkpoint else None
            preserve_partial = preserve_m2_inputs and state.task.current_brief is None and self._m2_draft(db, state).has_pending_inputs
            existing_briefs = len(state.briefs)
            changed = change(state) is not False
            if preserve_partial and state.task.mode == "sample":
                # Sample media remains available, but a sample brief must not
                # become formal input over a concurrently edited partial draft.
                del state.briefs[existing_briefs:]
                state.task.current_brief = None
            if checkpoint is not None:
                self._editor_commit_after(db, state, checkpoint)
            if changed:
                state.task.version += 1
            state = validate_state(state)
            db.execute("UPDATE tasks SET version = ?, payload = ? WHERE id = ?", (state.task.version, state.model_dump_json(), task_id))
        return state
