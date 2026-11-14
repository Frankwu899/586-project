"""Local HTTP integration with real persistence and explicitly injected model fixtures.

These checks establish workflow behavior, never live model accuracy or usefulness.
"""
from dataclasses import replace
import io
import json
import threading
import time
import wave
import zipfile

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.providers.transport import OpenAITransport
from backend.app.service import WorkflowService


@pytest.fixture(autouse=True)
def no_provider_requests(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    def prohibited(*_args, **_kwargs):
        raise AssertionError("This integration suite must not call a live provider")
    monkeypatch.setattr(OpenAITransport, "json_response", prohibited)
    monkeypatch.setattr(OpenAITransport, "web_search", prohibited)


def create(client, title="Travel mug launch"):
    response = client.post("/api/projects", json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()


def latest(client, project):
    response = client.get(f"/api/projects/{project['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def change(client, project, suffix, payload=None, *, code=200):
    response = client.post(f"/api/projects/{project['id']}{suffix}",
        json={"expected_version": project["version"], **(payload or {})})
    assert response.status_code == code, response.text
    return response.json()


def patch(client, project, **values):
    response = client.patch(f"/api/projects/{project['id']}", json={"expected_version": project["version"], **values})
    assert response.status_code == 200, response.text
    return response.json()


def settled(client, project):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        current = latest(client, project)
        if all(job["status"] not in {"queued", "running"} for job in current["jobs"]):
            return current
        threading.Event().wait(0.01)
    pytest.fail(f"Background work did not settle: {current['jobs']}")


def document(client, project, text=b"Audience: city commuters\nGoal: explain the daily routine."):
    response = client.post(f"/api/projects/{project['id']}/resources",
        data={"expected_version": project["version"], "role": "document"},
        files={"file": ("campaign.txt", text, "text/plain")})
    assert response.status_code == 202, response.text
    return settled(client, response.json())


def test_project_document_draft_and_workspace_survive_application_restart(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        project = create(client)
        assert project["workspace"] == "overview" and project["messages"] == []
        project = patch(client, project, workspace="resources", conversation_draft="An unfinished assignment")
        project = document(client, project)
        resource = project["resources"][0]
        assert resource["status"] == "ready"
        assert "city commuters" in resource["blocks"][0]["text"]
        assert resource["origin"] == "upload" and resource["original_path"].startswith("sources/")
        response = client.get(f"/api/projects/{project['id']}/resources/{resource['id']}/file")
        assert response.status_code == 200 and b"city commuters" in response.content
        assert "attachment" in response.headers["content-disposition"]
        assert response.headers["x-content-type-options"] == "nosniff"
    with TestClient(create_app(tmp_path)) as reopened:
        restored = latest(reopened, project)
        assert restored == project
        assert reopened.get("/api/projects").json() == [project]
        capabilities = reopened.get("/api/projects/capabilities").json()
        assert capabilities["discovery"] == "Reserved — awaiting Frank’s specification."


def test_no_key_message_is_saved_before_failed_assistance_without_sample_output(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        project = create(client)
        project = patch(client, project, conversation_draft="Plan a mug video.")
        admitted = change(client, project, "/messages", {"text": "Plan a mug video."}, code=202)
        assert admitted["messages"][0]["text"] == "Plan a mug video."
        completed = settled(client, admitted)
        assert completed["conversation_draft"] == ""
        assert completed["jobs"][-1]["status"] == "failed"
        assert completed["messages"][-1]["status"] == "failed"
        assert "API key" in completed["messages"][-1]["text"]
        assert completed["briefs"] == [] and completed["brief_draft"] == []
        assert not completed["editor_drafts"].get("conversation_requests")
    with TestClient(create_app(tmp_path)) as client:
        assert latest(client, completed) == completed


def test_empty_ideas_request_asks_starting_question_without_admitting_job(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        project = create(client)
        response = client.post(f"/api/projects/{project['id']}/concepts/generate",
                               json={"expected_version": project["version"], "instruction": ""})
        assert response.status_code == 422
        assert "?" in response.json()["error"]["message"]
        assert latest(client, project)["jobs"] == []


def test_release_diagnostics_expose_version_and_source_without_credentials(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        identity = client.get("/api/projects/capabilities").json()
        assert identity["version"] == "1.8.1"
        assert identity["source_commit"] is None or len(identity["source_commit"]) == 40
        assert client.get("/api/health").json()["application_version"] == "1.8.1"


def test_per_resource_recognition_retry_is_distinct_from_preview_and_keeps_selection(tmp_path):
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 16000)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        project = create(client)
        response = client.post(f"/api/projects/{project['id']}/resources",
            data={"expected_version": project["version"], "role": "reference"},
            files={"file": ("synthetic-silence.wav", audio.getvalue(), "audio/wav")})
        assert response.status_code == 202, response.text
        project = settled(client, response.json())
        resource = project["resources"][0]
        assert resource["status"] == "ready" and resource["evidence"] == []
        selection = project["selection"]
        admitted = change(client, project, f"/resources/{resource['id']}/recognize", code=202)
        finished = settled(client, admitted)
        parent = next(job for job in finished["jobs"] if job["kind"] == "recognize")
        child = next(job for job in finished["jobs"] if job["kind"] == "reference_extraction")
        assert parent["status"] == child["status"] == "failed"
        assert "API key" in parent["error"]
        assert finished["selection"] == selection
        assert finished["analyses"] == []
        assert finished["resources"][0]["evidence"] == []
        original = app.state.project_workspace.store.resolve_path(project["id"], resource["original_path"])
        assert original.read_bytes() == audio.getvalue()


def test_unreadable_project_is_visible_without_blocking_healthy_library(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        healthy = create(client, "Healthy")
        broken = create(client, "Damaged fixture")
    damaged_db = app.state.project_workspace.store.project_dir(broken["id"]) / "project.sqlite3"
    damaged_db.write_bytes(b"test-only damaged SQLite fixture")
    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/projects").json() == [healthy]
        warnings = client.get("/api/projects/capabilities").json()["library_errors"]
        assert len(warnings) == 1 and broken["id"] in warnings[0]
        assert client.get(f"/api/projects/{broken['id']}").status_code == 409
    assert damaged_db.read_bytes() == b"test-only damaged SQLite fixture"


def test_duplicate_trash_and_cache_operations_preserve_independent_originals(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        source = document(client, create(client))
        resource = source["resources"][0]
        original = app.state.project_workspace.store.resolve_path(source["id"], resource["original_path"])
        duplicate = change(client, source, "/duplicate")
        copied_path = app.state.project_workspace.store.resolve_path(duplicate["id"], resource["original_path"])
        assert copied_path != original and copied_path.read_bytes() == original.read_bytes()
        duplicate = patch(client, duplicate, title="Independent copy", conversation_draft="Different assignment")
        assert latest(client, source) == source
        cache = app.state.project_workspace.store.project_dir(duplicate["id"]) / "cache/scratch.txt"
        cache.write_text("disposable")
        duplicate = change(client, duplicate, "/cache/clear")
        assert not cache.exists() and copied_path.is_file()
        trashed = change(client, duplicate, "/trash")
        assert client.get(f"/api/projects/{duplicate['id']}").status_code == 410
        assert [item["id"] for item in client.get("/api/projects").json()] == [source["id"]]
        assert client.get("/api/projects?trashed=true").json() == [trashed]
        restored = change(client, trashed, "/restore")
        assert restored["conversation_draft"] == "Different assignment"
        assert copied_path.read_bytes() == original.read_bytes()
        assert latest(client, source) == source


def test_missing_original_is_visible_and_verified_relink_restores_it(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        project = document(client, create(client))
        resource = project["resources"][0]
        path = app.state.project_workspace.store.resolve_path(project["id"], resource["original_path"])
        original = path.read_bytes()
        path.unlink()
        missing = latest(client, project)
        assert missing["resources"][0]["status"] == "missing"
        blocked = client.post(f"/api/projects/{project['id']}/duplicate", json={"expected_version": missing["version"]})
        assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "duplicate_missing_source"
        wrong = client.post(f"/api/projects/{project['id']}/resources/{resource['id']}/relink",
            data={"expected_version": missing["version"]}, files={"file": ("wrong.txt", b"different", "text/plain")})
        assert wrong.status_code in {409, 422} and not path.exists()
        restored = client.post(f"/api/projects/{project['id']}/resources/{resource['id']}/relink",
            data={"expected_version": missing["version"]}, files={"file": ("campaign.txt", original, "text/plain")})
        assert restored.status_code == 200, restored.text
        assert path.read_bytes() == original
        assert restored.json()["resources"][0]["blocks"] == resource["blocks"]


def test_reserved_draft_scopes_stale_writes_and_foreign_sources_are_rejected(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        project = create(client)
        for key in ("conversation_requests", "conversation_forged"):
            response = client.patch(f"/api/projects/{project['id']}", json={"expected_version": project["version"], "editor_drafts": {key: {"status": "pending"}}})
            assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_draft_scope"
        changed = patch(client, project, title="Renamed")
        stale = client.patch(f"/api/projects/{project['id']}", json={"expected_version": project["version"], "conversation_draft": "Must not overwrite"})
        assert stale.status_code == 409
        invalid = client.post(f"/api/projects/{project['id']}/messages", json={"expected_version": changed["version"], "text": "Read this", "resource_ids": ["resource_other_project"]})
        assert invalid.status_code == 404
        assert latest(client, project) == changed


def test_editor_scope_guard_rejects_delayed_tab_after_aggregate_version_rebase(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        project = create(client)
        first = patch(client, project, editor_drafts={"production-one": {"script": "Newer tab text"}},
                      expected_editor_versions={"production-one": 0})
        assert first["editor_draft_versions"]["production-one"] == 1
        latest_state = patch(client, first, title="Unrelated workspace update")
        delayed = client.patch(f"/api/projects/{project['id']}", json={
            "expected_version": latest_state["version"],
            "expected_editor_versions": {"production-one": 0},
            "editor_drafts": {"production-one": {"script": "Delayed old tab text"}}})
        assert delayed.status_code == 409
        assert latest(client, project)["editor_drafts"]["production-one"]["script"] == "Newer tab text"
        independent = patch(client, latest_state, editor_drafts={"direction-one": {"hook": "Independent"}},
                            expected_editor_versions={"direction-one": 0})
        assert independent["editor_draft_versions"] == {"production-one": 1, "direction-one": 1}
        unchanged = patch(client, independent, editor_drafts={"production-one": {"script": "Newer tab text"}},
                          expected_editor_versions={"production-one": 1})
        assert unchanged["version"] == independent["version"]


def test_legacy_project_is_imported_once_and_its_original_task_stays_accessible(tmp_path):
    legacy = WorkflowService(tmp_path)
    old = legacy.create("Existing local project")
    with TestClient(create_app(tmp_path, service=legacy)) as client:
        projects = client.get("/api/projects").json()
        assert len(projects) == 1 and projects[0]["legacy_task_id"] == old.task.task_id
        assert projects[0]["contents"][0]["series_id"] is None
        original = client.get(f"/api/tasks/{old.task.task_id}")
        assert original.status_code == 200 and original.json() == old.model_dump(mode="json")
        assert client.get("/api/projects/capabilities").json()["migration_errors"] == []
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get("/api/projects").json() == projects


def test_shutdown_rejects_job_without_losing_message_or_leaving_queued_work(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        project = create(client)
        app.state.project_workspace.executor.shutdown(wait=True)
        response = client.post(f"/api/projects/{project['id']}/messages",
            json={"expected_version": project["version"], "text": "Keep this assignment."})
        assert response.status_code == 503
        retained = latest(client, project)
        assert retained["messages"][0]["text"] == "Keep this assignment."
        assert retained["messages"][-1]["status"] == "failed"
        assert retained["jobs"][-1]["status"] == "failed"
        assert not retained["editor_drafts"].get("conversation_requests")


class BlockingConversation:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def json_response(self, **_kwargs):
        self.calls += 1
        self.started.set()
        assert self.release.wait(5), "The test must release the fixture response"
        return {"reply": "Your assignment is saved.", "proposals": [], "unresolved": [], "research_query": None}


def test_busy_message_admission_does_not_append_a_second_user_message(tmp_path):
    app = create_app(tmp_path)
    runtime = app.state.project_workspace
    runtime.legacy_service.provider_settings = replace(runtime.legacy_service.provider_settings, api_key="test-only-key")
    fixture = BlockingConversation()
    runtime.conversation.transport_factory = lambda _settings: fixture
    with TestClient(app) as client:
        project = create(client)
        admitted = change(client, project, "/messages", {"text": "Plan a commuter video."}, code=202)
        assert fixture.started.wait(3)
        current = latest(client, admitted)
        try:
            second = client.post(f"/api/projects/{project['id']}/messages", json={"expected_version": current["version"], "text": "Second message"})
            assert second.status_code == 409
            trash = client.post(f"/api/projects/{project['id']}/trash", json={"expected_version": current["version"]})
            assert trash.status_code == 409
        finally:
            fixture.release.set()
        completed = settled(client, project)
        assert [message["text"] for message in completed["messages"] if message["role"] == "user"] == ["Plan a commuter video."]
        assert fixture.calls == 1


class PackFixture:
    def __init__(self):
        self.calls = []

    def json_response(self, **kwargs):
        self.calls.append(kwargs)
        return {"production_brief": "Prepare a mug and a desk. Confirm the available location.",
                "script": "VOICE: Ready for the day?", "shots": [
                    {"id": "shot_01", "start_seconds": 0, "end_seconds": 3,
                     "visual": "Hands place a mug into a bag.", "dialogue": "Ready?", "on_screen_text": "Morning", "sound": "Zipper", "notes": ""},
                    {"id": "shot_02", "start_seconds": 3, "end_seconds": 8,
                     "visual": "Commuter walks out of the room.", "dialogue": "Let's go.", "on_screen_text": "", "sound": "Footsteps", "notes": ""}],
                "shot_list": "01 — Close-up, mug and bag.\n02 — Wide, commuter exits.",
                "citations": [], "used_claim_ids": [], "claim_uses": []}


def test_four_document_pack_exports_exact_snapshot_and_rejects_pending_edits(tmp_path):
    app = create_app(tmp_path)
    runtime = app.state.project_workspace
    fixture = PackFixture()
    observed_keys = []
    def factory(settings):
        observed_keys.append(settings.api_key)
        return fixture
    runtime.planning.transport_factory = factory
    with TestClient(app) as client:
        project = create(client)
        facts = [{"id": "fact_product", "key": "product", "value": "Travel mug", "origin": "manual", "status": "confirmed"},
                 {"id": "fact_goal", "key": "goal", "value": "Explain a commuter routine", "origin": "manual", "status": "confirmed"},
                 {"id": "fact_duration", "key": "duration_seconds", "value": "8", "origin": "manual", "status": "confirmed"}]
        project = change(client, project, "/brief/apply", {"facts": facts})
        same = change(client, project, "/brief/apply", {"facts": facts})
        assert same["version"] == project["version"] and len(same["briefs"]) == 1
        project = change(client, project, "/contents", {"title": "The commute"})
        item_id = project["contents"][0]["id"]
        project = change(client, project, f"/contents/{item_id}/directions", {"title": "One less thing", "concept": "Show a calm morning routine.", "hook": "Train arriving", "narrative": "Pack, leave, arrive", "cta": "See the mug"})
        direction = project["contents"][0]["directions"][0]
        project = change(client, project, f"/contents/{item_id}/directions/{direction['id']}/approve", {"revision": direction["revision"]})
        again = change(client, project, f"/contents/{item_id}/directions/{direction['id']}/approve", {"revision": direction["revision"]})
        assert again["version"] == project["version"]
        runtime.legacy_service.provider_settings = replace(runtime.legacy_service.provider_settings,
            api_key="test-updated-key", research_model="gpt-6-luna")
        capabilities = client.get("/api/projects/capabilities").json()
        assert capabilities["configured"] and capabilities["model"] == "gpt-6.1-sol"
        assert "test-updated-key" not in json.dumps(capabilities)
        admitted = change(client, project, f"/contents/{item_id}/production/generate", code=202)
        project = settled(client, admitted)
        assert project["jobs"][-1]["status"] == "succeeded", project["jobs"]
        pack = project["packs"][0]
        assert all(pack[field] for field in ("production_brief", "script", "storyboard", "shot_list"))
        assert pack["inputs"]["brief_revision"] == 1
        assert pack["inputs"]["direction_id"] == direction["id"] and pack["inputs"]["direction_revision"] == 1
        assert pack["inputs"]["resource_ids"] == [] and pack["inputs"]["evidence_revisions"] == {}
        assert pack["inputs"]["model"] == "gpt-6.1-sol" and pack["inputs"]["instruction_digest"]
        assert observed_keys == ["test-updated-key"] and len(fixture.calls) == 1
        export_url = f"/api/projects/{project['id']}/packs/{pack['id']}/export?revision=1"
        markdown = client.get(export_url + "&format=markdown")
        assert markdown.status_code == 200 and "VOICE: Ready for the day?" in markdown.text
        html = client.get(export_url + "&format=html")
        assert html.status_code == 200 and "Production brief" in html.text and "Shot list" in html.text
        csv = client.get(export_url + "&format=csv")
        assert csv.status_code == 200 and "shot_01" in csv.text
        docx = client.get(export_url + "&format=docx")
        assert docx.status_code == 200
        with zipfile.ZipFile(io.BytesIO(docx.content)) as archive:
            assert "word/document.xml" in archive.namelist()
        documents = {field: pack[field] for field in ("production_brief", "script", "storyboard", "shot_list")}
        unchanged = change(client, project, f"/packs/{pack['id']}", {"revision": 1, **documents})
        assert unchanged["version"] == project["version"] and len(unchanged["packs"]) == 1
        project = patch(client, project, editor_drafts={f"production-{pack['id']}": {**documents, "script": "An unsaved replacement"}})
        rejected = client.get(export_url + "&format=docx")
        assert rejected.status_code == 422 and rejected.json()["error"]["code"] == "production_draft_pending"
    with TestClient(create_app(tmp_path)) as reopened:
        restored = latest(reopened, project)
        assert restored["packs"] == project["packs"] and restored["editor_drafts"] == project["editor_drafts"]
        assert reopened.get(export_url + "&format=html").status_code == 422
