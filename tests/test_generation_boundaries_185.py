"""Synthetic 1.8.5 regressions; no original QA provider response is available."""
import json

import pytest

from backend.app.project_workspace.conversation import ConversationService, _context, _validate_reply
from backend.app.project_workspace.models import Fact, Message, Project
from backend.app.project_workspace.planning import _target_duration
from backend.app.workflow_errors import WorkflowError
from test_project_workspace_conversation import reply
from test_project_workspace_planning import approve, idea_response, pack_response, setup


SOURCE = (
    "Northstar is a personalized wellness platform preparing to launch in the US. "
    "It brings personal wellness information into an understandable dashboard. "
    "No clinical benefits or disease-prevention capabilities have been established."
)


@pytest.mark.parametrize("text", [
    "Northstar is preparing for a US launch.",
    "Northstar has no established clinical benefits or disease-prevention capabilities.",
    "Avoid clinical benefits and disease-prevention claims, because neither is established for Northstar.",
])
def test_synthetic_safe_fact_and_full_negative_scope_remain_usable(text):
    context = _context(Project(messages=[Message(role="user", text=SOURCE)]))
    validated = _validate_reply(reply(text=text), context)
    assert validated.reply_valid, validated.issues


@pytest.mark.parametrize("text", [
    "Northstar prevents disease.",
    "Northstar has established clinical benefits.",
    "Northstar has no established clinical benefits, but it prevents disease.",
    "Northstar has no clinical benefits.",  # unknown efficacy is not proof of absence
    "Northstar is launching globally.",
    "Northstar is already available in the US.",
    "Northstar treats disease just like RivalCare.",
])
def test_synthetic_grounding_still_rejects_stronger_or_changed_scope(text):
    context = _context(Project(messages=[Message(role="user", text=SOURCE + " RivalCare treats disease.")]))
    validated = _validate_reply(reply(text=text), context)
    assert not validated.reply_valid


@pytest.mark.parametrize(("text", "seconds"), [
    ("Please make a 30-second video.", "30 seconds"),
    ("Target duration: 1 minute.", "60 seconds"),
    ("请制作一个45秒的视频。", "45 seconds"),
])
def test_explicit_duration_becomes_unconfirmed_proposal_even_without_provider(tmp_path, text, seconds):
    store, _, _, project = setup(tmp_path)
    # Remove setup's confirmed duration to test conversational intake alone.
    project = store.update(project.id, project.version, lambda state: (state.briefs.clear(), state.brief_draft.clear()))
    conversation = ConversationService(store, lambda: None)
    saved, message_id = conversation.begin_message(project.id, project.version, text)
    duration = next(fact for fact in saved.brief_draft if fact.key == "duration")
    assert duration.value == seconds and duration.status == "suggested"
    assert saved.briefs == []
    assert duration.sources[0].message_id == message_id
    assert duration.sources[0].excerpt in text
    assert not duration.permitted_for_use
    assert store.get(project.id).brief_draft == saved.brief_draft


@pytest.mark.parametrize("text", [
    "Please make a 30-45 second video.",
    "Make a 30-second or 60-second video.",
    "The reference runs 30 seconds; make the new video 45 seconds.",
])
def test_ambiguous_duration_keeps_open_decision_without_guess(tmp_path, text):
    store, _, _, project = setup(tmp_path)
    project = store.update(project.id, project.version, lambda state: (state.briefs.clear(), state.brief_draft.clear()))
    conversation = ConversationService(store, lambda: None)
    saved, _ = conversation.begin_message(project.id, project.version, text)
    assert not any(fact.key == "duration" for fact in saved.brief_draft)
    assert any("duration" in note.lower() for note in saved.unresolved)


def test_conflicting_confirmed_duration_never_silently_chooses_first(tmp_path):
    store, _, _, project = setup(tmp_path)
    project = store.update(project.id, project.version, lambda state: state.briefs[-1].facts.append(
        Fact(key="target_duration", value="30 seconds", status="confirmed")))
    with pytest.raises(WorkflowError) as failure:
        _target_duration(project)
    assert failure.value.code == "production_duration_ambiguous"


def test_before_approval_readiness_exposes_duration_without_blocking_manual_approval(tmp_path):
    store, service, _, project = setup(tmp_path)
    project = store.update(project.id, project.version, lambda state: setattr(state.briefs[-1], "facts", [
        fact for fact in state.briefs[-1].facts if fact.key != "duration"]))
    item = project.contents[0]
    project = service.save_direction(project.id, project.version, item.id,
                                     {"title": "Morning routine", "concept": "A quiet daily preparation."})
    readiness = service.direction_readiness(project.id, item.id)
    assert not readiness["production_ready"]
    assert any("duration" in requirement.lower() for requirement in readiness["production_requirements"])
    approved = approve(service, project)
    assert approved.contents[0].directions[-1].approved


def test_visual_only_source_can_support_new_voiceover_without_observed_audio(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), reference=True)
    project = store.update(project.id, project.version, lambda state: state.resources[0].evidence[-1].coverage.update(speech="failed"))
    project = service.generate_directions(project.id, project.contents[0].id, visual_only=True)
    context = json.loads(transport.calls[-1]["prompt"].split("INPUT_JSON:\n", 1)[1])
    assert context["audio_policy"]["reference_audio"] == "unknown"
    assert context["audio_policy"]["creation_audio"] == "creative_choice"
    project = approve(service, project)
    transport.response = pack_response()
    result = service.generate_pack(project.id, project.contents[0].id)
    assert result.packs[-1].shots[0].dialogue == "Ready?"


def test_explicit_silence_rejects_generated_speech_preserving_old_work(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    project = store.update(project.id, project.version, lambda state: state.briefs[-1].facts.append(
        Fact(key="constraints", value="The new video must be silent. No voice-over or music.", status="confirmed")))
    project = service.generate_directions(project.id, project.contents[0].id)
    project = approve(service, project)
    transport.response = pack_response()
    with pytest.raises(WorkflowError) as failure:
        service.generate_pack(project.id, project.contents[0].id)
    assert failure.value.code == "creation_audio_conflict"
    assert store.get(project.id).packs == []


def test_safe_reply_sentence_survives_independent_unsupported_sentence():
    context = _context(Project(messages=[Message(role="user", text=SOURCE)]))
    validated = _validate_reply(reply(text="Consider a short introduction. Northstar cures disease."), context)
    assert validated.reply_valid
    assert validated.parsed.reply == "Consider a short introduction."
    assert validated.issues == [("grounded_product_assertion", "reply[1]")]


# The source below is the exact section-4 QA user message. Responses remain
# synthetic because the rejected provider response was not included in the handoff.
QA_OVERVIEW_INPUT = """I lead marketing for WellPath, a fictional personalized preventive health platform preparing to launch in the US. Our confirmed product scope is helping users understand their health and wellness data, track long-term goals, and communicate with healthcare professionals. We have no established diagnostic, treatment, weight-loss or disease-prevention benefits.

For this test campaign, I want a 30-second English social video for US adults who find their health information confusing. The primary objective is to encourage interested viewers to explore WellPath and sign up; the tone should be clear, supportive, and trustworthy. Budget, clinical evidence, performance results and specific interface features have not been supplied.

I have uploaded Hims&Hers-8.mp4 as a reference and will later compare it with two more references. Help me shape a usable brief and identify what you still need to know. Borrow communication techniques only; do not assume that the reference brand’s lab testing, prescriptions, treatment, or clinician-network size are WellPath features."""


def test_exact_qa_source_accepts_synthetic_faithful_scope_and_full_restrictions():
    context = _context(Project(messages=[Message(role="user", text=QA_OVERVIEW_INPUT)]))
    response = reply(text="WellPath helps users understand their health and wellness data, track long-term goals, and communicate with healthcare professionals. WellPath has no established diagnostic, treatment, weight-loss or disease-prevention benefits.")
    result = _validate_reply(response, context)
    assert result.reply_valid and not result.issues


@pytest.mark.parametrize("text", [
    "WellPath offers lab testing and prescriptions.",
    "WellPath treats disease.",
    "WellPath has no established diagnostic benefits.",  # omits three restrictions
    "WellPath helps users understand their health and wellness data, track long-term goals, and communicate with healthcare professionals.",  # drops adjacent material restriction
])
def test_exact_qa_source_rejects_synthetic_feature_transfer_and_lost_scope(text):
    context = _context(Project(messages=[Message(role="user", text=QA_OVERVIEW_INPUT)]))
    assert not _validate_reply(reply(text=text), context).reply_valid


@pytest.mark.parametrize("text", [
    "Do not make a 30-second video.",
    "The source is a 30-second video.",
    "The reference is a 30-second video.",
])
def test_negated_or_source_duration_is_not_a_new_video_target(tmp_path, text):
    store, _, _, project = setup(tmp_path)
    project = store.update(project.id, project.version, lambda state: (state.briefs.clear(), state.brief_draft.clear()))
    saved, _ = ConversationService(store, lambda: None).begin_message(project.id, project.version, text)
    assert not any(fact.key == "duration" for fact in saved.brief_draft)


def test_approved_direction_voiceover_is_not_dropped_for_visual_only_source(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), reference=True)
    project = store.update(project.id, project.version, lambda state: state.resources[0].evidence[-1].coverage.update(speech="failed"))
    project = service.generate_directions(project.id, project.contents[0].id, visual_only=True)
    item = project.contents[0]
    direction = item.directions[-1]
    project = service.save_direction(project.id, project.version, item.id, {
        "concept": direction.concept, "narrative": "Include voice-over. Keep the spoken script around 45–55 English words."},
        direction.id, direction.revision)
    project = approve(service, project)
    transport.response = pack_response()
    for shot in transport.response["shots"]:
        shot["dialogue"] = "None"
    with pytest.raises(WorkflowError) as failure:
        service.generate_pack(project.id, item.id)
    assert failure.value.code == "creation_audio_conflict"
    context = json.loads(transport.calls[-1]["prompt"].split("INPUT_JSON:\n", 1)[1])
    assert context["audio_policy"]["creation_audio"] == "voiceover"
    assert store.get(project.id).packs == []


def test_exact_qa_input_proposes_duration_without_approving_other_assumptions(tmp_path):
    store, _, _, project = setup(tmp_path)
    project = store.update(project.id, project.version, lambda state: (state.briefs.clear(), state.brief_draft.clear()))
    saved, _ = ConversationService(store, lambda: None).begin_message(project.id, project.version, QA_OVERVIEW_INPUT)
    assert [(fact.key, fact.value, fact.status) for fact in saved.brief_draft] == [("duration", "30 seconds", "suggested")]
    assert saved.briefs == []


def test_direct_silence_instruction_survives_direction_approval(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    project = service.generate_directions(project.id, project.contents[0].id,
                                          instruction="The new video must be silent.")
    project = approve(service, project)
    transport.response = pack_response()
    with pytest.raises(WorkflowError) as failure:
        service.generate_pack(project.id, project.contents[0].id)
    assert failure.value.code == "creation_audio_conflict"
    assert store.get(project.id).packs == []


@pytest.mark.parametrize("text", [
    "Please make a video no longer than 30 seconds.",
    "Please make a video at least 30 seconds.",
    "Please make a video shorter than 30 seconds.",
    "Please make a video, but not 30 seconds.",
])
def test_bounded_or_negated_duration_remains_unresolved_not_exact(tmp_path, text):
    store, _, _, project = setup(tmp_path)
    project = store.update(project.id, project.version, lambda state: (state.briefs.clear(), state.brief_draft.clear()))
    saved, _ = ConversationService(store, lambda: None).begin_message(project.id, project.version, text)
    assert not any(fact.key == "duration" for fact in saved.brief_draft)
    assert any("duration" in note.lower() for note in saved.unresolved)


def test_qualified_safe_reply_group_survives_an_independent_unsupported_sentence():
    context = _context(Project(messages=[Message(role="user", text=QA_OVERVIEW_INPUT)]))
    safe_group = ("WellPath helps users understand their health and wellness data, track long-term goals, "
                  "and communicate with healthcare professionals. WellPath has no established diagnostic, "
                  "treatment, weight-loss or disease-prevention benefits.")
    result = _validate_reply(reply(text=safe_group + " WellPath cures disease."), context)
    assert result.reply_valid
    assert result.parsed.reply == safe_group
    assert result.issues == [("grounded_product_assertion", "reply[2]")]


@pytest.mark.parametrize(("requirement", "remove_audio"), [
    ("Do not include voice-over.", False),
    ("Do not use narration.", False),
    ("The new video should be silent.", False),
    ("Do not make a silent video.", True),
])
def test_explicit_negated_audio_choice_cannot_be_reversed(tmp_path, requirement, remove_audio):
    store, service, transport, project = setup(tmp_path, idea_response())
    project = store.update(project.id, project.version, lambda state: state.briefs[-1].facts.append(
        Fact(key="constraints", value=requirement, status="confirmed")))
    project = service.generate_directions(project.id, project.contents[0].id)
    project = approve(service, project)
    transport.response = pack_response()
    if remove_audio:
        for shot in transport.response["shots"]:
            shot["dialogue"], shot["sound"] = "None", "None"
    with pytest.raises(WorkflowError) as failure:
        service.generate_pack(project.id, project.contents[0].id)
    assert failure.value.code == "creation_audio_conflict"
    assert store.get(project.id).packs == []


@pytest.mark.parametrize("source", [
    "Northstar is not preparing to launch in the US.",
    "Northstar is not yet preparing to launch in the US.",
    "Northstar is considering preparing to launch in the US.",
    "Northstar is a platform that might be preparing to launch in the US.",
])
def test_launch_rephrase_never_drops_source_negation_or_modality(source):
    context = _context(Project(messages=[Message(role="user", text=source)]))
    assert not _validate_reply(reply(text="Northstar is preparing for a US launch."), context).reply_valid


@pytest.mark.parametrize(("source", "rewritten", "qualification"), [
    ("Northstar is a platform. Our confirmed product scope is helping users track long-term goals.",
     "Northstar helps users track long-term goals.", "However, access is limited to enrolled participants."),
    ("Northstar is a platform. Our confirmed product scope is helping users track long-term goals.",
     "Northstar helps users track long-term goals.", "Only enrolled participants can access this capability."),
    ("Northstar is a platform. Our confirmed product scope is helping users track long-term goals.",
     "Northstar helps users track long-term goals.", "If the service is available in their region."),
    ("Northstar is a platform. Our confirmed product scope is helping users track long-term goals.",
     "Northstar helps users track long-term goals.", "Unless participation is restricted by the study."),
    ("Northstar is preparing to launch in the US.",
     "Northstar is preparing for a US launch.", "Only after regulatory approval."),
])
def test_rephrase_never_omits_adjacent_material_qualification(source, rewritten, qualification):
    context = _context(Project(messages=[Message(role="user", text=source + " " + qualification)]))
    assert not _validate_reply(reply(text=rewritten), context).reply_valid
    complete = _validate_reply(reply(text=rewritten + " " + qualification), context)
    assert complete.reply_valid and not complete.issues


@pytest.mark.parametrize("text", [
    "Don't make a 30-second video.",
    "I don't want a 30-second video.",
    "Don’t create a 30-second video.",
    "I won't make a 30-second video.",
    "We shouldn't create a 30-second video.",
])
def test_negative_duration_contraction_remains_unresolved(tmp_path, text):
    store, _, _, project = setup(tmp_path)
    project = store.update(project.id, project.version, lambda state: (state.briefs.clear(), state.brief_draft.clear()))
    saved, _ = ConversationService(store, lambda: None).begin_message(project.id, project.version, text)
    assert not any(fact.key == "duration" for fact in saved.brief_draft)
    assert any("duration" in note.lower() for note in saved.unresolved)


def test_self_contained_qualified_source_sentence_survives_salvage_unchanged():
    safe = "In our study, Northstar reduced reported sleep problems by 5%."
    context = _context(Project(messages=[Message(role="user", text=safe)]))
    result = _validate_reply(reply(text=safe + " Northstar cures disease."), context)
    assert result.reply_valid
    assert result.parsed.reply == safe
    assert result.issues == [("grounded_product_assertion", "reply[1]")]


def test_exact_qa_first_person_identity_rewrite_retains_fictional_and_every_descriptor():
    context = _context(Project(messages=[Message(role="user", text=QA_OVERVIEW_INPUT)]))
    faithful = "WellPath is a fictional personalized preventive health platform preparing to launch in the US."
    result = _validate_reply(reply(text=faithful), context)
    assert result.reply_valid and not result.issues
    assert not _validate_reply(reply(text=faithful.replace("fictional ", "")), context).reply_valid


def test_safe_scope_with_if_precondition_survives_independent_unsupported_sentence():
    source = ("Northstar is a platform. Our confirmed product scope is helping users track long-term goals. "
              "If the service is available in their region.")
    safe_group = "Northstar helps users track long-term goals. If the service is available in their region."
    context = _context(Project(messages=[Message(role="user", text=source)]))
    result = _validate_reply(reply(text=safe_group + " Northstar cures disease."), context)
    assert result.reply_valid
    assert result.parsed.reply == safe_group
    assert result.issues == [("grounded_product_assertion", "reply[2]")]


@pytest.mark.parametrize("unsafe_first", [False, True])
def test_independent_full_source_sentence_survives_unsafe_sentence_in_either_order(unsafe_first):
    safe = "In our study, Northstar reduced reported sleep problems by 5%."
    unsafe = "Northstar cures disease."
    text = unsafe + " " + safe if unsafe_first else safe + " " + unsafe
    context = _context(Project(messages=[Message(role="user", text=safe)]))
    result = _validate_reply(reply(text=text), context)
    assert result.reply_valid
    assert result.parsed.reply == safe
    assert result.issues == [("grounded_product_assertion", "reply[0]" if unsafe_first else "reply[1]")]
