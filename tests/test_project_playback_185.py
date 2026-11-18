"""Real FFmpeg media/cache/HTTP regressions, with no inference or incident-media claim."""
import hashlib
import io
import json
import struct
import subprocess
import threading
import time

from fastapi.testclient import TestClient
import pytest

from backend.app.api import create_app
from backend.app.project_workspace.models import EvidenceEvent, EvidenceRevision
from backend.app.project_workspace.resources import ResourceService
from backend.app.project_workspace.store import ProjectStore


def video(path, *, pixel_format="yuv420p", color="blue"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c={color}:s=160x90:r=10:d=1", "-vf", f"format={pixel_format}",
                    "-c:v", "libx264", "-pix_fmt", pixel_format, str(path)], check=True, capture_output=True)
    return path.read_bytes()


def properties(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)["streams"][0]


def imported(tmp_path, *, name="source.mov", pixel_format="yuv420p", encoded_suffix=None):
    path = tmp_path / name
    original = video(path.with_suffix(encoded_suffix) if encoded_suffix else path, pixel_format=pixel_format)
    store = ProjectStore(tmp_path / "library")
    service = ResourceService(store)
    project = store.create("Synthetic playback recovery")
    project = service.import_file(project.id, project.version, name, io.BytesIO(original))
    resource_id = project.resources[0].id
    project = service.extract(project.id, resource_id)
    assert project.resources[0].status == "ready", project.resources[0].error
    evidence = EvidenceRevision(revision=1, reviewed=True, events=[
        EvidenceEvent(id="human_text", kind="on_screen_text", text="Human correction", start_seconds=0.1, end_seconds=0.2)])
    project = store.update(project.id, project.version, lambda state: state.resources[0].evidence.append(evidence))
    return store, service, project, original


@pytest.mark.parametrize("damage", ["corrupt", "incompatible", "wrong_frames"])
def test_rebuild_repairs_existing_proxy_and_preserves_original_evidence_and_timing(tmp_path, damage):
    store, service, project, original = imported(tmp_path)
    resource = project.resources[0]
    playback = service.path(project.id, resource.id, "playback")
    if damage == "corrupt":
        playback.write_bytes(b"damaged cached bytes")
    else:
        video(playback, pixel_format="yuv444p" if damage == "incompatible" else "yuv420p",
              color="blue" if damage == "incompatible" else "red")
    damaged_bytes = playback.read_bytes()
    fixed = service.extract(project.id, resource.id).resources[0]
    assert playback.read_bytes() != damaged_bytes
    assert fixed.status == "ready", fixed.error
    assert properties(playback)["pix_fmt"] == "yuv420p"
    assert service.path(project.id, resource.id).read_bytes() == original
    assert fixed.sha256 == hashlib.sha256(original).hexdigest()
    assert fixed.evidence == resource.evidence
    assert fixed.media_metadata["frame_timing"] == resource.media_metadata["frame_timing"]
    assert fixed.media_metadata["playback_frame_timing"]["frame_count"] == 10
    assert not list(playback.parent.glob("*.pending.mp4"))
    # The validated replacement also survives another explicit preparation.
    proxy_bytes = playback.read_bytes()
    again = service.extract(project.id, resource.id).resources[0]
    assert again.status == "ready" and playback.read_bytes() == proxy_bytes


def test_h264_non_browser_pixel_format_uses_compatible_preview_and_reports_actual_format(tmp_path):
    _, service, project, original = imported(tmp_path, name="source.mp4", pixel_format="yuv444p")
    resource = project.resources[0]
    assert resource.playback_path != resource.original_path
    assert properties(service.path(project.id, resource.id, "playback"))["pix_fmt"] == "yuv420p"
    assert resource.media_metadata["pixel_format"] == "yuv444p"
    assert service.path(project.id, resource.id).read_bytes() == original


def test_mp4_filename_does_not_override_actual_non_mp4_container(tmp_path):
    _, service, project, original = imported(tmp_path, name="misnamed.mp4", encoded_suffix=".mkv")
    resource = project.resources[0]
    assert resource.media_metadata["format_name"] == "matroska,webm"
    assert resource.playback_path != resource.original_path
    assert properties(service.path(project.id, resource.id, "playback"))["codec_name"] == "h264"
    assert service.path(project.id, resource.id).read_bytes() == original


def test_failed_compatible_rebuild_is_atomic_and_does_not_change_saved_evidence(tmp_path, monkeypatch):
    store, service, project, original = imported(tmp_path)
    resource = project.resources[0]
    playback = service.path(project.id, resource.id, "playback")
    broken = b"retain failed proxy for diagnosis"
    playback.write_bytes(broken)
    from backend.app.project_workspace import resources
    real_run = resources._run

    def fail_conversion(command, timeout):
        if "libx264" in command:
            raise ValueError("Synthetic conversion failure")
        return real_run(command, timeout)

    monkeypatch.setattr(resources, "_run", fail_conversion)
    saved = service.extract(project.id, resource.id).resources[0]
    assert saved.status == "failed" and "Synthetic conversion failure" in saved.error
    assert playback.read_bytes() == broken
    assert service.path(project.id, resource.id).read_bytes() == original
    assert ProjectStore(store.root).get(project.id).resources[0].evidence == resource.evidence


def test_original_and_preview_have_separate_mime_and_range_responses_and_relink_preserves_evidence(tmp_path):
    store, service, project, original = imported(tmp_path)
    resource = project.resources[0]
    with TestClient(create_app(store.root)) as client:
        base = f"/api/projects/{project.id}/resources/{resource.id}/file"
        for representation, mime in (("original", "video/quicktime"), ("playback", "video/mp4")):
            expected = service.path(project.id, resource.id, representation).read_bytes()
            response = client.get(base, params={"representation": representation}, headers={"Range": "bytes=2-31"})
            assert response.status_code == 206
            assert response.headers["content-type"] == mime
            assert response.headers["accept-ranges"] == "bytes"
            assert response.headers["content-range"] == f"bytes 2-31/{len(expected)}"
            assert response.content == expected[2:32]
            assert client.get(base, params={"representation": representation}, headers={"Range": f"bytes={len(expected)}-"}).status_code == 416
    service.path(project.id, resource.id).unlink()
    current = store.get(project.id)
    restored = service.relink(project.id, current.version, resource.id, io.BytesIO(original))
    assert restored.resources[0].evidence == resource.evidence
    assert service.path(project.id, resource.id).read_bytes() == original


@pytest.mark.parametrize("frequency,audio_duration", [(880, 1), (440, 0.25)])
def test_explicit_rebuild_replaces_decodable_wrong_or_truncated_audio_cache(tmp_path, frequency, audio_duration):
    def media(path, tone, duration):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
                        "-f", "lavfi", "-i", f"sine=frequency={tone}:duration={duration}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True, capture_output=True)
    source = tmp_path / "audio-source.mov"
    media(source, 440, 1)
    original = source.read_bytes()
    store = ProjectStore(tmp_path / "library")
    service = ResourceService(store)
    project = store.create("Synthetic audio correspondence")
    project = service.import_file(project.id, project.version, source.name, io.BytesIO(original))
    project = service.extract(project.id, project.resources[0].id)
    resource = project.resources[0]
    playback = service.path(project.id, resource.id, "playback")
    media(playback, frequency, audio_duration)
    damaged = playback.read_bytes()
    with TestClient(create_app(store.root)) as client:
        response = client.post(f"/api/projects/{project.id}/resources/{resource.id}/extract", json={"expected_version": project.version})
        assert response.status_code == 202, response.text
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            saved = store.get(project.id)
            if all(job.status not in {"queued", "running"} for job in saved.jobs):
                break
            threading.Event().wait(0.01)
        assert saved.jobs[-1].status == "succeeded", saved.jobs[-1].error
    assert playback.read_bytes() != damaged
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(playback), "-map", "0:a:0", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                             check=True, capture_output=True).stdout
    samples = struct.unpack(f"<{len(decoded) // 2}h", decoded)
    assert 0.9 < len(samples) / 8000 < 1.1
    # Count positive zero crossings after the AAC edge padding. The submitted
    # original is a 440Hz tone; the deliberately substituted 880Hz must be gone.
    center = samples[800:-800]
    crossings = sum(left <= 0 < right for left, right in zip(center, center[1:]))
    assert 425 < crossings / (len(center) / 8000) < 455
    assert service.path(project.id, resource.id).read_bytes() == original
    assert saved.resources[0].media_metadata["frame_timing"] == resource.media_metadata["frame_timing"]
