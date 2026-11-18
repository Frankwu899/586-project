"""Offline evidence preservation; authored text and local PCM are synthetic."""
import json
import wave

import pytest

from backend.app.media_preparation import AudioChunk, validate_audio_chunk
from backend.app.project_workspace.models import EvidenceEvent, EvidenceRevision
from backend.app.project_workspace.speech_retry import CORRECTED_IDS, SPEECH_INTERVALS, merge_retry
from backend.app.providers.config import ProviderSettings
from backend.app.providers.recognition import ProviderRecognitionAdapter
from test_project_speech_retry import setup_retry
from test_providers import AlternateSpeech, AlternateVision, recognition_input


def ocr(identity, text, start=1, end=2):
    return EvidenceEvent(id=identity, kind="on_screen_text", text=text,
                         start_seconds=start, end_seconds=end, precision="sample")


def test_retry_preserves_complete_simultaneous_ocr_sample_and_only_replaces_its_old_machine_output():
    speech = EvidenceEvent(id="native_speech", kind="speech", text="Existing words",
                           start_seconds=.123, end_seconds=2.987, precision="estimated")
    previous = EvidenceRevision(revision=4, coverage={"on_screen_text": "partial", "speech": "observations"},
        diagnostics={SPEECH_INTERVALS: json.dumps({"native_speech": [.151, 2.951]})},
        events=[ocr("obsolete", "Old machine text"), ocr("unrecovered", "Other sample", 3, 4), speech])
    before = previous.model_dump()
    incoming = EvidenceRevision(revision=1, coverage={"on_screen_text": "partial"},
        events=[ocr("line_a", "Brand name"), ocr("line_b", "Important qualification")])
    merged = merge_retry(previous, incoming)
    assert {event.text for event in merged.events} == {
        "Brand name", "Important qualification", "Other sample", "Existing words"}
    assert next(event for event in merged.events if event.id == "native_speech") == speech
    assert merged.diagnostics[SPEECH_INTERVALS] == previous.diagnostics[SPEECH_INTERVALS]
    assert previous.model_dump() == before
    assert len(incoming.events) == 2
    repeated = merge_retry(merged, incoming)
    assert repeated.events == merged.events


def test_qa_handoff_exact_ocr_example_recovers_new_sample_preserving_speech_and_history():
    # Exact values quoted in the supplied handoff, not a full incident replay.
    speech = EvidenceEvent(id="qa_speech", kind="speech",
        text="why would somebody want to work with the Ro Body Program?",
        start_seconds=12.554208, end_seconds=15.181833, start_frame=301, end_frame=364,
        precision="estimated")
    lines = [ocr("qa_line_a", "Can't you just get prescription weight loss", 0, .041708),
             ocr("qa_line_b", "medicine from your own doctor?", 0, .041708)]
    previous = EvidenceRevision(revision=2, events=[*lines, speech], correction_note="QA speech correction",
        coverage={"on_screen_text": "partial", "speech": "partial"},
        diagnostics={CORRECTED_IDS: '["qa_speech"]', SPEECH_INTERVALS: json.dumps({"qa_speech": [12.56, 15.17]})})
    before = previous.model_dump_json()
    incoming = EvidenceRevision(revision=1, events=[*lines, ocr("recovered", "New recovered sample", 5, 5.041708)],
        coverage={"on_screen_text": "observations", "speech": "partial"})
    merged = merge_retry(previous, incoming)
    assert {event.text for event in merged.events if event.kind == "on_screen_text"} == {
        "Can't you just get prescription weight loss", "medicine from your own doctor?", "New recovered sample"}
    assert next(event for event in merged.events if event.id == speech.id).model_dump_json() == speech.model_dump_json()
    assert merged.diagnostics[SPEECH_INTERVALS] == previous.diagnostics[SPEECH_INTERVALS]
    assert merged.coverage["speech"] == "partial"
    assert previous.model_dump_json() == before


def test_simultaneous_ocr_correction_does_not_suppress_an_independent_line():
    previous = EvidenceRevision(revision=2, coverage={"on_screen_text": "partial"},
        correction_note="User corrected the title",
        diagnostics={CORRECTED_IDS: json.dumps(["title"])},
        events=[ocr("title", "Corrected title"), ocr("subtitle", "Obsolete subtitle")])
    incoming = EvidenceRevision(revision=1, coverage={"on_screen_text": "observations"},
        events=[ocr("title", "Machine title"), ocr("subtitle", "New qualified subtitle")])
    merged = merge_retry(previous, incoming)
    assert {event.text for event in merged.events} == {"Corrected title", "New qualified subtitle"}
    assert next(event for event in merged.events if event.id == "title") == previous.events[0]


def test_accepted_empty_sample_clears_only_that_samples_obsolete_machine_ocr():
    previous = EvidenceRevision(revision=2, coverage={"on_screen_text": "partial"},
        events=[ocr("obsolete", "No longer observed"), ocr("outside", "Unrecovered sample", 3, 4)])
    incoming = EvidenceRevision(revision=1, coverage={"on_screen_text": "partial"},
        diagnostics={"machine_visual_sample_scopes": json.dumps({"10": [1, 2]})})
    merged = merge_retry(previous, incoming)
    assert merged.events == [previous.events[1]]
    assert merged.coverage["on_screen_text"] == "partial"


def test_changed_machine_identity_cannot_restore_the_original_of_a_corrected_ocr_line():
    previous = EvidenceRevision(revision=2, coverage={"on_screen_text": "partial"},
        correction_note="Corrected source title",
        diagnostics={CORRECTED_IDS: json.dumps(["title"]), "machine_ocr_originals": json.dumps({
            "title": {"start": 1, "end": 2, "text": "Original machine title"},
            "subtitle": {"start": 1, "end": 2, "text": "Original qualification"}})},
        events=[ocr("title", "User title"), ocr("subtitle", "Original qualification")])
    incoming = EvidenceRevision(revision=1, coverage={"on_screen_text": "observations"},
        diagnostics={"machine_ocr_originals": json.dumps({
            "shifted_title": {"start": 1, "end": 2, "text": "Original machine title"},
            "shifted_subtitle": {"start": 1, "end": 2, "text": "Original qualification"}})},
        events=[ocr("shifted_title", "Original machine title"), ocr("shifted_subtitle", "Original qualification")])
    merged = merge_retry(previous, incoming)
    assert {event.text for event in merged.events} == {"User title", "Original qualification"}
    assert json.loads(merged.diagnostics["machine_ocr_originals"])["title"]["text"] == "Original machine title"
    assert merged.coverage["on_screen_text"] == "observations"


def test_unknown_historical_correction_keeps_ambiguous_candidate_visible_as_partial():
    previous = EvidenceRevision(revision=2, coverage={"on_screen_text": "partial"},
        correction_note="Historical user correction", diagnostics={CORRECTED_IDS: '["title"]'},
        events=[ocr("title", "User title"), ocr("known_line", "Known separate line")])
    incoming = EvidenceRevision(revision=1, coverage={"on_screen_text": "observations"},
        events=[ocr("changed_identity", "Possibly the old title"), ocr("new_identity", "Known separate line")])
    merged = merge_retry(previous, incoming)
    assert {event.text for event in merged.events} == {"User title", "Known separate line"}
    assert merged.coverage["on_screen_text"] == "partial"
    assert any("Possibly the old title" in note for note in merged.limitations)
    assert "machine_ocr_originals" not in merged.diagnostics


@pytest.mark.parametrize("incoming_id", ["title", "shifted_identity"])
def test_corrected_ocr_timing_cannot_restore_its_known_original_at_the_old_interval(incoming_id):
    previous = EvidenceRevision(revision=2, coverage={"on_screen_text": "partial"},
        correction_note="User corrected text and timing", diagnostics={CORRECTED_IDS: '["title"]',
            "machine_ocr_originals": json.dumps({"title": {"start": 1, "end": 2, "text": "Machine title"}})},
        events=[ocr("title", "User title", 3, 4)])
    incoming = EvidenceRevision(revision=1, coverage={"on_screen_text": "observations"},
        events=[ocr(incoming_id, "Machine title", 1, 2), ocr("new_line", "Independent line", 1, 2)])
    merged = merge_retry(previous, incoming)
    assert {event.text for event in merged.events} == {"User title", "Independent line"}
    assert next(event for event in merged.events if event.id == "title") == previous.events[0]
    assert merged.coverage["on_screen_text"] == "observations"
    assert json.loads(merged.diagnostics["machine_ocr_originals"])["title"] == {
        "start": 1, "end": 2, "text": "Machine title"}
    assert merge_retry(merged, incoming).events == merged.events


def test_visual_adapter_records_empty_validated_samples_on_first_and_cached_run(tmp_path):
    request, prepared = recognition_input.__wrapped__(tmp_path)
    vision = AlternateVision()
    vision.response = {"frames": [{"frame_index": 2, "description": None, "visual_details": None,
        "on_screen_text": [], "uncertainty": None, "roles": ["other"], "interpretation": None}]}
    adapter = ProviderRecognitionAdapter(ProviderSettings(cache_dir=tmp_path / "cache"),
        vision_provider=vision, transcription_provider=AlternateSpeech(), prepare=lambda *_: prepared)
    assert adapter.analyze(request).status == "succeeded"
    assert getattr(adapter, "visual_sample_scopes", {}) == {"2": [.3, .6]}
    assert adapter.analyze(request).status == "succeeded"
    assert adapter.visual_sample_scopes == {"2": [.3, .6]}
    assert vision.calls == 1


def test_actual_source_retry_saves_host_ocr_originals_and_validated_sample_scope(tmp_path):
    store, project, service, resource, *_ = setup_retry(tmp_path)
    def partial(value):
        evidence = value.resources[0].evidence[-1]
        evidence.correction_note = None
        evidence.coverage["on_screen_text"] = "partial"
    store.update(project.id, project.version, partial)
    result = service.retry_reference(project.id, resource.id)
    evidence = result.resources[0].evidence[-1]
    event = next(item for item in evidence.events if item.kind == "on_screen_text"
                 and item.text == "Luma杯 500mL / Buy now 立即购买")
    assert json.loads(evidence.diagnostics["machine_ocr_originals"])[event.id] == {
        "start": .3, "end": .6, "text": "Luma杯 500mL / Buy now 立即购买"}
    assert json.loads(evidence.diagnostics["machine_visual_sample_scopes"]) == {"2": [.3, .6]}


def test_manual_correction_captures_machine_ocr_before_changing_text(tmp_path):
    store, project, service, resource, *_ = setup_retry(tmp_path)
    project = store.update(project.id, project.version,
                           lambda value: setattr(value.resources[0].evidence[0], "correction_note", None))
    submitted = [event.model_copy(deep=True) for event in project.resources[0].evidence[-1].events]
    next(event for event in submitted if event.kind == "on_screen_text").text = "Human replacement"
    result = service.correct_evidence(project.id, project.version, resource.id, submitted)
    original = next(event for event in resource.evidence[0].events if event.kind == "on_screen_text")
    assert json.loads(result.resources[0].evidence[-1].diagnostics["machine_ocr_originals"])[original.id] == {
        "start": .3, "end": .6, "text": "Qualified product wording"}


def test_unordered_valid_segments_keep_native_intervals_but_remain_partial(tmp_path):
    chunk = AudioChunk(tmp_path / "unused.wav", 60, 61)
    spans, issues, rounded = ProviderRecognitionAdapter._normalize_speech_result({"segments": [
        {"start": .6, "end": .8, "text": "Later words"},
        {"start": .1, "end": .3, "text": "Earlier words"},
        {"start": .4, "end": 3, "text": "Invalid endpoint"},
    ]}, chunk, 61)
    assert spans == [{"start": 60.1, "end": 60.3, "text": "Earlier words"},
                     {"start": 60.6, "end": 60.8, "text": "Later words"}]
    assert issues == ["segment_order", "segment_bounds"] and rounded == 0


@pytest.mark.parametrize("start,end,accepted,rounded", [
    (0, 1, True, 0), (-.1, 1.1, True, 2), (-.099, 1.099, True, 2),
    (-.100001, 1, False, 0), (0, 1.100001, False, 0), (1, 1.1, False, 0),
])
def test_speech_local_boundary_tolerance_and_global_offset(tmp_path, start, end, accepted, rounded):
    spans, issues, count = ProviderRecognitionAdapter._normalize_speech_result({"segments": [
        {"start": start, "end": end, "text": "Native words"},
    ]}, AudioChunk(tmp_path / "unused.wav", 120, 121), 121)
    assert spans == ([{"start": 120, "end": 121, "text": "Native words"}] if accepted else [])
    assert issues == ([] if accepted else ["segment_bounds"])
    assert count == rounded


def test_real_short_final_silent_pcm_retains_measured_length_and_empty_result(tmp_path):
    audio = tmp_path / "silent-final.wav"
    with wave.open(str(audio), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * 2000)
    chunk = AudioChunk(audio, 60, 60.125)
    assert validate_audio_chunk(chunk, source_duration=60.125)["sample_count"] == 2000
    assert ProviderRecognitionAdapter._normalize_speech_result(
        {"text": "", "segments": []}, chunk, 60.125) == ([], [], 0)
    assert ProviderRecognitionAdapter._normalize_speech_result(
        {"text": "Whole input chunk"}, chunk, 60.125, model="gpt-transcribe")[0] == [
            {"start": 60, "end": 60.125, "text": "Whole input chunk"}]


def test_unordered_result_is_not_persisted_as_complete_speech_cache(tmp_path):
    request, prepared = recognition_input.__wrapped__(tmp_path)
    speech = AlternateSpeech()
    speech.transcribe = lambda *_args, **_kwargs: {"segments": [
        {"start": .6, "end": .8, "text": "Later"}, {"start": .1, "end": .3, "text": "Earlier"}]}
    adapter = ProviderRecognitionAdapter(ProviderSettings(cache_dir=tmp_path / "cache"),
        vision_provider=AlternateVision(), transcription_provider=speech, prepare=lambda *_: prepared)
    result = adapter.analyze(request)
    assert result.status == "partial"
    assert {event.text for event in result.events if event.kind == "speech"} == {"Earlier", "Later"}
    assert not list((tmp_path / "cache" / "speech-chunks").glob("*.json"))
    detail = next(record for record in adapter.records if record.get("stage") == "transcription_chunk")
    assert detail["validation_outcome"] == "partial" and detail["validation_rule"] == "segment_order"
