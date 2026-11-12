"""Offline contracts for conversational intake; these do not establish model quality."""
from copy import deepcopy
from dataclasses import replace

import pytest

from backend.app.project_workspace.conversation import ConversationService, REQUESTS_KEY
from backend.app.project_workspace.models import (
    BriefRevision, ContentItem, Direction, ExtractedBlock, Fact, InputManifest,
    ProductionPack, Resource, SourceRef,
)
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.base import ProviderError
from backend.app.providers.config import ProviderSettings
from backend.app.workflow_errors import WorkflowError


class FixtureTransport:
    def __init__(self, response, *, before=None, error=None, research=None):
        self.response = response
        self.before = before
        self.error = error
        self.research = research
        self.calls = []

    def json_response(self, **kwargs):
        self.calls.append(kwargs)
        if self.before:
            self.before()
            self.before = None
        if self.error:
            raise self.error
        return deepcopy(self.response)

    def web_search(self, *args, **kwargs):
        self.calls.append({"research": args, **kwargs})
        if self.research is None:
            raise ProviderError("research_unavailable", "Research unavailable")
        return deepcopy(self.research)


def reply(*proposals, text="I have the audience. What should this piece help them decide?", **extra):
    return {"reply": text, "proposals": list(proposals), "unresolved": [], "research_query": None, **extra}


def proposal(key="audience", value="City commuters", source_index=0, excerpt="Audience: City commuters"):
    return {"key": key, "value": value, "kind": "extracted", "source_index": source_index, "excerpt": excerpt}


@pytest.fixture
def setup(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Travel mug launch")
    settings = ProviderSettings(api_key="test-only-key", research_model="gpt-6.1-sol", experiment_budget_enabled=False)
    transport = FixtureTransport(reply(proposal()))
    service = ConversationService(store, lambda: settings, lambda _: transport)
    return store, project, settings, transport, service


def test_extracts_grounded_suggestions_without_confirming_or_invalidating(setup):
    store, project, _, transport, service = setup
    result = service.send(project.id, project.version, "Audience: City commuters")
    assert [message.role for message in result.messages] == ["user", "assistant"]
    fact = result.brief_draft[0]
    assert fact.value == "City commuters" and fact.status == "suggested"
    assert fact.sources[0].message_id == result.messages[0].id
    assert not fact.permitted_for_use and result.briefs == []
    assert transport.calls[0]["model"] == "gpt-6.1-sol"
    assert "required-field questionnaire" in transport.calls[0]["prompt"]
    assert "untrusted" in transport.calls[0]["prompt"]
    assert store.get(project.id).brief_draft == result.brief_draft


def test_begin_message_saves_before_provider_and_duplicate_response_never_bills_twice(setup):
    store, project, _, transport, service = setup
    admitted, message_id = service.begin_message(project.id, project.version, "Audience: City commuters")
    assert admitted.messages[0].id == message_id and not transport.calls
    service.respond(project.id, message_id)
    completed = store.get(project.id)
    again = service.respond(project.id, message_id)
    assert again.version == completed.version
    assert len(transport.calls) == 1


@pytest.mark.parametrize("failure", [ProviderError("provider_timeout", "Provider timed out", True), RuntimeError("secret-looking-untrusted-error")])
def test_failure_retains_message_and_draft_without_exposing_raw_exception(setup, failure):
    store, project, _, transport, service = setup
    transport.error = failure
    with pytest.raises(WorkflowError):
        service.send(project.id, project.version, "Audience: City commuters")
    saved = store.get(project.id)
    assert saved.messages[0].text == "Audience: City commuters"
    assert saved.messages[-1].status == "failed"
    assert "secret-looking" not in saved.messages[-1].text
    assert not saved.editor_drafts[REQUESTS_KEY]
    assert saved.brief_draft == []


def test_unconfigured_service_keeps_conversation_and_manual_brief_available(setup):
    store, project, settings, transport, _ = setup
    service = ConversationService(store, lambda: replace(settings, api_key=""), lambda _: transport)
    with pytest.raises(WorkflowError, match="message is saved"):
        service.send(project.id, project.version, "Plan a product launch")
    saved = store.get(project.id)
    result = service.apply_brief(project.id, saved.version, [Fact(key="objective", value="Product launch", status="confirmed", origin="manual")])
    assert len(result.briefs) == 1
    assert not transport.calls


def test_dynamic_settings_are_read_for_each_response_and_no_silent_model_substitution(setup):
    store, project, settings, transport, _ = setup
    current = [settings]
    service = ConversationService(store, lambda: current[0], lambda _: transport)
    admitted, message_id = service.begin_message(project.id, project.version, "Audience: City commuters")
    current[0] = replace(settings, m2_model="gpt-6-luna")
    with pytest.raises(WorkflowError) as failure:
        service.respond(project.id, message_id)
    assert failure.value.code == "conversation_model_mismatch"
    assert not transport.calls
    assert store.get(admitted.id).messages[-1].status == "failed"


@pytest.mark.parametrize("bad", [
    proposal(source_index=999),
    proposal(excerpt="invented source"),
    proposal(key="claim", value="Keeps drinks warm", excerpt="Keeps drinks warm"),
    {"key": "claim", "value": "Leakproof", "kind": "suggestion", "source_index": None, "excerpt": None},
])
def test_rejects_ungrounded_and_strengthened_product_claims(setup, bad):
    store, project, _, transport, service = setup
    transport.response = reply(bad)
    with pytest.raises(WorkflowError) as failure:
        service.send(project.id, project.version, "Does not keep drinks warm all day\nKeeps drinks warm for up to six hours in our indoor test")
    assert failure.value.code == "invalid_conversation_response"
    saved = store.get(project.id)
    assert not saved.brief_draft and saved.messages[0].role == "user"


def test_document_excerpt_is_grounded_at_its_location_and_never_grants_claim_permission(setup):
    store, project, _, transport, service = setup
    statement = "Keeps drinks warm for up to six hours in our indoor test."
    resource = Resource(name="Facts.txt", kind="document", role="document", original_path="sources/documents/facts.txt",
                        sha256="a" * 64, size_bytes=50, blocks=[ExtractedBlock(locator="Line 1", text=statement)])
    project = store.update(project.id, project.version, lambda state: state.resources.append(resource))
    transport.response = reply(proposal(key="claim", value=statement, excerpt=statement, source_index=1))
    result = service.send(project.id, project.version, "Use the product facts.", [resource.id])
    fact = result.brief_draft[0]
    assert fact.origin == "document" and fact.sources[0].resource_id == resource.id
    assert fact.sources[0].locator == "Line 1" and not fact.permitted_for_use
    fact.status = "confirmed"
    with pytest.raises(WorkflowError) as failure:
        service.apply_brief(project.id, result.version, [fact])
    assert failure.value.code == "claim_permission_required"
    fact.permitted_for_use = True
    adopted = service.apply_brief(project.id, result.version, [fact])
    assert adopted.briefs[-1].facts[0].permitted_for_use


def test_stale_adopted_context_rejects_reply_but_unrelated_job_versions_do_not(setup):
    store, project, _, transport, service = setup
    transport.before = lambda: store.update(project.id, None, lambda state: setattr(state, "workspace", "resources"))
    result = service.send(project.id, project.version, "Audience: City commuters")
    assert result.brief_draft
    transport.before = lambda: store.update(project.id, None, lambda state: state.brief_draft.append(Fact(key="objective", value="Newer manual context", origin="manual")))
    with pytest.raises(WorkflowError) as failure:
        service.send(project.id, result.version, "Audience: City commuters")
    assert failure.value.code == "conversation_context_changed"
    saved = store.get(project.id)
    assert saved.brief_draft[-1].value == "Newer manual context"
    assert saved.messages[-1].status == "failed"


def test_later_message_supersedes_pending_earlier_reply(setup):
    store, project, _, _, service = setup
    admitted, first_id = service.begin_message(project.id, project.version, "Audience: City commuters")
    service.begin_message(project.id, admitted.version, "Actually, focus on weekend hikers.")
    with pytest.raises(WorkflowError) as failure:
        service.respond(project.id, first_id)
    assert failure.value.code == "conversation_context_changed"
    assert not store.get(project.id).brief_draft


def test_repeated_claim_proposal_does_not_replace_confirmed_fact(setup):
    store, project, _, transport, service = setup
    original = Fact(key="audience", value="City commuters", status="confirmed", origin="manual")
    project = service.apply_brief(project.id, project.version, [original])
    transport.response = reply(proposal(value="Weekend hikers", excerpt="Audience: Weekend hikers"))
    proposed = service.send(project.id, project.version, "Audience: Weekend hikers")
    assert proposed.briefs[-1].facts[0].value == "City commuters"
    assert [fact.status for fact in proposed.brief_draft] == ["suggested"]
    assert proposed.brief_draft[0].id == original.id
    assert proposed.brief_draft[0].value == "Weekend hikers"
    assert any("confirmed value remains unchanged" in note for note in proposed.unresolved)


def test_draft_edit_keeps_approval_but_meaningful_apply_invalidates_and_noop_preserves(setup):
    store, project, _, _, service = setup
    initial = Fact(key="audience", value="City commuters", status="confirmed", origin="manual")
    project = service.apply_brief(project.id, project.version, [initial])
    direction = Direction(title="Morning commute", concept="Show a commute", approved=True, inputs=InputManifest(brief_revision=1))
    item = ContentItem(title="Episode 1", directions=[direction], approved_direction_id=direction.id, approved_direction_revision=1)
    pack = ProductionPack(content_id=item.id, inputs=InputManifest(brief_revision=1), production_brief="Brief", script="Script", storyboard="Storyboard", shot_list="Shots")
    def add_outputs(state):
        state.contents.append(item)
        state.packs.append(pack)
    project = store.update(project.id, project.version, add_outputs)
    unchanged = service.apply_brief(project.id, project.version, project.brief_draft)
    assert unchanged.version == project.version and len(unchanged.briefs) == 1
    edited = project.brief_draft[0].model_copy(update={"value": "Weekend hikers"})
    draft = service.save_brief_draft(project.id, project.version, [edited])
    assert draft.brief_draft[0].status == "suggested"
    assert draft.contents[0].directions[0].approved and not draft.packs[0].needs_review
    draft.brief_draft[0].status = "confirmed"
    adopted = service.apply_brief(project.id, draft.version, draft.brief_draft)
    assert len(adopted.briefs) == 2 and adopted.briefs[0].facts[0].value == "City commuters"
    assert not adopted.contents[0].directions[0].approved and adopted.packs[0].needs_review


def test_omission_cannot_silently_remove_an_adopted_fact(setup):
    _, project, _, _, service = setup
    project = service.apply_brief(project.id, project.version, [Fact(key="objective", value="Awareness", status="confirmed", origin="manual")])
    with pytest.raises(WorkflowError) as failure:
        service.apply_brief(project.id, project.version, [])
    assert failure.value.code == "brief_fact_omitted"
    rejected = project.brief_draft[0].model_copy(update={"status": "rejected"})
    removed = service.apply_brief(project.id, project.version, [rejected])
    assert removed.briefs[-1].facts == []


def test_apply_unrelated_fact_retains_previous_value_of_unconfirmed_correction(setup):
    _, project, _, _, service = setup
    project = service.apply_brief(project.id, project.version, [Fact(key="audience", value="City commuters", status="confirmed", origin="manual")])
    edited = project.brief_draft[0].model_copy(update={"value": "Weekend hikers", "status": "suggested"})
    objective = Fact(key="objective", value="Consideration", status="confirmed", origin="manual")
    applied = service.apply_brief(project.id, project.version, [edited, objective])
    assert {fact.key: fact.value for fact in applied.briefs[-1].facts} == {"audience": "City commuters", "objective": "Consideration"}
    assert applied.brief_draft[0].value == "Weekend hikers" and applied.brief_draft[0].status == "suggested"


def test_chat_claim_correction_preserves_adopted_claim_until_explicit_permission(setup):
    _, project, _, transport, service = setup
    old = Fact(key="claim", value="Up to six hours in our indoor test", status="confirmed", permitted_for_use=True, origin="manual")
    project = service.apply_brief(project.id, project.version, [old])
    wording = "Up to four hours in our indoor test"
    transport.response = reply({**proposal(key="claim", value=wording, excerpt=wording), "replaces_fact_id": old.id})
    proposed = service.send(project.id, project.version, wording)
    assert len(proposed.brief_draft) == 1 and proposed.brief_draft[0].id == old.id
    assert not proposed.brief_draft[0].permitted_for_use
    pending = service.apply_brief(project.id, proposed.version, proposed.brief_draft)
    assert len(pending.briefs) == 1 and pending.briefs[-1].facts[0].value == old.value
    proposed.brief_draft[0].status = "confirmed"
    with pytest.raises(WorkflowError) as failure:
        service.apply_brief(project.id, pending.version, proposed.brief_draft)
    assert failure.value.code == "claim_permission_required"


def test_chat_can_revert_an_unadopted_correction_to_the_confirmed_value(setup):
    _, project, _, transport, service = setup
    old = Fact(key="audience", value="City commuters", status="confirmed", origin="manual")
    project = service.apply_brief(project.id, project.version, [old])
    pending = service.save_brief_draft(project.id, project.version, [old.model_copy(update={"value": "Weekend hikers"})])
    transport.response = reply(proposal())
    reverted = service.send(project.id, pending.version, "Audience: City commuters")
    assert len(reverted.brief_draft) == 1
    assert reverted.brief_draft[0].id == old.id and reverted.brief_draft[0].value == old.value


def test_adopted_document_quote_survives_further_extraction_corrections(setup):
    store, project, _, transport, service = setup
    resource = Resource(name="Audience.txt", kind="document", role="document", original_path="sources/documents/audience.txt",
                        sha256="a" * 64, size_bytes=50, extraction_revision=2,
                        blocks=[ExtractedBlock(id="block_audience", locator="Line 1", text="Audience: City commuters", original_text="Audience: City communities")])
    project = store.update(project.id, project.version, lambda state: state.resources.append(resource))
    transport.response = reply(proposal(source_index=1))
    proposed = service.send(project.id, project.version, "Use the audience document.")
    assert proposed.brief_draft[0].sources[0].extraction_revision == 2
    proposed.brief_draft[0].status = "confirmed"
    adopted = service.apply_brief(project.id, proposed.version, proposed.brief_draft)
    def correct_again(state):
        source = state.resources[0]
        source.extraction_history.append({"revision": source.extraction_revision, "blocks": [block.model_dump() for block in source.blocks]})
        source.extraction_revision = 3
        source.blocks[0].text = "Audience: Weekend hikers"
    corrected = store.update(project.id, adopted.version, correct_again)
    result = service.apply_brief(project.id, corrected.version, corrected.brief_draft)
    assert len(result.briefs) == 1 and result.briefs[-1].facts[0].value == "City commuters"


def test_delayed_apply_cannot_drop_new_provider_proposal_after_version_rebase(setup):
    store, project, _, _, service = setup
    initial = Fact(key="objective", value="Consideration", status="confirmed", origin="manual")
    draft = service.save_brief_draft(project.id, project.version, [initial])
    expected_draft_version = draft.brief_draft_version
    proposed = service.send(project.id, draft.version, "Audience: City commuters")
    with pytest.raises(WorkflowError) as failure:
        # Simulate a client queue using the newest project version while its
        # complete facts payload was captured before assistance completed.
        service.apply_brief(project.id, proposed.version, draft.brief_draft,
                            expected_draft_version=expected_draft_version)
    assert failure.value.code == "brief_draft_conflict"
    saved = store.get(project.id)
    assert len(saved.brief_draft) == 2 and not saved.briefs


def test_delayed_draft_save_cannot_overwrite_newer_edit_but_navigation_does_not_conflict(setup):
    store, project, _, _, service = setup
    draft = service.save_brief_draft(project.id, project.version, [Fact(key="audience", value="City commuters", origin="manual")])
    changed = service.save_brief_draft(project.id, draft.version,
        [draft.brief_draft[0].model_copy(update={"value": "Weekend hikers"})], expected_draft_version=draft.brief_draft_version)
    with pytest.raises(WorkflowError) as failure:
        service.save_brief_draft(project.id, changed.version, draft.brief_draft,
                                 expected_draft_version=draft.brief_draft_version)
    assert failure.value.code == "brief_draft_conflict"
    navigated = store.update(project.id, changed.version, lambda state: setattr(state, "workspace", "resources"))
    assert navigated.brief_draft_version == changed.brief_draft_version
    facts = [changed.brief_draft[0].model_copy(update={"status": "confirmed"})]
    applied = service.apply_brief(project.id, navigated.version, facts,
                                  expected_draft_version=changed.brief_draft_version)
    assert applied.briefs[-1].facts[0].value == "Weekend hikers"


def test_invalid_source_membership_and_urls_are_rejected(setup):
    _, project, _, _, service = setup
    for source in [SourceRef(resource_id="resource_wrong", excerpt="text"), SourceRef(url="https://user:password@example.com")]:
        with pytest.raises(WorkflowError) as failure:
            service.apply_brief(project.id, project.version, [Fact(key="context", value="Something", origin="manual", status="confirmed", sources=[source])])
        assert failure.value.code == "invalid_brief_source"


def test_research_failure_keeps_grounded_initial_reply_without_claiming_completion(setup):
    _, project, _, transport, service = setup
    transport.response = reply(proposal(), research_query="Official public Acme product information")
    result = service.send(project.id, project.version, "Audience: City commuters")
    assert result.brief_draft[0].value == "City commuters"
    assert "lookup did not complete" in result.messages[-1].text
    assert len(transport.calls) == 2


def test_generated_urls_must_be_returned_research_sources(setup):
    store, project, _, transport, service = setup
    transport.response = reply(text="Verified at https://invented.example/product")
    with pytest.raises(WorkflowError) as failure:
        service.send(project.id, project.version, "Help with the brief")
    assert failure.value.code == "invalid_conversation_response"
    assert not store.get(project.id).brief_draft


def test_successful_research_remains_attributed_and_unconfirmed_until_adoption(setup):
    _, project, settings, _, service = setup
    statement = "Uses a removable lid."
    class ResearchTransport(FixtureTransport):
        def json_response(self, **kwargs):
            self.calls.append(kwargs)
            if len([call for call in self.calls if "schema" in call]) == 1:
                return reply(research_query="Official public Acme mug lid")
            return reply(proposal(key="claim", value=statement, excerpt=statement, source_index=1),
                         text="The retrieved source describes a removable lid. Confirm whether this wording is approved for your product.")
    transport = ResearchTransport(None, research={"text": statement, "sources": [{"url": "https://example.com/mug"}], "citations": []})
    service.transport_factory = lambda _: transport
    result = service.send(project.id, project.version, "Help with the Acme mug.")
    fact = result.brief_draft[0]
    assert fact.origin == "research" and fact.status == "suggested"
    assert fact.sources[0].url == "https://example.com/mug" and not fact.permitted_for_use
    assert "not independently verified" in result.messages[-1].text
    assert transport.calls[1]["research"][0] == settings.research_model
    assert transport.calls[1]["max_tool_calls"] == 1
    fact.status, fact.permitted_for_use = "confirmed", True
    adopted = service.apply_brief(project.id, result.version, [fact])
    assert adopted.briefs[-1].facts[0].origin == "research"


def test_extracted_claim_can_drop_only_a_simple_label_not_qualifications(setup):
    _, project, _, transport, service = setup
    statement = "Keeps drinks warm for up to six hours in our indoor test."
    transport.response = reply(proposal(key="claim", value=statement, excerpt=f"Claim: {statement}"))
    result = service.send(project.id, project.version, f"Claim: {statement}")
    assert result.brief_draft[0].value == statement
    assert result.brief_draft[0].sources[0].excerpt == f"Claim: {statement}"


def test_no_fixed_required_fields_or_mandatory_claim_for_confirmed_context(setup):
    _, project, _, _, service = setup
    result = service.apply_brief(project.id, project.version, [Fact(key="objective", value="Tell our founding story", status="confirmed", origin="manual")])
    assert result.briefs == [BriefRevision(revision=1, facts=result.briefs[0].facts, created_at=result.briefs[0].created_at)]
