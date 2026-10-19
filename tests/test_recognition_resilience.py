"""Offline regressions for partial visual extraction and retry cost avoidance."""
from dataclasses import replace
import json
import pytest

from backend.app.media_preparation import PreparedFrame
from backend.app.providers.base import ProviderError
from backend.app.providers.recognition import OpenAIVisionProvider, ProviderRecognitionAdapter
from backend.app.providers.config import ProviderSettings
import test_providers
from test_providers import AlternateSpeech, AlternateVision


@pytest.fixture
def recognition_input(tmp_path):
    return test_providers.recognition_input.__wrapped__(tmp_path)


def batched_adapter(recognition_input, tmp_path):
    request, prepared = recognition_input
    frames = tuple(PreparedFrame(i, request.video.frame_timing.frame_boundaries_seconds[i],
                                 request.media_path, 16, 16) for i in range(5))
    prepared = replace(prepared, frames=frames)

    class Vision(AlternateVision):
        def __init__(self):
            super().__init__()
            self.batches = []
            self.failures = {}

        def extract(self, batch, *, metadata):
            indices = [frame.frame_index for frame in batch]
            self.batches.append(indices)
            if indices[0] in self.failures:
                raise self.failures[indices[0]]
            return super().extract(batch, metadata=metadata)

    vision, speech = Vision(), AlternateSpeech()
    adapter = ProviderRecognitionAdapter(ProviderSettings(cache_dir=tmp_path / "cache"),
        vision_provider=vision, transcription_provider=speech, prepare=lambda *_: prepared)
    return request, adapter, vision, speech


def test_visual_batches_retain_good_samples_and_retry_only_missing_batch(recognition_input, tmp_path):
    request, adapter, vision, speech = batched_adapter(recognition_input, tmp_path)
    vision.failures[3] = ProviderError("provider_incomplete", "Visual output reached its limit.")
    partial = adapter.analyze(request)
    assert partial.status == "partial"
    assert partial.coverage.visual_action == partial.coverage.on_screen_text == "observations"
    assert {key: error.code for key, error in partial.extraction_failures.items()} == {
        "visual_action": "provider_incomplete", "on_screen_text": "provider_incomplete"}
    assert [event.start_frame for event in partial.events if event.kind == "visual_action"] == [0, 1, 2]
    assert vision.batches == [[0, 1, 2], [3, 4]] and speech.calls == 1
    vision.failures.clear()
    recovered = adapter.analyze(request)
    assert recovered.status == "succeeded" and not recovered.extraction_failures
    assert [event.start_frame for event in recovered.events if event.kind == "visual_action"] == [0, 1, 2, 3, 4]
    assert vision.batches == [[0, 1, 2], [3, 4], [3, 4]]
    assert speech.calls == 1, "Successful source transcription must not be billed again."
    assert adapter.analyze(request).status == "succeeded"
    assert len(vision.batches) == 3 and speech.calls == 1


def test_bad_frame_batch_does_not_erase_later_samples_or_replay_budget_failure(recognition_input, tmp_path):
    request, adapter, vision, speech = batched_adapter(recognition_input, tmp_path)
    vision.failures[0] = ProviderError("provider_invalid_output", "Invalid sampled-frame indices.")
    first = adapter.analyze(request)
    assert first.status == "partial"
    assert [event.start_frame for event in first.events if event.kind == "visual_action"] == [3, 4]
    vision.failures[0] = ProviderError("experiment_budget_exhausted", "Budget cannot cover this attempt.")
    second = adapter.analyze(request)
    assert second.status == "partial"
    assert second.extraction_failures["visual_action"].code == "experiment_budget_exhausted"
    assert [event.start_frame for event in second.events if event.kind == "visual_action"] == [3, 4]
    assert vision.batches == [[0, 1, 2], [3, 4], [0, 1, 2]] and speech.calls == 1


def test_all_visual_failures_keep_exact_channel_cause_and_successful_speech(recognition_input, tmp_path):
    request, adapter, vision, speech = batched_adapter(recognition_input, tmp_path)
    vision.failures[0] = ProviderError("provider_forbidden", "The project cannot access this model.")
    result = adapter.analyze(request)
    assert result.status == "partial" and result.coverage.visual_action == "failed"
    assert result.coverage.on_screen_text == "failed" and result.coverage.speech == "observations"
    assert {event.kind for event in result.events} == {"speech"}
    assert result.extraction_failures["on_screen_text"].code == "provider_forbidden"
    assert vision.batches == [[0, 1, 2]] and speech.calls == 1


def test_corrupt_aggregate_cache_reuses_validated_visual_batches(recognition_input, tmp_path):
    request, adapter, vision, speech = batched_adapter(recognition_input, tmp_path)
    adapter.analyze(request)
    aggregate = next(path for path in (tmp_path / "cache").glob("*.json") if not path.name.startswith("speech-"))
    aggregate.write_text(json.dumps({"vision": {"frames": []}, "speech": []}))
    recovered = adapter.analyze(request)
    assert recovered.status == "succeeded" and len(vision.batches) == 2 and speech.calls == 1


def test_analysis_language_change_refreshes_only_visual_explanations(recognition_input, tmp_path):
    request, adapter, vision, speech = batched_adapter(recognition_input, tmp_path)
    adapter.analyze(request)
    adapter.settings = replace(adapter.settings, analysis_language="Chinese")
    adapter.analyze(request)
    assert len(vision.batches) == 4 and speech.calls == 1


def test_chinese_analysis_localizes_uncertainty_without_translating_evidence(recognition_input, tmp_path):
    request, adapter, vision, _ = batched_adapter(recognition_input, tmp_path)
    adapter.settings = replace(adapter.settings, analysis_language="Chinese")
    original_extract = vision.extract

    def extract(frames, *, metadata):
        raw = original_extract(frames, metadata=metadata)
        for frame in raw['frames']:
            frame.update(description='画面中有一个红色杯子。', interpretation=None, uncertainty=None)
        return raw

    vision.extract = extract
    result = adapter.analyze(request)
    assert result.output_language == 'Chinese'
    assert {event.text for event in result.events if event.kind == 'on_screen_text'} == {'Luma杯 500mL / Buy now 立即购买'}
    assert next(event for event in result.events if event.kind == 'speech').text == '今天 try LumaCup。'
    assert all('采样帧' in event.uncertainty for event in result.events if event.lane == 'visual')
    assert all('语音片段时间' in event.uncertainty for event in result.events if event.kind == 'speech')
    assert all('暂定叙事作用' in segment.interpretation for segment in result.segments)


def test_disabled_speech_does_not_call_transcription_or_claim_audio_absence(recognition_input, tmp_path):
    request, adapter, _, speech = batched_adapter(recognition_input, tmp_path)
    speech.model = 'disabled'
    result = adapter.analyze(request)
    assert result.status == 'succeeded'
    assert result.coverage.speech == 'not_analyzed'
    assert not any(event.kind == 'speech' for event in result.events)
    assert speech.calls == 0 and not result.extraction_failures
    assert adapter.records[-1]['cache_status'] == 'disabled'
    assert not list((tmp_path / 'cache').glob('speech-*.json'))
    assert 'Speech transcription is off' in result.origin.description
    repeated = adapter.analyze(request)
    assert repeated.coverage.speech == 'not_analyzed' and speech.calls == 0


def test_disabled_speech_with_known_no_audio_keeps_intake_absence(recognition_input, tmp_path):
    request, adapter, _, speech = batched_adapter(recognition_input, tmp_path)
    speech.model = 'disabled'
    request = replace(request, video=request.video.model_copy(update={'has_audio': False}))
    result = adapter.analyze(request)
    assert result.coverage.speech == 'none_found'
    assert speech.calls == 0


def test_visual_request_bounds_frame_ids_and_all_authored_fields_language(recognition_input):
    _, prepared = recognition_input

    class Transport:
        def json_response(self, model, prompt, schema, schema_name, **kwargs):
            self.prompt, self.schema = prompt, schema
            return AlternateVision().extract(prepared.frames, metadata={})

    transport = Transport()
    provider = OpenAIVisionProvider(ProviderSettings(analysis_language='Chinese'), transport)
    provider.extract(prepared.frames, metadata={})
    assert 'every generated description, interpretation, uncertainty' in transport.prompt
    assert 'visual_details (including subject descriptions, actions, and product presentations) in Chinese' in transport.prompt
    assert 'Preserve source OCR words verbatim' in transport.prompt
    assert transport.schema['$defs']['FrameObservation']['properties']['frame_index']['enum'] == [2]
    assert transport.schema['properties']['frames']['maxItems'] == 1


def test_disabled_transcription_reuses_matching_whisper_cache_without_call(recognition_input, tmp_path):
    request, adapter, _, speech = batched_adapter(recognition_input, tmp_path)
    speech.provider, speech.model = 'openai', 'whisper-1'
    initial = adapter.analyze(request)
    initial_speech = [event for event in initial.events if event.kind == 'speech']
    assert len(initial_speech) == 3 and speech.calls == 1
    speech.model = 'disabled'
    for _ in range(2):
        repeated = adapter.analyze(request)
        retained = [event for event in repeated.events if event.kind == 'speech']
        assert repeated.status == 'succeeded' and repeated.coverage.speech == 'observations'
        assert [(event.text, event.start_frame, event.end_frame) for event in retained] == [
            (event.text, event.start_frame, event.end_frame) for event in initial_speech]
        assert {event.source for event in retained} == {'openai/whisper-1'}
        assert {event.method for event in retained} == {'cached_timestamped_audio_transcription'}
        assert 'Reused validated source transcription from cache' in repeated.origin.description
        assert 'openai/disabled' not in repeated.origin.description
        assert speech.calls == 1
        assert adapter.records[-1]['attempts'] == 0
        assert adapter.records[-1]['cached_model'] == 'whisper-1'


@pytest.mark.parametrize('corruption', ['not-json', '[{"start": 0, "end": 999, "text": "Wrong timing"}]'])
def test_disabled_transcription_ignores_corrupt_whisper_cache(recognition_input, tmp_path, corruption):
    request, adapter, _, speech = batched_adapter(recognition_input, tmp_path)
    speech.provider, speech.model = 'openai', 'whisper-1'
    adapter.analyze(request)
    cache = next((tmp_path / 'cache').glob('speech-*.json'))
    cache.write_text(corruption)
    speech.model = 'disabled'
    result = adapter.analyze(request)
    assert result.status == 'succeeded' and result.coverage.speech == 'not_analyzed'
    assert not any(event.kind == 'speech' for event in result.events)
    assert speech.calls == 1


def test_disabled_transcription_never_reuses_another_provider_cache(recognition_input, tmp_path):
    request, adapter, _, speech = batched_adapter(recognition_input, tmp_path)
    adapter.analyze(request)  # alternate-offline fixture provider, not historical OpenAI speech.
    speech.model = 'disabled'
    result = adapter.analyze(request)
    assert result.coverage.speech == 'not_analyzed'
    assert speech.calls == 1


def test_disabled_transcription_requires_matching_chunk_boundaries(recognition_input, tmp_path):
    request, adapter, _, speech = batched_adapter(recognition_input, tmp_path)
    speech.provider, speech.model = 'openai', 'whisper-1'
    adapter.analyze(request)
    speech.model = 'disabled'
    prepared = adapter.prepare(request.media_path, request.video)
    changed = replace(prepared, audio_chunks=(replace(prepared.audio_chunks[0], end_seconds=.9),))
    adapter.prepare = lambda *_: changed
    result = adapter.analyze(request)
    assert result.coverage.speech == 'not_analyzed'
    assert speech.calls == 1
