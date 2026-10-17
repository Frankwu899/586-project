"""Offline provider-boundary checks; fixtures are not recognition-quality evidence."""
from copy import deepcopy
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from backend.app.models import AnalysisResult, CreativeFeedback, ReviewState, VersionRef, utc_now
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.providers.creative import OpenAICreativeAdapter
from backend.app.sample import sample_brief


class FakeContentProvider:
    """A plain content provider, independent of OpenAI HTTP response types."""
    def __init__(self, *results):
        self.results, self.calls = list(results), []
        self.records = []

    def json_response(self, **kwargs):
        self.calls.append(kwargs)
        self.records.append({"failure_code": None, "requested_model": kwargs["model"],
                             **kwargs.get("metadata", {})})
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)


@pytest.fixture
def inputs():
    brief = sample_brief("task_provider")
    brief.brand_company, brief.product = "示例品牌 Demo", "DemoCup 随行杯"
    brief.approved_messages = ["旋开杯盖 / Twist open"]
    brief.target_duration_seconds = 23
    brief.production_limits, brief.presenters = "仅桌面素材", "无人出镜"
    analysis = AnalysisResult.model_validate({
        "analysis_id": "analysis_provider", "task_id": brief.task_id, "video_id": "video_provider",
        "duration_seconds": 3, "frame_count": 60, "status": "succeeded",
        "events": [{"event_id": "event_product", "video_id": "video_provider", "start_frame": 0,
                    "end_frame": 60, "lane": "visual", "kind": "visual_action",
                    "description": "手旋开杯盖", "source": "Synthetic fixture", "method": "Fake provider"}],
        "coverage": {"visual_action": "observations"},
        "origin": {"kind": "provider", "description": "Fake provider fixture; no paid call."},
    })
    analysis.review = ReviewState(user_confirmed=True, confirmed_at=utc_now())
    analysis.updated_at = utc_now()
    return brief, analysis


def content(hook="旋开杯盖 / Twist open"):
    return {"core_message": "DemoCup 随行杯", "hook": hook, "narrative": "展示旋开动作，然后邀请探索。",
            "cta": "探索 DemoCup", "production_requirements": ["无人出镜，仅桌面素材"],
            "evidence": [{"event_id": "event_product", "reason": "Reference the visible opening sequence."}],
            "rationale": "The source shows a lid-opening action; product efficacy is unverified.",
            "hypotheses": [{"hypothesis": "A close-up may clarify the motion.",
                            "test_method": "Ask five viewers to describe the opening sequence."}],
            "production_notes": ["Use only approved copy."]}


def generated(inputs):
    fake = FakeContentProvider({"directions": [content(), content("产品细节 / Details")]})
    adapter = OpenAICreativeAdapter(ProviderSettings(), fake)
    return adapter, fake, adapter.generate_directions(*inputs)[0]


def feedback(target, instruction="请保留中文产品名，并把动作移到开头。"):
    return CreativeFeedback(feedback_id="feedback_provider", task_id=target.task_id,
                            instruction=instruction, target_direction=VersionRef(id=target.direction_id, revision=target.revision),
                            brief_ref=target.brief_ref, analysis_ref=target.analysis_ref)


def production_content():
    values = content()
    return {"production_brief": {"title": "DemoCup 制作简报",
                                **{key: values[key] for key in ("core_message", "hook", "narrative", "cta", "evidence", "production_notes")}},
            "rows": [{"start_seconds": 0.0, "end_seconds": 23.0, "visual": "手旋开杯盖",
                      "dialogue": None, "on_screen_text": "DemoCup 随行杯", "sound": None,
                      "cta": "探索 DemoCup", "evidence": values["evidence"]}]}


def test_two_unicode_drafts_have_application_owned_identity_and_exact_citations(inputs):
    brief, analysis = inputs
    fake = FakeContentProvider({"directions": [content(), content("产品细节 / Details")]})
    adapter = OpenAICreativeAdapter(ProviderSettings(creative_language="Chinese"), fake)
    first, second = adapter.generate_directions(brief, analysis)
    assert first.direction_id != second.direction_id
    assert first.approval_status == "draft" and first.approved_at is None
    assert first.revision == 1 and first.feedback_refs == [] and first.origin.kind == "provider"
    assert first.core_message == "DemoCup 随行杯"
    assert first.evidence[0].analysis_id == analysis.analysis_id
    assert first.evidence[0].analysis_revision == analysis.revision
    assert first.evidence[0].video_id == analysis.video_id
    assert "Test method" in first.hypotheses[0]
    assert "Production limits: 仅桌面素材" in first.production_notes
    prompt = fake.calls[0]["prompt"]
    assert "Chinese" in prompt and "旋开杯盖 / Twist open" in prompt and "prohibited_claims" in prompt
    assert "conversion" in prompt and "unmeasured" in prompt
    assert fake.calls[0]["metadata"]["capability"] == "creative"


@pytest.mark.parametrize("corrupt", [
    lambda result: result.update(directions=[content()]),
    lambda result: result["directions"].append(content()),
    lambda result: result["directions"][0].update(direction_id="direction_model"),
    lambda result: result["directions"][0].update(hook=" \t"),
    lambda result: result["directions"][0].update(hypotheses=[{"hypothesis": "Increase clicks"}]),
    lambda result: result["directions"][0]["evidence"][0].update(event_id="event_missing"),
    lambda result: result["directions"][0]["evidence"][0].update(analysis_revision=99),
    lambda result: result["directions"][0].update(evidence=[]),
    lambda result: result.update(directions=[content(), content()]),
])
def test_malformed_content_and_dangling_citations_fail_without_sample_fallback(inputs, corrupt):
    result = {"directions": [content(), content("Alternative opening")]}
    corrupt(result)
    fake = FakeContentProvider(result)
    with pytest.raises(ProviderError):
        OpenAICreativeAdapter(ProviderSettings(), fake).generate_directions(*inputs)
    assert len(fake.calls) == 1


def test_refinement_receives_exact_unicode_feedback_and_preserves_original(inputs):
    adapter, fake, target = generated(inputs)
    before = target.model_dump()
    instruction = feedback(target)
    fake.results.append(content("先旋开杯盖"))
    refined = adapter.refine_direction(*inputs, target, instruction)
    assert target.model_dump() == before
    assert refined.direction_id == target.direction_id and refined.revision == target.revision + 1
    assert refined.approval_status == "draft" and refined.approved_at is None
    assert refined.feedback_refs == [VersionRef(id=instruction.feedback_id, revision=instruction.revision)]
    assert instruction.instruction in fake.calls[-1]["prompt"]
    assert refined.hook == "先旋开杯盖"
    wrong = instruction.model_copy(update={"target_direction": VersionRef(id=target.direction_id, revision=99)})
    with pytest.raises(ValueError, match="exact direction"):
        adapter.refine_direction(*inputs, target, wrong)
    assert len(fake.calls) == 2


def test_production_requires_approval_and_uses_planned_seconds(inputs):
    adapter, fake, target = generated(inputs)
    with pytest.raises(ValueError, match="approval"):
        adapter.generate_production(*inputs, target)
    target.approval_status, target.approved_at = "approved", utc_now()
    target.updated_at = target.approved_at
    fake.results.append(production_content())
    production, story = adapter.generate_production(*inputs, target)
    assert production.direction_ref == VersionRef(id=target.direction_id, revision=target.revision)
    assert production.origin.kind == story.origin.kind == "provider"
    assert story.rows[0].end_seconds == 23 != inputs[1].duration_seconds
    assert story.rows[0].evidence[0].analysis_revision == inputs[1].revision
    assert "Prohibited claims: " in " ".join(production.production_notes)
    assert "无人出镜" in " ".join(production.production_notes)
    assert any("Test method" in note for note in production.production_notes)


@pytest.mark.parametrize("timing", [(1, 23), (0, 24), (22, 20), (0, float("nan"))])
def test_provider_storyboard_cannot_escape_planned_timing(inputs, timing):
    adapter, fake, target = generated(inputs)
    target.approval_status, target.approved_at = "approved", utc_now()
    result = production_content()
    result["rows"][0]["start_seconds"], result["rows"][0]["end_seconds"] = timing
    fake.results.append(result)
    with pytest.raises(ProviderError):
        adapter.generate_production(*inputs, target)


def test_gate_provider_failure_and_missing_key_make_no_fictional_outputs(inputs):
    brief, analysis = inputs
    fake = FakeContentProvider(ProviderError("provider_timeout", "Provider timed out.", True))
    adapter = OpenAICreativeAdapter(ProviderSettings(), fake)
    for changes in ({"status": "partial"}, {"review": ReviewState()}, {"frame_count": None}):
        with pytest.raises(ValueError):
            adapter.generate_directions(brief, analysis.model_copy(update=changes))
    assert not fake.calls
    with pytest.raises(ProviderError, match="timed out"):
        adapter.generate_directions(brief, analysis)
    with pytest.raises(ProviderError) as error:
        OpenAICreativeAdapter(replace(ProviderSettings(), api_key="")).generate_directions(*inputs)
    assert error.value.code == "provider_not_configured"


def test_creative_provider_setting_is_checked_before_request(inputs):
    fake = FakeContentProvider()
    adapter = OpenAICreativeAdapter(ProviderSettings(creative_provider="unsupported"), fake)
    with pytest.raises(ProviderError) as error:
        adapter.generate_directions(*inputs)
    assert error.value.code == "unsupported_provider" and not fake.calls


def test_diagnostics_identify_candidates_and_do_not_claim_service_persistence(inputs):
    adapter, fake, target = generated(inputs)
    proposed = fake.records[-1]["proposed_output_refs"]
    assert len(proposed) == 2 and proposed[0]["id"] == target.direction_id
    assert all(item["persistence"] == "adapter_candidate_not_committed" for item in proposed)
    assert "output_refs" not in fake.records[-1]
    previous = deepcopy(fake.records[-1])
    with pytest.raises(ValueError, match="approval"):
        adapter.generate_production(*inputs, target)
    assert fake.records[-1] == previous


def test_post_transport_validation_failure_is_recorded(inputs):
    adapter, fake, target = generated(inputs)
    target.approval_status, target.approved_at = "approved", utc_now()
    result = production_content()
    result["rows"][0]["end_seconds"] = 24
    fake.results.append(result)
    with pytest.raises(ProviderError):
        adapter.generate_production(*inputs, target)
    assert fake.records[-1]["failure_code"] == "invalid_creative_output"
    assert "proposed_output_refs" not in fake.records[-1]


def test_original_production_shot_has_no_fabricated_citation(inputs):
    adapter, fake, target = generated(inputs)
    target.approval_status, target.approved_at = "approved", utc_now()
    result = production_content()
    result["production_brief"]["evidence"] = []
    result["rows"][0].update(evidence=[], visual="A product illustration enters a new colored background.")
    fake.results.append(result)
    production, story = adapter.for_language("Chinese").generate_production(*inputs, target)
    assert production.evidence == story.rows[0].evidence == []
    assert story.rows[0].visual.startswith("原创制作建议：")
    assert "Original proposed shots may have evidence=[]" in fake.calls[-1]["prompt"]


def test_only_resource_changes_do_not_count_as_a_different_direction(inputs):
    other = content()
    other["production_requirements"] = ["A new background and a second presenter"]
    fake = FakeContentProvider({"directions": [content(), other]})
    with pytest.raises(ProviderError, match="distinct creative"):
        OpenAICreativeAdapter(ProviderSettings(), fake).generate_directions(*inputs)


def test_manual_direction_explanations_cannot_constrain_production_or_refine(inputs):
    adapter, fake, target = generated(inputs)
    stale_marker = "OBSOLETE presenter requirement must disappear"
    target.auxiliary_status = "needs_review"
    target.production_requirements = [stale_marker]
    target.production_notes = [stale_marker]
    target.rationale = stale_marker
    target.hypotheses = [stale_marker]
    target.evidence[0].reason = stale_marker
    target.hook = "The manually approved new hook"
    target.approval_status, target.approved_at = "approved", utc_now()
    fake.results.append(production_content())
    production, _ = adapter.generate_production(*inputs, target)
    context = json.loads(fake.calls[-1]["prompt"].split("INPUT_JSON:\n")[1])
    assert context["direction"]["hook"] == target.hook
    assert context["direction"]["auxiliary_status"] == "needs_review"
    assert stale_marker not in fake.calls[-1]["prompt"]
    assert stale_marker not in " ".join(production.production_notes)
    assert context["reviewed_analysis"]["events"]  # Valid source is independently available.
    fake.results.append(content("Refreshed hook"))
    revised = adapter.refine_direction(*inputs, target, feedback(target))
    assert stale_marker not in fake.calls[-1]["prompt"]
    assert revised.auxiliary_status == "current"
    assert revised.rationale == content()["rationale"]
    assert stale_marker not in " ".join(revised.production_notes)
    assert target.auxiliary_status == "needs_review"  # Prior revision is preserved.


def test_refinement_does_not_union_even_current_obsolete_notes(inputs):
    adapter, fake, target = generated(inputs)
    target.production_notes.append("Use a presenter throughout")
    replacement = content("No presenter opening")
    replacement["production_notes"] = ["Presenter-free product-only sequence"]
    fake.results.append(replacement)
    revised = adapter.refine_direction(*inputs, target, feedback(target, "Remove all presenters"))
    assert "Use a presenter throughout" not in revised.production_notes
    assert "Presenter-free product-only sequence" in revised.production_notes


def test_language_scopes_share_transport_and_diagnostics_without_global_mutation(inputs):
    fake = FakeContentProvider(*[{"directions": [content(), content("Second opening")]} for _ in range(2)])
    adapter = OpenAICreativeAdapter(ProviderSettings(), fake)
    def generate(language):
        scoped = adapter.for_language(language)
        scoped.diagnostics_context = {"task_id": language}
        return scoped.generate_directions(*inputs)
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(generate, ["Chinese", "English"]))
    assert adapter.settings.creative_language == "English"
    assert adapter.diagnostics_context == {}
    assert len(adapter.records) == 2
    for call in fake.calls:
        language = call["metadata"]["task_id"]
        assert f"Write creative narrative in {language}" in call["prompt"]
        assert "旋开杯盖 / Twist open" in call["prompt"]
    with pytest.raises(ValueError, match="English or Chinese"):
        adapter.for_language("French")
