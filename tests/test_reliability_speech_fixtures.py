"""Synthesized speech through real FFmpeg prep and injected transcription.

The voice/music are generated locally. Timestamped provider output is authored
test data, so these checks establish preparation/persistence, never ASR accuracy.
"""
from array import array
import hashlib
import shutil
import subprocess
import wave

import pytest

from backend.app.project_workspace.analysis import AnalysisService
from backend.app.project_workspace.resources import ResourceService
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.config import ProviderSettings
from backend.app.providers.transport import OpenAITransport


SPOKEN_TEXT = "This is a clear speech fixture for local audio preparation."


@pytest.fixture(scope="module")
def ffmpeg_with_flite():
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg is required for synthesized speech preparation fixtures")
    filters = subprocess.run([ffmpeg, "-hide_banner", "-filters"], check=True,
                             capture_output=True, text=True).stdout
    if not any("flite" in line.split() for line in filters.splitlines()):
        pytest.skip("This FFmpeg build does not include the optional flite voice filter")
    return ffmpeg


@pytest.mark.parametrize("music_bed", [False, True], ids=["clear-synthesized-speech", "synthesized-speech-and-music"])
def test_real_synthesized_speech_preparation_and_saved_timestamped_evidence(tmp_path, monkeypatch, ffmpeg_with_flite, music_bed):
    source = tmp_path / ("speech-with-music.wav" if music_bed else "clear-speech.wav")
    command = [ffmpeg_with_flite, "-v", "error", "-f", "lavfi", "-i", f"flite=text={SPOKEN_TEXT}:voice=slt"]
    if music_bed:
        command.extend(["-f", "lavfi", "-i", "sine=frequency=220:sample_rate=22050:duration=30",
                        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights='1 0.1'[mixed]",
                        "-map", "[mixed]"])
    # The original is deliberately stereo/22.05 kHz; preparation must produce
    # the actual mono/16 kHz PCM contract rather than forwarding browser audio.
    command.extend(["-ar", "22050", "-ac", "2", "-c:a", "pcm_s16le", str(source)])
    subprocess.run(command, check=True)
    original_bytes = source.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()
    with wave.open(str(source), "rb") as original:
        duration = original.getnframes() / original.getframerate()
        assert 1 < duration < 60
        assert original.getnchannels() == 2 and original.getframerate() == 22050

    def prohibit_live(*_args, **_kwargs):
        pytest.fail("Synthesized-media fixtures must not call a live provider")

    monkeypatch.setattr(OpenAITransport, "transcribe", prohibit_live)
    monkeypatch.setattr(OpenAITransport, "json_response", prohibit_live)

    class InjectedTimestampedSpeech:
        calls = 0

        def transcribe(self, model, audio_path, *, metadata):
            self.calls += 1
            assert model == "whisper-1"
            assert metadata["chunk_start_seconds"] == 0
            assert metadata["chunk_end_seconds"] == pytest.approx(duration, abs=.002)
            with wave.open(str(audio_path), "rb") as prepared:
                assert (prepared.getnchannels(), prepared.getframerate(), prepared.getsampwidth()) == (1, 16000, 2)
                assert prepared.getnframes() / 16000 == pytest.approx(duration, abs=.002)
                samples = array("h", prepared.readframes(prepared.getnframes()))
                assert max(abs(sample) for sample in samples) > 100
            # Explicit injected-provider timing, not measured word alignment.
            return {"text": SPOKEN_TEXT, "segments": [
                {"start": .125, "end": duration - .125, "text": SPOKEN_TEXT}]}

    fixture = InjectedTimestampedSpeech()
    settings = ProviderSettings(api_key="injected-test-key", experiment_budget_enabled=False)
    store = ProjectStore(tmp_path / "library")
    project = store.create("Synthesized media preparation")
    resources = ResourceService(store, lambda: settings)
    with source.open("rb") as stream:
        project = resources.import_file(project.id, project.version, source.name, stream,
            provenance="Locally synthesized flite voice; quiet generated sine music bed." if music_bed
            else "Locally synthesized flite voice; no recorded human speech.")
    resource_id = project.resources[0].id
    project = resources.extract(project.id, resource_id)
    resource = project.resources[0]
    assert resource.status == "ready", resource.error
    assert resource.kind == "audio" and resource.sha256 == original_hash
    assert resource.duration_seconds == pytest.approx(duration, abs=.002)
    assert resource.evidence == [] and fixture.calls == 0

    service = AnalysisService(store, lambda: settings, transport_factory=lambda _: fixture)
    completed = service.retry_reference(project.id, resource_id)
    evidence = completed.resources[0].evidence[-1]
    assert evidence.coverage["speech"] == "observations"
    assert evidence.coverage["music"] == "not_analyzed"
    assert evidence.coverage["sfx"] == "not_analyzed"
    assert len(evidence.events) == 1
    event = evidence.events[0]
    assert event.text == SPOKEN_TEXT and event.kind == "speech"
    assert event.start_seconds == .125 and event.end_seconds == pytest.approx(duration - .125)
    assert event.start_frame is None and event.end_frame is None
    assert not evidence.reviewed
    assert fixture.calls == 1
    assert store.resolve_path(project.id, resource.original_path).read_bytes() == original_bytes
    reused = service.retry_reference(project.id, resource_id)
    assert reused.resources[0].evidence == completed.resources[0].evidence
    assert fixture.calls == 1  # Explicit retry reuses completed evidence.
    reopened = ProjectStore(tmp_path / "library").get(project.id)
    assert reopened.resources[0].evidence == completed.resources[0].evidence
