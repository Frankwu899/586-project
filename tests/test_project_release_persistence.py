"""Release-launcher persistence with explicitly injected analysis, never paid inference.

Uses the same stable-data-directory selection and local_app factory as the
packaged browser/Finder launchers. It does not claim macOS execution.
"""
import hashlib
import json
import threading
import time

from fastapi.testclient import TestClient
import pytest

from backend.app.project_workspace.models import (
    ContentItem, EvidenceEvent, EvidenceRevision, Job, Resource,
)
from backend.app.providers.transport import OpenAITransport
from backend.app.service import WorkflowService
from scripts import local_server
from scripts.local_storage import default_data_dir


class AuthoredSynthesis:
    """Authored outputs exercise validation/storage, not recognition quality."""

    def __init__(self):
        self.calls = 0
        self.title = "Analysis A"
        self.invalid = False

    def json_response(self, _model, prompt, _schema, _name, **_kwargs):
        self.calls += 1
        context = json.loads(prompt.split("INPUT_JSON:\n", 1)[1])
        reference = context["references"][0]
        citation = {
            "resource_id": reference["resource_id"],
            "event_id": "invented" if self.invalid else reference["evidence"]["events"][0]["id"],
            "reason": "Authored test citation",
        }
        return {
            "conclusion": self.title,
            "findings": ["A product is visible in the authored fixture."],
            "differences": [], "opportunities": [],
            "limitations": ["Synthetic test evidence; no model quality evaluated."],
            "citations": [citation],
            "structures": [{
                "resource_id": reference["resource_id"], "summary": "One observed product moment",
                "method": "Visible product", "flow": "A single observed product moment; progression unknown.",
                "borrowable": "Show the product when an actual demonstration is available.",
                "nodes": [{"id": "moment", "label": "Product appears", "detail": "Authored observation",
                           "kind": "observation", "citations": [citation]}],
                "edges": [],
            }],
        }


@pytest.fixture
def launcher_library(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VIDEO_ANATOMY_DATA_DIR", raising=False)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Release persistence tests must not use a live provider")

    monkeypatch.setattr(OpenAITransport, "_request", forbidden)
    # A tiny served shell avoids making backend tests depend on a frontend build.
    install = tmp_path / "first-install"
    (install / "frontend/dist").mkdir(parents=True)
    (install / "frontend/dist/index.html").write_text("<title>Authored test shell</title>")
    monkeypatch.setattr(local_server, "ROOT", install)
    data = default_data_dir(platform="darwin", home=tmp_path / "home")
    assert data == tmp_path / "home/Library/Application Support/Video Anatomy"
    return data, install


def state(client, project_id):
    response = client.get(f"/api/projects/{project_id}")
    assert response.status_code == 200, response.text
    return response.json()


def current(project, content_id=None):
    return next((report for report in reversed(project["analyses"])
                 if report["content_id"] == content_id), None)


def analyze(client, project_id, resource_id, content_id=None):
    before = state(client, project_id)
    response = client.post(f"/api/projects/{project_id}/analyze", json={
        "expected_version": before["version"], "resource_ids": [resource_id], "content_id": content_id,
    })
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        saved = state(client, project_id)
        if not any(job["status"] in {"queued", "running"} for job in saved["jobs"]):
            return saved
        threading.Event().wait(.01)
    pytest.fail("Injected analysis did not settle")


def app_for(data, synthesis):
    app = local_server.local_app(data, local_server.local_settings(data, "", allow_empty=True))
    app.state.project_workspace.analysis.transport_factory = lambda _settings: synthesis
    return app


@pytest.mark.parametrize("migrated", [False, True], ids=["fresh", "legacy-import"])
def test_saved_analysis_replacement_survives_launcher_restart_and_cache_clear(launcher_library, monkeypatch, migrated):
    data, install = launcher_library
    original = None
    if migrated:
        legacy = WorkflowService(data)
        original = legacy.create("Existing legacy assignment")

    synthesis = AuthoredSynthesis()
    app = app_for(data, synthesis)
    with TestClient(app) as client:
        if migrated:
            project = client.get("/api/projects").json()[0]
            assert project["legacy_task_id"] == original.task.task_id
        else:
            project = client.post("/api/projects", json={"title": "Fresh assignment"}).json()
        project_id = project["id"]
        store = app.state.project_workspace.store
        # Recognition is not tested here: retained user-corrected evidence is
        # deliberately seeded, with a project-owned original and exact checksum.
        source = store.project_dir(project_id) / "sources/media/authored.bin"
        source.write_bytes(b"authored original; not a real video")
        evidence = EvidenceRevision(revision=1, reviewed=True, correction_note="Authored corrected fixture",
            coverage={"visual_action": "observations", "on_screen_text": "none_found", "speech": "none_found"},
            events=[EvidenceEvent(id="product", kind="visual", text="A cup is visible.",
                                  start_seconds=0, end_seconds=1)])
        resource = Resource(name="Authored reference", kind="video", original_path="sources/media/authored.bin",
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(), size_bytes=source.stat().st_size,
            status="ready", duration_seconds=1, evidence=[evidence])
        other = ContentItem(title="Independent video")

        def seed(record):
            record.resources.append(resource)
            record.contents.append(other)
            record.workspace = "analysis"

        store.update(project_id, project["version"], seed)
        saved_a = analyze(client, project_id, resource.id)
        assert current(saved_a)["conclusion"] == "Analysis A"
        synthesis.title = "Independent content report"
        saved = analyze(client, project_id, resource.id, other.id)
        independent = current(saved, other.id)
        saved_a = current(saved)
        calls = synthesis.calls
        assert client.get("/api/local/runtime").json()["data_dir"] == str(data)

    # Changing the install location does not change the explicitly selected
    # stable library, as in an extracted-app upgrade. Reopening is read-only.
    next_install = install.parent / "replacement-install"
    (next_install / "frontend/dist").mkdir(parents=True)
    (next_install / "frontend/dist/index.html").write_text("<title>Updated test shell</title>")
    monkeypatch.setattr(local_server, "ROOT", next_install)
    reopened_app = app_for(data, synthesis)
    with TestClient(reopened_app) as client:
        reopened = state(client, project_id)
        assert reopened["workspace"] == "analysis"
        assert current(reopened) == saved_a
        assert current(reopened, other.id) == independent
        assert synthesis.calls == calls
        synthesis.title = "Analysis B"
        saved_b = analyze(client, project_id, resource.id)
        assert current(saved_b)["conclusion"] == "Analysis B"
        assert current(saved_b)["id"] != saved_a["id"]
        assert current(saved_b, other.id) == independent
        synthesis.title, synthesis.invalid = "Invalid replacement C", True
        failed = analyze(client, project_id, resource.id)
        assert next(job for job in reversed(failed["jobs"]) if job["kind"] == "analyze")["status"] == "failed"
        assert current(failed) == current(saved_b)
        assert current(failed, other.id) == independent
        assert len(failed["analyses"]) == 3
        interrupted = Job(kind="analyze", status="running")
        reopened_app.state.project_workspace.store.update(project_id, failed["version"],
                                                         lambda record: record.jobs.append(interrupted))

    calls = synthesis.calls
    with TestClient(app_for(data, synthesis)) as client:
        restarted = state(client, project_id)
        assert restarted["jobs"][-1]["status"] == "failed"
        assert current(restarted) == current(saved_b)
        assert current(restarted, other.id) == independent
        response = client.post(f"/api/projects/{project_id}/cache/clear",
                               json={"expected_version": restarted["version"]})
        assert response.status_code == 200, response.text
        cleared = response.json()
        assert current(cleared) == current(saved_b)
        assert cleared["resources"][0]["evidence"] == restarted["resources"][0]["evidence"]
        assert source.read_bytes() == b"authored original; not a real video"
        assert synthesis.calls == calls
        if migrated:
            assert client.get(f"/api/tasks/{original.task.task_id}").json() == original.model_dump(mode="json")
