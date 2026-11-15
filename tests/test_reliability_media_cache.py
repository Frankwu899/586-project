"""Real FFmpeg preparation/cache tests with synthetic media; no speech API."""
import hashlib
import json
import subprocess
import wave

import pytest

from backend.app.media import MediaStore
from backend.app.media_preparation import validate_audio_chunk
from backend.app.project_workspace.analysis import AnalysisService
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport


@pytest.mark.parametrize("corruption", ["stereo", "short_duration", "truncated_samples", "source_alignment"])
def test_prepared_video_cache_validates_audio_even_with_matching_hash(tmp_path, monkeypatch, corruption):
    source = tmp_path / "synthetic-tone.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=64x48:r=12:d=1.25",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1.25",
                    "-c:v", "libx264", "-c:a", "aac", str(source)], check=True)
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    media = MediaStore(tmp_path / "media-library")
    with source.open("rb") as stream:
        video = media.save_upload("task_cache_regression", source.name, stream)
    store = ProjectStore(tmp_path / "project-library")
    project = store.create("Prepared audio corruption")
    settings = ProviderSettings(max_frames=1, audio_chunk_seconds=1, max_audio_chunks=3,
                                experiment_budget_enabled=False)
    service = AnalysisService(store, lambda: settings)

    def prohibit_provider(*_args, **_kwargs):
        pytest.fail("Media preparation must not call a paid provider")

    monkeypatch.setattr(OpenAITransport, "transcribe", prohibit_provider)
    monkeypatch.setattr(OpenAITransport, "json_response", prohibit_provider)
    with service._prepared(project.id, media.path_for(video), video, settings) as prepared:
        assert len(prepared.audio_chunks) == 2
        cached_audio = prepared.audio_chunks[0].path
        manifest_path = cached_audio.parent / "manifest.json"
        original_audio = cached_audio.read_bytes()
    manifest = json.loads(manifest_path.read_text())
    if corruption in {"stereo", "short_duration"}:
        with wave.open(str(cached_audio), "wb") as wav:
            channels = 2 if corruption == "stereo" else 1
            count = 16000 if corruption == "stereo" else 8000
            wav.setparams((channels, 2, 16000, 0, "NONE", "not compressed"))
            wav.writeframes(b"\0\0" * count * channels)
    elif corruption == "truncated_samples":
        cached_audio.write_bytes(original_audio[:-100])
    else:
        manifest["audio"][0]["end_seconds"] = .9
    # A cache checksum alone cannot establish PCM validity or source alignment.
    manifest["audio"][0]["sha256"] = hashlib.sha256(cached_audio.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))

    import backend.app.project_workspace.analysis as analysis_module
    original_prepare = analysis_module.prepare_media
    rebuilds = []

    def rebuilding(*args, **kwargs):
        rebuilds.append(True)
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(analysis_module, "prepare_media", rebuilding)
    with service._prepared(project.id, media.path_for(video), video, settings) as rebuilt:
        assert len(rebuilds) == 1
        assert [(item.start_seconds, item.end_seconds) for item in rebuilt.audio_chunks] == [(0, 1), (1, 1.25)]
        for chunk in rebuilt.audio_chunks:
            details = validate_audio_chunk(chunk, source_duration=video.duration_seconds)
            assert details["sample_rate"] == 16000 and details["channels"] == 1
        assert rebuilt.audio_chunks[0].path.read_bytes() == original_audio
    with service._prepared(project.id, media.path_for(video), video, settings):
        assert len(rebuilds) == 1  # Newly valid preparation is reusable.
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_digest
    assert hashlib.sha256(media.path_for(video).read_bytes()).hexdigest() == source_digest
