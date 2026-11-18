"""Synthetic offline regressions for durable per-source analysis and synthesis."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from backend.app.project_workspace.models import BriefRevision, Fact
from backend.app.providers.base import ProviderError
from backend.app.workflow_errors import WorkflowError
import test_project_workspace_analysis as baseline


class LayeredTransport(baseline.Synthesis):
    def __init__(self):
        super().__init__()
        self.stages = []
        self.contexts = []
        self.fail_summary = False
        self.commonality = False
        self.on_single = None

    def json_response(self, model, prompt, schema, name, **kwargs):
        context = json.loads(prompt.split("INPUT_JSON:\n", 1)[1])
        self.stages.append(name)
        self.contexts.append(deepcopy(context))
        if name == "project_reference_analysis" and self.fail_summary:
            raise ProviderError("provider_timeout", "Synthetic synthesis timeout")
        result = super().json_response(model, prompt, schema, name, **kwargs)
        refs = result["citations"]
        if name == "project_single_video_analysis" and self.on_single:
            self.on_single()
        result["key_insights"] = [{"title": "Promise first", "observation": "The source opens with a spoken promise.",
            "application": "Consider a concise opening promise when justified.",
            "scope": "commonality" if self.commonality else "observation", "citations": refs}]
        return result


@pytest.fixture
def workspace(tmp_path):
    store, project, service, recognizer, _ = baseline.workspace.__wrapped__(tmp_path)
    transport = LayeredTransport()
    service.transport_factory = lambda _: transport
    return store, project, service, recognizer, transport


def test_single_then_multiple_reuses_durable_source_analysis(workspace):
    store, project, service, recognizer, transport = workspace
    first, second = [resource.id for resource in project.resources]
    one = service.analyze(project.id, [first])
    assert len(one.single_video_analyses) == 1
    single_id = one.single_video_analyses[0].id
    multiple = service.analyze(project.id, [first, second])
    assert len(multiple.single_video_analyses) == 2
    assert multiple.analyses[-1].single_analysis_ids[first] == single_id
    assert transport.stages.count("project_single_video_analysis") == 2
    assert recognizer.calls == [first, second]
    reopened = type(store)(store.root).get(project.id)
    assert reopened.single_video_analyses == multiple.single_video_analyses


def test_failed_synthesis_retains_completed_single_analyses_and_retry_skips_upstream(workspace):
    store, project, service, recognizer, transport = workspace
    ids = [resource.id for resource in project.resources]
    transport.fail_summary = True
    with pytest.raises(ProviderError, match="Synthetic"):
        service.analyze(project.id, ids)
    failed = store.get(project.id)
    assert len(failed.single_video_analyses) == 2
    assert all(item.status == "succeeded" for item in failed.single_video_analyses)
    assert not failed.analyses
    upstream = deepcopy(failed.single_video_analyses)
    transport.fail_summary = False
    saved = service.analyze(project.id, ids, synthesis_only=True)
    assert saved.single_video_analyses == upstream
    assert transport.stages.count("project_single_video_analysis") == 2
    assert recognizer.calls == ids


def test_synthesis_reads_compact_analyses_and_citation_index_without_raw_evidence(workspace):
    _, project, service, _, transport = workspace
    service.analyze(project.id, [resource.id for resource in project.resources])
    context = transport.contexts[-1]
    assert context["single_video_analyses"]
    assert "One less thing to worry about." not in json.dumps(context)
    for reference in context["references"]:
        assert reference["evidence"]["events"] == [{"id": f"event_{reference['resource_id']}_0", "kind": "speech"}]
    for single_context in transport.contexts[:-1]:
        assert "confirmed_brief" not in single_context


def test_only_changed_source_reanalyzes_and_brief_change_reuses_core(workspace):
    store, project, service, recognizer, transport = workspace
    ids = [resource.id for resource in project.resources]
    saved = service.analyze(project.id, ids)
    event = saved.resources[0].evidence[-1].events[0].model_copy(update={"text": "A corrected promise."})
    saved = service.correct_evidence(project.id, saved.version, ids[0], [event])
    saved = service.analyze(project.id, ids)
    assert transport.stages.count("project_single_video_analysis") == 3
    old_ids = saved.analyses[-1].single_analysis_ids.copy()
    store.update(project.id, saved.version, lambda p: p.briefs.append(BriefRevision(revision=1, facts=[Fact(key="audience", value="Designers")])) )
    saved = service.analyze(project.id, ids, synthesis_only=True)
    assert transport.stages.count("project_single_video_analysis") == 3
    assert saved.analyses[-1].single_analysis_ids == old_ids
    assert recognizer.calls == ids


@pytest.mark.parametrize("change", ["model", "language", "visual_only", "configuration"])
def test_analysis_configuration_changes_invalidate_single_reuse(workspace, change):
    store, project, service, _, transport = workspace
    rid = project.resources[0].id
    saved = service.analyze(project.id, [rid])
    settings = service.settings_provider()
    if change == "model":
        service.settings_provider = lambda: replace(settings, structure_model="gpt-6.2-sol")
    elif change == "language":
        service.settings_provider = lambda: replace(settings, analysis_language="Chinese")
    elif change == "configuration":
        service.settings_provider = lambda: replace(settings, max_output_tokens=settings.max_output_tokens - 1)
    if change == "visual_only":
        from backend.app.project_workspace.models import EvidenceEvent
        store.update(project.id, saved.version, lambda p: p.resources[0].evidence[-1].events.append(
            EvidenceEvent(id="visual", kind="visual", text="A visible object.", start_seconds=0, end_seconds=.5)))
    service.analyze(project.id, [rid], visual_only=change == "visual_only")
    assert transport.stages.count("project_single_video_analysis") == 2


def test_single_source_cannot_be_labeled_commonality(workspace):
    store, project, service, _, transport = workspace
    transport.commonality = True
    with pytest.raises(WorkflowError) as error:
        service.analyze(project.id, [project.resources[0].id])
    assert error.value.code == "analysis_commonality_support"
    assert not store.get(project.id).analyses


def test_stale_single_result_cannot_overwrite_changed_evidence(workspace):
    store, project, service, _, transport = workspace
    rid = project.resources[0].id
    def mutate():
        state = store.get(project.id)
        event = state.resources[0].evidence[-1].events[0].model_copy(update={"text": "A newer correction."})
        service.correct_evidence(project.id, state.version, rid, [event])
    transport.on_single = mutate
    with pytest.raises(WorkflowError) as error:
        service.analyze(project.id, [rid])
    assert error.value.code == "analysis_inputs_changed"
    assert not store.get(project.id).analyses
    assert not any(item.status == "succeeded" for item in store.get(project.id).single_video_analyses)


def test_synthesis_cannot_omit_material_source_limitations(workspace):
    store, project, service, _, transport = workspace
    rid = project.resources[0].id
    state = service.retry_reference(project.id, rid)
    store.update(project.id, state.version, lambda p: p.resources[0].evidence[-1].limitations.append(
        "The critical action occurs outside the observed samples."))
    state = service.set_selection(project.id, store.get(project.id).version, [rid])
    saved = service.analyze(project.id, [rid], synthesis_only=True)
    assert "The critical action occurs outside the observed samples." in saved.analyses[-1].limitations


def test_same_revision_changed_evidence_rejects_inflight_synthesis(workspace):
    store, project, service, _, transport = workspace
    rid = project.resources[0].id
    original = transport.json_response
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[3] == "project_reference_analysis":
            store.update(project.id, None, lambda p: setattr(p.resources[0].evidence[-1].events[0], "text", "A different saved source."))
        return result
    transport.json_response = changed
    with pytest.raises(WorkflowError) as error:
        service.analyze(project.id, [rid])
    assert error.value.code == "analysis_inputs_changed"
    assert not store.get(project.id).analyses


def test_stop_during_extraction_prevents_next_source_calls(workspace):
    from backend.app.project_workspace.models import Job
    store, project, service, recognizer, transport = workspace
    job = Job(kind="analysis", status="running")
    store.update(project.id, None, lambda p: p.jobs.append(job))
    original = recognizer.analyze
    def stop(request):
        result = original(request)
        store.update(project.id, None, lambda p: setattr(next(item for item in p.jobs if item.id == job.id), "status", "stopped"))
        return result
    recognizer.analyze = stop
    ids = [resource.id for resource in project.resources]
    with pytest.raises(WorkflowError) as error:
        service.analyze(project.id, ids, parent_job_id=job.id)
    assert error.value.code == "analysis_stopped"
    assert recognizer.calls == ids[:1]
    assert not transport.stages
    assert store.get(project.id).resources[0].evidence


def test_stop_during_core_retains_valid_inflight_result_without_synthesis(workspace):
    from backend.app.project_workspace.models import Job
    store, project, service, _, transport = workspace
    job = Job(kind="analysis", status="running")
    store.update(project.id, None, lambda p: p.jobs.append(job))
    def stop():
        store.update(project.id, None, lambda p: setattr(next(item for item in p.jobs if item.id == job.id), "status", "stopped"))
    transport.on_single = stop
    with pytest.raises(WorkflowError) as error:
        service.analyze(project.id, [project.resources[0].id], parent_job_id=job.id)
    assert error.value.code == "analysis_stopped"
    state = store.get(project.id)
    assert state.single_video_analyses[0].status == "succeeded"
    assert transport.stages == ["project_single_video_analysis"]
    assert not state.analyses


def test_compact_report_source_index_includes_all_reused_core_graph_sources(workspace):
    _, project, service, _, transport = workspace
    original = transport.json_response
    def compliant(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[3] == "project_reference_analysis":
            result.pop("structures", None)
        return result
    transport.json_response = compliant
    saved = service.analyze(project.id, [r.id for r in project.resources])
    report = saved.analyses[-1]
    assert {source.resource_id for source in report.sources} == {r.id for r in project.resources}
    assert all((source.resource_id, source.evidence_revision, source.event_id) in
               {(ref.resource_id, ref.evidence_revision, ref.event_id) for ref in report.sources}
               for graph in report.structures for node in graph.nodes for source in node.sources)


def test_peer_failure_preserves_successfully_completed_source(workspace):
    store, project, service, _, transport = workspace
    ids = [resource.id for resource in project.resources]
    original = transport.json_response
    def partial(*args, **kwargs):
        context = json.loads(args[1].split("INPUT_JSON:\n", 1)[1])
        if args[3] == "project_single_video_analysis" and context["references"][0]["resource_id"] == ids[0]:
            raise ProviderError("provider_timeout", "One synthetic source timed out")
        return original(*args, **kwargs)
    transport.json_response = partial
    with pytest.raises(ProviderError):
        service.analyze(project.id, ids)
    states = {item.resource_id: item.status for item in store.get(project.id).single_video_analyses}
    assert states == {ids[0]: "failed", ids[1]: "succeeded"}
    assert not store.get(project.id).analyses


def test_instruction_change_invalidates_single_analysis_only(workspace, monkeypatch):
    import hashlib
    from backend.app.project_workspace import planning
    _, project, service, recognizer, transport = workspace
    rid = project.resources[0].id
    saved = service.analyze(project.id, [rid])
    old_core = saved.single_video_analyses[-1].id
    original = planning.load_instructions
    def changed(module):
        text, _ = original(module)
        text += "\nA changed source-analysis instruction."
        return text, hashlib.sha256(text.encode()).hexdigest()
    monkeypatch.setattr(planning, "load_instructions", changed)
    saved = service.analyze(project.id, [rid], synthesis_only=True)
    assert saved.single_video_analyses[-1].id != old_core
    assert recognizer.calls == [rid]
    assert transport.single_calls == 2


def test_single_analysis_concurrency_is_bounded_to_two(workspace):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from backend.app.project_workspace.models import uid
    store, project, service, _, transport = workspace
    third = project.resources[0].model_copy(deep=True, update={"id": uid("resource"), "name": "Third reference"})
    store.update(project.id, None, lambda p: p.resources.append(third))
    ids = [r.id for r in project.resources] + [third.id]
    lock, both_started, release = threading.Lock(), threading.Event(), threading.Event()
    active = maximum = started = 0
    original = transport.json_response
    def bounded(*args, **kwargs):
        nonlocal active, maximum, started
        if args[3] != "project_single_video_analysis":
            return original(*args, **kwargs)
        with lock:
            active += 1
            started += 1
            maximum = max(maximum, active)
            if active == 2:
                both_started.set()
        try:
            assert release.wait(10), "Test did not release the authored source responses"
            return original(*args, **kwargs)
        finally:
            with lock:
                active -= 1
    transport.json_response = bounded
    with ThreadPoolExecutor(max_workers=1) as caller:
        task = caller.submit(service.analyze, project.id, ids)
        try:
            assert both_started.wait(10), "Two independent sources did not start"
            with lock:
                assert started == 2 and maximum == 2
        finally:
            release.set()
        saved = task.result(timeout=10)
    assert maximum == 2
    assert len([item for item in saved.single_video_analyses if item.status == "succeeded"]) == 3


def test_support_records_preserve_available_usage_without_private_payload():
    from backend.app.project_workspace.analysis import _support_records
    record = {"stage": "single_video_analysis", "attempts": 2, "timeout_seconds": 45,
        "usage": {"input_tokens": {"value": 123, "unit": "tokens"}, "output_tokens": {"value": 47, "unit": "tokens"}},
        "prompt": "private source content", "response": "private response", "api_key": "private key"}
    support = _support_records([record], "project_test", "resource_test")[0]
    assert support["input_tokens"] == "123" and support["output_tokens"] == "47"
    assert support["timeout_seconds"] == "45"
    assert not any(value.startswith("private") for value in support.values())


@pytest.mark.parametrize("kinds", [("audio", "audio"), ("video", "audio"), ("video", "video")])
def test_commonality_requires_two_different_videos(workspace, kinds):
    from backend.app.project_workspace.analysis import Conclusion, _resolve_conclusion
    from backend.app.project_workspace.models import EvidenceEvent, EvidenceRevision
    _, project, _, _, _ = workspace
    resources = [resource.model_copy(deep=True) for resource in project.resources]
    for resource, kind in zip(resources, kinds, strict=True):
        resource.kind = kind
        resource.evidence = [EvidenceRevision(revision=1, events=[
            EvidenceEvent(id="opening", kind="visual" if kind == "video" else "speech", text="An opening promise", start_seconds=0, end_seconds=1)])]
    citations = [{"resource_id": resource.id, "event_id": "opening", "reason": "Supporting opening"} for resource in resources]
    result = Conclusion(conclusion="A scope", findings=[], differences=[], opportunities=[], limitations=[],
        citations=citations, key_insights=[{"title": "Shared opening", "scope": "commonality",
            "observation": "Both videos open with a promise.", "application": "Consider an opening promise when supported.", "citations": citations}])
    if kinds == ("video", "video"):
        _, insights, _ = _resolve_conclusion(result, resources, expected_structures=False)
        assert insights[0].support_resource_ids == [resource.id for resource in resources]
    else:
        with pytest.raises(WorkflowError) as error:
            _resolve_conclusion(result, resources, expected_structures=False)
        assert error.value.code == "analysis_commonality_support"


def test_failed_core_retains_actual_safe_transport_attempt_diagnostics(workspace):
    store, project, service, _, transport = workspace
    def failed(*_args, **_kwargs):
        raise ProviderError("provider_timeout", "Synthetic transport timeout")
    transport.json_response = failed
    transport.last_diagnostics = lambda: {"attempts": 2, "provider_request_id": "offline-request-2",
        "http_status": 504, "timeout_seconds": 45, "usage": {"input_tokens": {"value": 87, "unit": "tokens"}},
        "prompt": "private source prompt", "response": "private source response", "api_key": "private key"}
    with pytest.raises(ProviderError):
        service.analyze(project.id, [project.resources[0].id])
    run = store.get(project.id).single_video_analyses[0]
    assert run.status == "failed"
    assert run.diagnostics["attempts"] == "2"
    assert run.diagnostics["provider_request_id"] == "offline-request-2"
    assert run.diagnostics["input_tokens"] == "87"
    assert not any(value.startswith("private") for value in run.diagnostics.values())


def test_exact_duplicate_insights_merge_all_attribution_without_changing_scope(workspace):
    from backend.app.project_workspace.analysis import Conclusion, _resolve_conclusion
    from backend.app.project_workspace.models import EvidenceEvent, EvidenceRevision
    _, project, _, _, _ = workspace
    resources = [resource.model_copy(deep=True) for resource in project.resources]
    for resource in resources:
        resource.evidence = [EvidenceRevision(revision=1, events=[
            EvidenceEvent(id="opening", kind="visual", text="An observed opening", start_seconds=0, end_seconds=1)])]
    result = Conclusion(conclusion="Source scope", findings=[], differences=[], opportunities=[], limitations=[],
        key_insights=[{"title": "Opening", "scope": "observation", "observation": "An opening demonstrates the product.",
            "application": "Consider a demonstration where supported.", "citations": [{"resource_id": resource.id,
                "event_id": "opening", "reason": "Supporting opening"}]} for resource in resources])
    refs, insights, _ = _resolve_conclusion(result, resources, expected_structures=False)
    assert len(insights) == 1
    assert insights[0].scope == "observation"
    assert insights[0].support_resource_ids == [resource.id for resource in resources]
    assert [source.resource_id for source in insights[0].sources] == [resource.id for resource in resources]
    assert [source.resource_id for source in refs] == [resource.id for resource in resources]


@pytest.mark.parametrize("stage,field", [("project_single_video_analysis", "title"),
    ("project_single_video_analysis", "method"), ("project_single_video_analysis", "flow"),
    ("project_single_video_analysis", "borrowable"), ("project_reference_analysis", "title")])
@pytest.mark.parametrize("invalid", ["missing", "", "   "])
def test_new_provider_results_require_useful_compact_fields(workspace, stage, field, invalid):
    store, project, service, _, transport = workspace
    original = transport.json_response
    def malformed(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[3] == stage:
            target = result["key_insights"][0] if field == "title" else result["structures"][0]
            if invalid == "missing":
                target.pop(field, None)
            else:
                target[field] = invalid
        return result
    transport.json_response = malformed
    with pytest.raises(WorkflowError) as error:
        service.analyze(project.id, [project.resources[0].id])
    assert error.value.code == "invalid_analysis_response"
    assert not store.get(project.id).analyses
    if stage == "project_reference_analysis":
        assert store.get(project.id).single_video_analyses[0].status == "succeeded"


def test_legacy_saved_reports_keep_honest_absent_compact_fields(workspace):
    from backend.app.project_workspace.models import Analysis, AnalysisInsight, InputManifest, ReferenceStructure
    store, project, _, _, _ = workspace
    report = Analysis(inputs=InputManifest(), conclusion="A historical source report.",
        key_insights=[AnalysisInsight(observation="Historical observation", application="Historical advice")],
        structures=[ReferenceStructure(resource_id=project.resources[0].id, summary="Historical summary", nodes=[])])
    store.update(project.id, None, lambda p: p.analyses.append(report))
    reopened = type(store)(store.root).get(project.id)
    legacy = reopened.analyses[0]
    assert legacy.report_version is None and legacy.single_analysis_ids == {}
    assert legacy.key_insights[0].title == ""
    assert (legacy.structures[0].method, legacy.structures[0].flow, legacy.structures[0].borrowable) == ("", "", "")
    assert reopened.single_video_analyses == []


def test_stop_during_synthesis_preserves_frozen_job_inputs_and_completed_sources(workspace):
    from backend.app.project_workspace.models import Job
    store, project, service, _, transport = workspace
    parent = Job(kind="analyze", status="running")
    store.update(project.id, None, lambda p: p.jobs.append(parent))
    original = transport.json_response
    def stopped(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[3] == "project_reference_analysis":
            store.update(project.id, None, lambda p: setattr(next(job for job in p.jobs if job.id == parent.id), "status", "stopped"))
        return result
    transport.json_response = stopped
    rid = project.resources[0].id
    with pytest.raises(WorkflowError) as error:
        service.analyze(project.id, [rid], parent_job_id=parent.id)
    assert error.value.code == "analysis_stopped"
    saved = store.get(project.id)
    job = next(item for item in saved.jobs if item.id == parent.id)
    assert job.status == "stopped" and job.inputs is not None
    assert job.inputs.resource_ids == [rid]
    assert job.inputs.single_analysis_ids == {rid: saved.single_video_analyses[0].id}
    assert saved.single_video_analyses[0].status == "succeeded"
    assert not saved.analyses
