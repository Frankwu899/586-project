"""Persisted HTTP operation tickets. Polling never replays a provider request."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
import threading
import uuid

from datetime import datetime, timezone
from .storage import WorkflowError


def now():
    return datetime.now(timezone.utc)


class BackgroundOperations:
    def __init__(self, store, execute):
        self.store, self.execute = store, execute
        self.pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="video-operation")
        self.slots = threading.BoundedSemaphore(8)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS background_operations
                (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, operation TEXT NOT NULL,
                 status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                 error TEXT)""")
            # A restarted process must not repeat requests which may have been billed.
            db.execute("UPDATE background_operations SET status='failed', updated_at=?, error=? WHERE status IN ('queued','running')",
                       (now().isoformat(), json.dumps({"code": "interrupted", "message": "The local server restarted. Saved work is retained; this operation was not replayed."})))

    def connect(self):
        return sqlite3.connect(self.store.path, timeout=15)

    def submit(self, task_id, operation, payload):
        self.store.get(task_id)
        if not self.slots.acquire(blocking=False):
            raise WorkflowError("queue_full", "The local worker is busy. Wait for an active operation to finish.", 409)
        ticket_id, timestamp = "op_" + uuid.uuid4().hex, now().isoformat()
        try:
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT 1 FROM background_operations WHERE task_id=? AND operation=? AND status IN ('queued','running')", (task_id, operation)).fetchone():
                    raise WorkflowError("operation_running", "This operation is already running. Follow its saved activity instead of starting it again.", 409)
                db.execute("INSERT INTO background_operations VALUES (?,?,?,?,?,?,NULL)",
                           (ticket_id, task_id, operation, "queued", timestamp, timestamp))
            self.pool.submit(self.run, ticket_id, task_id, operation, payload)
        except Exception:
            self.slots.release()
            raise
        return self.get(task_id, ticket_id)

    def update(self, ticket_id, status, error=None):
        with self.connect() as db:
            db.execute("UPDATE background_operations SET status=?,updated_at=?,error=? WHERE id=?",
                       (status, now().isoformat(), json.dumps(error) if error else None, ticket_id))

    def run(self, ticket_id, task_id, operation, payload):
        try:
            self.update(ticket_id, "running")
            prior = {job.job_id for job in self.store.get(task_id).jobs}
            result = self.execute(task_id, operation, payload)
            job_kind = "analyze" if operation == "recognize" else operation
            failed = next((job for job in reversed(getattr(result, "jobs", [])) if job.job_id not in prior and job.operation == job_kind and job.status == "failed"), None)
            if failed is not None:
                error = failed.error
                self.update(ticket_id, "failed", {"code": error.code if error else "operation_failed", "message": error.message if error else "The operation could not finish."})
                return
            self.update(ticket_id, "succeeded")
        except WorkflowError as error:
            self.update(ticket_id, "failed", {"code": error.code, "message": error.message})
        except Exception:
            self.update(ticket_id, "failed", {"code": "operation_failed", "message": "The operation could not finish. Your saved work is retained."})
        finally:
            self.slots.release()

    def get(self, task_id, ticket_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM background_operations WHERE id=? AND task_id=?", (ticket_id, task_id)).fetchone()
        if row is None:
            raise WorkflowError("operation_not_found", "This operation does not belong to the task.", 404)
        return dict(zip(("operation_id", "task_id", "operation", "status", "created_at", "updated_at"), row[:6]),
                    error=json.loads(row[6]) if row[6] else None,
                    result=self.store.get(task_id).model_dump(mode="json") if row[3] in ("succeeded", "failed") else None)

    def list(self, task_id):
        self.store.get(task_id)
        with self.connect() as db:
            ids = db.execute("SELECT id FROM background_operations WHERE task_id=? ORDER BY created_at DESC LIMIT 20", (task_id,)).fetchall()
        return {"operations": [self.get(task_id, row[0]) for row in ids]}
