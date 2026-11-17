"""Offline speech-profile recovery, PCM preparation, and correction boundaries.

WAV signals and provider text are authored fixtures. These tests establish
request/preparation/persistence behavior, never live ASR or word alignment.
"""
from array import array
from dataclasses import replace
import hashlib
import json
import math
import shutil
import wave

import pytest

from backend.app.media_preparation import AudioChunk
from backend.app.project_workspace.analysis import AnalysisService
from backend.app.project_workspace.models import EvidenceEvent, EvidenceRevision, Resource
from backend.app.project_workspace.speech_retry import merge_retry
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.recognition import (
    OpenAITranscriptionProvider,
    ProviderRecognitionAdapter,
)
from backend.app.providers.transport import OpenAITransport
from backend.app.workflow_errors import WorkflowError
from test_project_speech_retry import setup_retry
from test_providers import recognition_input


def _write_wav(path, seconds, *, rate=16000, channels=1):
    samples = array("h")
    for index in range(round(seconds * rate)):
        value = round(2500 * math.sin(2 * math.pi * 220 * index / rate))
        samples.extend([value] * channels)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(samples.tobytes())
    return path


def _forbid_structured_provider(*_args, **_kwargs):
    pytest.fail("Speech profile tests must not send a visual or synthesis request")


def _audio_project(tmp_path, *, seconds=2.5):
    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required for actual local WAV preparation")
    store = ProjectStore(tmp_path / "library")
    project = store.create("Offline speech profile preparation")
    source = store.project_dir(project.id) / "sources/media/profile.wav"
    _write_wav(source, seconds, rate=22050, channels=2)
    with wave.open(str(source), "rb") as audio:
        measured_duration = audio.getnframes() / audio.getframerate()
    resource = Resource(
        name="Locally synthesized PCM fixture.wav", kind="audio", origin="upload",
        original_path="sources/media/profile.wav",
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        size_bytes=source.stat().st_size, duration_seconds=measured_duration,
        media_metadata={"has_audio": True, "media_start_seconds": 0}, status="ready",
        provenance="Locally synthesized tone with authored provider text; not recorded speech.",
    )
    project = store.update(project.id, project.version, lambda value: value.resources.append(resource))
    settings = ProviderSettings(
        api_key="offline-fixture-only", experiment_budget_enabled=False,
        audio_chunk_seconds=1, max_audio_chunks=10,
    )
    return store, project, resource, AnalysisService(store, lambda: settings)


def test_transport_profiles_keep_whisper_timestamp_payload_and_gpt_json_separate(tmp_path, monkeypatch):
    audio = _write_wav(tmp_path / "request.wav", 1)
    calls = []

    def request(_self, endpoint, model, payload, *, metadata=None, audio_path=None):
        calls.append((endpoint, model, payload, metadata, audio_path))
        return {"text": "Authored response."}

    monkeypatch.setattr(OpenAITransport, "_request", request)
    settings = ProviderSettings(api_key="offline-fixture-only", experiment_budget_enabled=False)
    assert settings.transcription_model == "whisper-1"
    transport = OpenAITransport(settings)
    transport.transcribe("whisper-1", audio)
    transport.transcribe("gpt-transcribe", audio, metadata={"chunk_index": 0})

    assert calls[0][0:2] == ("audio/transcriptions", "whisper-1")
    assert calls[0][2]["response_format"] == "verbose_json"
    assert calls[0][2]["timestamp_granularities[]"] == "segment"
    assert calls[1][0:2] == ("audio/transcriptions", "gpt-transcribe")
    assert calls[1][2]["response_format"] == "json"
    assert not any("timestamp" in field for field in calls[1][2])
    assert calls[1][3]["chunk_index"] == 0 and calls[1][4] == audio
    assert calls[1][3]["speech_model"] == "gpt-transcribe"
    assert calls[1][3]["speech_timing"] == "chunk"

    with pytest.raises(ProviderError) as error:
        transport.transcribe("gpt-4o-transcribe-diarize", audio)
    assert error.value.code == "unsupported_model_capability"
    assert len(calls) == 2


def test_gpt_json_normalization_keeps_one_complete_chunk_without_sentence_alignment(tmp_path):
    audio = _write_wav(tmp_path / "offset.wav", 1.25)
    chunk = AudioChunk(audio, 3.125, 4.375)
    text = "First complete sentence. 第二句保持原文。"
    spans, issues, rounded = ProviderRecognitionAdapter._normalize_speech_result(
        {"text": text, "languages": [{"code": "en"}, {"code": "zh"}]},
        chunk, 5, model="gpt-transcribe",
    )
    assert spans == [{"text": text, "start": 3.125, "end": 4.375}]
    assert issues == [] and rounded == 0
    assert ProviderRecognitionAdapter._normalize_speech_result(
        {"text": "", "languages": []}, chunk, 5, model="gpt-transcribe",
    ) == ([], [], 0)
    # Untimed text must still fail when the default timestamped profile is used.
    with pytest.raises(ProviderError) as error:
        ProviderRecognitionAdapter._normalize_speech_result({"text": text}, chunk, 5)
    assert error.value.code == "audio_timestamps_missing"


def test_real_wav_gpt_retry_uses_measured_chunks_and_reuses_only_its_own_profile(tmp_path, monkeypatch):
    store, project, resource, service = _audio_project(tmp_path)
    calls = []
    texts = ["First sentence. 第二句。", "The next complete chunk.", "Final chunk."]

    def transcribe(_self, model, audio_path, *, metadata):
        index = metadata["chunk_index"]
        assert model == "gpt-transcribe"
        with wave.open(str(audio_path), "rb") as audio:
            assert (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) == (1, 16000, 2)
            assert audio.getnframes() / 16000 == pytest.approx(
                metadata["chunk_end_seconds"] - metadata["chunk_start_seconds"], abs=1 / 16000,
            )
            samples = array("h", audio.readframes(audio.getnframes()))
            assert max(abs(sample) for sample in samples) > 100
        calls.append((model, metadata["chunk_start_seconds"], metadata["chunk_end_seconds"]))
        return {"text": texts[index], "languages": [{"code": "en"}]}

    monkeypatch.setattr(OpenAITransport, "transcribe", transcribe)
    monkeypatch.setattr(OpenAITransport, "json_response", _forbid_structured_provider)
    completed = service.retry_reference(
        project.id, resource.id, transcription_model="gpt-transcribe", parent_job_id="profile_parent",
    )
    evidence = completed.resources[0].evidence[-1]
    assert calls == [("gpt-transcribe", 0, 1), ("gpt-transcribe", 1, 2), ("gpt-transcribe", 2, 2.5)]
    assert evidence.coverage["speech"] == "observations"
    assert evidence.diagnostics["speech_model"] == "gpt-transcribe"
    assert evidence.diagnostics["speech_timing"] == "chunk"
    assert [(event.start_seconds, event.end_seconds, event.text) for event in evidence.events] == [
        (0, 1, texts[0]), (1, 2, texts[1]), (2, 2.5, texts[2]),
    ]
    assert all(event.precision == "interval" and event.start_frame is None and event.end_frame is None
               for event in evidence.events)
    limitations = " ".join(evidence.limitations).lower()
    assert "chunk" in limitations and ("sentence" in limitations or "word" in limitations)
    assert "not" in limitations or "no " in limitations
    child = completed.jobs[-1]
    assert child.status == "succeeded" and child.parent_job_id == "profile_parent"
    assert child.diagnostics["speech_model"] == "gpt-transcribe"
    assert child.diagnostics["speech_timing"] == "chunk"
    assert str(child.diagnostics["evidence_revision"]) == str(evidence.revision)

    reopened = ProjectStore(store.root).get(project.id)
    assert reopened.resources[0].evidence == completed.resources[0].evidence
    reused = service.retry_reference(project.id, resource.id, transcription_model="gpt-transcribe")
    assert len(calls) == 3
    assert reused.resources[0].evidence == completed.resources[0].evidence
    # An ordinary retry must retain the saved profile even though Settings
    # still defaults to Whisper. It must not silently create another API call.
    ordinary_retry = service.retry_reference(project.id, resource.id)
    assert len(calls) == 3
    assert ordinary_retry.resources[0].evidence == completed.resources[0].evidence
    assert ordinary_retry.jobs[-1].diagnostics["speech_model"] == "gpt-transcribe"
    assert ordinary_retry.jobs[-1].diagnostics["speech_timing"] == "chunk"


@pytest.mark.parametrize("corrected", [False, True], ids=["machine-speech", "user-correction"])
def test_explicit_model_switch_refreshes_speech_without_touching_saved_visuals(tmp_path, monkeypatch, corrected):
    store, project, service, resource, vision, _, _ = setup_retry(tmp_path)
    _, prepared = recognition_input.__wrapped__(tmp_path)
    chunk_file = _write_wav(tmp_path / "switch.wav", 1)
    prepared = replace(prepared, source_sha256=resource.sha256,
                       audio_chunks=(AudioChunk(chunk_file, 0, 1),))
    calls = []
    incoming_text = "A complete replacement sentence spanning the whole chunk."

    def transcribe(_self, model, _audio_path, *, metadata):
        calls.append(model)
        assert metadata["chunk_start_seconds"] == 0 and metadata["chunk_end_seconds"] == 1
        if model == "whisper-1":
            return {"text": "Old machine result.", "segments": [
                {"text": "Old machine result.", "start": 0, "end": .3},
            ]}
        assert model == "gpt-transcribe"
        return {"text": incoming_text, "languages": [{"code": "en"}]}

    monkeypatch.setattr(OpenAITransport, "transcribe", transcribe)
    monkeypatch.setattr(OpenAITransport, "json_response", _forbid_structured_provider)
    monkeypatch.setattr(vision, "extract", _forbid_structured_provider)
    service.recognition_factory = lambda settings: ProviderRecognitionAdapter(
        settings, vision_provider=vision,
        transcription_provider=OpenAITranscriptionProvider(settings), prepare=lambda *_: prepared,
    )

    # Seed the previous model's persisted speech cache through the real adapter.
    def make_machine_partial(value):
        previous = value.resources[0].evidence[0]
        previous.correction_note = None
        previous.events = [event for event in previous.events if event.kind != "speech"]

    store.update(project.id, project.version, make_machine_partial)
    first = service.retry_reference(project.id, resource.id)
    assert calls == ["whisper-1"]
    assert first.resources[0].evidence[-1].coverage["speech"] == "observations"

    def review_and_correct(value):
        current = value.resources[0].evidence[-1]
        current.reviewed = True
        if corrected:
            correction = current.model_copy(deep=True)
            correction.revision += 1
            correction.correction_note = "The user corrected the first words and their timing."
            event = next(event for event in correction.events if event.kind == "speech")
            event.text, event.start_seconds, event.end_seconds = "Exact user wording", .05, .25
            value.resources[0].evidence.append(correction)

    ready = store.update(project.id, first.version, review_and_correct)
    before = [revision.model_dump() for revision in ready.resources[0].evidence]
    prior = ready.resources[0].evidence[-1]
    visuals = [event for event in prior.events if event.kind in {"visual", "on_screen_text"}]
    speech = [event for event in prior.events if event.kind == "speech"]

    switched = service.retry_reference(project.id, resource.id, transcription_model="gpt-transcribe")
    assert calls == ["whisper-1", "gpt-transcribe"]
    assert [revision.model_dump() for revision in switched.resources[0].evidence[:-1]] == before
    current = switched.resources[0].evidence[-1]
    assert [event for event in current.events if event.kind in {"visual", "on_screen_text"}] == visuals
    assert current.diagnostics["speech_model"] == "gpt-transcribe"
    assert current.diagnostics["speech_timing"] == "chunk"
    assert not current.reviewed
    if corrected:
        assert [event for event in current.events if event.kind == "speech"] == speech
        assert current.correction_note == prior.correction_note
        assert current.coverage["speech"] == "partial"
        assert current.diagnostics["speech"] == "speech_merge_conflict"
        assert any(incoming_text in note for note in current.limitations)
    else:
        replacement = [event for event in current.events if event.kind == "speech"]
        assert len(replacement) == 1 and replacement[0].text == incoming_text
        assert (replacement[0].start_seconds, replacement[0].end_seconds) == (0, 1)
        assert replacement[0].precision == "interval"
        assert current.coverage["speech"] == "observations"
        assert "speech" not in current.diagnostics
    assert vision.calls == 0


def test_unsupported_retry_override_fails_before_provider_or_child_job(tmp_path, monkeypatch):
    store, project, service, resource, vision, speech, _ = setup_retry(tmp_path)
    monkeypatch.setattr(OpenAITransport, "transcribe", _forbid_structured_provider)
    monkeypatch.setattr(OpenAITransport, "json_response", _forbid_structured_provider)
    before = store.get(project.id).model_dump()
    with pytest.raises(WorkflowError) as error:
        service.retry_reference(project.id, resource.id, transcription_model="gpt-4o-transcribe")
    assert error.value.code == "unsupported_model_capability"
    assert store.get(project.id).model_dump() == before
    assert vision.calls == speech.calls == 0


@pytest.mark.parametrize("corrected", [False, True], ids=["replace-machine-partial", "keep-corrected-partial"])
def test_partial_recovery_replaces_machine_speech_but_preserves_correction_conflicts(corrected):
    visual = EvidenceEvent(id="saved_visual", kind="visual", text="Reviewed product label",
                           start_seconds=.4, end_seconds=.6, precision="sample")
    old = EvidenceEvent(id="old_partial", kind="speech", text="Truncated machine text",
                        start_seconds=0, end_seconds=.3, precision="estimated")
    candidate = EvidenceEvent(id="recovered", kind="speech", text="Complete recovered wording",
                              start_seconds=0, end_seconds=1, precision="interval")
    previous = EvidenceRevision(
        revision=2, events=[old, visual], reviewed=True,
        coverage={"speech": "partial", "visual_action": "observations"},
        diagnostics={"speech": "audio_timestamps_invalid"},
        correction_note="User supplied exact wording and timing" if corrected else None,
    )
    incoming = EvidenceRevision(
        revision=1, events=[candidate], coverage={"speech": "observations"},
        diagnostics={"speech_model": "gpt-transcribe", "speech_timing": "chunk"},
    )
    original = previous.model_dump()
    merged = merge_retry(previous, incoming, speech_only=True)
    assert previous.model_dump() == original and incoming.events == [candidate]
    assert visual in merged.events and not merged.reviewed
    assert merged.diagnostics["speech_model"] == "gpt-transcribe"
    assert merged.diagnostics["speech_timing"] == "chunk"
    if corrected:
        assert old in merged.events and candidate not in merged.events
        assert merged.coverage["speech"] == "partial"
        assert merged.diagnostics["speech"] == "speech_merge_conflict"
    else:
        assert candidate in merged.events and old not in merged.events
        assert merged.coverage["speech"] == "observations"
        assert "speech" not in merged.diagnostics


@pytest.mark.parametrize("edited_kind", ["visual", "speech"], ids=["visual-only-edit", "speech-text-and-time-edit"])
def test_correction_service_marks_only_changed_events_for_subsequent_speech_recovery(tmp_path, edited_kind):
    store, project, service, resource, vision, speech, _ = setup_retry(tmp_path)

    def make_machine_evidence(value):
        # Old records without an event marker stay conservative. This fixture
        # starts as explicitly uncorrected machine output before the real edit.
        value.resources[0].evidence[-1].correction_note = None

    machine = store.update(project.id, project.version, make_machine_evidence)
    previous = machine.resources[0].evidence[-1]
    submitted = [event.model_copy(deep=True) for event in previous.events]
    edited = next(event for event in submitted if event.kind == edited_kind)
    edited.text = "User corrected the product label" if edited_kind == "visual" else "Exact user speech wording"
    if edited_kind == "speech":
        edited.end_seconds = .1

    corrected = service.correct_evidence(
        project.id, machine.version, resource.id, submitted, reviewed=True,
        base_revision=previous.revision,
    )
    corrected_evidence = corrected.resources[0].evidence[-1]
    assert json.loads(corrected_evidence.diagnostics["human_corrected_event_ids"]) == [edited.id]
    assert corrected_evidence.reviewed
    assert corrected.resources[0].evidence[0] == previous
    protected = next(event for event in corrected_evidence.events if event.id == edited.id)
    history = [revision.model_dump() for revision in corrected.resources[0].evidence]

    recovered = service.retry_reference(project.id, resource.id)
    assert speech.calls == 1 and vision.calls == 0
    assert [revision.model_dump() for revision in recovered.resources[0].evidence[:-1]] == history
    evidence = recovered.resources[0].evidence[-1]
    assert protected in evidence.events
    assert json.loads(evidence.diagnostics["human_corrected_event_ids"]) == [edited.id]
    if edited_kind == "visual":
        assert evidence.coverage["speech"] == "observations"
        assert "speech" not in evidence.diagnostics
        assert all(event.text != "Corrected first words" for event in evidence.events if event.kind == "speech")
        assert any(event.text == "今天 try LumaCup。" for event in evidence.events if event.kind == "speech")
    else:
        assert evidence.coverage["speech"] == "partial"
        assert evidence.diagnostics["speech"] == "speech_merge_conflict"
        assert (protected.text, protected.start_seconds, protected.end_seconds) == ("Exact user speech wording", 0, .1)
        assert any("今天 try LumaCup。" in note for note in evidence.limitations)


def test_still_partial_recovery_retains_old_machine_coverage_outside_new_span():
    old = EvidenceEvent(id="old_complete_span", kind="speech", text="Previously recovered wording",
                        start_seconds=0, end_seconds=5, precision="estimated")
    recovered = EvidenceEvent(id="new_partial_span", kind="speech", text="Recovered only this portion",
                              start_seconds=1, end_seconds=3, precision="estimated")
    previous = EvidenceRevision(revision=1, events=[old], coverage={"speech": "partial"},
                                diagnostics={"speech": "audio_timestamps_invalid"})
    incoming = EvidenceRevision(revision=1, events=[recovered], coverage={"speech": "partial"},
                                diagnostics={"speech": "provider_timeout"})
    before = previous.model_dump()
    merged = merge_retry(previous, incoming, speech_only=True)
    assert old in merged.events and recovered in merged.events
    assert merged.coverage["speech"] == "partial"
    assert merged.diagnostics["speech"] == "provider_timeout"
    assert min(event.start_seconds for event in merged.events) == 0
    assert max(event.end_seconds for event in merged.events) == 5
    assert previous.model_dump() == before

    complete = recovered.model_copy(update={"id": "new_complete_span", "start_seconds": 0, "end_seconds": 5})
    finished = merge_retry(previous, EvidenceRevision(
        revision=1, events=[complete], coverage={"speech": "observations"},
    ), speech_only=True)
    assert finished.events == [complete] and old not in finished.events
    assert finished.coverage["speech"] == "observations" and "speech" not in finished.diagnostics


def test_gpt_speech_cache_rejects_subchunk_timestamps_instead_of_claiming_alignment(tmp_path):
    chunk = AudioChunk(_write_wav(tmp_path / "cache.wav", 1), 2, 3)
    full = [{"text": "The full submitted chunk.", "start": 2, "end": 3}]
    subchunk = [{"text": "An unsupported exact interval.", "start": 2.125, "end": 2.75}]
    validate = ProviderRecognitionAdapter._validate_cached_speech
    assert validate(full, 4, model="gpt-transcribe", chunks=[chunk]) == full
    with pytest.raises(ValueError, match="whole-chunk"):
        validate(subchunk, 4, model="gpt-transcribe", chunks=[chunk])
    # Provider-estimated subchunk timing remains valid for the timestamped
    # profile; a cache cannot acquire that capability by changing its label.
    assert validate(subchunk, 4, model="whisper-1", chunks=[chunk]) == subchunk


def test_successful_missing_chunk_recovery_keeps_disjoint_saved_machine_speech():
    old = EvidenceEvent(id="old_chunk", kind="speech", text="Earlier completed chunk",
                        start_seconds=0, end_seconds=1, precision="estimated")
    recovered = EvidenceEvent(id="later_chunk", kind="speech", text="Recovered later chunk",
                              start_seconds=2, end_seconds=3, precision="estimated")
    previous = EvidenceRevision(revision=1, events=[old], coverage={"speech": "partial"},
                                diagnostics={"speech": "provider_timeout"})
    incoming = EvidenceRevision(revision=1, events=[recovered], coverage={"speech": "observations"})
    merged = merge_retry(previous, incoming, speech_only=True)
    assert merged.events == [old, recovered]
    assert merged.coverage["speech"] == "observations"
    assert "speech" not in merged.diagnostics
    assert previous.events == [old]


def test_video_chunk_text_correction_preserves_non_frame_aligned_bounds_and_precise_marker(tmp_path):
    store, project, service, resource, _, _, _ = setup_retry(tmp_path)
    first = EvidenceEvent(id="chunk_first", kind="speech", text="First chunk text",
                          start_seconds=.0125, end_seconds=.5125, precision="interval")
    second = EvidenceEvent(id="chunk_second", kind="speech", text="Untouched chunk text",
                           start_seconds=.5125, end_seconds=.9875, precision="interval")

    def use_chunk_evidence(value):
        evidence = value.resources[0].evidence[-1]
        evidence.correction_note = None
        evidence.events = [event for event in evidence.events if event.kind != "speech"] + [first, second]
        evidence.coverage["speech"] = "observations"
        evidence.diagnostics = {"speech_model": "gpt-transcribe", "speech_timing": "chunk"}

    machine = store.update(project.id, project.version, use_chunk_evidence)
    previous = machine.resources[0].evidence[-1]
    submitted = [event.model_copy(deep=True) for event in previous.events]
    next(event for event in submitted if event.id == first.id).text = "User corrected this chunk's wording"
    corrected = service.correct_evidence(project.id, machine.version, resource.id, submitted,
                                         base_revision=previous.revision)
    evidence = corrected.resources[0].evidence[-1]
    assert json.loads(evidence.diagnostics["human_corrected_event_ids"]) == [first.id]
    chunks = [event for event in evidence.events if event.kind == "speech"]
    assert [(event.start_seconds, event.end_seconds) for event in chunks] == [(.0125, .5125), (.5125, .9875)]
    assert all(event.start_frame is None and event.end_frame is None for event in chunks)
    assert chunks[1] == second
    assert corrected.resources[0].evidence[0] == previous
