"""Reversible project organization, without deleting source media or saved work."""
from __future__ import annotations

from collections import Counter
import threading
from typing import Annotated

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .models import Nonempty, TaskState


class ProjectMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Annotated[int, Field(ge=1)]


class RenameProject(ProjectMutation):
    title: Nonempty


def install_project_api(app, workflow):
    router = APIRouter(tags=["Projects"])
    gate, active, trashing = threading.Lock(), Counter(), set()

    @app.middleware("http")
    async def project_activity(request: Request, call_next):
        # A synchronous upload, assistance or generation may not yet have a job
        # record. Reserve its task until the response completes. Persisted jobs
        # protect queued/background work after the submitting request returns.
        parts = request.url.path.strip("/").split("/")
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or len(parts) < 3 or parts[:2] != ["api", "tasks"]:
            return await call_next(request)
        task_id = parts[2]
        is_trash = parts[3:] == ["trash"]
        with gate:
            if task_id in trashing or (is_trash and active[task_id]):
                return JSONResponse(status_code=409, content={"error": {
                    "code": "task_busy", "message": "Wait for this project's current work to finish before moving it to Trash.", "retryable": True}})
            if is_trash:
                trashing.add(task_id)
            else:
                active[task_id] += 1
        try:
            return await call_next(request)
        finally:
            with gate:
                if is_trash:
                    trashing.discard(task_id)
                else:
                    active[task_id] -= 1
                    if not active[task_id]:
                        del active[task_id]

    @router.get("/api/trash/tasks", response_model=list[TaskState])
    def list_trash():
        return workflow.store.list_trash()

    @router.post("/api/tasks/{task_id}/rename", response_model=TaskState)
    def rename(task_id: str, body: RenameProject):
        return workflow.store.rename(task_id, body.expected_version, body.title)

    @router.post("/api/tasks/{task_id}/trash", response_model=TaskState)
    def trash(task_id: str, body: ProjectMutation):
        return workflow.store.set_trashed(task_id, body.expected_version, True)

    @router.post("/api/tasks/{task_id}/restore", response_model=TaskState)
    def restore(task_id: str, body: ProjectMutation):
        return workflow.store.set_trashed(task_id, body.expected_version, False)

    app.include_router(router)
