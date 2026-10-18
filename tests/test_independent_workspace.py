"""Independent Ideas must preserve explicit approval, history and evidence boundaries."""
import pytest
from pydantic import ValidationError

from backend.app.adapters import SampleCreativeAdapter
from backend.app.models import EvidenceReference, TaskState
from backend.app.providers.config import ProviderSettings
from backend.app.sample import sample_brief
from backend.app.service import WorkflowService, ref
from backend.app.workflow_errors import WorkflowError


@pytest.fixture
def original(tmp_path):
    # Explicit offline test injection, never a production upload fallback.
    service = WorkflowService(tmp_path, real_creative=SampleCreativeAdapter(), provider_settings=ProviderSettings())
    state = service.create('Original idea without a reference')
    state = service.set_language(state.task.task_id, state.task.version, 'English')
    brief = sample_brief(state.task.task_id)
    fields = brief.model_dump(exclude={'schema_version','brief_id','task_id','revision','created_at','updated_at'})
    state = service.save_brief(state.task.task_id, state.task.version, fields)
    return service, state


def idea_fields():
    return {'core_message':'Show the removable lid', 'hook':'Begin with a clear tabletop view',
            'narrative':'Lift the lid, show the color choices, and finish on the product.', 'cta':'Explore the colors'}


def test_manual_idea_without_media_still_requires_exact_approval_and_exports(original):
    service, state = original
    task_id = state.task.task_id
    assert not state.videos and state.task.current_analysis is None
    state = service.create_manual_direction(task_id, state.task.version, state.task.current_brief, idea_fields())
    direction = state.directions[-1]
    assert direction.origin.kind == 'manual' and direction.analysis_ref is None and direction.evidence == []
    assert state.task.selected_direction is None
    with pytest.raises(WorkflowError) as error:
        service.generate_outputs(task_id, state.task.version, ref(direction), state.task.current_brief, None)
    assert error.value.code == 'direction_unapproved'
    state = service.approve_direction(task_id, state.task.version, direction.direction_id, direction.revision, state.task.current_brief, None)
    state = service.generate_outputs(task_id, state.task.version, state.task.selected_direction, state.task.current_brief, None)
    assert state.jobs[-1].status == 'succeeded', state.jobs[-1].error
    assert state.production_briefs[-1].analysis_ref is None and state.production_briefs[-1].evidence == []
    assert all(not row.evidence for row in state.storyboards[-1].rows)
    assert 'none (original idea)' in service.export(task_id, 'brief.md')
    assert 'Original production suggestion' in service.export(task_id, 'storyboard.csv')


def test_explicit_original_generation_and_later_reference_do_not_break_approval(original):
    service, state = original
    task_id = state.task.task_id
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(task_id, state.task.version, state.task.current_brief, None)
    assert error.value.code == 'analysis_required'
    state = service.generate_directions(task_id, state.task.version, state.task.current_brief, None, use_reference=False)
    assert state.jobs[-1].status == 'succeeded', state.jobs[-1].error
    assert len(state.directions) == 2
    assert all(d.analysis_ref is None and not d.evidence for d in state.directions)
    direction = state.directions[0]
    state = service.approve_direction(task_id, state.task.version, direction.direction_id, direction.revision, state.task.current_brief, None)
    approved = state.task.selected_direction
    # Adding a reference should not retroactively turn an original idea into a
    # reference-dependent artifact or erase its exact approval.
    state = service.load_sample(task_id, state.task.version)
    state = service.recognize(task_id, state.task.version)
    assert state.task.selected_direction == approved
    assert state.directions[0].currentness == 'current'
    assert not state.analyses[-1].review.user_confirmed
    state = service.generate_outputs(task_id, state.task.version, approved, state.task.current_brief, None)
    assert state.jobs[-1].status == 'succeeded', state.jobs[-1].error


def test_original_artifacts_cannot_smuggle_reference_citations(original):
    service, state = original
    state = service.create_manual_direction(state.task.task_id, state.task.version, state.task.current_brief, idea_fields())
    state.directions[-1].evidence = [EvidenceReference(analysis_id='analysis_fake', analysis_revision=1,
        video_id='video_fake', event_id='event_fake', reason='Unsupported citation')]
    with pytest.raises(ValidationError, match='original creative work'):
        TaskState.model_validate(state.model_dump())


def test_manual_edit_retains_prior_version_and_requires_new_approval(original):
    service, state = original
    task_id = state.task.task_id
    state = service.create_manual_direction(task_id, state.task.version, state.task.current_brief, idea_fields())
    direction = state.directions[-1]
    state = service.approve_direction(task_id, state.task.version, direction.direction_id, direction.revision, state.task.current_brief, None)
    state = service.edit_direction(task_id, state.task.version, direction.direction_id, direction.revision, {'hook':'Open on a different color choice'})
    assert state.directions[0].hook == idea_fields()['hook']
    assert state.directions[-1].revision == 2 and state.directions[-1].approval_status == 'draft'
    assert state.task.selected_direction is None
    with pytest.raises(WorkflowError):
        service.generate_outputs(task_id, state.task.version, ref(state.directions[-1]), state.task.current_brief, None)


def test_real_original_generation_without_key_is_explicit_failure(original):
    service, state = original
    from backend.app.providers.creative import OpenAICreativeAdapter
    service.real_creative = OpenAICreativeAdapter(ProviderSettings())
    state = service.generate_directions(state.task.task_id, state.task.version, state.task.current_brief, None, use_reference=False)
    assert state.jobs[-1].status == 'failed'
    assert state.jobs[-1].error.code == 'provider_not_configured'
    assert not state.directions
