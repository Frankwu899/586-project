"""Small transactional storage boundary; one validated task aggregate per row."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Callable

from .frame_migration import migrate_v02_task
from .contract_migration import migrate_v03_task
from .models import TaskState, validate_state
from .m2_migration import migrate_v04_task
from .m2_storage import M2StoreMixin
from .workflow_errors import WorkflowError


class TaskStore(M2StoreMixin):
    def __init__(self, root: Path):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self.media_root = root / "media"
        self.path = root / "tasks.sqlite3"
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS task_migration_archive (
                task_id TEXT NOT NULL, source_schema_version TEXT NOT NULL,
                target_schema_version TEXT NOT NULL, original_task_version INTEGER NOT NULL,
                migrated_task_version INTEGER NOT NULL, original_payload TEXT NOT NULL,
                original_sha256 TEXT NOT NULL, migrated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, source_schema_version, original_sha256))""")
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS m2_drafts (task_id TEXT PRIMARY KEY REFERENCES tasks(id), version INTEGER NOT NULL, payload TEXT NOT NULL, last_apply_request TEXT)")
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
        if source_version not in ("0.2.0", "0.3.0", "0.4.0"):
            return validate_state(TaskState.model_validate(data))
        state = (migrate_v02_task(data, self.media_root) if source_version == "0.2.0"
                 else migrate_v03_task(data) if source_version == "0.3.0" else migrate_v04_task(data))
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

    def get(self, task_id: str) -> TaskState:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise WorkflowError("task_not_found", "This task does not exist.", 404)
            return self._read_state(db, task_id, row[0])

    def list(self) -> list[TaskState]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT id, payload FROM tasks ORDER BY rowid DESC").fetchall()
            return [self._read_state(db, task_id, payload) for task_id, payload in rows]

    def update(self, task_id: str, expected_version: int | None, change: Callable[[TaskState], None], *, require_m2_ready: bool = False, preserve_m2_inputs: bool = False) -> TaskState:
        """Lock, compare, validate and commit together; callers never mutate stored objects."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT version, payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise WorkflowError("task_not_found", "This task does not exist.", 404)
            state = self._read_state(db, task_id, row[1])
            if expected_version is not None and state.task.version != expected_version:
                raise WorkflowError("version_conflict", "This task changed. Reopen it and retry your edit.")
            if require_m2_ready:
                self._require_m2_ready(db, state)
            preserve_partial = preserve_m2_inputs and state.task.current_brief is None and self._m2_draft(db, state).has_pending_inputs
            existing_briefs = len(state.briefs)
            change(state)
            if preserve_partial and state.task.mode == "sample":
                # Sample media remains available, but a sample brief must not
                # become formal input over a concurrently edited partial draft.
                del state.briefs[existing_briefs:]
                state.task.current_brief = None
            state.task.version += 1
            state = validate_state(state)
            db.execute("UPDATE tasks SET version = ?, payload = ? WHERE id = ?", (state.task.version, state.model_dump_json(), task_id))
        return state
