"""M2 behavior across the HTTP, durable storage and running-provider boundaries.

All product claims and provider output here are synthetic offline fixtures.
"""
from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from backend.app import models as m
from backend.app.api import create_app
from backend.app.service import WorkflowService
from backend.app.storage import WorkflowError


@pytest.fixture
def service(tmp_path):
    return WorkflowService(tmp_path)


def save(service, task_id, *, fields=None, claims=None, notes=None):
    draft = service.store.get_m2_draft(task_id)
    payload = m.M2DraftUpdate(
        expected_draft_version=draft.draft_version,
        fields=draft.fields.model_copy(update=fields or {}),
        claims=draft.claims if claims is None else claims,
        source_notes=draft.source_notes if notes is None else notes,
    )
    return service.store.save_m2_draft(task_id, payload)


def apply(service, task_id):
    draft = service.store.get_m2_draft(task_id)
    task = service.store.get(task_id).task
    return service.apply_m2(task_id, m.M2ApplyRequest(
        expected_draft_version=draft.draft_version,
        expected_version=task.version, based_on_brief=task.current_brief,
    ))


def ready(service):
    state = service.create("M2 offline integration")
    state = service.load_sample(state.task.task_id, state.task.version)
    state = service.recognize(state.task.task_id, state.task.version)
    return service.confirm_analysis(state.task.task_id, state.task.version, state.task.current_analysis)


def generated(service):
    state = ready(service)
    return service.generate_directions(state.task.task_id, state.task.version,
                                       state.task.current_brief, state.task.current_analysis)


def produced(service):
    state = generated(service)
    target = state.directions[0]
    state = service.approve_direction(state.task.task_id, state.task.version,
                                     target.direction_id, target.revision,
                                     state.task.current_brief, state.task.current_analysis)
    return service.generate_outputs(state.task.task_id, state.task.version,
                                    state.task.selected_direction,
                                    state.task.current_brief, state.task.current_analysis)


def test_partial_http_draft_survives_restart_without_fabricating_inputs(service):
    client = TestClient(create_app(service=service))
    task = client.post("/api/tasks", json={"title": "Mixed-language partial input"}).json()
    path = f"/api/tasks/{task['task']['task_id']}"
    draft = client.get(path + "/m2/draft").json()
    response = client.post(path + "/m2/draft", json={
        "expected_draft_version": draft["draft_version"],
        "fields": {"brand_company": "示例 Luma", "product": "随行杯", "presenters": "None available"},
        "claims": [], "source_notes": "Brand notes 原文 preserved.",
    })
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["draft_version"] > draft["draft_version"]
    assert {"target_audience", "platform", "communication_goal", "target_duration_seconds"} <= set(saved["missing_fields"])
    assert saved["fields"]["target_audience"] is None
    assert saved["fields"]["presenters"] == "None available"
    assert saved["fields"]["locations"] is None
    assert client.get(path).json() == task
    restarted = TestClient(create_app(service.store.path.parent))
    assert restarted.get(path + "/m2/draft").json() == saved
    response = restarted.post(path + "/directions/generate", json={
        "expected_version": task["task"]["version"], "brief_ref": None, "analysis_ref": None,
    })
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "m2_incomplete"
    assert response.json()["error"]["message"]
    assert restarted.get(path).json() == task
    assert restarted.get(path + "/m2/draft").json() == saved


def test_draft_autosave_during_recognition_preserves_job_and_new_text(service):
    state = service.create("Type while reference processing")
    state = service.load_sample(state.task.task_id, state.task.version)
    task_id, delegate = state.task.task_id, service.sample_recognition
    original_brief = state.task.current_brief

    class EditingWhileRecognizing:
        def analyze(self, request):
            active = service.store.get(task_id)
            draft = save(service, task_id, fields={"product": "Newer 中文 product draft"})
            assert service.store.get(task_id).task.version == active.task.version
            assert draft.has_pending_inputs
            return delegate.analyze(request)

    service.sample_recognition = EditingWhileRecognizing()
    result = service.recognize(task_id, state.task.version)
    assert result.jobs[-1].status == "succeeded"
    assert result.task.current_brief == original_brief
    assert result.analyses[-1].status == "succeeded"
    assert service.store.get_m2_draft(task_id).fields.product == "Newer 中文 product draft"


@pytest.mark.parametrize("operation", ["directions", "refine", "production"])
def test_autosave_during_admitted_creative_job_does_not_discard_result(service, operation):
    state = ready(service) if operation == "directions" else generated(service)
    task_id, delegate = state.task.task_id, service.creative
    if operation == "production":
        target = state.directions[0]
        state = service.approve_direction(task_id, state.task.version, target.direction_id,
                                         target.revision, state.task.current_brief, state.task.current_analysis)
    original_brief = state.task.current_brief

    def edited():
        active = service.store.get(task_id)
        save(service, task_id, fields={"tone": "Pending handwritten tone 原文"})
        assert service.store.get(task_id).task.version == active.task.version

    class EditingWhileGenerating:
        def generate_directions(self, brief, analysis):
            edited()
            return delegate.generate_directions(brief, analysis)

        def refine_direction(self, brief, analysis, direction, feedback):
            edited()
            return delegate.refine_direction(brief, analysis, direction, feedback)

        def generate_production(self, brief, analysis, direction):
            edited()
            return delegate.generate_production(brief, analysis, direction)

    service.creative = EditingWhileGenerating()
    if operation == "directions":
        result = service.generate_directions(task_id, state.task.version, original_brief, state.task.current_analysis)
        assert len(result.directions) == 2
    elif operation == "refine":
        target = state.directions[0]
        result = service.refine_direction(task_id, state.task.version, target.direction_id,
                                          target.revision, original_brief, state.task.current_analysis,
                                          "Make it presenter-free")
        assert result.feedback[-1].status == "applied"
    else:
        result = service.generate_outputs(task_id, state.task.version, state.task.selected_direction,
                                          original_brief, state.task.current_analysis)
        assert result.production_briefs[-1].brief_ref == original_brief
    assert result.jobs[-1].status == "succeeded"
    assert result.task.current_brief == original_brief
    draft = service.store.get_m2_draft(task_id)
    assert draft.has_pending_inputs and draft.fields.tone == "Pending handwritten tone 原文"
    with pytest.raises(WorkflowError) as error:
        target = result.directions[-1]
        service.approve_direction(task_id, result.task.version, target.direction_id,
                                  target.revision, original_brief, result.task.current_analysis)
    assert error.value.code == "m2_pending_changes"


@pytest.mark.parametrize("operation", ["directions", "refine", "approve", "production"])
def test_api_pending_inputs_gate_every_new_creative_action_without_mutation(service, operation):
    state = produced(service)
    task_id = state.task.task_id
    save(service, task_id, fields={"production_limits": "A newly supplied optional constraint"})
    before = service.store.get(task_id)
    client = TestClient(create_app(service=service))
    direction = state.task.selected_direction
    body = {"expected_version": state.task.version,
            "brief_ref": state.task.current_brief.model_dump(),
            "analysis_ref": state.task.current_analysis.model_dump()}
    route = "directions/generate"
    if operation in {"refine", "approve"}:
        route = f"directions/{direction.id}/{operation}"
        body["direction_revision"] = direction.revision
        if operation == "refine":
            body["instruction"] = "Make it presenter-free"
    elif operation == "production":
        route = "outputs/generate"
        body["direction_ref"] = direction.model_dump()
    response = client.post(f"/api/tasks/{task_id}/{route}", json=body)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "m2_pending_changes"
    assert service.store.get(task_id) == before
    assert len(before.production_briefs) == len(before.storyboards) == 1
    assert all(item.currentness == "current" for item in before.production_briefs + before.storyboards)


@pytest.mark.parametrize("operation", ["directions", "approve"])
def test_pending_gate_is_checked_at_atomic_admission_not_only_prior_read(service, monkeypatch, operation):
    state = generated(service)
    original_update = service._update
    injected = False

    def race(task_id, version, mutate, **kwargs):
        nonlocal injected
        if kwargs.get("require_m2_ready") and not injected:
            injected = True
            save(service, task_id, fields={"tone": "Saved just before admission"})
        return original_update(task_id, version, mutate, **kwargs)

    monkeypatch.setattr(service, "_update", race)
    with pytest.raises(WorkflowError) as error:
        if operation == "directions":
            service.generate_directions(state.task.task_id, state.task.version,
                                        state.task.current_brief, state.task.current_analysis)
        else:
            target = state.directions[0]
            service.approve_direction(state.task.task_id, state.task.version, target.direction_id,
                                      target.revision, state.task.current_brief, state.task.current_analysis)
    assert injected and error.value.code == "m2_pending_changes"
    assert service.store.get(state.task.task_id) == state


def test_notes_only_do_not_gate_generation_or_mutate_formal_inputs(service):
    state = ready(service)
    task_id = state.task.task_id
    draft = save(service, task_id, notes="Notes only: 可选资料, not an accepted claim.")
    assert not draft.has_pending_inputs
    assert service.store.get(task_id) == state
    result = service.generate_directions(task_id, state.task.version,
                                         state.task.current_brief, state.task.current_analysis)
    assert result.jobs[-1].status == "succeeded"
    assert result.briefs == state.briefs
    assert service.store.get_m2_draft(task_id).source_notes == draft.source_notes


def test_apply_during_creative_job_rejects_superseded_provider_result(service):
    state = ready(service)
    task_id, delegate = state.task.task_id, service.creative
    original = state.briefs[-1].model_dump()

    class ApplyDuringGeneration:
        def generate_directions(self, brief, analysis):
            save(service, task_id, fields={"prohibited_claims": ["Do not claim dishwasher safety"]})
            result = apply(service, task_id)
            assert result.changed
            return delegate.generate_directions(brief, analysis)

    service.creative = ApplyDuringGeneration()
    result = service.generate_directions(task_id, state.task.version,
                                         state.task.current_brief, state.task.current_analysis)
    assert result.jobs[-1].status == "failed"
    assert result.jobs[-1].error.code == "stale_result"
    assert not result.directions and result.task.selected_direction is None
    assert result.briefs[0].model_dump() == original
    assert result.briefs[-1].revision == 2
    assert not service.store.get_m2_draft(task_id).has_pending_inputs


def test_manual_m2_claim_metadata_reaches_m6_m7_and_exports(service):
    state = service.create("Synthetic constrained product")
    task_id = state.task.task_id
    included = m.M2Claim(claim_id="claim_warm", statement="Keeps drinks warm for up to 6 hours",
                         qualification="In our indoor test only", supporting_notes="Synthetic supplied test note 原文",
                         source_urls=["https://example.com/synthetic-test"], confirmed_for_use=True)
    excluded = m.M2Claim(claim_id="claim_excluded", statement="Unconfirmed all-day claim")
    save(service, task_id, fields={
        "brand_company": "Fictional Luma", "product": "Fictional travel tumbler",
        "target_audience": "Office commuters", "platform": "TikTok",
        "communication_goal": "Demonstrate everyday usefulness", "target_duration_seconds": 20,
        "prohibited_claims": ["Do not claim dishwasher safety"],
    }, claims=[included, excluded])
    result = apply(service, task_id)
    assert result.changed and not result.draft.has_pending_inputs
    assert len(result.draft.claims) == 2
    state = service.load_sample(task_id, result.task.task.version)
    state = service.recognize(task_id, state.task.version)
    state = service.confirm_analysis(task_id, state.task.version, state.task.current_analysis)
    delegate, seen = service.creative, []

    class CaptureAppliedInputs:
        def generate_directions(self, brief, analysis):
            seen.append(brief.model_dump(mode="json"))
            return delegate.generate_directions(brief, analysis)

        def generate_production(self, brief, analysis, direction):
            seen.append(brief.model_dump(mode="json"))
            return delegate.generate_production(brief, analysis, direction)

    service.creative = CaptureAppliedInputs()
    state = service.generate_directions(task_id, state.task.version,
                                        state.task.current_brief, state.task.current_analysis)
    direction = state.directions[0]
    state = service.approve_direction(task_id, state.task.version, direction.direction_id,
                                     direction.revision, state.task.current_brief, state.task.current_analysis)
    state = service.generate_outputs(task_id, state.task.version, state.task.selected_direction,
                                    state.task.current_brief, state.task.current_analysis)
    assert len(seen) == 2
    for context in seen:
        assert context["selling_points"] == [included.statement]
        assert context["claim_details"] == [{
            "claim_id": included.claim_id, "statement": included.statement,
            "supporting_notes": included.supporting_notes, "source_urls": included.source_urls,
            "qualification": included.qualification, "confirmation_origin": "user_confirmed",
        }]
        assert context["prohibited_claims"] == ["Do not claim dishwasher safety"]
        assert excluded.statement not in str(context)
    assert state.jobs[-1].status == "succeeded"
    assert included.qualification in service.export(task_id, "brief.md")
    assert "Do not claim dishwasher safety" in service.export(task_id, "brief.md")
    assert "20" in service.export(task_id, "storyboard.csv")


def test_old_brief_route_cannot_skip_confirmation_and_identical_apply_retains_outputs(service):
    state = produced(service)
    task_id = state.task.task_id
    client = TestClient(create_app(service=service))
    fields = state.briefs[-1].model_dump(mode="json", exclude={
        "brief_id", "task_id", "revision", "schema_version", "created_at", "updated_at",
    })
    missing = deepcopy(fields)
    del missing["claim_details"]
    legacy = deepcopy(fields)
    legacy["claim_details"][0]["confirmation_origin"] = "legacy_unrecorded"
    for invalid in (missing, legacy):
        response = client.post(f"/api/tasks/{task_id}/brief", json={
            "expected_version": state.task.version, "brief": invalid,
        })
        assert response.status_code == 422, response.text
        assert service.store.get(task_id) == state
    response = client.post(f"/api/tasks/{task_id}/brief", json={
        "expected_version": state.task.version, "brief": fields,
    })
    assert response.status_code == 200, response.text
    assert response.json() == state.model_dump(mode="json")
    result = apply(service, task_id)
    assert not result.changed and result.task == state
    assert result.task.task.selected_direction == state.task.selected_direction
    assert result.task.task.current_storyboard == state.task.current_storyboard
    request = {"expected_version": state.task.version,
               "expected_draft_version": result.draft.draft_version,
               "based_on_brief": state.task.current_brief.model_dump()}
    for _ in range(2):
        response = client.post(f"/api/tasks/{task_id}/m2/apply", json=request)
        assert response.status_code == 200, response.text
        assert response.json()["changed"] is False
        assert response.json()["task"] == state.model_dump(mode="json")
    draft = save(service, task_id, fields={"tone": "Keep this newer draft wording"})
    response = client.post(f"/api/tasks/{task_id}/brief", json={
        "expected_version": state.task.version, "brief": fields,
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "m2_pending_changes"
    assert service.store.get(task_id) == state
    assert service.store.get_m2_draft(task_id) == draft


def test_apply_optional_restriction_invalidates_outputs_but_preserves_history(service):
    state = produced(service)
    task_id = state.task.task_id
    original_brief = state.briefs[-1].model_dump()
    original_output = state.production_briefs[-1]
    save(service, task_id, fields={"prohibited_claims": ["Newly supplied restriction"]})
    result = apply(service, task_id)
    assert result.changed and result.task.task.version == state.task.version + 1
    assert result.task.briefs[-1].revision == state.briefs[-1].revision + 1
    assert result.task.briefs[0].model_dump() == original_brief
    assert result.task.task.selected_direction is None
    assert all(item.currentness == "outdated" for item in result.task.production_briefs + result.task.storyboards)
    assert result.task.production_briefs[-1].core_message == original_output.core_message
    assert result.task.production_briefs[-1].direction_ref == original_output.direction_ref
    assert not result.draft.has_pending_inputs
