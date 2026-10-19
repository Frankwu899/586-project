"""Project organization retains work and rejects stale or concurrent destruction."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.models import EditorDraftUpdate, M2DraftUpdate, ProcessingJob
from backend.app.project_api import install_project_api
from backend.app.service import WorkflowService
from backend.app.storage import TaskStore, WorkflowError
from test_workflow import outputs


def project_app(tmp_path):
    app = create_app(tmp_path)
    if not any(getattr(route, "path", None) == "/api/trash/tasks" for route in app.routes):
        install_project_api(app, app.state.service)
    return app


def test_trash_restore_preserves_media_history_editors_and_budget(tmp_path):
    service = WorkflowService(tmp_path)
    state = outputs(service)
    task_id = state.task.task_id
    m2 = service.store.get_m2_draft(task_id)
    m2 = service.store.save_m2_draft(task_id, M2DraftUpdate(
        expected_draft_version=m2.draft_version, fields=m2.fields,
        claims=m2.claims, source_notes="Unsaved project context"))
    idea = service.store.get_editor_draft(task_id, "idea")
    idea = service.store.save_editor_draft(task_id, "idea", EditorDraftUpdate(
        expected_draft_version=idea.draft_version, base_refs=idea.base_refs,
        content={**idea.content, "hook": "Keep this private draft"}))
    media = {p: p.read_bytes() for p in service.media.root.iterdir() if p.is_file()}
    assert media
    budget = tmp_path / "provider-budget.sqlite3"
    budget.write_bytes(b"independent persisted budget must not be reset")
    cache = tmp_path / "provider-cache/paid-result.json"
    cache.parent.mkdir(exist_ok=True)
    cache.write_text('{"completed":true}')

    trashed = service.store.set_trashed(task_id, state.task.version, True)
    assert trashed.task.version == state.task.version + 1
    assert not service.store.list()
    assert service.store.list(include_trashed=True) == [trashed]
    assert service.store.list_trash() == [trashed]
    with pytest.raises(WorkflowError) as missing:
        service.store.get(task_id)
    assert missing.value.code == "task_trashed" and missing.value.status == 410
    reopened = TaskStore(tmp_path)
    assert reopened.list_trash() == [trashed]
    restored = reopened.set_trashed(task_id, trashed.task.version, False)
    assert restored.task.version == trashed.task.version + 1
    assert restored.model_dump(exclude={"task"}) == state.model_dump(exclude={"task"})
    assert restored.task.model_dump(exclude={"version", "updated_at"}) == state.task.model_dump(exclude={"version", "updated_at"})
    assert reopened.get_m2_draft(task_id) == m2
    assert reopened.get_editor_draft(task_id, "idea") == idea
    assert not reopened.list_trash() and reopened.list() == [restored]
    assert all(path.read_bytes() == content for path, content in media.items())
    assert budget.read_bytes() == b"independent persisted budget must not be reset"
    assert cache.read_text() == '{"completed":true}'


def test_stale_tab_cannot_write_task_or_drafts_in_trash(tmp_path):
    store = WorkflowService(tmp_path).store
    state = WorkflowService(tmp_path).create("Draft protection")
    task_id = state.task.task_id
    draft = store.get_m2_draft(task_id)
    idea = store.get_editor_draft(task_id, "idea")
    trashed = store.set_trashed(task_id, state.task.version, True)
    for operation in (
        lambda: store.rename(task_id, trashed.task.version, "Late rename"),
        lambda: store.get_m2_draft(task_id),
        lambda: store.save_m2_draft(task_id, M2DraftUpdate(
            expected_draft_version=draft.draft_version, fields=draft.fields,
            claims=[], source_notes="Late write")),
        lambda: store.save_editor_draft(task_id, "idea", EditorDraftUpdate(
            expected_draft_version=idea.draft_version, base_refs=idea.base_refs,
            content={**idea.content, "hook": "Late write"})),
    ):
        with pytest.raises(WorkflowError) as rejected:
            operation()
        assert rejected.value.code == "task_trashed"
    store.set_trashed(task_id, trashed.task.version, False)
    assert store.get_m2_draft(task_id) == draft
    assert store.get_editor_draft(task_id, "idea") == idea


def test_idempotent_retries_and_conflicts_do_not_toggle_or_lose_changes(tmp_path):
    service = WorkflowService(tmp_path)
    state = service.create("Initial")
    task_id, store = state.task.task_id, service.store
    renamed = store.rename(task_id, state.task.version, "Updated")
    with pytest.raises(WorkflowError, match="changed"):
        store.set_trashed(task_id, state.task.version, True)
    trashed = store.set_trashed(task_id, renamed.task.version, True)
    assert store.set_trashed(task_id, renamed.task.version, True) == trashed
    assert store.set_trashed(task_id, trashed.task.version, True) == trashed
    with pytest.raises(WorkflowError, match="changed"):
        store.set_trashed(task_id, renamed.task.version, False)
    restored = store.set_trashed(task_id, trashed.task.version, False)
    assert store.set_trashed(task_id, trashed.task.version, False) == restored
    assert store.set_trashed(task_id, restored.task.version, False) == restored
    with pytest.raises(WorkflowError, match="changed"):
        store.set_trashed(task_id, renamed.task.version, True)
    assert store.get(task_id).task.title == "Updated"


@pytest.mark.parametrize("status", ["pending", "running"])
def test_trash_refuses_processing_jobs(tmp_path, status):
    service = WorkflowService(tmp_path)
    state = service.create("Busy job")
    task_id = state.task.task_id
    state = service.store.update(task_id, state.task.version, lambda item: item.jobs.append(
        ProcessingJob(job_id="job_active", task_id=task_id, operation="analyze", status=status)))
    with pytest.raises(WorkflowError) as rejected:
        service.store.set_trashed(task_id, state.task.version, True)
    assert rejected.value.code == "task_busy"
    assert service.store.get(task_id) == state


@pytest.mark.parametrize("kind,status", [("background", "queued"), ("background", "running"),
    ("structure", "analyzing"), ("structure", "researching"), ("feedback", "running")])
def test_trash_refuses_queued_background_and_structure_work(tmp_path, kind, status):
    service = WorkflowService(tmp_path)
    state = service.create("Busy workspace")
    task_id = state.task.task_id
    with service.store._connect() as db:
        if kind == "background":
            db.execute("CREATE TABLE background_operations (task_id TEXT, status TEXT)")
            db.execute("INSERT INTO background_operations VALUES (?,?)", (task_id, status))
        else:
            db.execute("CREATE TABLE structure_runs (task_id TEXT, payload TEXT)")
            payload = {"status": status if kind == "structure" else "ready",
                       "feedback_status": status if kind == "feedback" else "idle"}
            db.execute("INSERT INTO structure_runs VALUES (?,?)", (task_id, json.dumps(payload)))
    with pytest.raises(WorkflowError) as rejected:
        service.store.set_trashed(task_id, state.task.version, True)
    assert rejected.value.code == "task_busy"
    assert service.store.list_trash() == []


def test_http_lifecycle_validation_and_project_isolation(tmp_path):
    app = project_app(tmp_path)
    with TestClient(app) as client:
        state = client.post("/api/tasks", json={"title": "First"}).json()
        other = client.post("/api/tasks", json={"title": "Other"}).json()
        base = f"/api/tasks/{state['task']['task_id']}"
        invalid = client.post(base + "/rename", json={"expected_version": 1, "title": "  "})
        assert invalid.status_code == 422
        renamed = client.post(base + "/rename", json={"expected_version": 1, "title": "  Renamed  "})
        assert renamed.status_code == 200 and renamed.json()["task"]["title"] == "Renamed"
        noop = client.post(base + "/rename", json={"expected_version": 2, "title": "Renamed"})
        assert noop.json() == renamed.json()
        trashed = client.post(base + "/trash", json={"expected_version": 2})
        assert trashed.status_code == 200
        assert client.get("/api/tasks").json() == [other]
        assert client.get("/api/trash/tasks").json() == [trashed.json()]
        assert client.get(base).status_code == 410
        assert client.post(base + "/trash", json={"expected_version": 2}).json() == trashed.json()
        restored = client.post(base + "/restore", json={"expected_version": 3})
        assert restored.status_code == 200
        assert client.get(base).json() == restored.json()
        assert client.get("/api/trash/tasks").json() == []
        assert len(client.get("/api/tasks").json()) == 2
        missing = client.post("/api/tasks/task_missing/restore", json={"expected_version": 1})
        assert missing.status_code == 404


def test_trash_cannot_race_inflight_sync_write_or_block_other_projects(tmp_path, monkeypatch):
    app = project_app(tmp_path)
    service = app.state.service
    state = service.create("Active")
    other = service.create("Inactive")
    base = f"/api/tasks/{state.task.task_id}"
    entered, release = threading.Event(), threading.Event()
    original = service.store.rename

    def delayed(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(service.store, "rename", delayed)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, base + "/rename", json={"expected_version": 1, "title": "Saved edit"})
        try:
            assert entered.wait(5)
            rejected = client.post(base + "/trash", json={"expected_version": 1})
            assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "task_busy"
            independent = client.post(f"/api/tasks/{other.task.task_id}/trash", json={"expected_version": 1})
            assert independent.status_code == 200
        finally:
            release.set()
        assert pending.result().status_code == 200
        assert client.post(base + "/trash", json={"expected_version": 2}).status_code == 200


def test_write_cannot_enter_while_trash_transaction_is_pending(tmp_path, monkeypatch):
    app = project_app(tmp_path)
    service = app.state.service
    state = service.create("Trash admission")
    base = f"/api/tasks/{state.task.task_id}"
    entered, release = threading.Event(), threading.Event()
    original = service.store.set_trashed

    def delayed(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(service.store, "set_trashed", delayed)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, base + "/trash", json={"expected_version": 1})
        try:
            assert entered.wait(5)
            rejected = client.post(base + "/rename", json={"expected_version": 1, "title": "Too late"})
            assert rejected.status_code == 409 and rejected.json()["error"]["code"] == "task_busy"
        finally:
            release.set()
        assert pending.result().status_code == 200
        assert service.store.get(state.task.task_id, include_trashed=True).task.title == "Trash admission"
