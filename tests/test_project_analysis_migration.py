"""Saved legacy logic reports are visible again, without another provider call."""
from dataclasses import replace
import json

from backend.app.models import TaskState
from backend.app.project_workspace.analysis import current_analysis
from backend.app.project_workspace.models import Analysis, EvidenceEvent, InputManifest
from backend.app.project_workspace.store import ProjectStore
from backend.app.service import WorkflowService
from backend.app.structure_models import Graph, Workspace
from backend.app.structure_store import StructureStore
from test_workflow import outputs


def legacy_with_graph(tmp_path):
    legacy = WorkflowService(tmp_path)
    state = outputs(legacy)
    evidence = next(item for item in state.analyses if item.analysis_id == state.task.current_analysis.id)
    events = evidence.events[:2]
    graph = Graph(title="Synthetic fixture structure", summary="An observed moment leads into a second moment.",
        nodes=[{"id": f"node_{index}", "label": f"Observed moment {index}", "explanation": event.text or event.description,
                "kind": "observation", "event_ids": [event.event_id], "source_ids": [], "context_ids": []}
               for index, event in enumerate(events)],
        edges=[{"id": "edge_one", "from_node": "node_0", "to_node": "node_1", "relation": "Then",
                "explanation": "The authored synthetic fixture describes these moments in order."}],
        methods=[], research_gaps=[])
    structures = StructureStore(legacy.store.path)
    workspace = structures.create(Workspace(structure_id="structure_saved", task_id=state.task.task_id,
        video_id=state.task.current_video_id, analysis_ref=state.task.current_analysis,
        graph_revision=1, graph=graph, status="ready", origin="sample"))
    return legacy, state, structures, workspace


def test_migrated_analysis_keeps_genuine_graph_and_exact_source_moments(tmp_path):
    legacy, state, _, _ = legacy_with_graph(tmp_path)
    store = ProjectStore(tmp_path)
    project = store.migrate_legacy(legacy)[0]
    result = current_analysis(project, project.contents[0].id)
    assert result is not None
    assert len(result.structures[0].nodes) == 2 and len(result.structures[0].edges) == 1
    assert result.structures[0].edges[0].label == "Then"
    source = result.structures[0].nodes[0].sources[0]
    original = state.analyses[0].events[0]
    assert source.event_id == original.event_id
    assert source.resource_id == state.task.current_video_id
    assert source.start_seconds == state.videos[0].frame_timing.frame_boundaries_seconds[original.start_frame]
    assert "fictional sample" in " ".join(result.limitations)
    reopened = ProjectStore(tmp_path)
    assert current_analysis(reopened.get(project.id), project.contents[0].id) == result
    assert reopened.migrate_legacy(legacy) == []
    assert len(reopened.get(project.id).analyses) == 1


def test_already_imported_archive_backfills_without_replacing_new_current_work(tmp_path):
    legacy, _, _, _ = legacy_with_graph(tmp_path)
    store = ProjectStore(tmp_path)
    project = store.migrate_legacy(legacy)[0]
    content_id = project.contents[0].id
    modern = Analysis(content_id=content_id, conclusion="A newer saved conclusion.", inputs=InputManifest())
    # Simulate the 1.8.0 state: graph lives only in the saved archive, followed by
    # a newer 1.8 report that must stay current during the 1.8.1 recovery.
    project = store.update(project.id, project.version, lambda p: setattr(p, "analyses", [modern]))
    archive = store.project_dir(project.id) / "legacy/related-records.json"
    before = archive.read_bytes()
    store.migrate_legacy(legacy)
    recovered = store.get(project.id)
    assert len(recovered.analyses) == 2
    assert current_analysis(recovered, content_id) == modern
    assert recovered.analyses[0].structures[0].nodes
    assert archive.read_bytes() == before
    version = recovered.version
    store.migrate_legacy(legacy)
    assert store.get(project.id).version == version


def test_failed_legacy_replacement_restores_last_successful_saved_graph(tmp_path):
    legacy, _, structures, workspace = legacy_with_graph(tmp_path)
    def fail(result):
        result.status = "failed"
        result.graph = None
    structures.update(workspace.structure_id, fail)
    project = ProjectStore(tmp_path).migrate_legacy(legacy)[0]
    result = current_analysis(project, project.contents[0].id)
    assert result is not None
    assert result.structures[0].summary == workspace.graph.summary


def test_existing_import_restores_failed_chunk_coverage_through_corrections_and_retries(tmp_path):
    """Actual adapter invocation with injected speech, not live transcription."""
    from backend.app.project_workspace.analysis import AnalysisService
    from backend.app.providers.config import ProviderSettings
    from backend.app.providers.recognition import ProviderRecognitionAdapter
    from test_providers import AlternateSpeech, AlternateVision, recognition_input

    legacy, _, _, _ = legacy_with_graph(tmp_path)
    store = ProjectStore(tmp_path)
    project = store.migrate_legacy(legacy)[0]
    archive = store.project_dir(project.id) / "legacy/task-state.json"
    snapshot = json.loads(archive.read_text())
    original = snapshot['analyses'][-1]
    original['status'] = 'partial'
    original['events'].append({'event_id': 'speech_partial', 'video_id': original['video_id'],
        'lane': 'audio', 'kind': 'speech', 'text': 'An earlier speech chunk survived.',
        'start_frame': 0, 'end_frame': 1, 'source': 'offline-test', 'method': 'fixture'})
    original['coverage']['speech'] = 'observations'
    original['extraction_failures'] = {'speech': {'code': 'provider_temporarily_unavailable',
        'message': 'A later chunk failed after earlier speech was retained.'}}
    for collection in ('directions', 'production_briefs', 'storyboards'):
        for artifact in snapshot[collection]:
            artifact['currentness'] = 'outdated'
    snapshot['task']['chosen_direction'] = None
    snapshot['task']['selected_direction'] = None
    # A real historical combination: observed partial speech plus failed chunk.
    snapshot = TaskState.model_validate(snapshot).model_dump(mode='json')
    archive.write_text(json.dumps(snapshot))
    archive_before = archive.read_bytes()
    resource = project.resources[0]
    def old_import(p):
        saved = p.resources[0]
        saved.status = 'ready'
        saved.media_metadata['has_audio'] = True
        saved.evidence[-1].coverage['speech'] = 'observations'
        saved.evidence[-1].diagnostics = {}
        saved.evidence[-1].events.append(EvidenceEvent(id='speech_partial', kind='speech',
            text='An earlier speech chunk survived.', start_seconds=0,
            end_seconds=saved.media_metadata['frame_timing']['frame_boundaries_seconds'][1],
            start_frame=0, end_frame=1))
    project = store.update(project.id, project.version, old_import)
    _, prepared = recognition_input.__wrapped__(tmp_path)
    prepared = replace(prepared, source_sha256=resource.sha256)
    speech, vision = AlternateSpeech(), AlternateVision()
    def recovered_chunk(*_args, **_kwargs):
        speech.calls += 1
        return {'text': 'Recovered later words.', 'segments': [
            {'start': .4, 'end': .6, 'text': 'Recovered later words.'}]}
    speech.transcribe = recovered_chunk
    service = AnalysisService(store, lambda: ProviderSettings(api_key='offline-fixture-only', experiment_budget_enabled=False),
        recognition_factory=lambda settings: ProviderRecognitionAdapter(settings, vision_provider=vision,
            transcription_provider=speech, prepare=lambda *_: prepared))
    events = [event.model_copy(deep=True) for event in project.resources[0].evidence[-1].events]
    events[0].text = 'User corrected this saved observation'
    project = service.correct_evidence(project.id, project.version, resource.id, events)
    correction = project.resources[0].evidence[-1]
    assert correction.coverage['speech'] == 'observations'
    store.migrate_legacy(legacy)
    recovered = store.get(project.id)
    assert recovered.resources[0].status == 'partial'
    assert recovered.resources[0].evidence[-1].coverage['speech'] == 'failed'
    assert recovered.resources[0].evidence[-1].events == events
    assert recovered.resources[0].evidence[-1].diagnostics['speech'] == 'provider_temporarily_unavailable'
    retried = service.retry_reference(project.id, resource.id)
    assert speech.calls == 1 and vision.calls == 0
    assert retried.resources[0].evidence[-1].coverage['speech'] == 'observations'
    assert all(event in retried.resources[0].evidence[-1].events for event in events)
    current = retried.resources[0].evidence[-1].model_dump()
    # Another launch must not reapply the archived failure after a real retry.
    store.migrate_legacy(legacy)
    assert store.get(project.id).resources[0].evidence[-1].model_dump() == current
    assert store.get(project.id).resources[0].status == 'ready'
    assert archive.read_bytes() == archive_before
