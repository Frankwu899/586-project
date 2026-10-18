"""Exact-byte media recovery retains evidence and refuses substitutions."""
from dataclasses import replace
from io import BytesIO
import subprocess

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.media import MediaError
from backend.app.media_repair import create_media_repair_router, relink_media
from backend.app.service import WorkflowService
from backend.app.workflow_errors import WorkflowError
from scripts.generate_sample_media import generate_sample_media


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    return generate_sample_media(tmp_path_factory.mktemp("relink-source") / "source.mp4")


def saved(service, source):
    state = service.create("Recover reference")
    return service.upload(state.task.task_id, state.task.version, source.name, BytesIO(source.read_bytes()))


def test_exact_relink_restores_original_and_preserves_analysis_and_drafts(tmp_path):
    service = WorkflowService(tmp_path)
    state = service.create("Sample recovery")
    state = service.load_sample(state.task.task_id, state.task.version)
    state = service.recognize(state.task.task_id, state.task.version)
    video = state.videos[0]
    path = service.media.path_for(video)
    content = path.read_bytes()
    prior_analyses = [analysis.model_dump() for analysis in state.analyses]
    current_ref = state.task.current_analysis
    original_video = video.model_dump()
    draft = service.store.get_editor_draft(state.task.task_id, 'analysis')
    draft.content['events'][0]['description'] = 'My retained correction'
    draft = service.store.save_editor_draft(state.task.task_id, 'analysis', {
        'expected_draft_version': draft.draft_version, 'base_refs': draft.base_refs,
        'content': draft.content,
    })
    assert draft.has_pending_changes
    path.unlink()
    repaired = relink_media(service, state.task.task_id, state.task.version, video.video_id, BytesIO(content))
    assert path.read_bytes() == content
    assert repaired.task.version == state.task.version + 1
    assert repaired.task.current_analysis == current_ref
    assert [analysis.model_dump() for analysis in repaired.analyses] == prior_analyses
    assert repaired.videos[0].model_dump() == original_video
    assert service.store.get_editor_draft(state.task.task_id, "analysis") == draft
    assert not list(service.media.root.glob('.relink-*'))


def test_different_bytes_are_not_relinked_or_installed(tmp_path, source):
    service = WorkflowService(tmp_path)
    state = saved(service, source)
    path = service.media.path_for(state.videos[0])
    path.unlink()
    with pytest.raises(WorkflowError) as failure:
        relink_media(service, state.task.task_id, state.task.version, state.videos[0].video_id, BytesIO(source.read_bytes() + b"different"))
    assert failure.value.code == "media_hash_mismatch"
    assert not path.exists()
    assert service.store.get(state.task.task_id) == state


def test_relink_never_resurrects_intentional_deletion(tmp_path, source):
    service = WorkflowService(tmp_path)
    state = saved(service, source)
    video = state.videos[0]
    state = service.delete_video(state.task.task_id, state.task.version, video.video_id)
    with pytest.raises(WorkflowError) as failure:
        relink_media(service, state.task.task_id, state.task.version, video.video_id, BytesIO(source.read_bytes()))
    assert failure.value.code == "video_deleted"
    assert not (service.media.root / video.storage_id).exists()


def test_regular_existing_original_is_a_verified_noop(tmp_path, source):
    service = WorkflowService(tmp_path)
    state = saved(service, source)
    result = relink_media(service, state.task.task_id, state.task.version, state.videos[0].video_id, BytesIO(source.read_bytes()))
    assert result == state


def test_size_limit_and_stale_version_do_not_write_media(tmp_path, source):
    service = WorkflowService(tmp_path)
    state = saved(service, source)
    video = state.videos[0]
    path = service.media.path_for(video)
    path.unlink()
    service.media.settings = replace(service.media.settings, max_bytes=10)
    with pytest.raises(MediaError) as error:
        relink_media(service, state.task.task_id, state.task.version, video.video_id, BytesIO(source.read_bytes()))
    assert error.value.code == "media_too_large"
    with pytest.raises(WorkflowError) as error:
        relink_media(service, state.task.task_id, state.task.version - 1, video.video_id, BytesIO(source.read_bytes()))
    assert error.value.code == "version_conflict"
    assert not path.exists()


def test_symlink_or_occupied_original_is_never_overwritten(tmp_path, source):
    service = WorkflowService(tmp_path / 'library')
    state = saved(service, source)
    video = state.videos[0]
    path = service.media.path_for(video)
    path.unlink()
    outside = tmp_path / 'outside'
    outside.write_bytes(b'private file')
    path.symlink_to(outside)
    with pytest.raises(WorkflowError) as error:
        relink_media(service, state.task.task_id, state.task.version, video.video_id, BytesIO(source.read_bytes()))
    assert error.value.code == 'media_path_conflict'
    assert outside.read_bytes() == b'private file'
    path.unlink()
    path.write_bytes(b'different managed content')
    with pytest.raises(WorkflowError) as error:
        relink_media(service, state.task.task_id, state.task.version, video.video_id, BytesIO(source.read_bytes()))
    assert error.value.code == 'media_path_conflict'
    assert path.read_bytes() == b'different managed content'


def test_transaction_failure_removes_only_newly_installed_files(tmp_path, source, monkeypatch):
    service = WorkflowService(tmp_path)
    state = saved(service, source)
    video = state.videos[0]
    path = service.media.path_for(video)
    path.unlink()
    def fail_after_copy(_task, _version, callback):
        callback(state.model_copy(deep=True))
        raise RuntimeError('simulated commit failure')
    monkeypatch.setattr(service, '_update', fail_after_copy)
    with pytest.raises(RuntimeError):
        relink_media(service, state.task.task_id, state.task.version, video.video_id, BytesIO(source.read_bytes()))
    assert not path.exists()
    assert service.store.get(state.task.task_id) == state


def test_router_restores_missing_file_with_exact_identity(tmp_path, source):
    service = WorkflowService(tmp_path)
    state = saved(service, source)
    video = state.videos[0]
    service.media.path_for(video).unlink()
    app = create_app(service=service)
    # Standalone router can also be mounted before the shared API integration.
    if not any(getattr(route, 'path', '') == '/api/tasks/{task_id}/videos/{video_id}/relink' for route in app.routes):
        app.include_router(create_media_repair_router(service))
    client = TestClient(app)
    response = client.post(f'/api/tasks/{state.task.task_id}/videos/{video.video_id}/relink', data={'expected_version': state.task.version}, files={'file': ('../../renamed.mp4', source.read_bytes(), 'video/mp4')})
    assert response.status_code == 200, response.text
    assert response.json()['videos'][0]['storage_id'] == video.storage_id
    assert client.get(f'/api/tasks/{state.task.task_id}/media/{video.video_id}').content == source.read_bytes()


def test_missing_hevc_proxy_rebuilt_without_changing_original_or_frame_map(tmp_path):
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=64x48:r=8:d=0.5', '-c:v', 'libx265', '-x265-params', 'pools=1:frame-threads=1:log-level=error', '-pix_fmt', 'yuv420p', str(source)], check=True, capture_output=True)
    service = WorkflowService(tmp_path / 'library')
    state = saved(service, source)
    video = state.videos[0]
    original_path = service.media.path_for(video)
    proxy_path = service.media.playback_path_for(video)
    original = original_path.read_bytes()
    proxy_path.unlink()
    result = relink_media(service, state.task.task_id, state.task.version, video.video_id, BytesIO(original))
    assert proxy_path.is_file()
    assert original_path.read_bytes() == original
    assert result.videos[0] == video
