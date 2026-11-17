"""Read-only formal direction checks expose stale inputs without rewriting history."""
from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.conversation import ConversationService
from backend.app.project_workspace.models import Fact
from backend.app.project_workspace.planning import PlanningService
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport
from test_project_workspace_planning import approve, idea_response, make_pack


@pytest.fixture(autouse=True)
def no_provider_requests(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("A readiness query must never invoke a provider")
    monkeypatch.setattr(OpenAITransport, "_request", forbidden)


def inspect(client, store, project, content_id, *, expected=200):
    before = store.get(project.id)
    response = client.get(f"/api/projects/{project.id}/contents/{content_id}/readiness")
    assert response.status_code == expected, response.text
    assert store.get(project.id) == before
    if expected == 200:
        result = response.json()
        assert set(result) == {"direction_current", "code", "message", "direction_id", "revision", "project_version"}
        assert result["project_version"] == before.version
    return response.json()


def test_nonempty_series_trash_exposes_outdated_direction_and_restore_recovers_exact_approval(tmp_path):
    store, service, transport, project = make_pack(tmp_path)
    video_id = project.contents[0].id
    project = service.create_series(project.id, project.version, "Creative group", "Observational story")
    group_id = project.series[-1].id
    project = service.edit_content(project.id, project.version, video_id, {"series_id": group_id})
    transport.response = idea_response()
    project = service.generate_directions(project.id, video_id)
    project = approve(service, project)
    approved = project.contents[0].directions[-1].model_copy(deep=True)
    calls = deepcopy(transport.calls)
    with TestClient(create_app(store.root)) as client:
        ready = inspect(client, store, project, video_id)
        assert ready["direction_current"] and ready["code"] is None and ready["message"] is None
        assert ready["direction_id"] == approved.id and ready["revision"] == approved.revision
        deleted = service.trash_series(project.id, project.version, group_id)
        stale = inspect(client, store, deleted, video_id)
        assert not stale["direction_current"] and stale["code"] == "direction_inputs_outdated"
        assert stale["direction_id"] == approved.id and stale["message"]
        assert store.get(project.id).contents[0].directions[-1] == approved
        restored = service.restore_series(project.id, deleted.version, group_id)
        assert inspect(client, store, restored, video_id)["direction_current"]
    assert transport.calls == calls


def test_organizational_rename_stays_current_but_real_description_edit_needs_approval(tmp_path):
    store, service, transport, project = make_pack(tmp_path)
    video = project.contents[0]
    original_manifest = video.directions[-1].inputs.model_copy(deep=True)
    calls = deepcopy(transport.calls)
    with TestClient(create_app(store.root)) as client:
        renamed = service.edit_content(project.id, project.version, video.id, {"title": "Changed display name"})
        assert inspect(client, store, renamed, video.id)["direction_current"]
        changed = service.edit_content(project.id, renamed.version, video.id, {"description": "A genuinely different creative premise"})
        result = inspect(client, store, changed, video.id)
        assert not result["direction_current"] and result["code"] == "direction_approval_required"
        assert result["direction_id"] is None and result["revision"] is None
        assert store.get(project.id).contents[0].directions[-1].inputs == original_manifest
    assert transport.calls == calls


def test_pending_direction_draft_returns_its_real_gate_without_applying_any_text(tmp_path):
    store, service, transport, project = make_pack(tmp_path)
    video = project.contents[0]
    direction = video.directions[-1]
    scope = f"direction-{video.id}-{direction.id}"
    project = store.update(project.id, project.version, lambda state: state.editor_drafts.update({
        scope: {"base_revision": direction.revision, "concept": "An unsaved replacement concept"}}))
    calls = len(transport.calls)
    with TestClient(create_app(store.root)) as client:
        result = inspect(client, store, project, video.id)
    assert not result["direction_current"] and result["code"] == "direction_draft_pending"
    assert store.get(project.id).contents[0].directions[-1].concept == direction.concept
    assert len(transport.calls) == calls


def test_unreviewed_evidence_and_missing_confirmed_context_are_exposed_as_real_gates(tmp_path):
    store, _, _, project = make_pack(tmp_path, reference=True)
    video = project.contents[0]
    project = store.update(project.id, project.version, lambda state: setattr(state.resources[0].evidence[0], "reviewed", False))
    with TestClient(create_app(store.root)) as client:
        result = inspect(client, store, project, video.id)
        assert not result["direction_current"] and result["code"] == "reference_review_required"
        project = store.update(project.id, project.version, lambda state: setattr(state, "briefs", []))
        result = inspect(client, store, project, video.id)
        assert not result["direction_current"] and result["code"] == "confirmed_context_required"


def test_readiness_does_not_require_ai_duration_and_manual_sheet_remains_possible(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Manual production without AI timing")
    settings = ProviderSettings(api_key="", experiment_budget_enabled=False)
    conversation = ConversationService(store, lambda: settings)
    service = PlanningService(store, lambda: settings)
    project = conversation.apply_brief(project.id, project.version, [
        Fact(key="goal", value="Explain an everyday routine", origin="manual", status="confirmed")])
    project = service.create_content(project.id, project.version, "Untimed manual video")
    video_id = project.contents[0].id
    project = service.save_direction(project.id, project.version, video_id,
                                     {"title": "Everyday opening", "concept": "Show a daily morning preparation."})
    project = approve(service, project)
    with TestClient(create_app(store.root)) as client:
        assert inspect(client, store, project, video_id)["direction_current"]
    manual = service.create_manual_pack(project.id, project.version, video_id)
    assert manual.packs[-1].sheet_format == "storyboard_sheet" and not manual.packs[-1].shots


def test_no_approved_direction_is_a_normal_false_readiness_result(tmp_path):
    store = ProjectStore(tmp_path)
    service = PlanningService(store, lambda: ProviderSettings(api_key="", experiment_budget_enabled=False))
    project = store.create("No approval yet")
    project = service.create_content(project.id, project.version, "Draft video")
    with TestClient(create_app(store.root)) as client:
        result = inspect(client, store, project, project.contents[0].id)
    assert not result["direction_current"] and result["code"] == "direction_approval_required"
    assert result["direction_id"] is None and result["revision"] is None


def test_trashed_and_missing_videos_keep_real_http_errors_without_mutating_history(tmp_path):
    store, service, transport, project = make_pack(tmp_path)
    video = project.contents[0]
    project = service.trash_content(project.id, project.version, video.id)
    calls = deepcopy(transport.calls)
    with TestClient(create_app(store.root)) as client:
        assert inspect(client, store, project, video.id, expected=410)["error"]["code"] == "content_trashed"
        assert inspect(client, store, project, "content_missing", expected=404)["error"]["code"] == "content_not_found"
    assert transport.calls == calls
