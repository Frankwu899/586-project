"""Regression checks from the independent workflow review; no external calls."""
import pytest

from backend.app.adapters import SampleCreativeAdapter
from backend.app.service import ref
from backend.app.structure_models import AnalyzeRequest, HandoffRequest
from backend.app.structure_service import StructureService
from backend.app.workflow_errors import WorkflowError
from test_structure_service import ImmediateExecutor, source as structure_source

source = structure_source


class RecordingCreative(SampleCreativeAdapter):
    def __init__(self):
        super().__init__()
        self.calls = []

    def remember(self, operation):
        self.calls.append((operation, self._research_handoff.model_dump(mode="json") if self._research_handoff else None))

    def generate_directions(self, brief, analysis):
        self.remember("directions")
        return super().generate_directions(brief, analysis)

    def refine_direction(self, brief, analysis, target, feedback):
        self.remember("refine")
        return super().refine_direction(brief, analysis, target, feedback)

    def generate_production(self, brief, analysis, direction):
        self.remember("production")
        return super().generate_production(brief, analysis, direction)


def with_selected_research(source):
    service, state, _, _ = source
    adapter = RecordingCreative()
    service.creative = adapter
    state = service.set_language(state.task.task_id, state.task.version, "English")
    structure = StructureService(service, executor=ImmediateExecutor())
    workspace = structure.analyze(state.task.task_id, AnalyzeRequest())
    handoff = structure.handoff(state.task.task_id, HandoffRequest(expected_version=workspace.version, all=True))
    state = service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief,
                                        None, use_reference=False)
    assert state.jobs[-1].status == "succeeded", state.jobs[-1].error
    return service, state, adapter, structure, handoff


def test_refinement_and_production_keep_original_research_selection_when_latest_changes(source):
    service, state, adapter, structure, handoff = with_selected_research(source)
    task_id = state.task.task_id
    target = state.directions[0]
    assert target.structure_handoff_id == handoff.handoff_id
    newer = handoff.model_copy(deep=True)
    newer.handoff_id = "handoff_later_selection"
    newer.methods[0].conditions = ["A later selection must not replace the original applicability condition."]
    structure.store.save_handoff(newer)
    assert structure.store.latest_handoff(task_id).handoff_id == newer.handoff_id
    state = service.refine_direction(task_id, state.task.version, target.direction_id, target.revision,
        target.brief_ref, target.analysis_ref, "presenter-free")
    assert state.jobs[-1].status == "succeeded", state.jobs[-1].error
    revised = state.directions[-1]
    assert revised.structure_handoff_id == handoff.handoff_id
    assert target.revision == 1 and revised.revision == 2
    state = service.approve_direction(task_id, state.task.version, revised.direction_id,
        revised.revision, revised.brief_ref, revised.analysis_ref)
    state = service.generate_outputs(task_id, state.task.version, ref(revised), revised.brief_ref, revised.analysis_ref)
    assert state.jobs[-1].status == "succeeded", state.jobs[-1].error
    assert [operation for operation, _ in adapter.calls] == ["directions", "refine", "production"]
    assert all(context["handoff_id"] == handoff.handoff_id for _, context in adapter.calls)
    assert all(context["methods"][0]["conditions"] == handoff.methods[0].conditions for _, context in adapter.calls)
    assert state.production_briefs[-1].analysis_ref is None
    assert all(not row.evidence for row in state.storyboards[-1].rows)


@pytest.mark.parametrize("wrong_context", ["missing", "another_task"])
def test_unresolvable_saved_research_fails_before_creative_provider(source, wrong_context):
    service, state, adapter, structure, handoff = with_selected_research(source)
    task_id = state.task.task_id
    target = state.directions[0]
    context_id = "handoff_not_owned"
    if wrong_context == "another_task":
        foreign = handoff.model_copy(deep=True)
        foreign.handoff_id, foreign.task_id = context_id, "task_other"
        structure.store.save_handoff(foreign)
    def corrupt_saved_link(item):
        item.directions[0].structure_handoff_id = context_id
    state = service.store.update(task_id, state.task.version, corrupt_saved_link)
    before = len(adapter.calls)
    with pytest.raises(WorkflowError) as failure:
        service.refine_direction(task_id, state.task.version, target.direction_id, target.revision,
            target.brief_ref, target.analysis_ref, "presenter-free")
    assert failure.value.code == "invalid_research_context"
    assert len(adapter.calls) == before
    assert service.store.get(task_id).feedback == []
