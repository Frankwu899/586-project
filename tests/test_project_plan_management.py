"""Recoverable Video/Series management preserves saved creative work and lineage."""
import json
from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.exports import export_pack
from backend.app.project_workspace.models import ContentItem, Job, Project, Series
from backend.app.project_workspace.store import ProjectStore
from backend.app.workflow_errors import WorkflowError
from test_project_workspace_planning import approve, idea_response, make_pack, pack_response, setup


def test_video_rename_preserves_approval_manifest_and_pack_until_real_context_edit(tmp_path):
    store, service, transport, project = make_pack(tmp_path)
    before = project.contents[0].model_copy(deep=True)
    pack = project.packs[-1].model_copy(deep=True)
    renamed = service.edit_content(project.id, project.version, before.id, {"title": "A new display label"})
    video = renamed.contents[0]
    assert video.title == "A new display label" and video.context_title == before.title
    assert video.directions == before.directions
    assert video.approved_direction_id == before.approved_direction_id
    assert renamed.packs[-1] == pack
    transport.response = pack_response()
    generated = service.generate_pack(project.id, before.id)
    assert generated.packs[-1].inputs.context_digest == pack.inputs.context_digest
    assert json.loads(transport.calls[-1]["prompt"].split("INPUT_JSON:\n", 1)[1])["content"]["title"] == before.title
    changed = service.edit_content(project.id, generated.version, before.id, {"description": "A genuinely different creative premise"})
    assert changed.contents[0].context_title is None
    assert changed.contents[0].approved_direction_id is None
    assert changed.packs[-1].needs_review
    assert changed.contents[0].directions[0].inputs == before.directions[0].inputs
    assert ProjectStore(store.root).get(project.id) == changed


def test_series_rename_preserves_nonempty_concept_manifest_and_approval(tmp_path):
    _, service, transport, project = make_pack(tmp_path)
    video_id = project.contents[0].id
    project = service.create_series(project.id, project.version, "Original series label", "An observational story")
    series_id = project.series[-1].id
    project = service.edit_content(project.id, project.version, video_id, {"series_id": series_id})
    transport.response = idea_response()
    project = service.generate_directions(project.id, video_id)
    project = approve(service, project)
    transport.response = pack_response()
    project = service.generate_pack(project.id, video_id)
    before = project.contents[0].model_copy(deep=True)
    pack = project.packs[-1].model_copy(deep=True)
    renamed = service.edit_series(project.id, project.version, series_id, {"title": "Renamed label"})
    assert renamed.series[-1].context_title == "Original series label"
    assert renamed.contents[0] == before and renamed.packs[-1] == pack
    after = service.generate_pack(project.id, video_id)
    assert after.packs[-1].inputs.context_digest == pack.inputs.context_digest
    changed = service.edit_series(project.id, after.version, series_id, {"concept": "A new creative concept"})
    assert changed.series[-1].context_title is None
    assert changed.contents[0].approved_direction_id is None and changed.packs[-1].needs_review


def test_video_trash_restore_preserves_all_saved_work_exports_and_active_fallback(tmp_path):
    store, service, _, project = make_pack(tmp_path)
    video = project.contents[0].model_copy(deep=True)
    pack = project.packs[-1].model_copy(deep=True)
    original_export = export_pack(store, project.id, pack.id, pack.revision, "csv")[0]
    project = service.create_content(project.id, project.version, "Second active video")
    next_id = project.contents[-1].id
    project = store.update(project.id, project.version, lambda state: setattr(state, "active_content_id", video.id))
    deleted = service.delete_content(project.id, project.version, video.id)
    assert deleted.active_content_id == next_id
    assert deleted.contents[0].trashed_at
    assert deleted.contents[0].model_dump(exclude={"trashed_at"}) == video.model_dump(exclude={"trashed_at"})
    assert deleted.packs[-1] == pack
    assert export_pack(store, project.id, pack.id, pack.revision, "csv")[0] == original_export
    assert service.trash_content(project.id, deleted.version, video.id) == deleted
    restored = service.restore_content(project.id, deleted.version, video.id)
    assert restored.active_content_id == next_id and restored.contents[0] == video
    assert service.restore_content(project.id, restored.version, video.id) == restored
    assert ProjectStore(store.root).get(project.id) == restored


def test_trashing_last_video_selects_none_and_restore_does_not_steal_selection(tmp_path):
    _, service, _, project = make_pack(tmp_path)
    video_id = project.contents[0].id
    deleted = service.trash_content(project.id, project.version, video_id)
    assert deleted.active_content_id is None
    restored = service.restore_content(project.id, deleted.version, video_id)
    assert restored.active_content_id is None and not restored.contents[0].trashed_at


def test_series_restore_respects_new_moves_explicit_standalone_and_individual_trash(tmp_path):
    store, service, _, project = make_pack(tmp_path)
    project = service.create_series(project.id, project.version, "Original group")
    group_id = project.series[-1].id
    first = project.contents[0].id
    project = service.edit_content(project.id, project.version, first, {"series_id": group_id})
    identifiers = [first]
    for title in ["Moved elsewhere", "Kept standalone", "Independently trashed", "Previously trashed"]:
        project = service.create_content(project.id, project.version, title, series_id=group_id)
        identifiers.append(project.contents[-1].id)
    project = service.trash_content(project.id, project.version, identifiers[-1])
    prior_trashed = project.contents[-1].model_copy(deep=True)
    before = project.contents[0].model_copy(deep=True)
    deleted = service.trash_series(project.id, project.version, group_id)
    group = deleted.series[-1]
    assert group.trashed_at and set(group.detached_contents) == set(identifiers[:-1])
    assert deleted.contents[-1] == prior_trashed
    assert deleted.contents[0].directions == before.directions
    assert deleted.contents[0].approved_direction_id == before.approved_direction_id
    assert all(video.series_id is None for video in deleted.contents[:-1])
    project = service.create_series(project.id, deleted.version, "New group")
    target_id = project.series[-1].id
    project = service.edit_content(project.id, project.version, identifiers[1], {"series_id": target_id})
    project = service.edit_content(project.id, project.version, identifiers[2], {"series_id": None})
    project = service.trash_content(project.id, project.version, identifiers[3])
    restored = service.restore_series(project.id, project.version, group_id)
    by_id = {video.id: video for video in restored.contents}
    assert by_id[first].series_id == group_id
    assert by_id[identifiers[1]].series_id == target_id
    assert by_id[identifiers[2]].series_id is None
    assert by_id[identifiers[3]].series_id is None and by_id[identifiers[3]].trashed_at
    assert by_id[identifiers[-1]] == prior_trashed
    assert not next(series for series in restored.series if series.id == group_id).detached_contents
    assert store.get(project.id) == restored


def test_restore_video_from_a_trashed_series_returns_standalone_without_restoring_group(tmp_path):
    _, service, _, project = make_pack(tmp_path)
    video_id = project.contents[0].id
    project = service.create_series(project.id, project.version, "Old group")
    group_id = project.series[-1].id
    project = service.edit_content(project.id, project.version, video_id, {"series_id": group_id})
    project = service.trash_content(project.id, project.version, video_id)
    project = service.trash_series(project.id, project.version, group_id)
    restored = service.restore_content(project.id, project.version, video_id)
    assert not restored.contents[0].trashed_at and restored.contents[0].series_id is None
    assert restored.series[-1].trashed_at


def test_trash_busy_video_or_series_is_rejected_without_losing_work(tmp_path):
    store, service, _, project = make_pack(tmp_path)
    video_id = project.contents[0].id
    project = service.create_series(project.id, project.version, "Busy group")
    group_id = project.series[-1].id
    project = service.edit_content(project.id, project.version, video_id, {"series_id": group_id})
    project = store.update(project.id, project.version, lambda state: state.jobs.append(Job(kind="directions", content_id=video_id, status="running")))
    for operation, identifier in [(service.trash_content, video_id), (service.trash_series, group_id)]:
        with pytest.raises(WorkflowError) as error:
            operation(project.id, project.version, identifier)
        assert error.value.code == "content_busy"
        assert store.get(project.id) == project
    project = store.update(project.id, project.version, lambda state: setattr(state.jobs[-1], "status", "succeeded"))
    project = service.trash_series(project.id, project.version, group_id)
    project = store.update(project.id, project.version, lambda state: state.jobs.append(Job(kind="directions", content_id=video_id, status="running")))
    with pytest.raises(WorkflowError) as restore_error:
        service.restore_series(project.id, project.version, group_id)
    assert restore_error.value.code == "content_busy" and store.get(project.id) == project


@pytest.mark.parametrize("status", ["queued", "running"])
@pytest.mark.parametrize("legacy_scope", [False, True])
def test_trash_series_waits_for_its_topic_generation_even_without_member_videos(tmp_path, status, legacy_scope):
    store, service, _, project = setup(tmp_path)
    project = service.create_series(project.id, project.version, "A series awaiting topics")
    group_id = project.series[-1].id
    diagnostics = {} if legacy_scope else {"series_id": group_id}
    project = store.update(project.id, project.version, lambda state: state.jobs.append(
        Job(kind="topics", status=status, diagnostics=diagnostics)))
    with pytest.raises(WorkflowError) as error:
        service.trash_series(project.id, project.version, group_id)
    assert error.value.code == "series_busy"
    assert store.get(project.id) == project


@pytest.mark.parametrize("scope,status", [("other", "running"), ("standalone", "running"), ("target", "succeeded")])
def test_unrelated_or_finished_topic_generation_does_not_block_series_trash(tmp_path, scope, status):
    store, service, _, project = setup(tmp_path)
    project = service.create_series(project.id, project.version, "Series to organize")
    group_id = project.series[-1].id
    project = service.create_series(project.id, project.version, "Another series")
    topic_scope = {"target": group_id, "other": project.series[-1].id, "standalone": ""}[scope]
    project = store.update(project.id, project.version, lambda state: state.jobs.append(
        Job(kind="topics", status=status, diagnostics={"series_id": topic_scope})))
    result = service.trash_series(project.id, project.version, group_id)
    assert result.series[0].trashed_at and not result.series[1].trashed_at
    assert result.jobs == project.jobs


def test_http_topic_generation_keeps_target_series_available_until_its_result_is_saved(tmp_path):
    store, service, transport, project = setup(tmp_path, {
        "standalone": [{"title": "A new episode", "description": "An observational morning routine"}]})
    project = service.create_series(project.id, project.version, "A series awaiting topics", "A daily routine")
    group_id = project.series[-1].id
    app = create_app(store.root)
    runtime = app.state.project_workspace
    runtime.legacy_service.provider_settings = replace(runtime.legacy_service.provider_settings, api_key="test-only-key")
    runtime.planning.transport_factory = lambda _settings: transport
    trash_outcomes = []
    def during_generation():
        current = store.get(project.id)
        try:
            service.trash_series(project.id, current.version, group_id)
        except WorkflowError as error:
            trash_outcomes.append(error.code)
        else:
            trash_outcomes.append("trashed")
    transport.callback = during_generation
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{project.id}/topics/suggest", json={
            "expected_version": project.version, "series_id": group_id, "instruction": "Another episode"})
        assert response.status_code == 202, response.text
        runtime.executor.shutdown(wait=True)
        saved = store.get(project.id)
    assert trash_outcomes == ["series_busy"]
    assert len(transport.calls) == 1
    assert not saved.series[-1].trashed_at
    assert saved.jobs[-1].diagnostics["series_id"] == group_id
    assert saved.jobs[-1].status == "succeeded"
    assert len(saved.topic_suggestions) == 1 and saved.topic_suggestions[0].series_id == group_id
    # Once the admitted generation is finished, the same lifecycle action succeeds.
    assert service.trash_series(project.id, saved.version, group_id).series[-1].trashed_at


def test_legacy_plan_records_receive_non_destructive_management_defaults():
    loaded = Project.model_validate({"contents": [{"id": "content_old", "title": "Old video", "series_id": "series_old"}],
                                    "series": [{"id": "series_old", "title": "Old group"}]})
    assert loaded.contents[0].trashed_at is None and loaded.contents[0].series_assignment_version == 1
    assert loaded.contents[0].context_title is None
    assert loaded.series[0].trashed_at is None and loaded.series[0].detached_contents == {}
    assert loaded.series[0].context_title is None
    assert ContentItem(title="New").trashed_at is None and Series(title="New").trashed_at is None


def test_plan_management_http_guards_reject_new_work_but_keep_historical_export(tmp_path):
    store, service, _, project = make_pack(tmp_path)
    video_id = project.contents[0].id
    pack = project.packs[-1]
    with TestClient(create_app(store.root)) as client:
        base = "/api/projects/" + project.id
        def mutate(path, body=None, method="post", expected=200):
            current = client.get(base).json()
            response = getattr(client, method)(base + path, json={"expected_version": current["version"], **(body or {})})
            assert response.status_code == expected, response.text
            return response.json()
        series = mutate("/series", {"title": "Managed group"})["series"][-1]
        mutate("/series/" + series["id"], {"title": "Renamed group"}, method="patch")
        mutate("/contents/" + video_id, {"series_id": series["id"]}, method="patch")
        mutate("/contents/" + video_id, {"title": "Renamed video"}, method="patch")
        mutate("/contents/" + video_id + "/trash")
        selection = mutate("", {"active_content_id": video_id}, method="patch", expected=410)
        assert selection["error"]["code"] == "content_trashed"
        scoped = mutate("/selection", {"content_id": video_id, "resource_ids": []}, expected=410)
        assert scoped["error"]["code"] == "content_trashed"
        for suffix, body, method in [
            ("/contents/" + video_id, {"title": "Must not update"}, "patch"),
            ("/contents/" + video_id + "/directions/generate", {"instruction": "A new concept"}, "post"),
            ("/contents/" + video_id + "/production/generate", {}, "post"),
            ("/packs/" + pack.id, {"revision": pack.revision, "production_brief": "Must not overwrite"}, "post"),
        ]:
            result = mutate(suffix, body, method=method, expected=410)
            assert result["error"]["code"] == "content_trashed"
        export = client.get(base + f"/packs/{pack.id}/export?revision={pack.revision}&format=csv")
        assert export.status_code == 200 and "Ready?" in export.text
        mutate("/series/" + series["id"] + "/trash")
        assert mutate("/contents", {"title": "Cannot create", "series_id": series["id"]}, expected=410)["error"]["code"] == "series_trashed"
        assert mutate("/topics/suggest", {"series_id": series["id"]}, expected=410)["error"]["code"] == "series_trashed"
        restored = mutate("/contents/" + video_id + "/restore")
        assert restored["contents"][0]["series_id"] is None
        assert restored["active_content_id"] is None
        assert restored["contents"][0]["approved_direction_id"]
