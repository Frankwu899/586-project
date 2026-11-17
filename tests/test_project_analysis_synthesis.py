"""Offline synthesis validation: redundant indexes never replace exact evidence."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from backend.app.project_workspace.models import ContentItem, EvidenceEvent
from backend.app.providers.transport import OpenAITransport
from backend.app.workflow_errors import WorkflowError
import test_project_workspace_analysis as baseline
from test_project_speech_profiles_184 import _audio_project


@pytest.fixture
def workspace(tmp_path):
    return baseline.workspace.__wrapped__(tmp_path)


@pytest.fixture(autouse=True)
def no_paid_requests(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Synthesis contract tests must not call a paid provider")
    monkeypatch.setattr(OpenAITransport, "_request", forbidden)


@pytest.fixture
def validation_records(workspace, monkeypatch):
    synthesis = workspace[-1]
    records = []
    def record(outcome, **details):
        records.append({"validation_outcome": outcome, **details})
    monkeypatch.setattr(synthesis, "validation_result", record, raising=False)
    monkeypatch.setattr(synthesis, "last_diagnostics", lambda: deepcopy(records[-1]), raising=False)
    return records


@pytest.mark.parametrize("omit_index", [False, True])
def test_valid_nested_citations_build_complete_exact_source_index(workspace, validation_records, omit_index):
    _, project, service, recognizer, synthesis = workspace
    original = synthesis.json_response
    def nested(model, prompt, schema, *args, **kwargs):
        assert schema["properties"]["citations"]["minItems"] == 1
        assert "citations" in schema["required"]
        assert "nonempty top-level citations index" in prompt
        result = original(model, prompt, schema, *args, **kwargs)
        result["key_insights"] = [{"observation": "A saved spoken promise.",
            "application": "Adapt its function without adopting its claim.",
            "citations": result["citations"]}]
        if omit_index:
            del result["citations"]
        else:
            result["citations"] = []
        return result
    synthesis.json_response = nested
    ids = [resource.id for resource in project.resources]
    saved = service.analyze(project.id, ids)
    report = saved.analyses[-1]
    assert [source.resource_id for source in report.sources] == ids
    assert len(report.sources) == 2
    for source in report.sources:
        evidence = next(resource for resource in saved.resources if resource.id == source.resource_id).evidence[-1]
        event = next(event for event in evidence.events if event.id == source.event_id)
        assert (source.evidence_revision, source.start_seconds, source.end_seconds, source.excerpt) == (
            evidence.revision, event.start_seconds, event.end_seconds, event.text)
    assert report.key_insights[0].sources[0] in report.sources
    assert recognizer.calls == ids
    assert validation_records[-1] == {"validation_outcome": "accepted", "code": None,
                                      "rule": "grounded_report", "field": "response"}


@pytest.mark.parametrize("empty_index", [False, True])
@pytest.mark.parametrize("location", ["insight", "node", "edge", "cross_graph"])
def test_invalid_nested_citation_cannot_be_hidden_by_another_valid_index(workspace, validation_records,
                                                                      empty_index, location):
    store, project, service, _, synthesis = workspace
    ids = [resource.id for resource in project.resources]
    saved = service.analyze(project.id, ids)
    original = synthesis.json_response
    def invalid(*args, **kwargs):
        result = original(*args, **kwargs)
        graph = result["structures"][0]
        bad = {"resource_id": ids[0], "event_id": "invented", "reason": "Unsupported fixture reference"}
        if location == "insight":
            result["key_insights"] = [{"observation": "A test observation.", "application": "A test application.",
                                       "citations": [bad]}]
        elif location == "node":
            graph["nodes"][0]["citations"] = [bad]
        elif location == "cross_graph":
            graph["nodes"][0]["citations"] = deepcopy(result["structures"][1]["nodes"][0]["citations"])
        else:
            node = deepcopy(graph["nodes"][0])
            node["id"] = "second_moment"
            graph["nodes"].append(node)
            graph["edges"] = [{"source": "moment_one", "target": "second_moment", "label": "A relationship",
                               "explanation": "An unsupported connection.", "citations": [bad]}]
        if empty_index:
            result["citations"] = []
        return result
    synthesis.json_response = invalid
    with pytest.raises(WorkflowError) as failed:
        service.analyze(project.id, ids)
    assert failed.value.code == "invalid_analysis_citation"
    assert store.get(project.id).analyses == saved.analyses
    assert validation_records[-1]["validation_outcome"] == "rejected"
    assert failed.value.diagnostics["rule"] == "exact_source_event"


def test_no_citations_anywhere_are_rejected_without_inventing_evidence(workspace, validation_records):
    store, project, service, _, synthesis = workspace
    original = synthesis.json_response
    def ungrounded(*args, **kwargs):
        result = original(*args, **kwargs)
        result["citations"] = []
        for graph in result["structures"]:
            for node in graph["nodes"]:
                node["citations"] = []
        return result
    synthesis.json_response = ungrounded
    with pytest.raises(WorkflowError) as failed:
        service.analyze(project.id, [project.resources[0].id])
    assert failed.value.code == "invalid_analysis_response"
    assert not store.get(project.id).analyses
    assert failed.value.diagnostics["rule"] == "response_schema"
    assert validation_records[-1]["validation_outcome"] == "rejected"


def test_synthesis_retry_reuses_partial_speech_and_keeps_its_limitations(workspace, validation_records):
    store, project, service, recognizer, synthesis = workspace
    rid = project.resources[0].id
    saved = service.analyze(project.id, [rid])
    def partial(state):
        resource = state.resources[0]
        resource.evidence[-1].coverage["speech"] = "partial"
        resource.evidence[-1].limitations.append("The saved transcript covers only part of the source.")
        resource.evidence[-1].events.append(EvidenceEvent(id="visual_saved", kind="visual",
            text="A retained sampled object.", start_seconds=1, end_seconds=1.5, precision="sample"))
        resource.status = "partial"
    saved = store.update(project.id, saved.version, partial)
    original = synthesis.json_response
    def bad_summary(*args, **kwargs):
        result = original(*args, **kwargs)
        result["citations"][0]["event_id"] = "invented"
        return result
    synthesis.json_response = bad_summary
    with pytest.raises(WorkflowError, match="outside the selected"):
        service.analyze(project.id, [rid], synthesis_only=True)
    synthesis.json_response = original
    stages = []
    retried = service.analyze(project.id, [rid], synthesis_only=True,
        progress=lambda stage, **details: stages.append((stage, details)))
    assert recognizer.calls == [rid]
    assert retried.resources == saved.resources
    assert retried.jobs == saved.jobs
    assert len(retried.analyses) == 2
    assert not retried.analyses[-1].inputs.visual_only
    assert "incomplete coverage" in " ".join(retried.analyses[-1].limitations)
    assert synthesis.context["references"][0]["evidence"]["coverage"]["speech"] == "partial"
    assert "part of the source" in " ".join(synthesis.context["references"][0]["evidence"]["limitations"])
    assert [stage for stage, _ in stages] == ["validating", "synthesizing", "validating", "saving"]
    assert validation_records[-1]["validation_outcome"] == "accepted"


@pytest.mark.parametrize("change", ["hash", "draft"])
def test_summary_only_retry_validates_original_and_pending_corrections_before_provider(workspace, change):
    store, project, service, recognizer, synthesis = workspace
    rid = project.resources[0].id
    saved = service.analyze(project.id, [rid])
    if change == "hash":
        service._original(project.id, saved.resources[0]).write_bytes(b"Changed original bytes")
    else:
        store.update(project.id, saved.version, lambda state: state.editor_drafts.update({
            f"evidence-{rid}": {"base_revision": 1, "events": []}}))
    with pytest.raises(WorkflowError) as failed:
        service.analyze(project.id, [rid], synthesis_only=True)
    assert failed.value.code == ("source_hash_mismatch" if change == "hash" else "evidence_pending_changes")
    assert synthesis.calls == 1
    assert recognizer.calls == [rid]
    assert store.get(project.id).analyses == saved.analyses


@pytest.mark.parametrize("change", ["hash", "draft"])
def test_late_changed_source_or_draft_rejects_the_whole_validated_summary(workspace, validation_records, change):
    store, project, service, _, synthesis = workspace
    rid = project.resources[0].id
    saved = service.analyze(project.id, [rid])
    original = synthesis.json_response
    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        result["citations"] = []
        def modify(state):
            if change == "hash":
                state.resources[0].sha256 = "0" * 64
            else:
                state.editor_drafts[f"evidence-{rid}"] = {"base_revision": 1, "events": []}
        store.update(project.id, None, modify)
        return result
    synthesis.json_response = late
    with pytest.raises(WorkflowError) as failed:
        service.analyze(project.id, [rid], synthesis_only=True)
    assert failed.value.code == ("analysis_inputs_changed" if change == "hash" else "evidence_pending_changes")
    assert store.get(project.id).analyses == saved.analyses
    assert validation_records[-1]["validation_outcome"] == "rejected"
    assert failed.value.diagnostics["rule"] == "current_inputs"


@pytest.mark.parametrize("model,options,code", [
    ("invented-model", {}, "unsupported_model_capability"),
    ("gpt-transcribe", {"synthesis_only": True}, "invalid_analysis_options"),
    ("whisper-1", {"visual_only": True}, "invalid_analysis_options"),
])
def test_invalid_operation_model_choices_do_not_mutate_selection_or_call_providers(workspace, model, options, code):
    store, project, service, recognizer, synthesis = workspace
    with pytest.raises(WorkflowError) as failed:
        service.analyze(project.id, [project.resources[0].id], transcription_model=model, **options)
    assert failed.value.code == code
    assert store.get(project.id) == project
    assert not recognizer.calls and not synthesis.calls


def test_explicit_transcription_model_is_operation_scoped_and_parent_is_forwarded(workspace, monkeypatch):
    store, project, service, _, _ = workspace
    rid = project.resources[0].id
    saved = service.analyze(project.id, [rid])
    observed = []
    def extract(project_id, resource_id, settings, content_id=None, *, parent_job_id=None, transcription_model=None):
        observed.append((resource_id, settings.transcription_model, parent_job_id, transcription_model))
    monkeypatch.setattr(service, "_extract_reference", extract)
    service.analyze(project.id, [rid], transcription_model="gpt-transcribe", parent_job_id="job_parent")
    service.analyze(project.id, [rid])
    assert observed == [(rid, "gpt-transcribe", "job_parent", "gpt-transcribe"), (rid, "whisper-1", None, None)]
    assert store.get(project.id).resources == saved.resources


def test_trashed_video_keeps_reports_but_refuses_new_selection_or_synthesis(workspace):
    store, project, service, recognizer, synthesis = workspace
    rid = project.resources[0].id
    video = ContentItem(title="A preserved video")
    saved = store.update(project.id, project.version, lambda state: state.contents.append(video))
    saved = service.analyze(project.id, [rid], video.id)
    deleted = store.update(project.id, saved.version,
        lambda state: setattr(state.contents[0], "trashed_at", "2026-11-18T00:00:00Z"))
    for action in [lambda: service.analyze(project.id, [rid], video.id, synthesis_only=True),
                   lambda: service.set_selection(project.id, deleted.version, [], video.id)]:
        with pytest.raises(WorkflowError) as failed:
            action()
        assert failed.value.code == "content_trashed" and failed.value.status == 410
    assert store.get(project.id) == deleted
    assert deleted.analyses == saved.analyses
    assert recognizer.calls == [rid] and synthesis.calls == 1


def test_final_semantic_validation_is_persisted_without_private_response_data(workspace, monkeypatch, tmp_path):
    _, project, service, _, synthesis = workspace
    settings = replace(service.settings_provider(), cache_dir=tmp_path / "provider-support")
    transport = OpenAITransport(settings)
    invalid = False
    def response(*args, **kwargs):
        # Exercise the real transport's semantic diagnostic persistence after
        # a decoded offline response, without issuing an HTTP request.
        transport._thread_record.value = {"stage": "responses", "validation_outcome": "decoded",
            "provider_request_id": "offline-request", "prompt": "Private prompt must not enter support records"}
        result = synthesis.json_response(*args, **kwargs)
        result["citations"] = []
        if invalid:
            result["structures"][0]["nodes"][0]["citations"][0]["event_id"] = "invented"
        return result
    monkeypatch.setattr(transport, "json_response", response)
    monkeypatch.setattr(service, "transport_factory", lambda _: transport)
    rid = project.resources[0].id
    service.analyze(project.id, [rid])
    invalid = True
    with pytest.raises(WorkflowError) as failed:
        service.analyze(project.id, [rid], synthesis_only=True)
    records = [json.loads(line) for line in (settings.cache_dir / "validation.jsonl").read_text().splitlines()]
    assert [item["validation_outcome"] for item in records] == ["accepted", "rejected"]
    assert records[-1]["failure_code"] == "invalid_analysis_citation"
    assert records[-1]["validation_rule"] == "exact_source_event"
    assert failed.value.diagnostics == records[-1]
    assert "Private prompt" not in json.dumps(records) and "prompt" not in records[-1]


def test_batch_explicit_model_switch_reaches_real_extraction_and_default_keeps_saved_profile(tmp_path, monkeypatch):
    store, project, resource, service = _audio_project(tmp_path)
    synthesis = baseline.Synthesis()
    calls = []
    def transcribe(_transport, model, _path, *, metadata):
        calls.append((model, metadata["chunk_index"]))
        text = f"Authored {model} text for chunk {metadata['chunk_index']}."
        if model == "whisper-1":
            return {"text": text, "segments": [{"text": text, "start": 0,
                "end": metadata["chunk_end_seconds"] - metadata["chunk_start_seconds"]}]}
        assert model == "gpt-transcribe"
        return {"text": text, "languages": [{"code": "en"}]}
    monkeypatch.setattr(OpenAITransport, "transcribe", transcribe)
    monkeypatch.setattr(OpenAITransport, "json_response",
        lambda _transport, *args, **kwargs: synthesis.json_response(*args, **kwargs))
    first = service.analyze(project.id, [resource.id])
    assert first.resources[0].evidence[-1].diagnostics["speech_model"] == "whisper-1"
    switched = service.analyze(project.id, [resource.id], transcription_model="gpt-transcribe",
                               parent_job_id="batch_parent")
    assert calls == [(model, index) for model in ["whisper-1", "gpt-transcribe"] for index in range(3)]
    evidence = switched.resources[0].evidence[-1]
    assert evidence.revision == 2
    assert evidence.diagnostics["speech_model"] == "gpt-transcribe"
    assert evidence.diagnostics["speech_timing"] == "chunk"
    assert all(event.precision == "interval" for event in evidence.events)
    assert switched.jobs[-1].parent_job_id == "batch_parent"
    assert switched.jobs[-1].diagnostics["requested_speech_model"] == "gpt-transcribe"

    reused = service.analyze(project.id, [resource.id])
    assert len(calls) == 6
    assert reused.resources[0].evidence == switched.resources[0].evidence
    assert reused.jobs[-1].diagnostics["speech_model"] == "gpt-transcribe"
    assert service.settings_provider().transcription_model == "whisper-1"
    assert len(store.get(project.id).analyses) == 3


@pytest.mark.parametrize("video_scope", [False, True])
def test_summary_retry_with_changed_scope_cannot_restore_selection_or_touch_evidence(workspace, video_scope):
    store, project, service, recognizer, synthesis = workspace
    first, second = [resource.id for resource in project.resources]
    content_id = None
    if video_scope:
        video = ContentItem(title="A video with its own current references")
        project = store.update(project.id, project.version, lambda state: state.contents.append(video))
        content_id = video.id
    saved = service.analyze(project.id, [first], content_id)
    changed = service.set_selection(project.id, saved.version, [second], content_id)
    calls = recognizer.calls.copy(), synthesis.calls
    with pytest.raises(WorkflowError) as failed:
        service.analyze(project.id, [first], content_id, synthesis_only=True)
    assert failed.value.code == "analysis_inputs_changed" and failed.value.status == 409
    assert store.get(project.id) == changed
    assert (recognizer.calls, synthesis.calls) == calls
