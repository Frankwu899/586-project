"""Logical project folders preserve local bytes, identities and historical evidence."""
import io
import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.models import (
    Analysis, EvidenceEvent, EvidenceRevision, InputManifest, Project, Resource, SourceRef,
    resource_is_trashed,
)
from backend.app.project_workspace.resources import ResourceService
from backend.app.project_workspace.store import ProjectStore
from backend.app.workflow_errors import WorkflowError


@pytest.fixture
def library(tmp_path):
    store = ProjectStore(tmp_path)
    service = ResourceService(store)
    project = store.create("Folder compatibility fixture")
    project = service.import_file(project.id, project.version, "Original.txt", io.BytesIO(b"Original evidence text"))
    return store, service, project


def test_legacy_missing_fields_migrate_deterministically_once_without_moving_bytes(library):
    store, service, project = library
    source = project.resources[0]
    legacy = project.model_dump(mode="json")
    legacy.pop("resource_folders")
    legacy.pop("topic_suggestions")
    legacy["resources"][0].pop("folder_id")
    legacy["resources"][0].pop("trashed_at")
    legacy["resources"][0]["role"] = "document"
    path = store.project_dir(project.id) / "project.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE project SET payload=? WHERE id=?", (json.dumps(legacy), project.id))
    first = store.get(project.id)
    second = store.get(project.id)
    assert first == second
    assert [folder.id for folder in first.resource_folders] == [
        "folder_inbox", "folder_references", "folder_documents", "folder_production_assets"]
    assert first.resources[0].folder_id == "folder_documents"
    assert first.resources[0].id == source.id and first.resources[0].original_path == source.original_path
    assert first.resources[0].sha256 == source.sha256
    assert service.path(project.id, source.id).read_bytes() == b"Original evidence text"
    moved = service.move_resources(project.id, first.version, [source.id], "folder_production_assets")
    assert store.get(project.id).resources[0].folder_id == "folder_production_assets"
    assert moved.resources[0].role == "document"  # A later read never remaps explicit placement.


def test_entry_default_destinations_are_explicit_not_guessed_from_file_extension(library):
    _, service, project = library
    assert project.resources[0].folder_id == "folder_inbox"
    assert project.resources[0].role == "reference" and project.resources[0].kind == "document"
    project = service.import_file(project.id, project.version, "Overview.mp4", io.BytesIO(b"not decoded here"), role="document")
    assert project.resources[-1].folder_id == "folder_documents"
    project = service.import_file(project.id, project.version, "Found.txt", io.BytesIO(b"Future channel"), origin="discovery")
    assert project.resources[-1].folder_id == "folder_references"
    project = service.import_file(project.id, project.version, "Explicit.txt", io.BytesIO(b"Explicit destination"),
                                  role="document", folder_id="folder_production_assets")
    assert project.resources[-1].folder_id == "folder_production_assets" and project.resources[-1].role == "document"


def test_logical_move_rename_and_folder_rename_preserve_revision_links_and_original(library):
    store, service, project = library
    resource = project.resources[0]
    event = EvidenceEvent(id="saved_event", kind="visual", text="Original observation", start_seconds=1, end_seconds=2)
    ref = SourceRef(resource_id=resource.id, evidence_revision=1, event_id=event.id, start_seconds=1, end_seconds=2)
    def history(state):
        state.resources[0].evidence = [EvidenceRevision(revision=1, events=[event])]
        state.analyses = [Analysis(inputs=InputManifest(resource_ids=[resource.id], evidence_revisions={resource.id: 1}),
                                   conclusion="Saved report", sources=[ref])]
    project = store.update(project.id, project.version, history)
    before = project.resources[0].model_dump()
    project = service.create_folder(project.id, project.version, "Client sources", "folder_documents")
    folder = project.resource_folders[-1]
    project = service.move_resources(project.id, project.version, [resource.id], folder.id)
    project = service.edit_resource(project.id, project.version, resource.id, {"name": "Renamed source.mp4"})
    project = service.edit_folder(project.id, project.version, folder.id, {"name": "Client references"})
    after = project.resources[0].model_dump()
    assert {key: value for key, value in after.items() if key not in {"name", "folder_id"}} == {
        key: value for key, value in before.items() if key not in {"name", "folder_id"}}
    assert project.analyses[0].sources == [ref] and not project.analyses[0].needs_review
    assert service.path(project.id, resource.id).name == "Original.txt"
    assert service.path(project.id, resource.id).read_bytes() == b"Original evidence text"
    assert store.get(project.id) == project


def test_folder_trash_inherits_without_erasing_independent_resource_trash(library):
    store, service, project = library
    first = project.resources[0].id
    project = service.import_file(project.id, project.version, "Second.txt", io.BytesIO(b"Second"))
    second = project.resources[-1].id
    project = service.create_folder(project.id, project.version, "Nested", "folder_inbox")
    nested = project.resource_folders[-1].id
    project = service.move_resources(project.id, project.version, [first, second], nested)
    project = service.resource_trash(project.id, project.version, second)
    independently_deleted = project.resources[-1].trashed_at
    project = service.folder_trash(project.id, project.version, "folder_inbox")
    assert all(resource_is_trashed(project, resource) for resource in project.resources)
    assert project.resources[0].trashed_at is None
    with pytest.raises(WorkflowError) as error:
        service.path(project.id, first)
    assert error.value.status == 410
    with pytest.raises(WorkflowError) as restore_error:
        service.resource_trash(project.id, project.version, first, restore=True)
    assert restore_error.value.code == "folder_trashed"
    project = service.folder_trash(project.id, project.version, "folder_inbox", restore=True)
    assert not resource_is_trashed(project, project.resources[0])
    assert project.resources[-1].trashed_at == independently_deleted
    assert service.path(project.id, first).read_bytes() == b"Original evidence text"
    project = service.resource_trash(project.id, project.version, second, restore=True)
    assert service.path(project.id, second).read_bytes() == b"Second"
    assert not any(resource_is_trashed(store.get(project.id), resource) for resource in project.resources)


def test_cycle_invalid_destination_and_bulk_partial_failure_are_atomic(library):
    store, service, project = library
    project = service.create_folder(project.id, project.version, "Nested", "folder_inbox")
    child = project.resource_folders[-1].id
    with pytest.raises(WorkflowError, match="itself"):
        service.edit_folder(project.id, project.version, "folder_inbox", {"name": "Not applied", "parent_id": child})
    assert store.get(project.id) == project
    with pytest.raises(WorkflowError):
        service.move_resources(project.id, project.version, [project.resources[0].id, "missing"], "folder_documents")
    assert store.get(project.id) == project
    with pytest.raises(WorkflowError):
        service.edit_resource(project.id, project.version, project.resources[0].id, {"name": "../escaped"})
    assert store.get(project.id) == project


def test_legacy_insights_precision_and_sheet_sources_are_honest_defaults():
    resource = Resource(name="Old video", kind="video", original_path="sources/media/old.mp4", sha256="a" * 64,
                        size_bytes=1, evidence=[EvidenceRevision(revision=1, events=[EvidenceEvent(
                            id="event_old", kind="visual", text="Old sample", start_seconds=1, end_seconds=2)])])
    project = Project(resources=[resource], analyses=[Analysis(inputs=InputManifest(), conclusion="Legacy", findings=["Old finding"])])
    assert project.analyses[0].key_insights == []
    assert project.resources[0].evidence[0].events[0].precision == "unknown"


def test_folder_and_file_management_http_routes_preserve_data(library):
    store, _, project = library
    with TestClient(create_app(store.root)) as client:
        base = "/api/projects/" + project.id
        def mutate(path, payload=None, method="post"):
            current = client.get(base).json()
            response = getattr(client, method)(base + path, json={"expected_version": current["version"], **(payload or {})})
            assert response.status_code == 200, response.text
            return response.json()
        result = mutate("/folders", {"name": "Owned folder", "parent_id": "folder_documents"})
        folder = result["resource_folders"][-1]["id"]
        result = mutate("/resources/move", {"resource_ids": [project.resources[0].id], "folder_id": folder})
        result = mutate("/resources/" + project.resources[0].id, {"name": "Display rename.txt"}, method="patch")
        assert result["resources"][0]["folder_id"] == folder
        result = mutate("/folders/" + folder + "/trash")
        assert client.get(base + "/resources/" + project.resources[0].id + "/file").status_code == 410
        result = mutate("/folders/" + folder + "/restore")
        assert client.get(base + "/resources/" + project.resources[0].id + "/file").content == b"Original evidence text"


def test_http_analysis_rejects_trashed_selection_before_admitting_a_job(library):
    store, service, project = library
    # A controlled media record; it must be rejected before any decode/provider work.
    project = store.update(project.id, project.version, lambda state: setattr(state.resources[0], "kind", "video"))
    project = service.resource_trash(project.id, project.version, project.resources[0].id)
    with TestClient(create_app(store.root)) as client:
        base = "/api/projects/" + project.id
        current = client.get(base).json()
        response = client.post(base + "/analyze", json={"expected_version": current["version"],
                                                       "resource_ids": [project.resources[0].id]})
        assert response.status_code == 410 and response.json()["error"]["code"] == "resource_trashed"
        assert client.get(base).json()["jobs"] == []
