"""Separate durable Structure runs/history; never mutates the task aggregate."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from .structure_models import Workspace, Handoff, StructureError, timestamp
from .workflow_errors import WorkflowError


class StructureStore:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS structure_runs (
                structure_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, video_id TEXT NOT NULL,
                analysis_id TEXT NOT NULL, analysis_revision INTEGER NOT NULL,
                version INTEGER NOT NULL, payload TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS structure_task ON structure_runs(task_id)")
            db.execute("""CREATE TABLE IF NOT EXISTS structure_history (
                structure_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(structure_id, version))""")
            db.execute("""CREATE TABLE IF NOT EXISTS structure_handoffs (
                handoff_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, payload TEXT NOT NULL)""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def create(self, workspace: Workspace) -> Workspace:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT payload FROM structure_runs WHERE task_id=?", (workspace.task_id,)).fetchall()
            if any(Workspace.model_validate_json(row[0]).status in ("analyzing", "researching") for row in rows):
                raise WorkflowError("structure_busy", "Structure analysis is already running for this task.")
            db.execute("INSERT INTO structure_runs VALUES (?,?,?,?,?,?,?)", (
                workspace.structure_id, workspace.task_id, workspace.video_id, workspace.analysis_ref.id,
                workspace.analysis_ref.revision, workspace.version, workspace.model_dump_json()))
            db.execute("INSERT INTO structure_history VALUES (?,?,?)", (workspace.structure_id, workspace.version, workspace.model_dump_json()))
        return workspace

    def latest(self, task_id: str) -> Workspace | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM structure_runs WHERE task_id=? ORDER BY rowid DESC LIMIT 1", (task_id,)).fetchone()
        return Workspace.model_validate_json(row[0]) if row else None

    def get(self, structure_id: str) -> Workspace:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM structure_runs WHERE structure_id=?", (structure_id,)).fetchone()
        if not row:
            raise WorkflowError("structure_not_found", "This Structure analysis does not exist.", 404)
        return Workspace.model_validate_json(row[0])

    def update(self, structure_id: str, change: Callable, expected_version: int | None = None) -> Workspace:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM structure_runs WHERE structure_id=?", (structure_id,)).fetchone()
            if not row:
                raise WorkflowError("structure_not_found", "This Structure analysis does not exist.", 404)
            item = Workspace.model_validate_json(row[0])
            if expected_version is not None and expected_version != item.version:
                raise WorkflowError("structure_version_conflict", "Structure changed. Refresh it before applying this action.")
            change(item)
            item.version += 1
            item.updated_at = timestamp()
            item = Workspace.model_validate(item.model_dump())
            db.execute("UPDATE structure_runs SET version=?,payload=? WHERE structure_id=?", (item.version, item.model_dump_json(), structure_id))
            db.execute("INSERT INTO structure_history VALUES (?,?,?)", (structure_id, item.version, item.model_dump_json()))
        return item

    def recover(self):
        with self.connect() as db:
            rows = db.execute("SELECT structure_id,payload FROM structure_runs").fetchall()
        for structure_id, payload in rows:
            item = Workspace.model_validate_json(payload)
            if item.status in ("analyzing", "researching") or item.feedback_status == "running":
                def close(workspace):
                    workspace.status = "partial" if workspace.graph else "failed"
                    workspace.feedback_status = "idle"
                    workspace.error = StructureError(code="interrupted_structure", message="Processing stopped when the application closed. Completed analysis is retained.")
                self.update(structure_id, close)

    def save_handoff(self, handoff: Handoff):
        with self.connect() as db:
            db.execute("INSERT INTO structure_handoffs VALUES (?,?,?)", (handoff.handoff_id, handoff.task_id, handoff.model_dump_json()))
        return handoff

    def get_handoff(self, handoff_id: str, task_id: str | None = None) -> Handoff | None:
        """Read an immutable selected snapshot; callers must check task ownership."""
        with self.connect() as db:
            row = db.execute("SELECT task_id,payload FROM structure_handoffs WHERE handoff_id=?", (handoff_id,)).fetchone()
        if row is None or (task_id is not None and row[0] != task_id):
            return None
        return Handoff.model_validate_json(row[1])

    def latest_handoff(self, task_id: str) -> Handoff | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM structure_handoffs WHERE task_id=? ORDER BY rowid DESC LIMIT 1", (task_id,)).fetchone()
        return Handoff.model_validate_json(row[0]) if row else None
