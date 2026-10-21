"""Workflow invariants exercised through real storage and adapter boundaries."""

import json
from pathlib import Path

import pytest

from backend.app import models as m
from backend.app.service import WorkflowService, find, ref
from backend.app.storage import WorkflowError


@pytest.fixture
def service(tmp_path):
    return WorkflowService(tmp_path)


def sample(service):
    state = service.create("Workflow test")
    state = service.set_language(state.task.task_id, state.task.version, "English")
    state = service.load_sample(state.task.task_id, state.task.version)
    return service.recognize(state.task.task_id, state.task.version)


def ready(service):
    state = sample(service)
    return service.confirm_analysis(state.task.task_id, state.task.version, state.task.current_analysis)


def directions(service):
    state = ready(service)
    return service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)


def outputs(service):
    state = directions(service)
    direction = state.directions[0]
    state = service.approve_direction(state.task.task_id, state.task.version, direction.direction_id, direction.revision, state.task.current_brief, state.task.current_analysis)
    return service.generate_outputs(state.task.task_id, state.task.version, state.task.selected_direction, state.task.current_brief, state.task.current_analysis)


def brief_fields(brief):
    return brief.model_dump(exclude={"brief_id", "task_id", "revision", "created_at", "updated_at", "schema_version"})


def test_original_corrections_confirmation_and_forbidden_fields(service):
    state = ready(service)
    original = state.analyses[0].model_dump(mode="json")
    task_id = state.task.task_id
    for event_id, fields in (("event_intro_text", {"start_seconds": 0.5}), ("event_intro_text", {"start_frame": 1}), ("event_intro_text", {"end_frame": 80}), ("event_melody", {"description": "Forbidden audio correction"}), ("event_intro_shape", {"text": "Not recognized text"})):
        with pytest.raises(WorkflowError):
            service.correct_analysis(task_id, state.task.version, state.task.current_analysis, [{"event_id": event_id, **fields}], [])
    state = service.correct_analysis(task_id, state.task.version, state.task.current_analysis, [{"event_id": "event_intro_text", "text": "LumaCup fictional sample"}], [{"segment_id": "segment_hook", "roles": ["other"]}])
    assert state.analyses[0].model_dump(mode="json") == original
    corrected = state.analyses[-1]
    assert corrected.revision == 2 and not corrected.review.user_confirmed
    assert len(corrected.corrections) == 2
    assert all(section.interpretation is None for section in corrected.segments)
    assert corrected.origin.kind == "sample"
    assert [(e.event_id, e.start_frame, e.end_frame) for e in corrected.events] == [(e["event_id"], e["start_frame"], e["end_frame"]) for e in original["events"]]
    with pytest.raises(WorkflowError, match="reviewed analysis"):
        service.generate_directions(task_id, state.task.version, state.task.current_brief, state.task.current_analysis)


def test_generation_gates_exact_task_revision_and_confirmation(service):
    state = sample(service)
    task_id = state.task.task_id
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert error.value.code == "analysis_unconfirmed"
    state = service.confirm_analysis(task_id, state.task.version, state.task.current_analysis)
    wrong = m.VersionRef(id="analysis_another_task", revision=1)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(task_id, state.task.version, state.task.current_brief, wrong)
    assert error.value.code == "outdated_inputs"
    state = service.generate_directions(task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert len(state.directions) == 2
    direction = state.directions[0]
    with pytest.raises(WorkflowError) as error:
        service.generate_outputs(task_id, state.task.version, ref(direction), state.task.current_brief, state.task.current_analysis)
    assert error.value.code == "direction_unapproved"
    with pytest.raises(WorkflowError):
        service.approve_direction(task_id, state.task.version, direction.direction_id, 999, state.task.current_brief, state.task.current_analysis)


def test_feedback_reaches_adapter_and_requires_new_approval(service):
    state = directions(service)
    first = state.directions[0]
    recorded = []
    delegate = service.creative
    class Spy:
        def refine_direction(self, brief, analysis, target, feedback):
            recorded.append(feedback.model_dump())
            return delegate.refine_direction(brief, analysis, target, feedback)
    service.creative = Spy()
    state = service.refine_direction(state.task.task_id, state.task.version, first.direction_id, first.revision, state.task.current_brief, state.task.current_analysis, "Make it presenter-free")
    assert recorded[0]["instruction"] == "Make it presenter-free"
    assert recorded[0]["target_direction"] == ref(first).model_dump()
    assert state.feedback[-1].status == "applied"
    draft = state.directions[-1]
    assert draft.revision == 2 and draft.approval_status == "draft"
    assert "presenter" in " ".join(draft.production_requirements).lower()
    assert draft.hook != first.hook or draft.narrative != first.narrative
    assert state.task.selected_direction is None
    with pytest.raises(WorkflowError):
        service.generate_outputs(state.task.task_id, state.task.version, ref(draft), state.task.current_brief, state.task.current_analysis)
    state = service.refine_direction(state.task.task_id, state.task.version, draft.direction_id, draft.revision, state.task.current_brief, state.task.current_analysis, "Use an emerald telescope")
    assert state.feedback[-1].status == "not_interpreted"
    assert state.feedback[-1].instruction == "Use an emerald telescope"
    assert state.feedback[-1].resulting_direction is None
    assert len(state.directions) == 3


def test_upstream_change_outdates_outputs_and_preserves_edits(service):
    state = outputs(service)
    assert len(state.production_briefs) == len(state.storyboards) == 1
    state = service.edit_outputs(state.task.task_id, state.task.version, state.task.current_production_brief, state.task.current_storyboard, {"core_message": "Saved manual wording"}, None)
    assert len(state.production_briefs) == len(state.storyboards) == 2
    assert state.production_briefs[-1].core_message == "Saved manual wording"
    assert state.production_briefs[-1].edited
    old_direction = state.task.selected_direction
    fields = brief_fields(state.briefs[-1])
    fields["target_duration_seconds"] = 25
    state = service.save_brief(state.task.task_id, state.task.version, fields)
    assert state.task.selected_direction is None
    assert all(o.currentness == "outdated" for o in state.production_briefs + state.storyboards)
    assert state.production_briefs[-1].core_message == "Saved manual wording"
    with pytest.raises(WorkflowError):
        service.generate_outputs(state.task.task_id, state.task.version, old_direction, state.task.current_brief, state.task.current_analysis)


def test_direct_direction_edit_invalidates_exact_approval(service):
    state = outputs(service)
    selected = state.task.selected_direction
    state = service.edit_direction(state.task.task_id, state.task.version, selected.id, selected.revision, {"hook": "Edited Hook"})
    assert state.task.selected_direction is None
    assert state.directions[-1].revision == selected.revision + 1
    assert state.directions[-1].approval_status == "draft"
    assert all(o.currentness == "outdated" for o in state.production_briefs + state.storyboards)
    with pytest.raises(WorkflowError):
        service.approve_direction(state.task.task_id, state.task.version, selected.id, selected.revision, state.task.current_brief, state.task.current_analysis)


def test_delayed_analysis_result_cannot_replace_new_correction(service):
    state = ready(service)
    original_adapter = service.sample_recognition
    task_id = state.task.task_id
    class Delayed:
        def analyze(self, request):
            latest = service.store.get(task_id)
            service.correct_analysis(task_id, latest.task.version, latest.task.current_analysis, [{"event_id": "event_intro_text", "text": "Concurrent saved correction"}], [])
            return original_adapter.analyze(request)
    service.sample_recognition = Delayed()
    state = service.recognize(task_id, state.task.version)
    assert state.jobs[-1].status == "failed" and state.jobs[-1].error.code == "stale_result"
    assert len(state.analyses) == 2
    assert find(state.analyses, state.task.current_analysis).events[1].text == "Concurrent saved correction"


def test_delayed_production_result_cannot_replace_manual_output(service):
    state = outputs(service)
    original_adapter = service.creative
    task_id = state.task.task_id
    class Delayed:
        def generate_production(self, brief, analysis, direction):
            latest = service.store.get(task_id)
            service.edit_outputs(task_id, latest.task.version, latest.task.current_production_brief, latest.task.current_storyboard, {"hook": "Concurrent manual Hook"}, None)
            return original_adapter.generate_production(brief, analysis, direction)
    service.creative = Delayed()
    state = service.generate_outputs(task_id, state.task.version, state.task.selected_direction, state.task.current_brief, state.task.current_analysis)
    assert state.jobs[-1].error.code == "stale_result"
    assert len(state.production_briefs) == 2 and state.production_briefs[-1].hook == "Concurrent manual Hook"


def test_current_guards_and_persistence_reopen(service):
    state = outputs(service)
    task_id = state.task.task_id
    with pytest.raises(WorkflowError) as error:
        service.confirm_analysis(task_id, state.task.version - 1, state.task.current_analysis)
    assert error.value.code == "version_conflict"
    reopened = WorkflowService(service.store.path.parent).store.get(task_id)
    assert reopened.model_dump(mode="json") == state.model_dump(mode="json")
    assert reopened.task.selected_direction == state.task.selected_direction
    assert reopened.storyboards[-1].target_duration_seconds == reopened.briefs[-1].target_duration_seconds
    assert reopened.storyboards[-1].target_duration_seconds != reopened.videos[-1].duration_seconds


def test_adapters_cannot_grant_review_or_approval(service):
    state = service.create("Untrusted adapter test")
    state = service.set_language(state.task.task_id, state.task.version, "English")
    state = service.load_sample(state.task.task_id, state.task.version)
    delegate = service.sample_recognition
    class SelfReviewing:
        def analyze(self, request):
            result = delegate.analyze(request)
            from backend.app.service import now
            result.review = m.ReviewState(user_confirmed=True, confirmed_at=now())
            result.updated_at = now()
            return result
    service.sample_recognition = SelfReviewing()
    state = service.recognize(state.task.task_id, state.task.version)
    assert state.jobs[-1].error.code == "invalid_adapter_result"
    assert state.task.current_analysis is None and not state.analyses
    service.sample_recognition = delegate
    state = service.recognize(state.task.task_id, state.task.version)
    state = service.confirm_analysis(state.task.task_id, state.task.version, state.task.current_analysis)
    creative = service.creative
    class SelfApproving:
        def generate_directions(self, brief, analysis):
            result = creative.generate_directions(brief, analysis)
            from backend.app.service import now
            for direction in result:
                direction.approval_status, direction.approved_at = "approved", now()
                direction.updated_at = now()
            return result
    service.creative = SelfApproving()
    state = service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert state.jobs[-1].error.code == "invalid_adapter_result"
    assert state.directions == [] and state.task.selected_direction is None


def test_unrelated_pending_title_edit_preserved_and_restart_recovery(service, monkeypatch):
    state = ready(service)
    original_update = service._update
    intervened = False
    def update(task_id, version, mutate, **kwargs):
        nonlocal intervened
        saved = original_update(task_id, version, mutate, **kwargs)
        if not intervened and saved.jobs[-1].status == "pending":
            intervened = True
            original_update(task_id, saved.task.version, lambda task: setattr(task.task, "title", "Concurrent title"))
        return saved
    monkeypatch.setattr(service, "_update", update)
    state = service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert state.jobs[-1].status == "succeeded" and state.jobs[-1].error is None
    assert len(state.directions) == 2 and state.task.title == "Concurrent title"
    def interrupted(task):
        task.jobs.append(m.ProcessingJob(job_id="job_interrupted", task_id=task.task.task_id, operation="directions", status="running"))
    original_update(state.task.task_id, state.task.version, interrupted)
    reopened = WorkflowService(service.store.path.parent).store.get(state.task.task_id)
    assert reopened.jobs[-1].error.code == "interrupted_job"
    assert reopened.jobs[-1].error.retryable


@pytest.mark.parametrize(("failure", "error_code"), [
    ("exception", "generation_failed"),
    ("invalid_result", "invalid_adapter_result"),
    ("pending_race", "stale_result"),
    ("running_race", "stale_result"),
    ("restart_pending", "interrupted_job"),
    ("restart_running", "interrupted_job"),
])
def test_failed_refinement_resolves_only_its_pending_feedback(service, monkeypatch, failure, error_code):
    state = directions(service)
    target = state.directions[0]
    task_id = state.task.task_id
    state = service.refine_direction(task_id, state.task.version, target.direction_id, target.revision,
                                     state.task.current_brief, state.task.current_analysis, "Make it presenter-free")
    target = state.directions[-1]
    saved_directions = [item.model_dump(mode="json") for item in state.directions]
    saved_feedback = state.feedback[0].model_dump(mode="json")
    delegate = service.creative
    original_update = service._update

    class StoppedBackend(BaseException):
        pass

    def update(task_id, version, mutate, **kwargs):
        saved = original_update(task_id, version, mutate, **kwargs)
        job = saved.jobs[-1]
        if job.operation == "refine":
            if failure == "pending_race" and job.status == "pending":
                original_update(task_id, saved.task.version, lambda task: setattr(task.task, "generation_language", "Chinese"))
            if failure == f"restart_{job.status}":
                raise StoppedBackend
        return saved

    class FailingRefinement:
        def refine_direction(self, brief, analysis, direction, feedback):
            if failure == "exception":
                raise RuntimeError("Synthetic adapter failure")
            if failure == "running_race":
                latest = service.store.get(task_id)
                original_update(task_id, latest.task.version, lambda task: setattr(task.task, "generation_language", "Chinese"))
            result = delegate.refine_direction(brief, analysis, direction, feedback)
            if failure == "invalid_result":
                result.revision += 1
            return result

    monkeypatch.setattr(service, "_update", update)
    service.creative = FailingRefinement()
    instruction = "Make this direction presenter-free."

    def refine():
        return service.refine_direction(task_id, state.task.version, target.direction_id, target.revision,
                                        state.task.current_brief, state.task.current_analysis, instruction)

    if failure.startswith("restart_"):
        with pytest.raises(StoppedBackend):
            refine()
        result = WorkflowService(service.store.path.parent).store.get(task_id)
    else:
        result = refine()
    assert result.jobs[-1].status == "failed" and result.jobs[-1].error.code == error_code
    feedback = result.feedback[-1]
    assert feedback.status == "not_interpreted" and feedback.resulting_direction is None
    assert feedback.instruction == instruction and feedback.target_direction == ref(target)
    assert error_code in feedback.explanation
    assert feedback.updated_at >= feedback.created_at
    assert result.feedback[0].model_dump(mode="json") == saved_feedback
    assert [item.model_dump(mode="json") for item in result.directions] == saved_directions
    assert result.task.selected_direction is None and not result.production_briefs and not result.storyboards
    assert WorkflowService(service.store.path.parent).store.get(task_id) == result


@pytest.mark.parametrize("status", ["pending", "running", "failed", "partial"])
def test_non_success_analysis_cannot_enter_creative_workflow(service, status):
    state = sample(service)
    def replace_current(task):
        analysis = task.analyses[0]
        analysis.status = status
        if status == "partial":
            analysis.events = [event for event in analysis.events if event.kind != "music"]
            for segment in analysis.segments:
                segment.evidence_ids = [item for item in segment.evidence_ids if item != "event_melody"]
            analysis.coverage.music = "failed"
        else:
            analysis.events, analysis.segments = [], []
            analysis.coverage = m.Coverage()
            if status == "failed":
                analysis.error = m.ErrorInfo(code="test_failure", message="Synthetic extraction failure")
    state = service.store.update(state.task.task_id, state.task.version, replace_current)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert error.value.code == "analysis_not_succeeded"
    with pytest.raises(WorkflowError) as error:
        service.confirm_analysis(state.task.task_id, state.task.version, state.task.current_analysis)
    assert error.value.code == "analysis_not_succeeded"


def test_unapproved_choice_persists_and_invalidates_other_approval(service):
    state = outputs(service)
    task_id = state.task.task_id
    alternate = state.directions[1]
    with pytest.raises(WorkflowError) as error:
        service.generate_outputs(task_id, state.task.version, ref(alternate), state.task.current_brief, state.task.current_analysis)
    assert error.value.code == "direction_unapproved"
    with pytest.raises(WorkflowError) as error:
        service.refine_direction(task_id, state.task.version, alternate.direction_id, alternate.revision, m.VersionRef(id=state.task.current_brief.id, revision=999), state.task.current_analysis, "Make it presenter-free")
    assert error.value.code == "outdated_inputs"
    state = service.choose_direction(task_id, state.task.version, alternate.direction_id, alternate.revision)
    assert state.task.chosen_direction == ref(alternate)
    assert state.task.selected_direction is None
    assert all(item.currentness == "outdated" for item in state.production_briefs + state.storyboards)
    reopened = WorkflowService(service.store.path.parent).store.get(task_id)
    assert reopened.task.chosen_direction == ref(alternate)
    assert reopened.task.selected_direction is None
    with pytest.raises(WorkflowError):
        service.generate_outputs(task_id, reopened.task.version, ref(alternate), reopened.task.current_brief, reopened.task.current_analysis)


def test_archived_unknown_timing_cannot_be_confirmed_or_used_for_creative(service, tmp_path):
    from backend.app.frame_migration import migrate_v02_task
    payload = json.loads((Path(__file__).resolve().parents[1] / "examples/v0.2.sample-task.json").read_text())
    state = service.store.create(migrate_v02_task(payload, tmp_path / "no-media"))
    assert state.analyses[-1].review.user_confirmed  # Historical review is retained.
    with pytest.raises(WorkflowError) as confirmation:
        service.confirm_analysis(state.task.task_id, state.task.version, state.task.current_analysis)
    assert confirmation.value.code == "frame_timing_unavailable"
    with pytest.raises(WorkflowError) as generation:
        service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert generation.value.code == "m2_legacy_review_required"
    assert service.store.get(state.task.task_id) == state
    original_analysis = state.analyses[-1].model_dump()
    draft = service.store.get_m2_draft(state.task.task_id)
    reviewed = service.store.save_m2_draft(state.task.task_id, m.M2DraftUpdate(
        expected_draft_version=draft.draft_version, fields=draft.fields,
        claims=[claim.model_copy(update={"confirmed_for_use": True}) for claim in draft.claims],
        source_notes=draft.source_notes,
    ))
    state = service.apply_m2(state.task.task_id, m.M2ApplyRequest(
        expected_draft_version=reviewed.draft_version, expected_version=state.task.version,
        based_on_brief=state.task.current_brief,
    )).task
    assert state.analyses[-1].model_dump() == original_analysis
    with pytest.raises(WorkflowError) as generation:
        service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, state.task.current_analysis)
    assert generation.value.code == "frame_timing_unavailable"
    assert service.store.get(state.task.task_id) == state
