"""Durable operation tickets and input-specific concurrency; no provider calls."""
from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.background_jobs import BackgroundOperations
from backend.app.content_region import RegionUpdate, save_content_region
from backend.app.service import WorkflowService
from backend.app.sample import sample_analysis
from backend.app.models import Origin
from backend.app.storage import WorkflowError


class QueuedExecutor:
    def __init__(self):
        self.pending = []

    def submit(self, operation, *args):
        self.pending.append((operation, args))

    def finish(self):
        operation, args = self.pending.pop(0)
        operation(*args)


def queue(operations):
    operations.pool.shutdown(wait=True)
    operations.pool = QueuedExecutor()
    return operations.pool


def source(service):
    state = service.create("Background fixture")
    return service.load_sample(state.task.task_id, state.task.version)


def imported_source(service):
    state = source(service)
    with service.media.path_for(state.videos[0]).open("rb") as stream:
        return service.upload(state.task.task_id, state.task.version, "fictional-test-input.mp4", stream)


class FixtureRecognition:
    def analyze(self, request):
        result = sample_analysis(request.task_id, request.video, request.job_id)
        result.origin = Origin(kind="provider", description="Offline scripted fixture on imported synthetic media; no model run.")
        return result


def test_tickets_persist_guard_duplicates_and_polling_never_executes(tmp_path):
    service = WorkflowService(tmp_path)
    task = service.create("First").task
    other = service.create("Other").task
    executed = []
    operations = BackgroundOperations(service.store, lambda *args: executed.append(args))
    executor = queue(operations)
    ticket = operations.submit(task.task_id, "recognize", {"expected_version": task.version})
    assert ticket["status"] == "queued" and ticket["result"] is None
    assert operations.list(task.task_id)["operations"][0]["operation_id"] == ticket["operation_id"]
    for _ in range(3):
        assert operations.get(task.task_id, ticket["operation_id"])["status"] == "queued"
    assert executed == []
    with pytest.raises(WorkflowError) as duplicate:
        operations.submit(task.task_id, "recognize", {})
    assert duplicate.value.code == "operation_running"
    with pytest.raises(WorkflowError) as cross_task:
        operations.get(other.task_id, ticket["operation_id"])
    assert cross_task.value.status == 404
    executor.finish()
    saved = operations.get(task.task_id, ticket["operation_id"])
    assert len(executed) == 1 and saved["status"] == "succeeded"
    assert saved["result"]["task"]["task_id"] == task.task_id
    operations.get(task.task_id, ticket["operation_id"])
    assert len(executed) == 1


def test_restart_marks_interrupted_ticket_without_replaying(tmp_path):
    service = WorkflowService(tmp_path)
    task = service.create("Restart fixture").task
    calls = []
    old = BackgroundOperations(service.store, lambda *args: calls.append(args))
    queue(old)
    ticket = old.submit(task.task_id, "directions", {"expected_version": task.version})
    restarted = BackgroundOperations(service.store, lambda *args: calls.append(args))
    restarted.pool.shutdown(wait=True)
    saved = restarted.get(task.task_id, ticket["operation_id"])
    assert saved["status"] == "failed" and saved["error"]["code"] == "interrupted"
    assert saved["result"]["task"]["title"] == "Restart fixture"
    assert calls == []


@pytest.mark.parametrize("change", ["language", "title", "other_task"])
def test_unrelated_writes_do_not_discard_recognition_and_remain_saved(tmp_path, change):
    service = WorkflowService(tmp_path)
    initial = source(service)
    task_id = initial.task.task_id
    delegate = service.sample_recognition

    class Interleaved:
        def analyze(self, request):
            current = service.store.get(task_id)
            if change == "language":
                service.set_language(task_id, current.task.version, "Chinese")
            elif change == "title":
                service.store.update(task_id, current.task.version, lambda state: setattr(state.task, "title", "Edited while analyzing"))
            else:
                service.create("Another task while analyzing")
            return delegate.analyze(request)

    service.sample_recognition = Interleaved()
    result = service.recognize(task_id, initial.task.version)
    assert result.jobs[-1].status == "succeeded" and result.analyses[-1].status == "succeeded"
    assert not result.analyses[-1].review.user_confirmed
    if change == "language":
        assert result.task.generation_language == "Chinese"
    elif change == "title":
        assert result.task.title == "Edited while analyzing"
    else:
        assert len(service.store.list()) == 2


def test_relevant_content_area_change_discards_inflight_result_but_keeps_edit(tmp_path):
    service = WorkflowService(tmp_path)
    initial = imported_source(service)
    task_id = initial.task.task_id
    delegate = FixtureRecognition()

    class Interleaved:
        def analyze(self, request):
            result = delegate.analyze(request)
            current = service.store.get(task_id)
            save_content_region(service, task_id, current.task.current_video_id, RegionUpdate(
                expected_version=current.task.version, expected_revision=0,
                crop={"x": 0, "y": .1, "width": 1, "height": .9}, exclusions=[]))
            return result

    service.real_recognition = Interleaved()
    result = service.recognize(task_id, initial.task.version)
    assert result.jobs[-1].status == "failed" and result.jobs[-1].error.code == "stale_result"
    assert result.analyses == [] and result.task.current_analysis is None
    from backend.app.content_region import get_content_region
    region = get_content_region(service.store, task_id, result.videos[-1])
    assert region.revision == 1 and region.crop.y == .1


def test_http_queued_operation_returns_saved_failure_and_does_not_repeat(tmp_path):
    service = WorkflowService(tmp_path)
    initial = imported_source(service)
    task_id = initial.task.task_id
    app = create_app(service=service)
    executor = queue(app.state.operations)
    delegate = FixtureRecognition()

    class StaleResult:
        def analyze(self, request):
            result = delegate.analyze(request)
            current = service.store.get(task_id)
            save_content_region(service, task_id, current.task.current_video_id, RegionUpdate(
                expected_version=current.task.version, expected_revision=0,
                crop={"x": 0, "y": .1, "width": 1, "height": .9}, exclusions=[]))
            return result

    service.real_recognition = StaleResult()
    with TestClient(app) as client:
        response = client.post(f"/api/tasks/{task_id}/operations", json={"operation": "recognize", "payload": {"expected_version": initial.task.version}})
        assert response.status_code == 202, response.text
        ticket_id = response.json()["operation_id"]
        duplicate = client.post(f"/api/tasks/{task_id}/operations", json={"operation": "recognize", "payload": {"expected_version": initial.task.version}})
        assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "operation_running"
        executor.finish()
        response = client.get(f"/api/tasks/{task_id}/operations/{ticket_id}")
        ticket = response.json()
        assert ticket["status"] == "failed" and ticket["error"]["code"] == "stale_result"
        assert ticket["result"]["jobs"][-1]["error"]["code"] == "stale_result"
        assert executor.pending == []
