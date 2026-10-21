"""v0.6 recovery, atomic editor gates, language choice and source deletion."""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api import create_app
from backend.app.models import EditorDraftUpdate
from backend.app.service import WorkflowService, ref
from backend.app.storage import TaskStore, WorkflowError
from test_workflow import directions, outputs, ready


def save_draft(service, state, scope, change):
    draft = service.store.get_editor_draft(state.task.task_id, scope)
    content = copy.deepcopy(draft.content)
    change(content)
    return service.store.save_editor_draft(state.task.task_id, scope, EditorDraftUpdate(
        expected_draft_version=draft.draft_version, base_refs=draft.base_refs, content=content))


def test_analysis_draft_survives_restart_blocks_creative_and_applies_atomically(tmp_path):
    service = WorkflowService(tmp_path)
    state = ready(service)
    task_id = state.task.task_id
    draft = save_draft(service, state, 'analysis', lambda content: content['events'][0].update(description='Corrected synthetic cup observation'))
    assert draft.has_pending_changes
    assert service.store.get(task_id).task.version == state.task.version
    reopened = WorkflowService(tmp_path)
    assert reopened.store.get_editor_draft(task_id, 'analysis') == draft
    with pytest.raises(WorkflowError, match='pending analysis'):
        reopened.generate_directions(task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    with pytest.raises(WorkflowError, match='pending analysis'):
        reopened.recognize(task_id, state.task.version)
    with pytest.raises(WorkflowError, match='does not match'):
        reopened.correct_analysis(task_id, state.task.version, state.task.current_analysis,
            [{'event_id': draft.content['events'][0]['event_id'], 'description': 'An unacknowledged other change'}], [], draft.draft_version)
    assert reopened.store.get(task_id).task.version == state.task.version
    applied = reopened.correct_analysis(task_id, state.task.version, state.task.current_analysis,
        [{'event_id': draft.content['events'][0]['event_id'], 'description': draft.content['events'][0]['description']}], [], draft.draft_version)
    checkpoint = reopened.store.get_editor_draft(task_id, 'analysis')
    assert not checkpoint.has_pending_changes and not checkpoint.conflict
    assert checkpoint.base_refs['analysis'] == applied.task.current_analysis
    assert not applied.analyses[-1].review.user_confirmed
    assert state.analyses[0].events[0].description != applied.analyses[-1].events[0].description


def test_draft_version_conflict_never_overwrites_saved_text(tmp_path):
    service = WorkflowService(tmp_path)
    state = directions(service)
    scope = 'direction-' + state.directions[0].direction_id
    original = service.store.get_editor_draft(state.task.task_id, scope)
    saved = save_draft(service, state, scope, lambda content: content.update(hook='First browser change'))
    with pytest.raises(WorkflowError) as error:
        service.store.save_editor_draft(state.task.task_id, scope, EditorDraftUpdate(
            expected_draft_version=original.draft_version, base_refs=original.base_refs,
            content={**original.content, 'hook': 'Late second browser write'}))
    assert error.value.code == 'editor_draft_conflict'
    assert service.store.get_editor_draft(state.task.task_id, scope).content == saved.content


def test_manual_direction_save_marks_auxiliary_stale_and_requires_exact_checkpoint(tmp_path):
    service = WorkflowService(tmp_path)
    state = outputs(service)
    direction = next(item for item in state.directions if ref(item) == state.task.selected_direction)
    scope = 'direction-' + direction.direction_id
    draft = save_draft(service, state, scope, lambda content: content.update(hook='Original hand-written product opening'))
    task_id = state.task.task_id
    for action in (
        lambda: service.approve_direction(task_id, state.task.version, direction.direction_id, direction.revision, state.task.current_brief, state.task.current_analysis),
        lambda: service.generate_outputs(task_id, state.task.version, ref(direction), state.task.current_brief, state.task.current_analysis),
        lambda: service.refine_direction(task_id, state.task.version, direction.direction_id, direction.revision, state.task.current_brief, state.task.current_analysis, 'Make it presenter-free'),
    ):
        with pytest.raises(WorkflowError) as error:
            action()
        assert error.value.code == 'editor_pending_changes'
    assert service.store.get(task_id).task.selected_direction == ref(direction)
    edited = service.edit_direction(task_id, state.task.version, direction.direction_id, direction.revision, draft.content, draft.draft_version)
    current = edited.directions[-1]
    assert current.auxiliary_status == 'needs_review' and current.approval_status == 'draft'
    assert current.rationale == direction.rationale
    assert not service.store.get_editor_draft(task_id, scope).has_pending_changes
    edited = service.approve_direction(task_id, edited.task.version, current.direction_id, current.revision, edited.task.current_brief, edited.task.current_analysis)
    assert edited.task.selected_direction == ref(current)


def test_production_draft_survives_switch_and_blocks_regeneration_and_export(tmp_path):
    service = WorkflowService(tmp_path)
    state = outputs(service)
    task_id = state.task.task_id
    draft = save_draft(service, state, 'production', lambda content: content['rows'][0].update(dialogue='Saved recoverable draft'))
    other = service.create('Another task')
    assert service.store.get(other.task.task_id).task.title == 'Another task'
    assert service.store.get_editor_draft(task_id, 'production') == draft
    with pytest.raises(WorkflowError) as error:
        service.generate_outputs(task_id, state.task.version, state.task.selected_direction, state.task.current_brief, state.task.current_analysis)
    assert error.value.code == 'editor_pending_changes'
    with pytest.raises(WorkflowError):
        service.export(task_id, 'storyboard.csv')
    saved = service.edit_outputs(task_id, state.task.version, state.task.current_production_brief, state.task.current_storyboard,
        draft.content['brief_fields'], draft.content['rows'], draft.draft_version)
    assert 'Saved recoverable draft' in service.export(task_id, 'storyboard.csv')
    assert saved.storyboards[-1].bundle_id == saved.production_briefs[-1].bundle_id
    assert saved.storyboards[-1].bundle_id != state.storyboards[-1].bundle_id


def test_formal_noops_preserve_revisions_approval_and_task_version(tmp_path):
    service = WorkflowService(tmp_path)
    state = outputs(service)
    task_id = state.task.task_id
    direction = next(item for item in state.directions if ref(item) == state.task.selected_direction)
    no_direction = service.edit_direction(task_id, state.task.version, direction.direction_id, direction.revision, {'hook': direction.hook})
    assert no_direction == state
    no_analysis = service.correct_analysis(task_id, state.task.version, state.task.current_analysis, [], [])
    assert no_analysis == state
    draft = service.store.get_editor_draft(task_id, 'production')
    no_production = service.edit_outputs(task_id, state.task.version, state.task.current_production_brief, state.task.current_storyboard,
        draft.content['brief_fields'], draft.content['rows'], draft.draft_version)
    assert no_production == state


def test_new_draft_during_generation_discards_provider_result_without_losing_text(tmp_path):
    service = WorkflowService(tmp_path)
    state = ready(service)
    delegate = service.creative
    class ConcurrentEditor:
        def generate_directions(self, brief, analysis):
            save_draft(service, state, 'analysis', lambda content: content['events'][0].update(description='Typed during generation'))
            return delegate.generate_directions(brief, analysis)
    service.creative = ConcurrentEditor()
    result = service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert result.jobs[-1].error.code == 'stale_result'
    assert not result.directions
    assert service.store.get_editor_draft(state.task.task_id, 'analysis').content['events'][0]['description'] == 'Typed during generation'


def test_language_requires_explicit_choice_and_change_keeps_review_history(tmp_path):
    service = WorkflowService(tmp_path)
    empty = service.create('Explicit choice')
    assert empty.task.generation_language is None
    state = service.load_sample(empty.task.task_id, empty.task.version)
    state = service.recognize(state.task.task_id, state.task.version)
    state = service.confirm_analysis(state.task.task_id, state.task.version, state.task.current_analysis)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert error.value.code == 'generation_language_required'
    state = outputs(service)
    analysis_before = [item.model_dump() for item in state.analyses]
    changed = service.set_language(state.task.task_id, state.task.version, 'Chinese')
    assert changed.task.generation_language == 'Chinese'
    assert [item.model_dump() for item in changed.analyses] == analysis_before
    assert changed.task.selected_direction is None
    assert all(item.currentness == 'outdated' for item in [*changed.directions, *changed.production_briefs, *changed.storyboards])


def test_delete_media_tombstone_preserves_history_removes_bytes_and_denies_fetch(tmp_path):
    service = WorkflowService(tmp_path)
    state = outputs(service)
    video = state.videos[0]
    original = service.media.path_for(video)
    client = TestClient(create_app(tmp_path, service=service))
    response = client.post(f'/api/tasks/{state.task.task_id}/videos/{video.video_id}/delete', json={'expected_version': state.task.version})
    assert response.status_code == 200, response.text
    deleted = service.store.get(state.task.task_id)
    assert deleted.videos[0].deleted_at is not None
    assert not original.exists()
    assert deleted.task.current_video_id is None and deleted.task.current_analysis is None
    assert deleted.briefs == state.briefs and deleted.analyses == state.analyses
    assert deleted.task.selected_direction is None
    assert client.get(f'/api/tasks/{state.task.task_id}/media/{video.video_id}').status_code == 410
    assert 'HISTORICAL VERSION' in service.export(state.task.task_id, 'brief.md')
    assert 'reference media deleted' in service.export(state.task.task_id, 'brief.md')


def test_v05_archive_preserves_exact_source_and_historical_approval(tmp_path):
    source = Path('examples/v0.5.sample-task.json').read_text()
    old = json.loads(source)
    task_id = old['task']['task_id']
    store = TaskStore(tmp_path)
    with sqlite3.connect(store.path) as db:
        db.execute('INSERT INTO tasks VALUES(?,?,?)', (task_id, old['task']['version'], source))
    migrated = TaskStore(tmp_path).get(task_id)
    assert migrated.task.schema_version == '0.6.0'
    assert migrated.task.generation_language is None
    assert migrated.task.selected_direction.model_dump() == old['task']['selected_direction']
    assert [(item.approval_status, item.approved_at.isoformat() if item.approved_at else None) for item in migrated.directions] == [(item['approval_status'], item['approved_at'].replace('Z','+00:00') if item['approved_at'] else None) for item in old['directions']]
    with sqlite3.connect(store.path) as db:
        archived = db.execute('SELECT original_payload, original_sha256, source_schema_version,target_schema_version FROM task_migration_archive').fetchone()
    assert archived == (source, hashlib.sha256(source.encode()).hexdigest(), '0.5.0', '0.6.0')


def test_historical_export_filenames_and_content_use_exact_output_version(tmp_path):
    service = WorkflowService(tmp_path)
    state = outputs(service)
    task_id = state.task.task_id
    old = state.production_briefs[-1]
    state = service.generate_outputs(task_id, state.task.version, state.task.selected_direction, state.task.current_brief, state.task.current_analysis)
    client = TestClient(create_app(tmp_path, service=service))
    historical = client.get(f'/api/tasks/{task_id}/export/brief.md', params={'output_id': old.output_id, 'revision': old.revision})
    assert historical.status_code == 200
    assert f'historical-brief-{old.output_id}-r{old.revision}.md' in historical.headers['content-disposition']
    assert 'HISTORICAL VERSION' in historical.text
    assert f'output {old.output_id} revision {old.revision}' in historical.text
    state = service.set_language(task_id, state.task.version, 'Chinese')
    latest = client.get(f'/api/tasks/{task_id}/export/storyboard.csv')
    assert latest.status_code == 200
    assert 'historical-storyboard-' in latest.headers['content-disposition']
    assert 'HISTORICAL VERSION' in latest.text
