"""Offline project analysis tests: lineage, isolation, honest failures and citations."""
from dataclasses import replace
import hashlib
import json
import subprocess
from types import SimpleNamespace

import pytest

from backend.app.media_preparation import AudioChunk
from backend.app.media import MediaStore
from backend.app.models import AnalysisResult, FrameTiming
from backend.app.project_workspace.analysis import AnalysisService
from backend.app.project_workspace.models import ContentItem, Direction, InputManifest, ProductionPack, Resource
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.recognition import ProviderRecognitionAdapter
from backend.app.storage import WorkflowError
import test_providers
from test_providers import AlternateSpeech, AlternateVision


class Synthesis:
    def __init__(self):
        self.calls = 0
        self.bad_citation = False
        self.context = None

    def json_response(self, _model, prompt, _schema, _name, **_kwargs):
        self.calls += 1
        self.context = json.loads(prompt.split("INPUT_JSON:\n", 1)[1])
        resource = next(r for r in self.context["references"] if r["evidence"] and r["evidence"]["events"])
        return {"conclusion": "The references introduce a problem before showing the product.",
                "findings": ["Observed: a product appears. Interpretation: it introduces the solution."],
                "differences": [], "opportunities": ["Adapt the problem-solution progression."],
                "limitations": ["Sparse frames cannot establish complete pacing."],
                "structures": [{"resource_id": item["resource_id"], "summary": "A spoken promise introduces the reference.",
                    "nodes": [{"id": "moment_one", "label": "Spoken promise", "detail": "The source introduces a promise in speech.",
                               "kind": "interpretation", "citations": [{"resource_id": item["resource_id"],
                                   "event_id": item["evidence"]["events"][0]["id"], "reason": "Source moment"}]}],
                    "edges": []} for item in self.context["references"] if item["evidence"] and item["evidence"]["events"]],
                "citations": [{"resource_id": resource["resource_id"],
                               "event_id": "invented" if self.bad_citation else resource["evidence"]["events"][0]["id"],
                               "reason": "Observed product introduction"}]}


class Recognizer:
    def __init__(self):
        self.calls = []
        self.fail = set()

    def analyze(self, request):
        self.calls.append(request.video.video_id)
        if request.video.video_id in self.fail:
            raise ProviderError("provider_unavailable", "This reference failed extraction.")
        return AnalysisResult(analysis_id="analysis_test", task_id=request.task_id, video_id=request.video.video_id,
            duration_seconds=2, frame_count=4, status="succeeded",
            events=[{"event_id": "event_test", "video_id": request.video.video_id,
                     "lane": "audio", "kind": "speech", "text": "One less thing to worry about.",
                     "start_frame": 0, "end_frame": 2, "source": "offline-test", "method": "fixture"}],
            coverage={"speech": "observations", "visual_action": "none_found", "on_screen_text": "none_found"},
            origin={"kind": "provider", "description": "Explicit offline fixture; no provider call."})


@pytest.fixture
def workspace(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Reference test")
    timing = FrameTiming(fps_numerator=2, fps_denominator=1, frame_count=4,
                         frame_boundaries_seconds=[0, .5, 1, 1.5, 2], media_start_seconds=0,
                         rate_mode="constant", source="probed")
    resources = []
    for index in range(2):
        content = f"local source {index}".encode()
        path = store.project_dir(project.id) / "sources" / "media" / f"{index}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        resources.append(Resource(name=f"Reference {index}", kind="video", original_path=str(path.relative_to(store.project_dir(project.id))),
            sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content), status="ready", duration_seconds=2,
            media_metadata={"frame_timing": timing.model_dump(), "width": 16, "height": 16, "video_codec": "h264", "audio_codec": "aac", "has_audio": True}))
    project = store.update(project.id, project.version, lambda p: p.resources.extend(resources))
    recognizer, synthesis = Recognizer(), Synthesis()
    service = AnalysisService(store, lambda: ProviderSettings(api_key="test-offline", experiment_budget_enabled=False),
                              recognition_factory=lambda _: recognizer, transport_factory=lambda _: synthesis)
    return store, project, service, recognizer, synthesis


def test_selection_reuses_evidence_and_keeps_each_content_independent(workspace):
    store, project, service, recognizer, _ = workspace
    first, second = [r.id for r in project.resources]
    selected = service.set_selection(project.id, project.version, [first])
    assert service.set_selection(project.id, selected.version, [first]).version == selected.version
    completed = service.analyze(project.id, [first])
    assert recognizer.calls == [first]
    content = ContentItem(title="Standalone")
    store.update(project.id, completed.version, lambda p: p.contents.append(content))
    latest = service.analyze(project.id, [first, second], content.id)
    assert recognizer.calls == [first, second]
    assert latest.selection.resource_ids == [first]
    assert latest.contents[0].selection.resource_ids == [first, second]
    assert latest.analyses[-1].inputs.evidence_revisions == {first: 1, second: 1}
    assert latest.analyses[-1].sources[0].start_seconds == 0
    assert latest.analyses[-1].sources[0].end_seconds == 1


def test_text_and_timestamp_corrections_preserve_history_and_only_invalidate_dependents(workspace):
    store, project, service, _, _ = workspace
    first = project.resources[0].id
    state = service.analyze(project.id, [first])
    dependent = ContentItem(title="Dependent", directions=[Direction(title="A", concept="Product proof", approved=True,
        inputs=InputManifest(resource_ids=[first], evidence_revisions={first: 1}))])
    unrelated = ContentItem(title="Original", directions=[Direction(title="B", concept="Original", approved=True)])
    pack = ProductionPack(content_id=dependent.id, inputs=InputManifest(resource_ids=[first]),
                          production_brief="Brief", script="Script", storyboard="Storyboard", shot_list="Shots")
    def setup(p):
        p.contents.extend([dependent, unrelated])
        p.packs.append(pack)
    state = store.update(project.id, state.version, setup)
    event = state.resources[0].evidence[-1].events[0].model_dump()
    event.update(text="Corrected source words", start_seconds=.51, end_seconds=1.51)
    saved = service.correct_evidence(project.id, state.version, first, [event], reviewed=True)
    evidence = saved.resources[0].evidence
    assert evidence[0].events[0].text == "One less thing to worry about."
    assert evidence[-1].events[0].start_seconds == .5
    assert evidence[-1].events[0].end_seconds == 1.5
    assert evidence[-1].reviewed and evidence[-1].revision == 2
    assert saved.contents[0].directions[0].needs_review
    assert saved.contents[1].directions[0].approved and not saved.contents[1].directions[0].needs_review
    assert saved.packs[0].needs_review and saved.analyses[0].needs_review
    assert service.correct_evidence(project.id, saved.version, first, evidence[-1].events, True).version == saved.version


def test_invalid_timing_and_invented_citations_do_not_commit(workspace):
    store, project, service, _, synthesis = workspace
    first = project.resources[0].id
    state = service.analyze(project.id, [first])
    event = state.resources[0].evidence[-1].events[0].model_dump()
    event["end_seconds"] = 99
    with pytest.raises(WorkflowError, match="inside the original source"):
        service.correct_evidence(project.id, state.version, first, [event])
    synthesis.bad_citation = True
    with pytest.raises(WorkflowError, match="outside the selected"):
        service.analyze(project.id, [first])
    assert len(store.get(project.id).analyses) == 1


def test_structure_is_resource_scoped_and_citations_use_saved_source_timing(workspace):
    _, project, service, _, _ = workspace
    result = service.analyze(project.id, [resource.id for resource in project.resources])
    structures = result.analyses[-1].structures
    assert [graph.resource_id for graph in structures] == [resource.id for resource in project.resources]
    for graph in structures:
        source = graph.nodes[0].sources[0]
        assert source.resource_id == graph.resource_id
        assert source.evidence_revision == 1 and source.start_seconds == 0 and source.end_seconds == 1


@pytest.mark.parametrize("invalid", ["foreign_source", "broken_edge", "duplicate_node", "missing_structure"])
def test_invalid_graph_never_replaces_saved_analysis(workspace, invalid):
    store, project, service, _, synthesis = workspace
    ids = [resource.id for resource in project.resources]
    saved = service.analyze(project.id, ids)
    response = synthesis.json_response
    def corrupt(*args, **kwargs):
        data = response(*args, **kwargs)
        graph = data["structures"][0]
        if invalid == "foreign_source":
            graph["nodes"][0]["citations"] = data["structures"][1]["nodes"][0]["citations"]
        elif invalid == "broken_edge":
            graph["edges"] = [{"source": "moment_one", "target": "invented", "label": "Supports", "explanation": "An unsupported connection",
                               "citations": graph["nodes"][0]["citations"]}]
        elif invalid == "duplicate_node":
            graph["nodes"].append(graph["nodes"][0])
        else:
            data["structures"].pop()
        return data
    synthesis.json_response = corrupt
    with pytest.raises((WorkflowError, ValueError)):
        service.analyze(project.id, ids)
    assert store.get(project.id).analyses == saved.analyses


def test_late_context_change_does_not_replace_current_analysis(workspace):
    from backend.app.project_workspace.analysis import current_analysis
    store, project, service, _, synthesis = workspace
    ids = [resource.id for resource in project.resources]
    saved = service.analyze(project.id, ids)
    response = synthesis.json_response
    def delayed(*args, **kwargs):
        data = response(*args, **kwargs)
        current = store.get(project.id)
        service.set_selection(project.id, current.version, ids[:1])
        return data
    synthesis.json_response = delayed
    with pytest.raises(WorkflowError, match="changed during analysis"):
        service.analyze(project.id, ids)
    assert current_analysis(store.get(project.id)).id == saved.analyses[-1].id


def test_visual_only_analysis_preserves_original_speech_and_skips_recognition(workspace):
    from backend.app.project_workspace.models import EvidenceEvent
    store, project, service, recognizer, synthesis = workspace
    rid = project.resources[0].id
    state = service.retry_reference(project.id, rid)
    def partial(p):
        resource = p.resources[0]
        resource.evidence[-1].coverage["speech"] = "failed"
        resource.evidence[-1].events.append(EvidenceEvent(id="visual_one", kind="visual", text="The mug enters the frame.", start_seconds=0, end_seconds=.5))
        resource.status = "partial"
    store.update(project.id, state.version, partial)
    result = service.analyze(project.id, [rid], visual_only=True)
    assert recognizer.calls == [rid]
    assert len(result.resources[0].evidence[-1].events) == 2
    assert result.resources[0].evidence[-1].coverage["speech"] == "failed"
    report = result.analyses[-1]
    assert report.inputs.visual_only
    assert "visual evidence only" in " ".join(report.limitations)
    assert all(event["kind"] != "speech" for event in synthesis.context["references"][0]["evidence"]["events"])


def test_failed_item_is_explicit_and_does_not_erase_completed_work(workspace):
    _, project, service, recognizer, synthesis = workspace
    first, second = [r.id for r in project.resources]
    recognizer.fail.add(second)
    state = service.analyze(project.id, [first, second])
    assert state.resources[0].evidence
    assert not state.resources[1].evidence
    assert state.jobs[-1].status == "failed"
    assert state.analyses[-1].inputs.resource_ids == [first, second]
    assert state.analyses[-1].limitations
    assert synthesis.context["references"][1]["error"]
    recognizer.fail.clear()
    state = service.analyze(project.id, [first, second])
    assert recognizer.calls == [first, second, second]
    assert state.resources[1].evidence


def test_project_selection_apply_invalidates_only_exploration_reports(workspace):
    store, project, service, _, _ = workspace
    first, second = [resource.id for resource in project.resources]
    state = service.analyze(project.id, [first])
    content = ContentItem(title="Independent selection")
    state = store.update(project.id, state.version, lambda p: p.contents.append(content))
    state = service.analyze(project.id, [first], content.id)
    direction = Direction(title="Saved direction", concept="A useful idea", approved=True)
    pack = ProductionPack(content_id=content.id, inputs=InputManifest(resource_ids=[first]),
                          production_brief="Brief", script="Script", storyboard="Board", shot_list="Shots")
    def attach(p):
        p.contents[0].directions.append(direction)
        p.packs.append(pack)
    state = store.update(project.id, state.version, attach)
    unchanged = service.set_selection(project.id, state.version, [first])
    assert unchanged.version == state.version
    assert not any(report.needs_review for report in unchanged.analyses)
    changed = service.set_selection(project.id, state.version, [first, second])
    assert changed.analyses[0].needs_review
    assert not changed.analyses[1].needs_review
    assert changed.contents[0].selection.resource_ids == [first]
    assert changed.contents[0].directions[0].approved
    assert not changed.contents[0].directions[0].needs_review
    assert not changed.packs[0].needs_review


def test_per_item_retry_recovers_without_selection_changes_or_synthesis(workspace):
    store, project, service, recognizer, synthesis = workspace
    first, second = [resource.id for resource in project.resources]
    state = service.set_selection(project.id, project.version, [first])
    content = ContentItem(title="Other selection")
    state = store.update(project.id, state.version, lambda p: p.contents.append(content))
    recognizer.fail.add(second)
    state = service.retry_reference(project.id, second)
    assert state.resources[1].status == "failed" and state.jobs[-1].status == "failed"
    assert state.selection.resource_ids == [first]
    assert not state.contents[0].selection.resource_ids and not state.analyses
    recognizer.fail.clear()
    recovered = service.retry_reference(project.id, second)
    assert recovered.resources[1].status == "ready"
    assert len(recovered.resources[1].evidence) == 1
    assert recovered.jobs[-1].status == "succeeded"
    # Restoring/relinking an exact original can leave intake at stored. Its
    # validated durable evidence should become available without another call.
    store.update(project.id, recovered.version, lambda p: setattr(p.resources[1], "status", "stored"))
    repeated = service.retry_reference(project.id, second)
    assert len(repeated.resources[1].evidence) == 1
    assert repeated.resources[1].status == "ready"
    assert recognizer.calls == [second, second]
    assert synthesis.calls == 0
    assert repeated.selection == state.selection
    assert repeated.contents[0].selection == state.contents[0].selection


def test_retry_preserves_pending_edits_at_admission_and_completion(workspace):
    store, project, service, recognizer, _ = workspace
    rid = project.resources[0].id
    state = service.retry_reference(project.id, rid)
    original = state.resources[0].evidence[0].events[0].model_dump()
    draft = {"events": [{**original, "text": "A pending correction"}], "base_revision": 1}
    scope = f"evidence-{rid}"
    state = store.update(project.id, state.version, lambda p: p.editor_drafts.update({scope: draft}))
    rejected = service.retry_reference(project.id, rid)
    assert rejected.jobs[-1].status == "failed"
    assert "pending evidence corrections" in rejected.jobs[-1].error
    assert rejected.resources[0].status == "ready"
    assert rejected.editor_drafts[scope] == draft
    assert recognizer.calls == [rid]

    def prepare_retry(p):
        del p.editor_drafts[scope]
        p.resources[0].evidence[0].coverage["speech"] = "failed"
        p.resources[0].status = "partial"
    state = store.update(project.id, rejected.version, prepare_retry)
    before = state.resources[0].evidence[0].model_dump()
    recognize = recognizer.analyze
    def concurrent_edit(request):
        store.update(project.id, None, lambda p: p.editor_drafts.update({scope: draft}))
        return recognize(request)
    recognizer.analyze = concurrent_edit
    rejected = service.retry_reference(project.id, rid)
    assert rejected.jobs[-1].status == "failed"
    assert rejected.resources[0].evidence[0].model_dump() == before
    assert len(rejected.resources[0].evidence) == 1
    assert rejected.editor_drafts[scope] == draft


def test_retry_fills_corrected_partial_evidence_without_replacing_corrections(workspace):
    store, project, service, recognizer, _ = workspace
    rid = project.resources[0].id
    state = service.retry_reference(project.id, rid)
    state = store.update(project.id, state.version, lambda p: p.resources[0].evidence[0].coverage.update({"speech": "failed"}))
    event = state.resources[0].evidence[0].events[0].model_dump()
    event["text"] = "User corrected this partial transcript"
    state = service.correct_evidence(project.id, state.version, rid, [event])
    before = state.resources[0].evidence
    retried = service.retry_reference(project.id, rid)
    assert retried.resources[0].evidence[:-1] == before
    assert retried.resources[0].evidence[-1].events[0].text == "User corrected this partial transcript"
    assert retried.resources[0].evidence[-1].coverage["speech"] == "observations"
    assert retried.jobs[-1].status == "succeeded"
    assert recognizer.calls == [rid, rid]


def test_no_key_keeps_sources_and_explicit_failure_without_fake_evidence(workspace):
    store, project, _, _, _ = workspace
    service = AnalysisService(store, lambda: ProviderSettings())
    with pytest.raises(WorkflowError, match="No selected reference"):
        service.analyze(project.id, [project.resources[0].id])
    state = store.get(project.id)
    assert not state.resources[0].evidence and not state.analyses
    assert state.jobs[-1].status == "failed"
    assert "API key" in state.jobs[-1].error
    assert (store.project_dir(project.id) / state.resources[0].original_path).is_file()


def test_video_speech_retry_reuses_completed_chunks_and_preserves_partial_words(tmp_path):
    request, prepared = test_providers.recognition_input.__wrapped__(tmp_path)
    prepared = replace(prepared, audio_chunks=(AudioChunk(request.media_path, 0, .5), AudioChunk(request.media_path, .5, 1)))
    class Speech(AlternateSpeech):
        def __init__(self):
            super().__init__()
            self.chunks, self.fail = [], True

        def transcribe(self, chunk, *, metadata):
            self.chunks.append(chunk.start_seconds)
            if self.fail and chunk.start_seconds == .5:
                raise ProviderError("provider_timeout", "Second chunk failed.")
            return {"segments": [{"start": 0, "end": .4, "text": "Retained words"}]}
    speech = Speech()
    adapter = ProviderRecognitionAdapter(ProviderSettings(cache_dir=tmp_path / "results"),
        vision_provider=AlternateVision(), transcription_provider=speech, prepare=lambda *_: prepared)
    partial = adapter.analyze(request)
    assert partial.status == "partial" and "speech" in partial.extraction_failures
    assert any(event.text == "Retained words" for event in partial.events)
    assert not list((tmp_path / "results").glob("speech-*.json"))
    speech.fail = False
    complete = adapter.analyze(request)
    assert complete.status == "succeeded"
    assert speech.chunks == [0, .5, .5]


def test_audio_only_chunk_retry_preserves_timebase_and_partial_speech(workspace, monkeypatch):
    store, project, _, _, _ = workspace
    resource = project.resources[0]
    resource.kind = "audio"
    resource.duration_seconds = 2
    resource.media_metadata = {"has_audio": True}
    store.update(project.id, project.version, lambda p: setattr(p.resources[0], "kind", "audio"))
    class Transport:
        def __init__(self):
            self.calls, self.fail = [], True

        def transcribe(self, _model, path, **_kwargs):
            self.calls.append(path.name)
            if path.name == "001.wav" and self.fail:
                raise ProviderError("provider_timeout", "Retry the second chunk")
            return {"segments": [{"start": 0, "end": .5, "text": "Audio words"}]}
    def extract(command, _timeout):
        import wave
        with wave.open(command[-1], "wb") as output:
            output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            output.writeframes(b"\0" * 32000)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("backend.app.project_workspace.analysis._run_media", extract)
    transport = Transport()
    settings = ProviderSettings(audio_chunk_seconds=1, max_audio_chunks=2)
    service = AnalysisService(store, lambda: settings, transport_factory=lambda _: transport)
    path = store.project_dir(project.id) / resource.original_path
    first = service._audio_evidence(project.id, resource, path, settings, "job_test")
    assert first.coverage["speech"] == "partial" and len(first.events) == 1
    assert first.events[0].start_frame is None
    transport.fail = False
    second = service._audio_evidence(project.id, resource, path, settings, "job_test")
    assert second.coverage["speech"] == "observations" and len(second.events) == 2
    assert transport.calls == ["000.wav", "001.wav", "001.wav"]


def test_scene_sampling_keeps_temporal_coverage_and_source_indices(monkeypatch):
    timing = FrameTiming(fps_numerator=10, fps_denominator=1, frame_count=100,
                         frame_boundaries_seconds=[i / 10 for i in range(101)], media_start_seconds=2,
                         rate_mode="constant", source="probed")
    # Scene cut at original source frame 23 (absolute PTS 4.3s).
    output = "frame:0 pts:4300 pts_time:4.3\nlavfi.scene_score=0.8\n"
    monkeypatch.setattr("backend.app.project_workspace.analysis._run_media", lambda *_: SimpleNamespace(stdout=output))
    samples = AnalysisService._scene_samples("source.mp4", timing, 6)
    assert len(samples) <= 6 and tuple(sorted(set(samples))) == samples
    assert {0, 22, 23, 99}.issubset(samples)


def test_evidence_save_checkpoints_only_exact_draft(workspace):
    store, project, service, _, _ = workspace
    rid = project.resources[0].id
    state = service.analyze(project.id, [rid])
    event = state.resources[0].evidence[-1].events[0].model_dump()
    event["text"] = "Saved correction"
    scope = f"evidence-{rid}"
    state = store.update(project.id, state.version, lambda p: p.editor_drafts.update({scope: {"events": [event], "base_revision": 1}}))
    state = service.correct_evidence(project.id, state.version, rid, [event])
    assert scope not in state.editor_drafts
    newer = {**event, "text": "Newer typing"}
    state = store.update(project.id, state.version, lambda p: p.editor_drafts.update({scope: {"events": [newer], "base_revision": 2}}))
    state = service.correct_evidence(project.id, state.version, rid, [event], True)
    assert state.editor_drafts[scope]["events"][0]["text"] == "Newer typing"
    with pytest.raises(WorkflowError, match="changed after the editor opened"):
        service.correct_evidence(project.id, state.version, rid, [newer], base_revision=1)


def test_editor_revision_blocks_rebased_stale_correction(workspace):
    store, project, service, _, _ = workspace
    rid = project.resources[0].id
    state = service.analyze(project.id, [rid])
    event = state.resources[0].evidence[-1].events[0].model_dump()
    first = {**event, "text": "First editor correction"}
    scope = f"evidence-{rid}"
    state = store.update(project.id, state.version, lambda p: p.editor_drafts.update({scope: {"events": [first], "base_revision": 1}}))
    first_editor_version = state.editor_draft_versions[scope]
    second = {**event, "text": "Newer correction from another editor"}
    state = store.update(project.id, state.version, lambda p: p.editor_drafts.update({scope: {"events": [second], "base_revision": 1}}))
    with pytest.raises(WorkflowError, match="draft changed in another editor"):
        service.correct_evidence(project.id, state.version, rid, [first], base_revision=1,
                                 expected_editor_version=first_editor_version)
    unchanged = store.get(project.id)
    assert unchanged.editor_drafts[scope]["events"] == [second]
    assert unchanged.resources[0].evidence[-1].revision == 1
    saved = service.correct_evidence(project.id, unchanged.version, rid, [second], base_revision=1,
                                     expected_editor_version=unchanged.editor_draft_versions[scope])
    assert saved.resources[0].evidence[-1].revision == 2
    assert scope not in saved.editor_drafts


def test_review_rejects_dirty_or_stale_evidence_draft_atomically(workspace):
    store, project, service, _, _ = workspace
    rid = project.resources[0].id
    state = service.analyze(project.id, [rid])
    original = state.resources[0].evidence[-1].events[0].model_dump()
    scope = f"evidence-{rid}"
    for draft in ({"events": [{**original, "text": "Pending correction"}], "base_revision": 1},
                  {"events": [original], "base_revision": 0}):
        state = store.update(project.id, state.version, lambda p, d=draft: p.editor_drafts.update({scope: d}))
        with pytest.raises(WorkflowError, match="Apply or discard"):
            service.review_evidence(project.id, state.version, rid,
                                    expected_editor_version=state.editor_draft_versions[scope])
        state = store.get(project.id)
        assert not state.resources[0].evidence[-1].reviewed
        assert state.editor_drafts[scope] == draft
    old_version = state.editor_draft_versions[scope]
    state = store.update(project.id, state.version, lambda p: p.editor_drafts.update({scope: {"events": [original], "base_revision": 1}}))
    with pytest.raises(WorkflowError, match="draft changed in another editor"):
        service.review_evidence(project.id, state.version, rid, expected_editor_version=old_version)
    reviewed = service.review_evidence(project.id, state.version, rid,
                                       expected_editor_version=state.editor_draft_versions[scope])
    assert reviewed.resources[0].evidence[-1].reviewed
    assert scope not in reviewed.editor_drafts
    assert service.review_evidence(project.id, reviewed.version, rid).version == reviewed.version


def test_real_scene_sampling_persists_source_aligned_preparation(workspace, tmp_path, monkeypatch):
    store, project, service, _, _ = workspace
    source = tmp_path / "scene.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=64x48:r=10:d=0.7",
                    "-f", "lavfi", "-i", "color=blue:s=64x48:r=10:d=1.3",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
                    "-c:v", "libx264", "-output_ts_offset", "2", str(source)], check=True)
    media = MediaStore(tmp_path / "originals")
    with source.open("rb") as stream:
        video = media.save_upload(project.id, source.name, stream)
    original = media.path_for(video)
    indices = service._scene_samples(original, video.frame_timing, 4)
    assert indices == (0, 6, 7, 19)
    settings = ProviderSettings(max_frames=4)
    with service._prepared(project.id, original, video, settings) as prepared:
        assert tuple(frame.frame_index for frame in prepared.frames) == indices
        assert [frame.source_seconds for frame in prepared.frames] == pytest.approx([0, .6, .7, 1.9])
        cached = [frame.path for frame in prepared.frames]
    assert all(path.is_file() for path in cached)
    def reject(*_args, **_kwargs):
        pytest.fail("Valid persisted preparation should not decode again")
    monkeypatch.setattr("backend.app.project_workspace.analysis.prepare_media", reject)
    with service._prepared(project.id, original, video, settings) as reused:
        assert [frame.path for frame in reused.frames] == cached


def test_disabled_standalone_transcription_does_not_prepare_or_call(workspace, monkeypatch):
    store, project, _, _, _ = workspace
    resource = project.resources[0].model_copy(update={"kind": "audio", "duration_seconds": 2})
    monkeypatch.setattr("backend.app.project_workspace.analysis._run_media", lambda *a: pytest.fail("Disabled audio preparation"))
    settings = ProviderSettings(transcription_provider="disabled")
    service = AnalysisService(store, lambda: settings, transport_factory=lambda _: pytest.fail("Disabled paid transport"))
    result = service._audio_evidence(project.id, resource, None, settings, "job_disabled")
    assert result.coverage["speech"] == "not_analyzed" and "disabled" in result.limitations[0]


def test_standalone_preparation_validated_and_partial_support_preserved(workspace, monkeypatch):
    from pathlib import Path
    import wave
    store, project, _, _, _ = workspace
    resource = project.resources[0].model_copy(update={"kind": "audio", "duration_seconds": 2.25})
    prepared = []
    def extract(command, _timeout):
        prepared.append(command[-1])
        seconds = float(command[command.index("-t") + 1])
        with wave.open(command[-1], "wb") as output:
            output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            output.writeframes(b"\0" * round(seconds * 32000))
    monkeypatch.setattr("backend.app.project_workspace.analysis._run_media", extract)
    class Transport:
        def __init__(self):
            self.calls, self.fail = [], True

        def transcribe(self, model, path, **kwargs):
            self.calls.append(path.name)
            if path.name == "001.wav" and self.fail:
                raise ProviderError("provider_timeout", "private detail")
            return {"segments": [{"start": 0, "end": .2, "text": "Speech fixture"}]}
    transport = Transport()
    settings = ProviderSettings(audio_chunk_seconds=1, max_audio_chunks=3)
    service = AnalysisService(store, lambda: settings, transport_factory=lambda _: transport)
    first = service._audio_evidence(project.id, resource, None, settings, "job_first")
    assert first.coverage["speech"] == "partial" and len(first.events) == 2
    assert transport.calls == ["000.wav", "001.wav", "002.wav"]
    assert first.support_details[1]["failure_code"] == "provider_timeout"
    assert first.support_details[-1]["chunk_end_seconds"] == "2.25"
    failed_wav = next(Path(path) for path in prepared if path.endswith("001.wav"))
    failed_wav.write_bytes(b"corrupt prepared cache")
    transport.fail = False
    second = service._audio_evidence(project.id, resource, None, settings, "job_second")
    assert second.coverage["speech"] == "observations" and len(second.events) == 3
    assert transport.calls == ["000.wav", "001.wav", "002.wav", "001.wav"]
    assert len(prepared) == 4  # Only corrupt/missing work was prepared again.
    assert [record["cache_status"] for record in second.support_details] == ["hit", "miss", "hit"]
    assert "private detail" not in str(first.support_details)


def test_empty_transcription_is_no_detection_not_proof_of_no_speech(workspace, monkeypatch):
    import wave
    store, project, _, _, _ = workspace
    resource = project.resources[0].model_copy(update={"kind": "audio", "duration_seconds": 1})
    def extract(command, _timeout):
        with wave.open(command[-1], "wb") as output:
            output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            output.writeframes(b"\0" * 32000)
    monkeypatch.setattr("backend.app.project_workspace.analysis._run_media", extract)
    transport = SimpleNamespace(transcribe=lambda *a, **kw: {"text": "", "segments": []})
    settings = ProviderSettings()
    result = AnalysisService(store, lambda: settings, transport_factory=lambda _: transport)._audio_evidence(
        project.id, resource, None, settings, "job_empty")
    assert result.coverage["speech"] == "none_found"
    assert any("does not establish" in note for note in result.limitations)
