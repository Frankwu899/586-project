"""Offline transport and alternate-provider integration; no real recognition claims."""
from copy import deepcopy
from dataclasses import replace
import json

import httpx
import pytest

from backend.app.adapters import RecognitionRequest
from backend.app.media_preparation import AudioChunk, PreparedFrame, PreparedMedia
from backend.app.models import FrameTiming, VideoAsset
from backend.app.providers.base import ProviderCapabilities, ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.recognition import ProviderRecognitionAdapter
from backend.app.providers.transport import OpenAITransport


def details():
    return {name: {"status": "none_found", "items": [], "error": None}
            for name in ("subjects", "actions", "product_presentations")}


class AlternateVision:
    """Second provider proves domain consumers accept no OpenAI SDK objects."""
    provider, model = "alternate-offline", "fixture-v1"
    capabilities = ProviderCapabilities(vision=True, structured_output=True)

    def __init__(self):
        self.calls = 0
        self.response = None

    def extract(self, frames, *, metadata):
        self.calls += 1
        return deepcopy(self.response) if self.response else {"frames": [
            {"frame_index": frame.frame_index, "description": "A red cup is visible.",
             "visual_details": details(), "on_screen_text": ["Luma杯 500mL / Buy now 立即购买"],
             "uncertainty": None, "roles": ["product_demo"], "interpretation": "Tentative product view."}
            for frame in frames]}


class AlternateSpeech:
    provider, model = "alternate-offline", "fixture-speech-v1"
    capabilities = ProviderCapabilities(timestamped_transcription=True)

    def __init__(self):
        self.calls = 0
        self.fail = False

    def transcribe(self, chunk, *, metadata):
        self.calls += 1
        if self.fail:
            raise ProviderError("provider_timeout", "Speech timed out.", True)
        return {"text": "今天 try LumaCup。买买！", "segments": [
            {"start": 0.0, "end": .2, "text": "今天 try LumaCup。", "no_speech_prob": .01},
            {"start": .2, "end": .4, "text": "买"}, {"start": .4, "end": .6, "text": "买！"}]}


@pytest.fixture
def recognition_input(tmp_path):
    timing = FrameTiming(fps_numerator=5, fps_denominator=1, frame_count=5,
        media_start_seconds=2.5, frame_boundaries_seconds=[0, .1, .3, .6, .8, 1.0], rate_mode="variable")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not-real-media-injected-preparation")
    video = VideoAsset(video_id="video_real", task_id="task_real", input_method="file", storage_id="a"*32 + ".mp4",
        content_sha256="b"*64, duration_seconds=1, frame_timing=timing, has_audio=True, intake_status="ready",
        origin={"kind": "manual", "description": "Synthetic offline provider boundary fixture; not recognized footage."})
    frame = PreparedFrame(2, .3, source, 16, 16)
    chunk = AudioChunk(source, 0, 1)
    prepared = PreparedMedia((frame,), (chunk,), "b"*64)
    return RecognitionRequest("task_real", video, "job_real", "real", source), prepared


def adapter_for(recognition_input, **settings):
    _, prepared = recognition_input
    vision, speech = AlternateVision(), AlternateSpeech()
    return ProviderRecognitionAdapter(ProviderSettings(**settings), vision_provider=vision,
            transcription_provider=speech, prepare=lambda *_: prepared), vision, speech


def test_fake_alternate_provider_preserves_bilingual_sources_and_vfr_timing(recognition_input):
    adapter, vision, speech = adapter_for(recognition_input)
    result = adapter.analyze(recognition_input[0])
    assert result.status == "succeeded" and not result.review.user_confirmed
    assert result.origin.kind == "provider" and vision.calls == speech.calls == 1
    assert result.coverage.music == result.coverage.sfx == "not_analyzed"
    ocr = next(event for event in result.events if event.kind == "on_screen_text")
    assert ocr.text == "Luma杯 500mL / Buy now 立即购买"
    assert (ocr.start_frame, ocr.end_frame) == (2, 3)
    spans = [event for event in result.events if event.kind == "speech"]
    assert [event.text for event in spans] == ["今天 try LumaCup。", "买", "买！"]
    assert spans[0].start_frame == 0 and spans[0].end_frame == 2
    assert "alternate-offline" in result.origin.description


def test_no_audio_skips_transcription_and_records_known_absence(recognition_input):
    request, prepared = recognition_input
    request = replace(request, video=request.video.model_copy(update={"has_audio": False}))
    prepared = replace(prepared, audio_chunks=())
    adapter, _, speech = adapter_for((request, prepared))
    result = adapter.analyze(request)
    assert result.status == "succeeded" and result.coverage.speech == "none_found"
    assert speech.calls == 0 and "no audio stream" in result.origin.description
    assert adapter.records[-1]["cache_status"] == "skipped_no_audio"
    assert adapter.records[-1]["attempts"] == 0


def test_failed_capability_preserves_visual_evidence_as_partial(recognition_input):
    adapter, _, speech = adapter_for(recognition_input)
    speech.fail = True
    result = adapter.analyze(recognition_input[0])
    assert result.status == "partial" and result.coverage.speech == "failed"
    assert result.coverage.visual_action == "observations"
    assert not any(event.kind == "speech" for event in result.events)
    assert adapter.records[-1]["failure_code"] == "provider_timeout"


def test_missing_timestamp_capability_never_calls_provider(recognition_input):
    adapter, _, speech = adapter_for(recognition_input)
    speech.capabilities = ProviderCapabilities()
    result = adapter.analyze(recognition_input[0])
    assert result.status == "partial" and speech.calls == 0
    assert adapter.records[-1]["failure_code"] == "unsupported_model_capability"


def test_missing_key_real_transport_never_substitutes_sample(recognition_input):
    request, prepared = recognition_input
    result = ProviderRecognitionAdapter(ProviderSettings(api_key=""), prepare=lambda *_: prepared).analyze(request)
    assert result.status == "failed" and result.origin.kind == "provider"
    assert result.events == [] and result.error.code == "provider_not_configured"


def test_malformed_visual_indices_and_timestamp_output_are_rejected(recognition_input):
    adapter, vision, speech = adapter_for(recognition_input)
    vision.response = {"frames": [{"frame_index": 4, "description": "Invented frame", "visual_details": details(),
        "on_screen_text": [], "uncertainty": None, "roles": ["other"], "interpretation": None}]}
    speech.transcribe = lambda *_args, **_kwargs: {"text": "missing timing", "segments": []}
    result = adapter.analyze(recognition_input[0])
    assert result.status == "failed" and not result.events
    assert result.error.code == "provider_invalid_output"


def test_nested_group_failure_is_partial_not_succeeded(recognition_input):
    adapter, vision, _ = adapter_for(recognition_input)
    vision.response = vision.extract(recognition_input[1].frames, metadata={})
    vision.response["frames"][0]["visual_details"]["actions"] = {
        "status": "failed", "items": [], "error": {"code": "unclear", "message": "Action extraction failed", "retryable": False}}
    result = adapter.analyze(recognition_input[0])
    assert result.status == "partial"
    assert result.coverage.visual_action == "observations"


def test_cache_is_version_model_source_and_settings_scoped(recognition_input, tmp_path):
    adapter, vision, speech = adapter_for(recognition_input, cache_dir=tmp_path / "cache")
    first = adapter.analyze(recognition_input[0])
    second = adapter.analyze(recognition_input[0])
    assert first.analysis_id != second.analysis_id
    assert vision.calls == speech.calls == 1
    assert adapter.records[-1]["cache_status"] == "hit"
    vision.model = "fixture-v2"
    adapter.analyze(recognition_input[0])
    assert vision.calls == 2 and speech.calls == 1
    speech.model = "fixture-speech-v2"
    adapter.analyze(recognition_input[0])
    assert speech.calls == 2
    diagnostic = (tmp_path / "cache" / "runs.jsonl").read_text()
    assert "job_real" in diagnostic and "input_tokens" not in diagnostic
    assert "Luma杯" not in diagnostic  # no recognized private text in run records


@pytest.mark.parametrize("configuration", ["environment", "local_launcher"])
def test_runtime_budget_path_allows_recognition_and_cache_reuse(recognition_input, tmp_path, monkeypatch, configuration):
    """Use deployed settings: bare ProviderSettings() omits the ledger Path."""
    monkeypatch.setenv("VIDEO_ANATOMY_DATA_DIR", str(tmp_path / "library"))
    monkeypatch.setenv("VIDEO_EXPERIMENT_BUDGET_PATH", str(tmp_path / "ledger.sqlite3"))
    if configuration == "local_launcher":
        from scripts.local_server import local_settings
        settings = local_settings(tmp_path / "library", "offline-fake-key")
    else:
        settings = ProviderSettings.from_env()
    vision, speech = AlternateVision(), AlternateSpeech()
    request, prepared = recognition_input
    adapter = ProviderRecognitionAdapter(settings, vision_provider=vision,
        transcription_provider=speech, prepare=lambda *_: prepared)
    first = adapter.analyze(request)
    assert first.status == "succeeded" and first.events
    # Relocating an accounting file must not invalidate already paid evidence.
    adapter.settings = replace(settings, budget_path=tmp_path / "relocated-ledger.sqlite3")
    second = adapter.analyze(request)
    assert second.status == "succeeded"
    assert vision.calls == speech.calls == 1
    # Output-affecting settings still invalidate the visual cache.
    adapter.settings = replace(adapter.settings, analysis_language="French")
    assert adapter.analyze(request).status == "succeeded"
    assert vision.calls == 2 and speech.calls == 1


def test_changed_source_hash_fails_before_any_provider(recognition_input):
    request, prepared = recognition_input
    adapter, vision, speech = adapter_for((request, replace(prepared, source_sha256="c"*64)))
    result = adapter.analyze(request)
    assert result.error.code == "source_hash_mismatch"
    assert vision.calls == speech.calls == 0


def transport_with(handler, **settings):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAITransport(ProviderSettings(api_key="offline-fake-key", **settings), client=client, sleep=lambda _: None)


def completed(text='{"value":"中文 English"}'):
    return {"status": "completed", "model": "gpt-4.1-mini-2025-04-14",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}}


def json_call(transport):
    return transport.json_response("gpt-4.1-mini", "test", {"type": "object", "properties": {"value": {"type": "string"}}}, "test")


def test_responses_request_uses_documented_shape_and_reports_usage():
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=completed())
    transport = transport_with(handler)
    assert json_call(transport)["value"] == "中文 English"
    assert requests[0]["text"]["format"]["strict"] is True
    assert requests[0]["text"]["format"]["schema"]["required"] == ["value"]
    assert requests[0]["store"] is False
    assert transport.records[0]["usage"]["input_tokens"] == {"value": 12, "unit": "tokens"}
    assert transport.records[0]["resolved_model"] == "gpt-4.1-mini-2025-04-14"


@pytest.mark.parametrize("body,code", [
    (completed("{bad"), "provider_invalid_json"),
    ({"status": "incomplete", "output": []}, "provider_incomplete"),
    ({"status": "completed", "output": [{"content": [{"type": "refusal", "refusal": "private raw refusal"}]}]}, "provider_refusal"),
])
def test_malformed_refused_incomplete_responses_are_safe(body, code):
    transport = transport_with(lambda _: httpx.Response(200, json=body))
    with pytest.raises(ProviderError) as exc:
        json_call(transport)
    assert exc.value.code == code and "private raw" not in str(exc.value)
    assert transport.records[0]["failure_code"] == code


def test_timeout_transient_retries_are_bounded_and_budgeted():
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret host detail", request=request)
    transport = transport_with(handler, max_retries=2)
    charges = []
    transport.before_attempt = lambda model, payload: charges.append(model)
    with pytest.raises(ProviderError) as exc:
        json_call(transport)
    assert exc.value.code == "provider_timeout" and "secret" not in str(exc.value)
    assert len(calls) == len(charges) == transport.records[0]["attempts"] == 3


@pytest.mark.parametrize("status,code,expected", [(401, "invalid_api_key", "provider_authentication"),
    (429, "insufficient_quota", "provider_quota"), (400, "invalid_request", "provider_request_rejected")])
def test_auth_quota_and_bad_requests_are_never_retried(status, code, expected):
    transport = transport_with(lambda _: httpx.Response(status, json={"error": {"code": code, "message": "secret raw body"}}))
    with pytest.raises(ProviderError) as exc:
        json_call(transport)
    assert exc.value.code == expected and transport.records[0]["attempts"] == 1
    assert "secret raw" not in str(exc.value)


def test_transient_failure_then_success_uses_bounded_retry():
    calls = []
    def handler(_):
        calls.append(1)
        return httpx.Response(503, json={}) if len(calls) == 1 else httpx.Response(200, json=completed())
    transport = transport_with(handler)
    assert json_call(transport)["value"] == "中文 English"
    assert transport.records[0]["attempts"] == 2


def test_unsupported_models_fail_before_paid_request(tmp_path):
    transport = transport_with(lambda _: pytest.fail("Unexpected paid attempt"))
    with pytest.raises(ProviderError, match="documented supported model"):
        transport.json_response("text-only-model", "test", {}, "test")
    with pytest.raises(ProviderError, match="whisper-1"):
        transport.transcribe("gpt-4o-transcribe", tmp_path / "missing.wav")


def test_transcription_multipart_requests_original_language_with_segment_timing(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fixture")
    captured = []
    def handler(request):
        captured.append(request.content)
        return httpx.Response(200, json={"text": "品牌 Brand", "segments": [{"start": 0, "end": 1, "text": "品牌 Brand"}]})
    transport = transport_with(handler)
    assert transport.transcribe("whisper-1", audio)["text"] == "品牌 Brand"
    assert b"verbose_json" in captured[0] and b"timestamp_granularities[]" in captured[0]
    assert b'name="language"' not in captured[0]


@pytest.mark.parametrize("settings", [{"max_retries": 20}, {"timeout_seconds": float("inf")},
                                      {"max_frames": 100}, {"max_output_tokens": 1000000}])
def test_unbounded_settings_rejected(settings):
    with pytest.raises(ValueError):
        ProviderSettings(**settings)


def test_corrupt_cache_is_revalidated_and_recomputed(recognition_input, tmp_path):
    adapter, vision, speech = adapter_for(recognition_input, cache_dir=tmp_path / "cache")
    adapter.analyze(recognition_input[0])
    cache = next(path for path in (tmp_path / "cache").glob("*.json") if not path.name.startswith("speech-"))
    cache.write_text('{"vision": {"frames": []}, "speech": []}')
    result = adapter.analyze(recognition_input[0])
    assert result.status == "succeeded" and vision.calls == 2 and speech.calls == 1


def test_openai_responses_and_audio_normalize_end_to_end_offline(recognition_input):
    from backend.app.providers.recognition import OpenAIVisionProvider, OpenAITranscriptionProvider
    request, prepared = recognition_input
    visual_response = AlternateVision().extract(prepared.frames, metadata={})
    endpoints = []
    def handler(http_request):
        endpoints.append(http_request.url.path)
        if http_request.url.path.endswith("responses"):
            return httpx.Response(200, json=completed(json.dumps(visual_response, ensure_ascii=False)))
        return httpx.Response(200, json={"text": "声音不同 English", "segments": [
            {"start": 0.1, "end": 0.7, "text": "声音不同 English"}]})
    transport = transport_with(handler)
    settings = transport.settings
    adapter = ProviderRecognitionAdapter(settings,
        vision_provider=OpenAIVisionProvider(settings, transport),
        transcription_provider=OpenAITranscriptionProvider(settings, transport), prepare=lambda *_: prepared)
    result = adapter.analyze(request)
    assert result.status == "succeeded"
    assert endpoints == ["/v1/responses", "/v1/audio/transcriptions"]
    assert any(event.text == "声音不同 English" for event in result.events)
    assert any(event.text == "Luma杯 500mL / Buy now 立即购买" for event in result.events)
    assert all(record["job_id"] == request.job_id for record in adapter.records)
    assert all(record["analysis_id"] == result.analysis_id for record in adapter.records)


def test_speech_chunk_offset_uses_source_relative_clock_without_double_origin(recognition_input):
    request, prepared = recognition_input
    chunk = replace(prepared.audio_chunks[0], start_seconds=.3, end_seconds=1)
    adapter, _, speech = adapter_for((request, replace(prepared, audio_chunks=(chunk,))))
    result = adapter.analyze(request)
    spans = [event for event in result.events if event.kind == "speech"]
    assert result.status == "succeeded" and speech.calls == 1
    assert spans[0].start_frame == 2  # .3 source seconds, not source origin + .3
    assert spans[0].end_frame == 3


def test_speech_timing_tolerance_never_leaks_into_the_next_chunk(tmp_path):
    chunk = AudioChunk(tmp_path / "unused.wav", 0, 1)
    spans = ProviderRecognitionAdapter._normalize_speech({"segments": [
        {"start": .9, "end": 1.04, "text": "end"},
        {"start": 1.01, "end": 1.04, "text": "outside"},
    ]}, chunk, 2)
    assert spans == [{"start": .9, "end": 1, "text": "end"}]


def test_protocol_errors_are_safe_and_bounded():
    def handler(request):
        raise httpx.RemoteProtocolError("private peer details", request=request)
    transport = transport_with(handler, max_retries=0)
    with pytest.raises(ProviderError) as exc:
        json_call(transport)
    assert exc.value.code == "provider_network" and "private" not in str(exc.value)
    assert transport.records[0]["attempts"] == 1


def test_preparation_inherits_custom_media_tools(recognition_input, monkeypatch):
    from types import SimpleNamespace
    from backend.app.media import MediaSettings
    request, prepared = recognition_input
    settings = MediaSettings(ffmpeg="custom-ffmpeg")
    calls = []
    def prepare(path, video, **kwargs):
        from contextlib import nullcontext
        calls.append(kwargs)
        return nullcontext(prepared)
    monkeypatch.setattr("backend.app.media_preparation.prepare_media", prepare)
    adapter = ProviderRecognitionAdapter(ProviderSettings(), media_store=SimpleNamespace(settings=settings),
        vision_provider=AlternateVision(), transcription_provider=AlternateSpeech())
    assert adapter.analyze(request).status == "succeeded"
    assert calls[0]["media_settings"] is settings


def test_actual_visual_schema_projects_unsupported_constraints_only_for_transport():
    from backend.app.providers.recognition import VisionOutput
    from backend.app.providers.transport import strict_schema
    source = VisionOutput.model_json_schema()
    projected = strict_schema(source)
    forbidden = {"allOf", "not", "dependentRequired", "dependentSchemas", "if", "then", "else",
                 "uniqueItems", "contains", "minContains", "maxContains", "default"}
    def validate_schema(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            for child in value.values():
                validate_schema(child)
        elif isinstance(value, list):
            for child in value:
                validate_schema(child)
    validate_schema(projected)
    assert "allOf" in source["$defs"]["VisualSubject"]
    assert "allOf" in source["$defs"]["ObservationGroup_VisualSubject_"]
    assert source == VisionOutput.model_json_schema()  # canonical exported schema stays intact
    assert projected["$defs"]["VisualSubject"]["properties"]["kind"] == source["$defs"]["VisualSubject"]["properties"]["kind"]


def test_provider_schema_keeps_legitimate_properties_named_like_schema_keywords():
    from backend.app.providers.transport import strict_schema
    projected = strict_schema({"type": "object", "properties": {
        "default": {"type": "string", "default": "x"},
        "contains": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
    }})
    assert set(projected["required"]) == {"default", "contains"}
    assert projected["properties"]["default"] == {"type": "string"}
    assert "uniqueItems" not in projected["properties"]["contains"]
