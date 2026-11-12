"""Project folders preserve drafts, history and originals across lifecycle changes."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3
import threading

import pytest

from backend.app.project_workspace.models import (ContentItem, Direction, EvidenceEvent, EvidenceRevision, Fact,
    InputManifest, Job, Message, ProductionPack, Resource)
from backend.app.project_workspace.store import ProjectStore
from backend.app.service import WorkflowService
from backend.app.workflow_errors import WorkflowError
from test_workflow import outputs


def populated(store):
    project = store.create("Travel mug")
    folder = store.project_dir(project.id)
    source = folder / "sources/media/resource_clip/clip.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"private original bytes")
    proxy = folder / "cache/playback/clip.mp4"
    proxy.parent.mkdir(parents=True)
    proxy.write_bytes(b"rebuildable proxy")
    durable = folder / "evidence/transcript.json"
    durable.write_text('{"corrected":"A corrected transcript"}')

    def add(state):
        state.messages.append(Message(role="user", text="Make a commuter video."))
        state.conversation_draft = "Incomplete thought"
        state.resources.append(Resource(id="resource_clip", name="clip.mp4", kind="video",
            original_path="sources/media/resource_clip/clip.mp4", playback_path="cache/playback/clip.mp4",
            sha256=hashlib.sha256(source.read_bytes()).hexdigest(), size_bytes=source.stat().st_size,
            status="ready", evidence=[EvidenceRevision(revision=1,
                events=[EvidenceEvent(id="speech_one", kind="speech", text="A corrected transcript", start_seconds=0, end_seconds=2)])]))
        direction = Direction(id="direction_one", title="Bag test", concept="Show the claim", approved=True, approved_at=state.created_at)
        state.contents.append(ContentItem(id="content_one", title="One video", directions=[direction],
            approved_direction_id=direction.id, approved_direction_revision=1))
        state.packs.append(ProductionPack(content_id="content_one", inputs=InputManifest(direction_id=direction.id, direction_revision=1),
            production_brief="Shoot brief", script="Hello", storyboard="Scene one", shot_list="Close-up"))
        state.editor_drafts["production"] = {"script": "Unfinished edit"}
        state.workspace = "production"
        state.active_content_id = "content_one"
    return store.update(project.id, project.version, add)


def test_restart_preserves_content_and_noop_version(tmp_path):
    store = ProjectStore(tmp_path)
    project = populated(store)
    assert store.update(project.id, project.version, lambda item: setattr(item, "title", item.title)) == project
    restarted = ProjectStore(tmp_path)
    assert restarted.get(project.id) == project
    assert restarted.get(project.id).conversation_draft == "Incomplete thought"
    assert restarted.get(project.id).editor_drafts["production"]["script"] == "Unfinished edit"
    assert (restarted.project_dir(project.id) / "project.json").is_file()


def test_brief_draft_version_changes_once_only_for_draft_content(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Independent brief version")
    assert project.brief_draft_version == 1
    project = store.update(project.id, project.version, lambda item: item.brief_draft.append(
        Fact(id="fact_audience", key="audience", value="Commuters")))
    assert project.brief_draft_version == 2
    project = store.update(project.id, project.version, lambda item: setattr(item, "workspace", "resources"))
    assert project.brief_draft_version == 2

    def revise(item):
        item.brief_draft[0].value = "Morning commuters"
        item.brief_draft[0].status = "confirmed"
        item.title = "Revised assignment"
    project = store.update(project.id, project.version, revise)
    assert project.brief_draft_version == 3
    assert ProjectStore(tmp_path).get(project.id).brief_draft_version == 3


def test_callbacks_cannot_forge_brief_counter_and_noops_restore_original_draft(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("No-op draft")
    same = store.update(project.id, project.version, lambda item: setattr(item, "brief_draft_version", 900))
    assert same == project

    def declined(item):
        item.brief_draft.append(Fact(key="goal", value="Discard this proposed write"))
        item.brief_draft_version = 1000
        return False
    assert store.update(project.id, project.version, declined) == project
    renamed = store.update(project.id, project.version, lambda item: setattr(item, "title", "Renamed"))
    assert renamed.brief_draft_version == 1
    with pytest.raises(WorkflowError) as error:
        store.update(project.id, project.version, lambda item: item.brief_draft.append(Fact(key="goal", value="Stale")))
    assert error.value.code == "project_version_conflict"
    assert store.get(project.id) == renamed


def test_editor_versions_are_independent_and_survive_delete_recreate_and_restart(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Editor channels")
    project = store.update(project.id, project.version, lambda item: item.editor_drafts.update(
        {"production-one": {"script": "First"}, "direction-one": {"hook": "Hook"}}))
    assert project.editor_draft_versions == {"production-one": 1, "direction-one": 1}
    project = store.update(project.id, project.version, lambda item: item.editor_drafts["production-one"].update(
        {"script": "Second", "storyboard": "Scene"}))
    assert project.editor_draft_versions == {"production-one": 2, "direction-one": 1}
    project = store.update(project.id, project.version, lambda item: item.editor_drafts.pop("production-one"))
    assert project.editor_draft_versions["production-one"] == 3
    project = store.update(project.id, project.version, lambda item: item.editor_drafts.update({"production-one": {"script": "Third"}}))
    assert project.editor_draft_versions == {"production-one": 4, "direction-one": 1}
    assert ProjectStore(tmp_path).get(project.id).editor_draft_versions == project.editor_draft_versions


def test_editor_counter_forgery_and_declined_changes_do_not_create_revisions(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("No forged editor revisions")
    project = store.update(project.id, project.version, lambda item: item.editor_drafts.update({"production-one": {"script": "Saved"}}))
    assert store.update(project.id, project.version, lambda item: setattr(item, "editor_draft_versions", {"production-one": 900})) == project
    assert store.update(project.id, project.version, lambda item: item.editor_drafts.update({"production-one": {"script": "Saved"}})) == project
    def decline(item):
        item.editor_drafts["production-one"]["script"] = "Discarded"
        item.editor_draft_versions = {}
        return False
    assert store.update(project.id, project.version, decline) == project


def test_trash_blocks_stale_writes_and_restore_keeps_files(tmp_path):
    store = ProjectStore(tmp_path)
    project = populated(store)
    original = store.project_dir(project.id) / project.resources[0].original_path
    trashed = store.trash(project.id, project.version)
    assert store.list() == [] and store.list(include_trashed=True) == [trashed]
    with pytest.raises(WorkflowError) as error:
        store.update(project.id, project.version, lambda item: setattr(item, "title", "Lost update"))
    assert error.value.code == "project_trashed"
    restored = ProjectStore(tmp_path).restore(project.id, trashed.version)
    assert restored.messages == project.messages and restored.packs == project.packs
    assert original.read_bytes() == b"private original bytes"


def test_duplicate_is_independent_and_archives_approval_provenance(tmp_path):
    store = ProjectStore(tmp_path)
    project = populated(store)
    (tmp_path / "provider-budget.sqlite3").write_bytes(b"do not copy")
    copied = store.duplicate(project.id, project.version)
    assert copied.id != project.id and copied.duplicated_from == project.id
    assert copied.messages == project.messages and copied.resources[0].evidence == project.resources[0].evidence
    assert not copied.contents[0].directions[0].approved and copied.packs[0].needs_review
    copied_source = store.project_dir(copied.id) / copied.resources[0].original_path
    copied_source.write_bytes(b"changed duplicate")
    store.update(copied.id, copied.version, lambda item: setattr(item, "conversation_draft", "Different thought"))
    assert store.get(project.id) == project
    assert (store.project_dir(project.id) / project.resources[0].original_path).read_bytes() == b"private original bytes"
    archived = json.loads((store.project_dir(copied.id) / "evidence/duplicated-project-snapshot.json").read_text())
    assert archived["contents"][0]["directions"][0]["approved"] is True
    assert not (store.project_dir(copied.id) / "provider-budget.sqlite3").exists()
    assert not (store.project_dir(copied.id) / "cache/playback/clip.mp4").exists()


def test_lost_response_retries_do_not_toggle_trash_or_bypass_intervening_change(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Recovery")
    trashed = store.trash(project.id, project.version)
    assert store.trash(project.id, project.version) == trashed
    restored = store.restore(project.id, trashed.version)
    assert store.restore(project.id, trashed.version) == restored
    with pytest.raises(WorkflowError):
        store.trash(project.id, project.version)
    changed = store.update(project.id, restored.version, lambda item: setattr(item, "title", "Changed"))
    with pytest.raises(WorkflowError):
        store.restore(project.id, trashed.version)
    assert store.get(project.id) == changed


def test_missing_source_prevents_incomplete_duplicate(tmp_path):
    store = ProjectStore(tmp_path)
    project = populated(store)
    (store.project_dir(project.id) / project.resources[0].original_path).unlink()
    with pytest.raises(WorkflowError) as error:
        store.duplicate(project.id, project.version)
    assert error.value.code == "duplicate_missing_source"
    assert len(store.list()) == 1
    assert not list(store.projects.glob(".stage-*"))


def test_cache_clear_keeps_durable_sources_corrections_and_outputs(tmp_path):
    store = ProjectStore(tmp_path)
    project = populated(store)
    cleared = store.clear_cache(project.id, project.version)
    assert cleared.resources[0].playback_path is None
    assert cleared.resources[0].evidence == project.resources[0].evidence
    assert cleared.packs == project.packs and cleared.messages == project.messages
    folder = store.project_dir(project.id)
    assert (folder / project.resources[0].original_path).read_bytes() == b"private original bytes"
    assert (folder / "evidence/transcript.json").is_file()
    assert list((folder / "cache").iterdir()) == []


def test_restart_fails_jobs_without_replay_and_preserves_completed_work(tmp_path):
    store = ProjectStore(tmp_path)
    project = populated(store)
    project = store.update(project.id, project.version, lambda item: item.jobs.append(Job(kind="analysis", status="running")))
    restarted = ProjectStore(tmp_path).get(project.id)
    assert restarted.jobs[0].status == "failed" and "retry explicitly" in restarted.jobs[0].error
    assert restarted.resources[0].evidence == project.resources[0].evidence
    assert ProjectStore(tmp_path).get(project.id).version == restarted.version


def test_restart_closes_orphan_conversation_requests_without_losing_user_message(tmp_path):
    store = ProjectStore(tmp_path)
    project = populated(store)
    project = store.update(project.id, project.version, lambda item: item.editor_drafts.update(
        {"conversation_requests": {item.messages[0].id: {"status": "running", "context": {}}}}))
    reopened = ProjectStore(tmp_path).get(project.id)
    assert reopened.messages[0] == project.messages[0]
    assert reopened.messages[-1].role == "assistant" and reopened.messages[-1].status == "failed"
    assert "conversation_requests" not in reopened.editor_drafts
    assert ProjectStore(tmp_path).get(project.id) == reopened


def test_active_jobs_block_trash_duplicate_and_cache_clear(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Busy")
    project = store.update(project.id, project.version, lambda item: item.jobs.append(Job(kind="chat")))
    for action in (store.trash, store.duplicate, store.clear_cache):
        with pytest.raises(WorkflowError) as error:
            action(project.id, project.version)
        assert error.value.code == "project_busy"


def test_optimistic_update_allows_only_one_concurrent_writer(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Original")
    barrier = threading.Barrier(2)

    def rename(title):
        barrier.wait()
        try:
            return store.update(project.id, project.version, lambda item: setattr(item, "title", title)).title
        except WorkflowError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(rename, ["First", "Second"]))
    assert results.count("project_version_conflict") == 1
    assert store.get(project.id).version == 2


def test_invalid_paths_and_symlinks_cannot_escape_project(tmp_path):
    store = ProjectStore(tmp_path / "library")
    project = store.create("Safe")
    for value in ("../outside", "/tmp/outside", "project/../../outside", "a\\b"):
        with pytest.raises(WorkflowError):
            store.resolve_path(project.id, value)
    external = tmp_path / "external"
    external.mkdir()
    (store.project_dir(project.id) / "sources/linked").symlink_to(external, target_is_directory=True)
    with pytest.raises(WorkflowError):
        store.resolve_path(project.id, "sources/linked/secret")


def test_failed_import_does_not_publish_half_project(tmp_path):
    from backend.app.project_workspace.models import Project
    store = ProjectStore(tmp_path)

    def fail(stage):
        (stage / "partial.txt").write_text("partial")
        raise OSError("Disk full")
    with pytest.raises(OSError):
        store.import_project(Project(title="Partial"), fail)
    assert store.list() == [] and not list(store.projects.glob(".stage-*"))


@pytest.mark.parametrize("corruption", ["sqlite", "payload"])
def test_corrupt_project_is_isolated_without_changing_its_files(tmp_path, corruption):
    store = ProjectStore(tmp_path)
    healthy = populated(store)
    damaged = store.create("Damaged project")
    folder = store.project_dir(damaged.id)
    original = folder / "sources/documents/keep.txt"
    original.write_bytes(b"Preserve this original")
    database = folder / "project.sqlite3"
    backup = database.read_bytes()
    if corruption == "sqlite":
        database.write_bytes(b"broken SQLite bytes containing private source information")
    else:
        with sqlite3.connect(database) as db:
            db.execute("UPDATE project SET payload='not a valid project record'")
    corrupted_bytes = database.read_bytes()
    assert store.list() == [healthy]
    assert len(store.library_errors) == 1 and damaged.id in store.library_errors[0]
    assert "private source information" not in store.library_errors[0]
    reopened = ProjectStore(tmp_path)
    assert reopened.list() == [healthy] and len(reopened.library_errors) == 1
    with pytest.raises(WorkflowError) as error:
        reopened.get(damaged.id)
    assert error.value.code == "project_unreadable"
    assert database.read_bytes() == corrupted_bytes
    assert original.read_bytes() == b"Preserve this original"
    database.write_bytes(backup)
    assert len(reopened.list()) == 2 and reopened.library_errors == []


def test_migration_preserves_legacy_history_drafts_and_originals_without_mutating_source(tmp_path):
    legacy = WorkflowService(tmp_path)
    state = outputs(legacy)
    unrelated = legacy.create("Unrelated")
    draft = legacy.store.get_m2_draft(state.task.task_id)
    with sqlite3.connect(legacy.store.path) as db:
        db.execute("INSERT INTO structure_runs VALUES ('structure_one',?,?,?,?,1,?)", (state.task.task_id,
            state.task.current_video_id, state.task.current_analysis.id, state.task.current_analysis.revision, '{"private":"retained graph"}'))
        db.execute("INSERT INTO structure_history VALUES ('structure_one',1,?)", ('{"private":"retained history"}',))
    before_db = legacy.store.path.read_bytes()
    media = {path.name: path.read_bytes() for path in legacy.media.root.iterdir() if path.is_file()}
    store = ProjectStore(tmp_path)
    migrated = store.migrate_legacy(legacy)
    project = next(item for item in migrated if item.legacy_task_id == state.task.task_id)
    assert len(migrated) == 2 and store.migrate_legacy(legacy) == []
    assert project.contents[0].series_id is None and project.messages == []
    assert project.contents[0].directions[0].id == state.directions[0].direction_id
    assert project.contents[0].approved_direction_id == state.task.selected_direction.id
    assert project.packs[0].script == "" and project.packs[0].shot_list == ""
    assert project.briefs and project.resources[0].evidence
    archive = store.project_dir(project.id) / "legacy"
    assert json.loads((archive / "task-state.json").read_text()) == state.model_dump(mode="json")
    snapshots = json.loads((archive / "related-records.json").read_text())
    assert json.loads(snapshots["m2_drafts"]["rows"][0][2])["task_id"] == draft.task_id
    assert snapshots["structure_history"]["rows"][0][2] == '{"private":"retained history"}'
    assert unrelated.task.task_id not in (archive / "related-records.json").read_text()
    assert legacy.store.path.read_bytes() == before_db
    assert all((legacy.media.root / name).read_bytes() == data for name, data in media.items())
    for resource in project.resources:
        assert (store.project_dir(project.id) / resource.original_path).is_file()


def test_migration_keeps_trash_and_continues_past_a_malformed_project(tmp_path):
    legacy = WorkflowService(tmp_path)
    trashed = legacy.create("Trashed legacy")
    legacy.store.set_trashed(trashed.task.task_id, trashed.task.version, True)
    healthy = legacy.create("Healthy legacy")
    with sqlite3.connect(legacy.store.path) as db:
        db.execute("INSERT INTO tasks VALUES ('task_broken',1,'{}')")
    store = ProjectStore(tmp_path)
    imported = store.migrate_legacy(legacy)
    assert len(imported) == 2
    assert [project.legacy_task_id for project in store.list()] == [healthy.task.task_id]
    assert any(project.trashed_at for project in store.list(include_trashed=True))
    assert len(store.migration_errors) == 1 and "task_broken" in store.migration_errors[0]
    assert store.migrate_legacy(legacy) == []
    assert len(store.migration_errors) == 1


def test_migration_retains_independent_source_and_playback_clocks(tmp_path):
    from backend.app.models import FrameTiming, Origin, PlaybackRepresentation, VideoAsset
    legacy = WorkflowService(tmp_path)
    state = legacy.create("Synthetic timing metadata fixture")
    source_name, playback_name = "a" * 32 + ".mp4", "b" * 32 + ".mp4"
    # This verifies migration of recorded clocks, not decoder correspondence.
    (legacy.media.root / source_name).write_bytes(b"synthetic original fixture")
    (legacy.media.root / playback_name).write_bytes(b"synthetic derivative fixture")
    source_timing = FrameTiming(fps_numerator=1, fps_denominator=1, frame_count=2,
        media_start_seconds=5.25, frame_boundaries_seconds=[0, 1, 2], rate_mode="constant")
    playback_timing = FrameTiming(fps_numerator=10, fps_denominator=9, frame_count=2,
        media_start_seconds=0.1, frame_boundaries_seconds=[0, 0.9, 1.8], rate_mode="constant")
    video = VideoAsset(video_id="video_clock_fixture", task_id=state.task.task_id,
        input_method="legacy", storage_id=source_name,
        content_sha256=hashlib.sha256(b"synthetic original fixture").hexdigest(),
        original_file_name="timing-fixture.mp4", duration_seconds=2, frame_timing=source_timing,
        video_codec="hevc", width=2, height=2, has_audio=False, audio_codec=None, intake_status="ready",
        origin=Origin(kind="legacy", description="Synthetic migration timing fixture; not real recognition evidence"),
        playback=PlaybackRepresentation(storage_id=playback_name, video_codec="h264", audio_codec=None,
            duration_seconds=1.8, frame_timing=playback_timing))
    def add(task):
        task.videos.append(video)
        task.task.current_video_id = video.video_id
    legacy.store.update(state.task.task_id, state.task.version, add)
    store = ProjectStore(tmp_path)
    imported = store.migrate_legacy(legacy)
    assert not store.migration_errors
    resource = imported[0].resources[0]
    assert resource.media_metadata["frame_timing"] == source_timing.model_dump(mode="json")
    assert resource.media_metadata["playback_frame_timing"] == playback_timing.model_dump(mode="json")
    assert resource.duration_seconds == 2 and resource.media_metadata["playback_duration_seconds"] == 1.8
    assert (store.project_dir(imported[0].id) / resource.playback_path).read_bytes() == b"synthetic derivative fixture"
