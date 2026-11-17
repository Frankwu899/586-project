"""Project planning invariants with explicitly injected provider responses."""
from __future__ import annotations

from dataclasses import replace
import io
import json
import zipfile
import xml.etree.ElementTree as ET

import pytest

from backend.app.providers.config import ProviderSettings
from backend.app.project_workspace.exports import export_pack
from backend.app.project_workspace.analysis import AnalysisService
from backend.app.project_workspace.models import (
    Analysis, BriefRevision, EvidenceEvent, EvidenceRevision, Fact, InputManifest, Resource, Selection,
)
from backend.app.project_workspace.planning import PlanningService, load_instructions
from backend.app.project_workspace.store import ProjectStore
from backend.app.workflow_errors import WorkflowError


class Transport:
    def __init__(self, response=None, callback=None):
        self.response = response
        self.callback = callback
        self.calls = []

    def json_response(self, **kwargs):
        self.calls.append(kwargs)
        if self.callback:
            self.callback()
        return self.response


def setup(tmp_path, response=None, reference=False):
    store = ProjectStore(tmp_path)
    project = store.create("Travel mug launch")
    def seed(current):
        current.briefs.append(BriefRevision(revision=1, facts=[
            Fact(id="fact_product", key="product", value="Travel mug", status="confirmed"),
            Fact(id="fact_goal", key="goal", value="Help commuters choose a daily mug", status="confirmed"),
            Fact(id="fact_duration", key="duration", value="8 seconds", status="confirmed"),
            Fact(id="fact_claim", key="claim", value="Fits the user's cup holder", status="confirmed", permitted_for_use=True),
        ]))
        if reference:
            current.resources.append(Resource(id="resource_one", name="Reference.mp4", kind="video", original_path="sources/media/reference.mp4",
                sha256="0" * 64, size_bytes=10, duration_seconds=12, status="ready", evidence=[EvidenceRevision(revision=1, reviewed=True,
                    events=[EvidenceEvent(id="event_one", kind="visual", text="A commuter places a mug into a bag", start_seconds=1, end_seconds=2)])]))
            current.selection = Selection(revision=2, resource_ids=["resource_one"])
    project = store.update(project.id, project.version, seed)
    transport = Transport(response)
    settings = ProviderSettings(api_key="test-key", experiment_budget_enabled=False)
    service = PlanningService(store, lambda: settings, lambda _settings: transport)
    project = service.create_content(project.id, project.version, "The daily routine", "A relatable commute")
    if reference:
        project = AnalysisService(store, lambda: settings).set_selection(project.id, project.version, project.selection.resource_ids, project.contents[0].id)
    return store, service, transport, project


def idea_response(citations=None, claims=None):
    return {"directions": [{"title": "One less thing", "concept": "Follow the morning handoff from desk to train.",
                            "hook": "The train is arriving.", "narrative": "Pack, walk, settle in.", "cta": "See the mug.",
                            "citations": citations or [], "used_claim_ids": claims or []}]}


def pack_response(citations=None):
    return {"production_brief": "Prepare a mug, bag and station location. Timing is estimated.",
            "script": "VOICE: One less thing to think about.",
            "shots": [{"id": "shot_01", "start_seconds": 0, "end_seconds": 3,
                       "visual": "Hands put the mug into a bag.", "dialogue": "Ready?", "on_screen_text": "Morning",
                       "sound": "Bag zipper", "notes": "Confirm access to the location."},
                      {"id": "shot_02", "start_seconds": 3, "end_seconds": 8,
                       "visual": "The commuter leaves the desk.", "dialogue": "Let's go.", "on_screen_text": "",
                       "sound": "Footsteps", "notes": ""}],
            "shot_list": "01 — Hands, mug and bag.\n02 — Commuter exits.",
            "citations": citations or [], "used_claim_ids": []}


def approve(service, project):
    item = project.contents[0]
    direction = item.directions[-1]
    return service.approve_direction(project.id, project.version, item.id, direction.id, direction.revision)


def make_pack(tmp_path, reference=False):
    citations = [{"resource_id": "resource_one", "event_id": "event_one"}] if reference else []
    store, service, transport, project = setup(tmp_path, idea_response(citations), reference)
    project = service.generate_directions(project.id, project.contents[0].id)
    project = approve(service, project)
    transport.response = pack_response(citations)
    project = service.generate_pack(project.id, project.contents[0].id)
    return store, service, transport, project


def test_standalone_manual_direction_works_without_provider_and_keeps_explicit_approval(tmp_path):
    store, service, transport, project = setup(tmp_path)
    item = project.contents[0]
    assert item.series_id is None
    project = service.save_direction(project.id, project.version, item.id,
                                     {"title": "A calm morning", "concept": "Show a commuter getting ready without a rush."})
    assert not project.contents[0].directions[-1].approved
    project = approve(service, project)
    approved_version = project.version
    same = approve(service, project)
    assert same.version == approved_version
    assert not transport.calls
    assert ProjectStore(tmp_path).get(project.id).contents[0].approved_direction_id


def test_module_instructions_are_loaded_at_runtime_and_pinned_in_manifest(tmp_path):
    _, service, transport, project = setup(tmp_path, idea_response())
    generated = service.generate_directions(project.id, project.contents[0].id)
    direction = generated.contents[0].directions[-1]
    assert direction.inputs.model == "gpt-6.1-sol"
    assert direction.inputs.instruction_digest == load_instructions("IDEAS")[1]
    assert direction.inputs.context_digest
    assert direction.inputs.brief_revision == 1
    assert "SOURCE: references/IDEAS.md" in transport.calls[0]["prompt"]
    assert "SOURCE: references/STORYBOARD.md" not in transport.calls[0]["prompt"]
    assert direction.sources == []


def test_reference_citations_get_server_timestamps_and_exact_evidence_revisions(tmp_path):
    _, service, _, project = setup(tmp_path, idea_response([{"resource_id": "resource_one", "event_id": "event_one"}]), True)
    generated = service.generate_directions(project.id, project.contents[0].id)
    direction = generated.contents[0].directions[-1]
    source = direction.sources[0]
    assert source.resource_id == "resource_one" and source.event_id == "event_one"
    assert source.start_seconds == 1 and source.evidence_revision == 1
    assert direction.inputs.evidence_revisions == {"resource_one": 1}
    assert direction.inputs.selection_revision == 2


@pytest.mark.parametrize("response,code", [
    (idea_response([{"resource_id": "resource_one", "event_id": "invented"}]), "invalid_generation_citation"),
    (idea_response(claims=["unconfirmed_claim"]), "unapproved_claim"),
])
def test_invalid_sources_or_unapproved_claims_cannot_be_persisted(tmp_path, response, code):
    store, service, _, project = setup(tmp_path, response, True)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == code
    assert store.get(project.id).contents[0].directions == []


def test_unreviewed_evidence_can_inform_provisional_ideas_but_not_final_approval(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), True)
    project = store.update(project.id, project.version, lambda current: setattr(current.resources[0].evidence[-1], "reviewed", False))
    generated = service.generate_directions(project.id, project.contents[0].id)
    assert transport.calls
    assert any("provisional" in text for text in generated.contents[0].directions[-1].inputs.limitations)
    with pytest.raises(WorkflowError, match="Review the corrected evidence"):
        approve(service, generated)


def test_unrelated_drafts_do_not_discard_generation_but_applied_context_changes_do(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    transport.callback = lambda: store.update(project.id, None, lambda current: setattr(current, "conversation_draft", "Unfinished next thought"))
    project = service.generate_directions(project.id, project.contents[0].id)
    assert project.conversation_draft == "Unfinished next thought"
    transport.callback = lambda: store.update(project.id, None, lambda current: current.briefs.append(BriefRevision(revision=2, facts=current.briefs[-1].facts)))
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "generation_inputs_changed"
    assert len(store.get(project.id).contents[0].directions) == 1


def test_direction_revision_requires_new_approval_and_preserves_old_pack(tmp_path):
    _, service, _, project = make_pack(tmp_path)
    item, old_pack = project.contents[0], project.packs[0]
    original = item.directions[0]
    project = service.save_direction(project.id, project.version, item.id, {"hook": "Watch the morning change."}, original.id, original.revision)
    assert project.contents[0].directions[0].approved
    assert not project.contents[0].directions[-1].approved
    assert project.contents[0].approved_direction_id is None
    assert project.packs[0].id == old_pack.id and project.packs[0].needs_review
    with pytest.raises(WorkflowError) as error:
        service.approve_direction(project.id, project.version, item.id, original.id, original.revision)
    assert error.value.code == "direction_revision_conflict"


def test_explicit_direction_save_rebases_changed_context_without_overwriting_history(tmp_path):
    store, service, _, project = setup(tmp_path, idea_response())
    project = service.generate_directions(project.id, project.contents[0].id)
    old = project.contents[0].directions[0]
    project = store.update(project.id, project.version, lambda current: current.briefs.append(BriefRevision(revision=2, facts=current.briefs[-1].facts)))
    with pytest.raises(WorkflowError):
        approve(service, project)
    project = service.save_direction(project.id, project.version, project.contents[0].id, {"concept": old.concept}, old.id, old.revision)
    assert project.contents[0].directions[-1].revision == 2
    assert project.contents[0].directions[-1].inputs.brief_revision == 2
    assert project.contents[0].directions[0].inputs.brief_revision == 1
    assert approve(service, project).contents[0].directions[-1].approved


def test_production_requires_approval_and_saves_four_documents_and_structured_shots(tmp_path):
    _, service, transport, project = setup(tmp_path, idea_response())
    with pytest.raises(WorkflowError) as error:
        service.generate_pack(project.id, project.contents[0].id)
    assert error.value.code == "direction_approval_required"
    project = service.generate_directions(project.id, project.contents[0].id)
    project = approve(service, project)
    transport.response = pack_response()
    project = service.generate_pack(project.id, project.contents[0].id)
    pack = project.packs[0]
    assert all(getattr(pack, field) for field in ("production_brief", "script", "storyboard", "shot_list"))
    assert pack.shots[0].dialogue == "Ready?"
    assert pack.shots[0].on_screen_text == "Morning"
    assert pack.inputs.direction_id == project.contents[0].approved_direction_id
    assert pack.inputs.instruction_digest == load_instructions("STORYBOARD")[1]


def test_invalid_planned_timing_never_commits_pack(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    project = approve(service, service.generate_directions(project.id, project.contents[0].id))
    response = pack_response()
    response["shots"][1]["start_seconds"] = 5
    transport.response = response
    with pytest.raises(WorkflowError) as error:
        service.generate_pack(project.id, project.contents[0].id)
    assert error.value.code == "invalid_production_timing"
    assert store.get(project.id).packs == []


def test_noop_pack_apply_preserves_revision_approval_and_structured_shots(tmp_path):
    _, service, _, project = make_pack(tmp_path)
    pack = project.packs[0]
    fields = {key: getattr(pack, key) for key in ("production_brief", "script", "storyboard", "shot_list")}
    same = service.save_pack(project.id, project.version, pack.id, pack.revision, fields)
    assert same.version == project.version and len(same.packs) == 1
    assert same.packs[0].shots == pack.shots
    changed = service.save_pack(project.id, project.version, pack.id, pack.revision, {"storyboard": "A revised written storyboard."})
    assert len(changed.packs) == 2 and changed.packs[-1].revision == 2
    assert changed.packs[-1].shots == [] and changed.packs[0].shots == pack.shots


def test_pending_editor_gates_are_specific_and_formal_save_checkpoints_exact_draft(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    project = service.generate_directions(project.id, project.contents[0].id)
    item, direction = project.contents[0], project.contents[0].directions[0]
    scope = f"direction-{item.id}-{direction.id}"
    project = store.update(project.id, project.version, lambda current: current.editor_drafts.update({scope: {"hook": "Changed hook", "base_revision": 1}}))
    with pytest.raises(WorkflowError) as error:
        approve(service, project)
    assert error.value.code == "direction_draft_pending"
    with pytest.raises(WorkflowError) as error:
        service.save_direction(project.id, project.version, item.id, {"hook": "Older request"}, direction.id, 1)
    assert error.value.code == "editor_draft_changed"
    project = service.save_direction(project.id, project.version, item.id, {"hook": "Changed hook"}, direction.id, 1)
    assert project.editor_drafts[scope]["base_revision"] == 2
    project = approve(service, project)
    transport.response = pack_response()
    project = service.generate_pack(project.id, item.id)
    pack = project.packs[-1]
    project = store.update(project.id, project.version, lambda current: current.editor_drafts.update({f"production-{pack.id}": {"script": "Changed script", "base_revision": 1}}))
    with pytest.raises(WorkflowError) as error:
        export_pack(store, project.id, pack.id)
    assert error.value.code == "production_draft_pending"
    with pytest.raises(WorkflowError):
        service.generate_pack(project.id, item.id)
    project = service.save_pack(project.id, project.version, pack.id, 1, {"script": "Changed script"})
    assert project.editor_drafts[f"production-{pack.id}"]["base_revision"] == 2
    assert b"Changed script" in export_pack(store, project.id, pack.id)[0]


def test_export_snapshots_are_safe_editable_and_pin_input_history(tmp_path):
    store, service, _, project = make_pack(tmp_path, True)
    pack = project.packs[0]
    project = service.save_pack(project.id, project.version, pack.id, 1, {"script": "<script>alert('x')</script> & a new line"})
    current = project.packs[-1]
    markdown, _, _ = export_pack(store, project.id, pack.id, 1, "markdown")
    assert b"Historical revision" in markdown and b"evidence revision 1" in markdown
    assert b'"brief_revision": 1' in markdown
    page, _, _ = export_pack(store, project.id, pack.id, 2, "html")
    assert b"<script>" not in page and b"&lt;script&gt;" in page
    document, mime, filename = export_pack(store, project.id, pack.id, 2, "docx")
    assert "wordprocessingml.document" in mime and filename.endswith(".docx")
    with zipfile.ZipFile(io.BytesIO(document)) as archive:
        xml = archive.read("word/document.xml")
        ET.fromstring(xml)
        assert b"&lt;script&gt;" in xml
    assert (store.project_dir(project.id) / "outputs" / current.content_id / current.id / "revision-2.docx").read_bytes() == document
    csv_data, _, _ = export_pack(store, project.id, pack.id, 2, "csv")
    assert b"on-screen text" in csv_data.lower() and b"dialogue" in csv_data.lower()


def test_csv_protects_spreadsheet_formulas(tmp_path):
    store, _, _, project = make_pack(tmp_path)
    def modify(current):
        current.packs[0].shots[0].dialogue = "=HYPERLINK(\"https://example.invalid\")"
    project = store.update(project.id, project.version, modify)
    data, _, _ = export_pack(store, project.id, project.packs[0].id, 1, "csv")
    assert b"'=HYPERLINK" in data


def test_missing_key_and_wrong_model_never_trigger_transport_or_fake_results(tmp_path):
    store, _, transport, project = setup(tmp_path, idea_response())
    settings = ProviderSettings(experiment_budget_enabled=False)
    service = PlanningService(store, lambda: settings, lambda _settings: transport)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "provider_not_configured"
    settings = replace(settings, api_key="test", creative_model="gpt-6-luna")
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "model_baseline_mismatch"
    assert not transport.calls and not store.get(project.id).contents[0].directions


def test_concept_planning_can_return_standalone_topics_without_series(tmp_path):
    response = {"series": [], "standalone": [{"title": "Desk to station", "description": "A morning situation."}], "used_claim_ids": []}
    _, service, transport, project = setup(tmp_path, response)
    project = service.generate_concepts(project.id, None, "One standalone video")
    assert not project.series
    assert project.contents[-1].series_id is None
    assert project.contents[-1].title == "Desk to station"
    assert project.contents[-1].inputs.brief_revision == 1
    assert project.contents[-1].inputs.instruction_digest == load_instructions("IDEAS")[1]
    assert "existing_topics" in transport.calls[0]["prompt"]
    json.dumps(project.model_dump())


def test_qualified_declared_claim_requires_full_approved_wording_in_artifact(tmp_path):
    response = idea_response(claims=["fact_claim"])
    response["directions"][0]["claim_uses"] = [{"fact_id": "fact_claim", "wording": "Fits every cup holder"}]
    store, service, transport, project = setup(tmp_path, response)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "claim_qualification_changed"
    response["directions"][0]["claim_uses"][0]["wording"] = "Fits the user's cup holder"
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "claim_qualification_changed"
    response["directions"][0]["concept"] += " Fits the user's cup holder."
    transport.response = response
    project = service.generate_directions(project.id, project.contents[0].id)
    assert project.contents[0].directions[-1].inputs.claim_ids == ["fact_claim"]
    assert len(store.get(project.id).contents[0].directions) == 1


@pytest.mark.parametrize("key", ["Selling Points", "approved-messages", " PRODUCT CLAIM "])
def test_claim_key_normalization_matches_intake_and_excludes_unpermitted_claims(tmp_path, key):
    store, service, transport, project = setup(tmp_path, idea_response())
    def change(current):
        current.briefs[-1].facts.append(Fact(id="fact_forbidden", key=key, value="Magically self-filling", status="confirmed", permitted_for_use=False))
    project = store.update(project.id, project.version, change)
    service.generate_directions(project.id, project.contents[0].id)
    assert "Magically self-filling" not in transport.calls[-1]["prompt"]


def test_partial_reference_cannot_be_silently_used_as_complete_evidence(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), True)
    def change(current):
        current.resources[0].evidence[-1].coverage["speech"] = "failed"
    project = store.update(project.id, project.version, change)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "reference_incomplete" and not transport.calls


def test_production_duration_is_action_specific_and_checked_against_confirmed_value(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    def remove_duration(current):
        current.briefs[-1].facts = [fact for fact in current.briefs[-1].facts if fact.key != "duration"]
    project = store.update(project.id, project.version, remove_duration)
    project = service.generate_directions(project.id, project.contents[0].id)
    project = approve(service, project)
    calls_before = len(transport.calls)
    with pytest.raises(WorkflowError) as error:
        service.generate_pack(project.id, project.contents[0].id)
    assert error.value.code == "production_duration_required" and len(transport.calls) == calls_before
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    pack = project.packs[-1]
    assert pack.production_brief == pack.script == pack.storyboard == pack.shot_list == ""
    with pytest.raises(WorkflowError) as error:
        export_pack(store, project.id, pack.id)
    assert error.value.code == "production_empty"


def test_generation_rejects_wrong_total_duration(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    def longer(current):
        next(fact for fact in current.briefs[-1].facts if fact.key == "duration").value = "12 seconds"
    project = store.update(project.id, project.version, longer)
    project = approve(service, service.generate_directions(project.id, project.contents[0].id))
    transport.response = pack_response()
    with pytest.raises(WorkflowError) as error:
        service.generate_pack(project.id, project.contents[0].id)
    assert error.value.code == "production_duration_mismatch" and not store.get(project.id).packs


def test_export_includes_explicit_source_time_even_without_locator_and_rejects_symlink(tmp_path):
    store, _, _, project = make_pack(tmp_path, True)
    def remove_locator(current):
        current.packs[0].sources[0].locator = ""
    project = store.update(project.id, project.version, remove_locator)
    pack = project.packs[0]
    data, _, _ = export_pack(store, project.id, pack.id)
    assert b"1s" in data and b"2s" in data
    target = store.project_dir(project.id) / "outputs" / pack.content_id / pack.id
    for file in target.iterdir():
        file.unlink()
    target.rmdir()
    target.symlink_to(store.project_dir(project.id) / "cache", target_is_directory=True)
    with pytest.raises(WorkflowError) as error:
        export_pack(store, project.id, pack.id)
    assert error.value.code == "unsafe_project_path"


def test_direction_apply_rejects_stale_editor_version_even_after_aggregate_rebase(tmp_path):
    store, service, _, project = setup(tmp_path, idea_response())
    project = service.generate_directions(project.id, project.contents[0].id)
    item, direction = project.contents[0], project.contents[0].directions[0]
    scope = f"direction-{item.id}-{direction.id}"
    def save_draft(hook):
        return store.update(project.id, None, lambda current: current.editor_drafts.update({scope: {"hook": hook, "base_revision": 1}}))
    project = save_draft("The saved hook")
    flushed_version = project.editor_draft_versions[scope]
    save_draft("Another tab's hook")
    project = save_draft("The saved hook")
    with pytest.raises(WorkflowError) as error:
        service.save_direction(project.id, project.version, item.id, {"hook": "The saved hook"}, direction.id, 1,
                               expected_editor_version=flushed_version)
    assert error.value.code == "editor_draft_conflict"
    assert len(store.get(project.id).contents[0].directions) == 1
    saved = service.save_direction(project.id, project.version, item.id, {"hook": "The saved hook"}, direction.id, 1,
                                   expected_editor_version=project.editor_draft_versions[scope])
    assert saved.contents[0].directions[-1].revision == 2
    assert saved.editor_draft_versions[scope] > project.editor_draft_versions[scope]


def test_pack_apply_rejects_stale_editor_version_without_losing_current_draft(tmp_path):
    store, service, _, project = make_pack(tmp_path)
    pack = project.packs[-1]
    scope = f"production-{pack.id}"
    def save_draft(script):
        return store.update(project.id, None, lambda current: current.editor_drafts.update({scope: {"script": script, "base_revision": 1}}))
    project = save_draft("The saved script")
    flushed_version = project.editor_draft_versions[scope]
    save_draft("Another tab's script")
    project = save_draft("The saved script")
    with pytest.raises(WorkflowError) as error:
        service.save_pack(project.id, project.version, pack.id, 1, {"script": "The saved script"},
                          expected_editor_version=flushed_version)
    assert error.value.code == "editor_draft_conflict"
    current = store.get(project.id)
    assert len(current.packs) == 1 and current.editor_drafts[scope]["script"] == "The saved script"
    saved = service.save_pack(project.id, project.version, pack.id, 1, {"script": "The saved script"},
                              expected_editor_version=project.editor_draft_versions[scope])
    assert saved.packs[-1].revision == 2


def test_manual_direction_checks_its_own_editor_scope_not_other_drafts(tmp_path):
    store, service, _, project = setup(tmp_path)
    item = project.contents[0]
    scope = f"manual-direction-{item.id}"
    project = store.update(project.id, project.version, lambda current: current.editor_drafts.update({scope: {"title": "A draft", "concept": "A saved idea"}}))
    with pytest.raises(WorkflowError) as error:
        service.save_direction(project.id, project.version, item.id, {"title": "A draft", "concept": "A saved idea"},
                               expected_editor_version=0)
    assert error.value.code == "editor_draft_conflict"
    expected = project.editor_draft_versions[scope]
    project = store.update(project.id, project.version, lambda current: current.editor_drafts.update({"unrelated": {"text": "another draft"}}))
    saved = service.save_direction(project.id, project.version, item.id, {"title": "A draft", "concept": "A saved idea"},
                                   expected_editor_version=expected)
    assert saved.contents[0].directions[-1].concept == "A saved idea"


def test_pending_selected_evidence_blocks_new_creative_actions_without_invalidating_saved_work(tmp_path):
    store, service, transport, project = make_pack(tmp_path, True)
    item, evidence = project.contents[0], project.resources[0].evidence[-1]
    events = [event.model_dump() for event in evidence.events]
    events[0]["text"] = "The commuter does not place the mug in the bag."
    project = store.update(project.id, project.version, lambda current: current.editor_drafts.update({
        "evidence-resource_one": {"events": events, "base_revision": evidence.revision}}))
    calls_before = len(transport.calls)
    for operation in (
        lambda: service.generate_directions(project.id, item.id),
        lambda: approve(service, project),
        lambda: service.generate_pack(project.id, item.id),
    ):
        with pytest.raises(WorkflowError) as error:
            operation()
        assert error.value.code == "reference_draft_pending"
    saved = store.get(project.id)
    assert len(transport.calls) == calls_before
    assert saved.contents[0].directions[0].approved
    assert saved.contents[0].approved_direction_id == item.approved_direction_id
    assert not saved.packs[0].needs_review
    assert export_pack(store, project.id, project.packs[0].id)[0]


def test_stale_base_evidence_draft_blocks_even_when_event_text_matches(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), True)
    evidence = project.resources[0].evidence[-1]
    def change(current):
        current.resources[0].evidence.append(evidence.model_copy(update={"revision": 2}, deep=True))
        current.editor_drafts["evidence-resource_one"] = {"events": [event.model_dump() for event in evidence.events], "base_revision": 1}
    project = store.update(project.id, project.version, change)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "reference_draft_pending" and not transport.calls


def test_evidence_drafts_are_selection_scoped_and_rechecked_after_provider_call(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), True)
    evidence = project.resources[0].evidence[-1]
    clean = {"events": [event.model_dump() for event in evidence.events], "base_revision": evidence.revision}
    project = store.update(project.id, project.version, lambda current: current.editor_drafts.update({
        "evidence-resource_one": clean, "evidence-unselected": {"events": [], "base_revision": -1}}))
    project = service.generate_directions(project.id, project.contents[0].id)
    def edit_during_call():
        def edit(current):
            current.editor_drafts["evidence-resource_one"]["events"][0]["text"] = "A different observation"
        store.update(project.id, None, edit)
    transport.callback = edit_during_call
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "reference_draft_pending"
    assert len(store.get(project.id).contents[0].directions) == 1


def test_series_context_is_in_prompt_and_changes_invalidate_only_member_outputs(tmp_path):
    store, service, transport, project = make_pack(tmp_path)
    standalone_id = project.contents[0].id
    project = service.create_series(project.id, project.version, "Commuter proof", "Real commuter demonstration")
    series_id = project.series[-1].id
    project = service.create_content(project.id, project.version, "Bag test", "A physical demonstration", series_id)
    member_id = project.contents[-1].id
    transport.response = idea_response()
    project = service.generate_directions(project.id, member_id)
    member = project.contents[-1]
    direction = member.directions[-1]
    old_digest = direction.inputs.context_digest
    assert '"series": {"id": "' + series_id in transport.calls[-1]["prompt"]
    assert "Real commuter demonstration" in transport.calls[-1]["prompt"]
    project = service.approve_direction(project.id, project.version, member_id, direction.id, direction.revision)
    transport.response = pack_response()
    project = service.generate_pack(project.id, member_id)
    def add_source_analysis(current):
        current.contents[-1].inputs = direction.inputs.model_copy(deep=True)
        current.analyses.append(Analysis(content_id=member_id, inputs=InputManifest(), conclusion="Source analysis without series context"))
    project = store.update(project.id, project.version, add_source_analysis)
    same = service.edit_series(project.id, project.version, series_id, {"concept": "Real commuter demonstration"})
    assert same.version == project.version
    project = service.edit_series(project.id, project.version, series_id, {"concept": "Surreal animated comedy"})
    member = next(item for item in project.contents if item.id == member_id)
    standalone = next(item for item in project.contents if item.id == standalone_id)
    assert member.approved_direction_id is None and member.needs_review
    assert member.directions[-1].needs_review
    assert standalone.approved_direction_id and standalone.directions[-1].approved
    assert next(pack for pack in project.packs if pack.content_id == member_id).needs_review
    assert not next(pack for pack in project.packs if pack.content_id == standalone_id).needs_review
    assert not project.analyses[-1].needs_review
    transport.response = idea_response()
    project = service.generate_directions(project.id, member_id)
    assert next(item for item in project.contents if item.id == member_id).directions[-1].inputs.context_digest != old_digest
    assert "Surreal animated comedy" in transport.calls[-1]["prompt"]


def test_moving_content_between_series_and_deleting_series_change_creative_inputs(tmp_path):
    _, service, transport, project = make_pack(tmp_path)
    item_id = project.contents[0].id
    project = service.create_series(project.id, project.version, "New series", "An observational story")
    series_id = project.series[-1].id
    project = service.edit_content(project.id, project.version, item_id, {"series_id": series_id})
    assert project.contents[0].approved_direction_id is None and project.packs[0].needs_review
    transport.response = idea_response()
    project = service.generate_directions(project.id, item_id)
    project = approve(service, project)
    assert project.contents[0].approved_direction_id
    project = service.delete_series(project.id, project.version, series_id)
    assert project.contents[0].series_id is None
    assert project.contents[0].approved_direction_id is None
    assert project.contents[0].directions[-1].needs_review


def test_series_changes_during_generation_discard_result_but_unrelated_series_edits_do_not(tmp_path):
    _, service, transport, project = setup(tmp_path, idea_response())
    project = service.create_series(project.id, project.version, "Selected series", "Real observations")
    selected_id = project.series[-1].id
    project = service.edit_content(project.id, project.version, project.contents[0].id, {"series_id": selected_id})
    project = service.create_series(project.id, project.version, "Other series", "Unrelated")
    unrelated_id = project.series[-1].id
    def unrelated():
        current = service.store.get(project.id)
        service.edit_series(current.id, current.version, unrelated_id, {"concept": "Unrelated updated concept"})
    transport.callback = unrelated
    project = service.generate_directions(project.id, project.contents[0].id)
    assert len(project.contents[0].directions) == 1
    def selected():
        current = service.store.get(project.id)
        service.edit_series(current.id, current.version, selected_id, {"concept": "A new creative premise"})
    transport.callback = selected
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id)
    assert error.value.code == "generation_inputs_changed"
    assert len(service.store.get(project.id).contents[0].directions) == 1


def test_concepts_generate_from_confirmed_context_with_empty_instruction(tmp_path):
    response = {"series": [], "standalone": [{"title": "A calm departure", "description": "Show the morning routine."}],
                "used_claim_ids": []}
    store, service, transport, project = setup(tmp_path, response)
    preflight = service.preflight_generation(project.id)
    assert preflight == {"exploratory": False, "visual_only": False, "limitations": []}
    result = service.generate_concepts(project.id, project.version)
    assert result.contents[-1].title == "A calm departure"
    assert not result.contents[-1].inputs.exploratory
    assert json.loads(transport.calls[-1]["prompt"].split("INPUT_JSON:\n")[1])["instruction"] == ""


def test_reference_only_ideas_remain_exploratory_and_cannot_approve_for_production(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), True)
    project = store.update(project.id, project.version, lambda current: current.briefs.clear())
    assert service.preflight_generation(project.id, project.contents[0].id)["exploratory"]
    result = service.generate_directions(project.id, project.contents[0].id)
    direction = result.contents[0].directions[-1]
    assert direction.inputs.exploratory and direction.inputs.brief_revision is None
    assert any("context is not confirmed" in text for text in direction.inputs.limitations)
    context = json.loads(transport.calls[-1]["prompt"].split("INPUT_JSON:\n")[1])
    assert context["confirmed_facts"] == []
    assert context["reference_evidence"][0]["resource_id"] == "resource_one"
    with pytest.raises(WorkflowError) as error:
        approve(service, result)
    assert error.value.code == "confirmed_context_required"
    assert store.get(project.id).packs == []


def test_empty_start_asks_question_before_provider_or_persisted_job(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response())
    project = store.update(project.id, project.version, lambda current: current.briefs.clear())
    for operation in (lambda: service.preflight_generation(project.id),
                      lambda: service.generate_concepts(project.id, None),
                      lambda: service.generate_directions(project.id, project.contents[0].id)):
        with pytest.raises(WorkflowError) as error:
            operation()
        assert error.value.code == "generation_starting_question"
        assert "What would you like to create?" in error.value.message
    assert not transport.calls and store.get(project.id) == project


def test_visual_only_is_explicit_filters_speech_and_carries_limitations_into_pack(tmp_path):
    citations = [{"resource_id": "resource_one", "event_id": "event_one"}]
    store, service, transport, project = setup(tmp_path, idea_response(citations), True)
    def partial(current):
        resource = current.resources[0]
        resource.status = "partial"
        evidence = resource.evidence[-1]
        evidence.coverage = {"speech": "failed", "visual": "observations", "music": "not_analyzed"}
        evidence.events.append(EvidenceEvent(id="speech_one", kind="speech", text="Incomplete recognized speech", start_seconds=3, end_seconds=4))
    project = store.update(project.id, project.version, partial)
    with pytest.raises(WorkflowError, match="Continue with visual evidence only"):
        service.preflight_generation(project.id, project.contents[0].id)
    result = service.generate_directions(project.id, project.contents[0].id, visual_only=True)
    context = json.loads(transport.calls[-1]["prompt"].split("INPUT_JSON:\n")[1])
    assert [event["id"] for event in context["reference_evidence"][0]["evidence"]["events"]] == ["event_one"]
    direction = result.contents[0].directions[-1]
    assert direction.inputs.visual_only and direction.inputs.limitations
    result = approve(service, result)
    transport.response = pack_response(citations)
    result = service.generate_pack(project.id, result.contents[0].id)
    assert result.packs[-1].inputs.visual_only
    assert any("visual evidence only" in text for text in result.packs[-1].inputs.limitations)
    for format in ("markdown", "html"):
        data, _, _ = export_pack(store, result.id, result.packs[-1].id, 1, format)
        assert b"visual evidence only" in data
    sheet, _, _ = export_pack(store, result.id, result.packs[-1].id, 1, "csv")
    assert "Shot,Start,End,Framing / Camera" in sheet.decode("utf-8-sig")
    assert b"Input manifest" not in sheet and b"Supporting reference" not in sheet
    assert store.get(project.id).resources[0].evidence[-1].events[-1].text == "Incomplete recognized speech"


def test_visual_only_cannot_cite_speech_or_cover_missing_visuals(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response([{"resource_id": "resource_one", "event_id": "speech_one"}]), True)
    def partial(current):
        current.resources[0].evidence[-1].coverage["speech"] = "failed"
        current.resources[0].evidence[-1].events.append(EvidenceEvent(id="speech_one", kind="speech", text="Old partial speech", start_seconds=3, end_seconds=4))
    project = store.update(project.id, project.version, partial)
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id, visual_only=True)
    assert error.value.code == "invalid_generation_citation"
    assert store.get(project.id).contents[0].directions == []
    project = store.update(project.id, project.version, lambda current: setattr(current.resources[0].evidence[-1], "events", []))
    with pytest.raises(WorkflowError):
        service.preflight_generation(project.id, visual_only=True)


def test_changed_evidence_during_visual_only_generation_keeps_prior_work(tmp_path):
    store, service, transport, project = setup(tmp_path, idea_response(), True)
    project = store.update(project.id, project.version, lambda current: current.resources[0].evidence[-1].coverage.update(speech="failed"))
    def changed():
        store.update(project.id, None, lambda current: current.resources[0].evidence.append(
            EvidenceRevision(revision=2, reviewed=True, events=current.resources[0].evidence[0].events, coverage={"speech": "failed"})))
    transport.callback = changed
    with pytest.raises(WorkflowError) as error:
        service.generate_directions(project.id, project.contents[0].id, visual_only=True)
    assert error.value.code == "generation_inputs_changed"
    assert store.get(project.id).contents[0].directions == []
