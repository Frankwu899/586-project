"""Offline capture-region regression coverage; no API calls or accuracy claims."""
from dataclasses import replace
import subprocess

import pytest
from pydantic import ValidationError

from backend.app.content_region import (ContentRegion, Rect, RegionUpdate, get_content_region,
    region_from_database, save_content_region, suggest_content_region)
from backend.app.media_preparation import PreparationSettings, prepare_media
from backend.app.service import WorkflowService
from backend.app.storage import WorkflowError


def source(tmp_path):
    path = tmp_path / 'screen.mp4'
    # Bright static edge chrome and a valid stationary price panel inside content.
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=s=160x160:r=10:d=1,drawbox=x=0:y=0:w=iw:h=32:c=white:t=fill,drawbox=x=0:y=128:w=iw:h=32:c=white:t=fill,drawbox=x=60:y=60:w=40:h=30:c=white:t=fill',
                    '-c:v', 'libx264', str(path)], check=True)
    return path


def uploaded(tmp_path):
    svc = WorkflowService(tmp_path / 'store')
    state = svc.create('Content area test')
    path = source(tmp_path)
    with path.open('rb') as stream:
        state = svc.upload(state.task.task_id, state.task.version, path.name, stream)
    return svc, state, state.videos[-1]


def test_normalized_rectangles_reject_out_of_bounds_nonfinite_and_empty():
    for value in [dict(x=.9, y=0, width=.2, height=1), dict(x=0, y=0, width=0, height=1),
                  dict(x=float('nan'), y=0, width=1, height=1)]:
        with pytest.raises(ValidationError):
            Rect(**value)


def test_region_save_is_versioned_atomic_and_noop_preserves_revision(tmp_path):
    svc, state, video = uploaded(tmp_path)
    initial = get_content_region(svc.store, state.task.task_id, video)
    assert initial.revision == 0 and initial.source_sha256 == video.content_sha256
    body = RegionUpdate(expected_version=state.task.version, expected_revision=0,
                        crop=Rect(x=0, y=.2, width=1, height=.6))
    saved = save_content_region(svc, state.task.task_id, video.video_id, body)
    region = get_content_region(svc.store, state.task.task_id, video)
    assert region.revision == 1
    assert saved.task.version == state.task.version + 1
    unchanged = save_content_region(svc, state.task.task_id, video.video_id,
                                   body.model_copy(update={'expected_version': saved.task.version, 'expected_revision': 1}))
    assert unchanged.task.version == saved.task.version
    with pytest.raises(WorkflowError, match='changed'):
        save_content_region(svc, state.task.task_id, video.video_id, body)
    with svc.store._connect() as db:
        db.execute('BEGIN IMMEDIATE')
        assert region_from_database(svc.store, state.task.task_id, video) == region
    # Region reads/restarts do not move or alter the imported original.
    restored = WorkflowService(tmp_path / 'store')
    assert get_content_region(restored.store, state.task.task_id, video) == region
    assert restored.media.path_for(video).read_bytes() == source_bytes(tmp_path)


def source_bytes(tmp_path):
    return (tmp_path / 'screen.mp4').read_bytes()


def test_preparation_crops_masks_and_retains_original_hash_timing(tmp_path):
    svc, state, video = uploaded(tmp_path)
    original = svc.media.path_for(video).read_bytes()
    region = ContentRegion(revision=1, source_sha256=video.content_sha256,
        crop=Rect(x=0, y=.2, width=1, height=.6), exclusions=[Rect(x=.375, y=.375, width=.25, height=.1875)])
    with prepare_media(svc.media.path_for(video), video, PreparationSettings(max_frames=3), content_region=region.model_dump()) as prepared:
        assert prepared.source_sha256 == video.content_sha256
        assert prepared.content_region_fingerprint == region.fingerprint
        assert [(frame.width, frame.height) for frame in prepared.frames] == [(160, 96)] * 3
        assert [frame.frame_index for frame in prepared.frames] == [0, 5, 9]
        # The explicit interior mask is black in the prepared crop only.
        output = tmp_path / 'cropped.gray'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(prepared.frames[0].path), '-vf', 'format=gray', '-f', 'rawvideo', str(output)], check=True)
        data = output.read_bytes()
        center = [data[y*160+x] for y in range(34, 48) for x in range(68, 90)]
        assert max(center) < 15
    assert svc.media.path_for(video).read_bytes() == original
    assert video.frame_timing.frame_count == 10


def test_suggestion_only_edge_bars_never_interior_stationary_panel(tmp_path):
    svc, state, video = uploaded(tmp_path)
    suggestion = suggest_content_region(svc.media.path_for(video), video, svc.media.settings)
    assert suggestion['suggestion_found']
    assert suggestion['requires_review']
    assert .18 <= suggestion['crop']['y'] <= .22
    assert .57 <= suggestion['crop']['height'] <= .64
    assert suggestion['crop']['x'] == 0 and suggestion['crop']['width'] == 1
    assert suggestion['exclusions'] == []
    assert get_content_region(svc.store, state.task.task_id, video).revision == 0


def test_region_cache_identity_changes_even_when_original_bytes_do_not(tmp_path):
    from test_providers import recognition_input, adapter_for
    # Reuse the offline alternate-provider fixture without calling any provider API.
    request, prepared = recognition_input.__wrapped__(tmp_path)
    first = ContentRegion(source_sha256=request.video.content_sha256)
    changed = first.model_copy(update={'revision': 1, 'crop': Rect(x=0, y=.1, width=1, height=.9)})
    adapter, vision, speech = adapter_for((request, replace(prepared, content_region_fingerprint=first.fingerprint)), cache_dir=tmp_path / 'cache')
    result = adapter.analyze(replace(request, content_region=first.model_dump()))
    assert result.status == 'succeeded'
    adapter.prepare = lambda *_: replace(prepared, content_region_fingerprint=changed.fingerprint)
    result = adapter.analyze(replace(request, content_region=changed.model_dump()))
    assert result.status == 'succeeded'
    assert vision.calls == 2
    assert speech.calls == 1, "Unchanged source audio must not be billed again after a crop"
    assert len(list((tmp_path / 'cache').glob('speech-*.json'))) == 1
    assert len(list((tmp_path / 'cache').glob('*.json'))) == 3


def test_region_changes_invalidate_current_analysis_but_preserve_history(tmp_path):
    from backend.app.models import AnalysisResult
    svc, state, video = uploaded(tmp_path)
    class OfflineRecognition:
        def analyze(self, request):
            return AnalysisResult(analysis_id='analysis_region_test', task_id=request.task_id,
                video_id=request.video.video_id, duration_seconds=request.video.duration_seconds,
                frame_count=request.video.frame_timing.frame_count, status='succeeded',
                origin={'kind': 'provider', 'description': 'Offline synthetic boundary check.'},
                empty_result_reason='Empty synthetic fixture, not a real recognition result.')
    svc.real_recognition = OfflineRecognition()
    state = svc.recognize(state.task.task_id, state.task.version)
    state = svc.confirm_analysis(state.task.task_id, state.task.version, state.task.current_analysis)
    original = state.analyses[0].model_dump()
    saved = save_content_region(svc, state.task.task_id, video.video_id,
        RegionUpdate(expected_version=state.task.version, expected_revision=0,
                     crop=Rect(x=0, y=.2, width=1, height=.6)))
    assert saved.task.current_analysis is None
    assert saved.analyses[0].model_dump() == original
    assert saved.videos[0].content_sha256 == video.content_sha256


def test_router_rejects_cross_task_asset_and_invalid_crop(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.api import create_app
    from backend.app.content_region import create_content_region_router
    svc, state, video = uploaded(tmp_path)
    app = create_app(service=svc)
    # Safe to mount explicitly for this contract test during app integration.
    app.include_router(create_content_region_router(svc))
    client = TestClient(app)
    other = svc.create('Other task')
    endpoint = f'/api/tasks/{state.task.task_id}/videos/{video.video_id}/content-region'
    assert client.get(endpoint).json()['revision'] == 0
    assert client.get(f'/api/tasks/{other.task.task_id}/videos/{video.video_id}/content-region').status_code == 404
    response = client.post(endpoint, json={'expected_version': state.task.version, 'expected_revision': 0,
        'crop': {'x': .9, 'y': 0, 'width': 1, 'height': 1}, 'exclusions': []})
    assert response.status_code == 422
    assert client.get(endpoint).json()['revision'] == 0


def test_content_area_does_not_block_or_discard_an_unrelated_idea_draft(tmp_path):
    from backend.app.models import EditorDraftUpdate
    svc, state, video = uploaded(tmp_path)
    draft = svc.store.get_editor_draft(state.task.task_id, 'idea')
    saved_draft = svc.store.save_editor_draft(state.task.task_id, 'idea', EditorDraftUpdate(
        expected_draft_version=draft.draft_version, base_refs=draft.base_refs,
        content={**draft.content, 'hook': 'Keep this independently written opening.'}))
    assert saved_draft.has_pending_changes
    saved = save_content_region(svc, state.task.task_id, video.video_id,
        RegionUpdate(expected_version=state.task.version, expected_revision=0,
                     crop=Rect(x=0, y=.2, width=1, height=.6)))
    assert saved.task.version == state.task.version + 1
    assert svc.store.get_editor_draft(state.task.task_id, 'idea') == saved_draft


def test_rotated_hevc_crop_uses_displayed_coordinates_not_encoded_dimensions(tmp_path):
    from test_media import make_hevc_fixture
    from backend.app.media import MediaStore
    path = make_hevc_fixture(tmp_path / 'source-hevc.mp4', variable=True, rotation=True)
    store = MediaStore(tmp_path / 'rotated-store')
    with path.open('rb') as stream:
        video = store.save_upload('task_rotated', 'rotated.mp4', stream)
    region = ContentRegion(source_sha256=video.content_sha256, revision=1,
                           crop=Rect(x=0, y=.25, width=1, height=.5))
    with prepare_media(store.path_for(video), video, PreparationSettings(max_frames=2), content_region=region.model_dump()) as prepared:
        assert [(frame.width, frame.height) for frame in prepared.frames] == [(48, 32), (48, 32)]
        assert [frame.frame_index for frame in prepared.frames] == [0, 7]
