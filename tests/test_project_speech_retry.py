"""Offline speech recovery regression fixtures; not live transcription accuracy."""
from dataclasses import replace
import hashlib

import httpx
import pytest

from backend.app.project_workspace.analysis import AnalysisService
from backend.app.project_workspace.models import EvidenceEvent, EvidenceRevision, Resource
from backend.app.project_workspace.speech_retry import public_failure
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.auth import provider_http_error
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.recognition import ProviderRecognitionAdapter
from test_providers import AlternateSpeech, AlternateVision, recognition_input


def setup_retry(tmp_path, *, has_audio=True):
    request, prepared = recognition_input.__wrapped__(tmp_path)
    store = ProjectStore(tmp_path / 'library')
    project = store.create('Migrated partial source')
    original = store.project_dir(project.id) / 'sources/media/legacy.mp4'
    original.write_bytes(request.media_path.read_bytes())
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    prepared = replace(prepared, source_sha256=digest)
    resource = Resource(name='Legacy reference', origin='legacy', kind='video',
        original_path='sources/media/legacy.mp4', sha256=digest, size_bytes=original.stat().st_size,
        duration_seconds=1, status='partial', media_metadata={
            'frame_timing': request.video.frame_timing.model_dump(), 'has_audio': has_audio},
        evidence=[EvidenceRevision(revision=1, processor='legacy-import', correction_note='Imported user corrections',
            events=[EvidenceEvent(id='visual_saved', kind='visual', text='Corrected blue package', start_seconds=.3, end_seconds=.6),
                    EvidenceEvent(id='ocr_saved', kind='on_screen_text', text='Qualified product wording', start_seconds=.3, end_seconds=.6),
                    EvidenceEvent(id='speech_saved', kind='speech', text='Corrected first words', start_seconds=0, end_seconds=.3)],
            coverage={'visual_action':'observations', 'on_screen_text':'observations', 'speech':'failed', 'music':'not_analyzed', 'sfx':'not_analyzed'},
            diagnostics={'speech':'provider_timeout'}, limitations=['Speech transcription failed. Retry transcription.'])])
    project = store.update(project.id, project.version, lambda p: p.resources.append(resource))
    class AlignedSpeech(AlternateSpeech):
        def transcribe(self, chunk, *, metadata):
            result = super().transcribe(chunk, metadata=metadata)
            for segment, (start, end) in zip(result['segments'], [(0, .3), (.3, .6), (.6, .8)]):
                segment.update(start=start, end=end)
            return result
    vision, speech = AlternateVision(), AlignedSpeech()
    adapters = []
    def factory(settings):
        adapter = ProviderRecognitionAdapter(settings, vision_provider=vision, transcription_provider=speech, prepare=lambda *_: prepared)
        adapters.append(adapter)
        return adapter
    service = AnalysisService(store, lambda: ProviderSettings(api_key='offline-fixture-only', experiment_budget_enabled=False), recognition_factory=factory)
    return store, project, service, resource, vision, speech, adapters


def test_migrated_corrected_partial_retries_speech_without_sending_visuals(tmp_path):
    store, project, service, resource, vision, speech, adapters = setup_retry(tmp_path)
    previous = resource.evidence[0].model_dump()
    result = service.retry_reference(project.id, resource.id)
    assert speech.calls == 1 and vision.calls == 0
    assert result.resources[0].evidence[0].model_dump() == previous
    current = result.resources[0].evidence[-1]
    retained = {event.id: event for event in current.events}
    for old in resource.evidence[0].events:
        assert retained[old.id] == old
    assert len(current.events) > len(resource.evidence[0].events)
    assert current.coverage['speech'] == 'observations'
    assert 'speech' not in current.diagnostics
    assert current.reviewed is False and result.jobs[-1].status == 'succeeded'
    assert all(record['capability'] != 'vision' for record in adapters[0].records)
    reopened = ProjectStore(store.root).get(project.id)
    assert reopened.resources[0].evidence == result.resources[0].evidence
    service.retry_reference(project.id, resource.id)
    assert speech.calls == 1


def test_retry_failure_retains_corrections_and_sanitizes_provider_payload(tmp_path):
    _, project, service, resource, vision, speech, _ = setup_retry(tmp_path)
    def failed(*_args, **_kwargs):
        raise ProviderError('provider_quota', 'PRIVATE RAW provider body with secret sk-test')
    speech.transcribe = failed
    result = service.retry_reference(project.id, resource.id)
    assert result.resources[0].evidence == resource.evidence
    assert result.jobs[-1].status == 'failed'
    assert result.jobs[-1].error_code == 'provider_quota'
    assert 'billing' in result.jobs[-1].error
    assert 'PRIVATE' not in result.jobs[-1].error and vision.calls == 0


@pytest.mark.parametrize('has_audio,expected,calls', [(False,'no_audio',0), (True,'none_found',1)])
def test_no_audio_and_empty_transcript_are_distinct(tmp_path, has_audio, expected, calls):
    _, project, service, resource, _, speech, _ = setup_retry(tmp_path, has_audio=has_audio)
    def empty(*_args, **_kwargs):
        speech.calls += 1
        return {'text':'', 'segments':[]}
    speech.transcribe = empty
    result = service.retry_reference(project.id, resource.id)
    assert result.resources[0].evidence[-1].coverage['speech'] == expected
    assert speech.calls == calls


def test_billing_is_diagnosed_only_from_actual_error_code():
    busy = provider_http_error(httpx.Response(429, json={'error': {'message':'secret body'}}))
    quota = provider_http_error(httpx.Response(429, json={'error': {'code':'insufficient_quota', 'message':'secret body'}}))
    assert 'busy' in public_failure(busy)[1] and 'billing' not in public_failure(busy)[1]
    assert 'billing' in public_failure(quota)[1]
    assert 'secret' not in public_failure(quota)[1]


def test_explicit_retry_transcribes_previously_not_analyzed_corrected_evidence(tmp_path):
    store, project, service, resource, vision, speech, _ = setup_retry(tmp_path)
    store.update(project.id, project.version,
        lambda p: p.resources[0].evidence[0].coverage.update({'speech':'not_analyzed'}))
    result = service.retry_reference(project.id, resource.id)
    assert speech.calls == 1 and vision.calls == 0
    assert result.resources[0].evidence[-1].coverage['speech'] == 'observations'


def test_synthesis_version_change_does_not_invalidate_extraction(tmp_path, monkeypatch):
    from backend.app.project_workspace import analysis
    _, _, service, resource, _, _, _ = setup_retry(tmp_path)
    before = service._processor(resource, service.settings_provider())
    monkeypatch.setattr(analysis, 'ANALYSIS_VERSION', 'new-synthesis-only')
    assert service._processor(resource, service.settings_provider()) == before


def test_retry_partial_overlap_is_unresolved_and_exposes_candidate_without_splitting():
    from backend.app.project_workspace.speech_retry import merge_retry
    old = EvidenceEvent(id='corrected', kind='speech', text='User wording', start_seconds=0, end_seconds=1)
    candidate = EvidenceEvent(id='new', kind='speech', text='New complete sentence extending beyond the correction.',
                              start_seconds=0, end_seconds=5)
    previous = EvidenceRevision(revision=2, events=[old], coverage={'speech':'failed'}, correction_note='User correction')
    incoming = EvidenceRevision(revision=1, events=[candidate], coverage={'speech':'observations'})
    merged = merge_retry(previous, incoming, speech_only=True)
    assert merged.events == [old]
    assert merged.coverage['speech'] == 'partial'
    assert merged.diagnostics['speech'] == 'speech_merge_conflict'
    assert any('0–5s' in note and candidate.text in note for note in merged.limitations)
    assert any('apply your correction' in note for note in merged.limitations)
    assert previous.events == [old] and incoming.events == [candidate]
    # The user can reconcile wording/timing; a cached retry clears only the
    # resolved warning, without replacing their new correction or splitting text.
    resolved = merged.model_copy(deep=True)
    resolved.events[0].end_seconds = 5
    resolved.events[0].text = 'User reconciled complete wording'
    complete = merge_retry(resolved, incoming, speech_only=True)
    assert complete.coverage['speech'] == 'observations'
    assert complete.events == resolved.events
    assert 'speech' not in complete.diagnostics
    assert not any(note.startswith('Recovery needs review:') for note in complete.limitations)


def test_retry_detects_uncovered_gap_inside_overlapping_corrections():
    from backend.app.project_workspace.speech_retry import merge_retry
    saved = [EvidenceEvent(id='first', kind='speech', text='First correction', start_seconds=0, end_seconds=1),
             EvidenceEvent(id='last', kind='speech', text='Last correction', start_seconds=3, end_seconds=5)]
    previous = EvidenceRevision(revision=2, events=saved, coverage={'speech':'partial'}, correction_note='Corrected')
    incoming = EvidenceRevision(revision=1, coverage={'speech':'observations'}, events=[
        EvidenceEvent(id='candidate', kind='speech', text='A sentence spanning the gap', start_seconds=0, end_seconds=5)])
    merged = merge_retry(previous, incoming, speech_only=True)
    assert merged.events == saved
    assert merged.coverage['speech'] == 'partial'
    # Adjacent retained intervals cover the candidate; this is not a conflict.
    previous.events[0].end_seconds = 3
    assert merge_retry(previous, incoming, speech_only=True).coverage['speech'] == 'observations'
