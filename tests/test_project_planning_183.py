"""Saved planning/sheet contracts with injected provider outputs, never live AI."""
from copy import deepcopy
import csv
import io

import pytest

from backend.app.project_workspace.exports import export_pack
from backend.app.project_workspace.analysis import AnalysisService
from backend.app.project_workspace.models import (
    BriefRevision, EvidenceEvent, EvidenceRevision, Fact, ProductionShot, Resource, SourceRef,
)
from backend.app.project_workspace.planning import PlanningService
from backend.app.project_workspace.store import ProjectStore
from backend.app.providers.config import ProviderSettings
from backend.app.workflow_errors import WorkflowError


class Transport:
    def __init__(self):
        self.response = {"series": [], "standalone": [{"title": "Bag test", "description": "Show a commuter packing a bag."}]}
        self.calls = []
        self.callback = None

    def json_response(self, **kwargs):
        self.calls.append(kwargs)
        if self.callback:
            self.callback()
        return deepcopy(self.response)


@pytest.fixture
def workspace(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Synthetic sheet project")
    def seed(state):
        state.briefs = [BriefRevision(revision=1, facts=[
            Fact(key="objective", value="Introduce the product", status="confirmed"),
            Fact(key="duration", value="8 seconds", status="confirmed"),
        ])]
    project = store.update(project.id, project.version, seed)
    transport = Transport()
    service = PlanningService(store, lambda: ProviderSettings(api_key="offline-test-only", experiment_budget_enabled=False), lambda _: transport)
    return store, service, transport, project


def approved_video(service, project, *, reference=False):
    project = service.create_content(project.id, project.version, "One planned video")
    video = project.contents[-1]
    if reference:
        project = AnalysisService(service.store, service.settings_provider).set_selection(project.id, project.version, project.selection.resource_ids, video.id)
    project = service.save_direction(project.id, project.version, video.id, {"title": "Bag first", "concept": "Show an everyday packing moment."})
    direction = project.contents[-1].directions[-1]
    return service.approve_direction(project.id, project.version, video.id, direction.id, direction.revision)


def rows():
    return [{"id": "shot_stable_a", "start_seconds": 0, "end_seconds": 3,
             "framing_camera": "Static close-up", "visual": "Place a mug beside a bag.",
             "dialogue": "Ready?", "on_screen_text": "Morning", "sound": "Room tone", "notes": "Use natural light."},
            {"id": "shot_stable_b", "start_seconds": 3, "end_seconds": 8,
             "framing_camera": "Wide", "visual": "Pick up the bag.", "dialogue": "Let's go.",
             "on_screen_text": "", "sound": "Footsteps", "notes": ""}]


def test_topic_preview_add_is_explicit_idempotent_and_does_not_create_series(workspace):
    store, service, transport, project = workspace
    transport.response["series"] = [{"title": "Unrequested series", "concept": "Do not create this group.",
                                     "topics": [{"title": "Desk test", "description": "A second topic."}]}]
    preview = service.suggest_topics(project.id)
    assert not preview.contents and not preview.series
    assert [item.title for item in preview.topic_suggestions] == ["Bag test", "Desk test"]
    saved = service.add_topic(project.id, preview.version, preview.topic_suggestions[0].id)
    video = saved.contents[0]
    assert video.title == "Bag test" and video.series_id is None
    assert saved.active_content_id == video.id
    assert saved.topic_suggestions[0].added_content_id == video.id
    assert service.add_topic(project.id, saved.version, saved.topic_suggestions[0].id) == saved
    assert ProjectStore(store.root).get(project.id).contents[0].id == video.id


def test_explicit_series_topic_preview_targets_only_selected_existing_series(workspace):
    _, service, _, project = workspace
    project = service.create_series(project.id, project.version, "Commute tests", "A repeatable commute experiment")
    series_id = project.series[0].id
    preview = service.suggest_topics(project.id, series_id=series_id)
    assert len(preview.series) == 1 and not preview.contents
    added = service.add_topic(project.id, preview.version, preview.topic_suggestions[0].id)
    assert added.contents[0].series_id == series_id


def test_stale_topic_generation_and_stale_add_preserve_saved_plan(workspace):
    store, service, transport, project = workspace
    def change_brief():
        store.update(project.id, None, lambda current: current.briefs.append(BriefRevision(revision=2, facts=[])))
    transport.callback = change_brief
    with pytest.raises(WorkflowError):
        service.suggest_topics(project.id)
    assert not store.get(project.id).topic_suggestions and not store.get(project.id).contents
    transport.callback = None
    preview = service.suggest_topics(project.id, "Show a commuter packing a bag.")
    changed = store.update(project.id, preview.version, lambda current: current.briefs.append(BriefRevision(revision=3, facts=[Fact(key="goal", value="A different goal", status="confirmed")])))
    with pytest.raises(WorkflowError) as error:
        service.add_topic(project.id, changed.version, preview.topic_suggestions[0].id)
    assert error.value.code == "generation_inputs_changed" and not store.get(project.id).contents


def test_instruction_only_exploration_proposes_no_confirmed_project_facts(workspace):
    store, service, transport, project = workspace
    project = store.update(project.id, project.version, lambda state: state.briefs.clear())
    assert service.preflight_generation(project.id, instruction="Show a commuter packing a bag.")["exploratory"]
    preview = service.suggest_topics(project.id, "Show a commuter packing a bag.")
    assert preview.topic_suggestions[0].inputs.exploratory
    assert preview.topic_suggestions[0].inputs.brief_revision is None
    assert not preview.briefs and not preview.brief_draft
    assert "Instruction-led exploration" in preview.topic_suggestions[0].inputs.limitations[0]
    assert transport.calls


def test_grouping_only_reparent_keeps_video_direction_and_pack_identity(workspace):
    _, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    old_video = project.contents[0].model_copy(deep=True)
    old_pack = project.packs[-1].model_copy(deep=True)
    project = service.create_series(project.id, project.version, "Optional group")
    project = service.edit_content(project.id, project.version, old_video.id, {"series_id": project.series[0].id})
    assert project.contents[0].id == old_video.id
    assert project.contents[0].approved_direction_id == old_video.approved_direction_id
    assert project.packs[-1] == old_pack
    project = service.edit_series(project.id, project.version, project.series[0].id, {"title": "Renamed optional group"})
    assert project.contents[0].approved_direction_id == old_video.approved_direction_id
    project = service.delete_series(project.id, project.version, project.series[0].id)
    assert project.contents[0].series_id is None
    assert project.contents[0].approved_direction_id == old_video.approved_direction_id
    project = service.edit_content(project.id, project.version, old_video.id, {"series_id": None})
    assert project.contents[0].directions == old_video.directions
    project = service.create_manual_pack(project.id, project.version, old_video.id)
    assert project.packs[-1].inputs.direction_id == old_video.approved_direction_id


def test_series_with_creative_context_marks_affected_approval_for_review(workspace):
    _, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_series(project.id, project.version, "Experiments", "Every video compares two methods.")
    project = service.edit_content(project.id, project.version, project.contents[0].id, {"series_id": project.series[0].id})
    assert project.contents[0].approved_direction_id is None
    assert project.contents[0].directions[-1].needs_review


def test_sheet_edit_reopen_export_share_exact_saved_revision_and_clean_columns(workspace):
    store, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    pack = project.packs[-1]
    assert pack.sheet_format == "storyboard_sheet" and not pack.shots
    project = service.save_pack(project.id, project.version, pack.id, pack.revision,
                                {"production_brief": "A compact shoot brief.", "shots": rows(), "sheet_format": "storyboard_sheet"})
    saved = project.packs[-1]
    assert saved.revision == 2 and saved.shots[0].id == "shot_stable_a"
    assert "Static close-up" in saved.storyboard and "Ready?" in saved.script
    assert "Use natural light." in saved.shot_list
    assert store.get(project.id).packs[-1] == saved
    data, _, _ = export_pack(store, project.id, pack.id, 2, "csv")
    table = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert table[0] == ["Shot", "Start", "End", "Framing / Camera", "Visual / Action", "Dialogue / VO", "On-screen Text", "Music / SFX", "Production Notes"]
    assert table[1] == ["01", "0.0", "3.0", "Static close-up", "Place a mug beside a bag.", "Ready?", "Morning", "Room tone", "Use natural light."]
    assert len(table) == 3 and all(len(row) == 9 for row in table)
    assert b"Input manifest" not in data and b"shot_stable_a" not in data and b"Production pack" not in data
    before = project.version
    unchanged = service.save_pack(project.id, before, saved.id, saved.revision, {"production_brief": saved.production_brief, "shots": [shot.model_dump(mode="json") for shot in saved.shots]})
    assert unchanged.version == before


def test_pending_row_edits_block_current_export_but_keep_historical_snapshot(workspace):
    store, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    project = service.save_pack(project.id, project.version, project.packs[-1].id, 1, {"shots": rows()})
    pack = project.packs[-1]
    edited = [shot.model_dump(mode="json") for shot in pack.shots]
    edited[0]["visual"] = "An unsaved row change."
    project = store.update(project.id, project.version, lambda state: state.editor_drafts.update({f"production-{pack.id}": {"base_revision": pack.revision, "shots": edited}}))
    with pytest.raises(WorkflowError) as error:
        export_pack(store, project.id, pack.id, pack.revision, "csv")
    assert error.value.code == "production_draft_pending"
    with pytest.raises(WorkflowError):
        service.save_pack(project.id, project.version, pack.id, pack.revision, {"shots": rows()})
    saved = service.save_pack(project.id, project.version, pack.id, pack.revision, {"shots": edited})
    assert saved.editor_drafts[f"production-{pack.id}"]["shots"] == [shot.model_dump(mode="json") for shot in saved.packs[-1].shots]
    historical, _, _ = export_pack(store, project.id, pack.id, pack.revision, "csv")
    assert b"An unsaved row change." not in historical


def test_legacy_free_text_is_preserved_without_invented_rows(workspace):
    store, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_pack(project.id, project.version, project.contents[0].id,
                                  {"production_brief": "Old brief", "script": "Hand-edited words", "storyboard": "Free text with no timing", "shot_list": "Old notes"})
    legacy = project.packs[-1].model_copy(deep=True)
    assert legacy.sheet_format == "legacy_documents" and legacy.shots == []
    original, _, _ = export_pack(store, project.id, legacy.id, 1, "csv")
    assert b"Saved text (no synchronized structured shots" in original and b"Hand-edited words" in original
    project = service.save_pack(project.id, project.version, legacy.id, 1, {"shots": rows()})
    assert project.packs[0] == legacy and project.packs[-1].sheet_format == "storyboard_sheet"
    historical, _, _ = export_pack(store, project.id, legacy.id, 1, "csv")
    assert b"Free text with no timing" in historical and b"Saved text (no synchronized structured shots" in historical


def test_legacy_structured_csv_keeps_original_columns_after_explicit_new_revision(workspace):
    store, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_pack(project.id, project.version, project.contents[0].id,
                                  {"production_brief": "Legacy brief", "script": "Legacy dialogue", "storyboard": "Original storyboard text", "shot_list": "Original shot list"})
    project = store.update(project.id, project.version, lambda state: setattr(state.packs[-1], "shots", [ProductionShot.model_validate(row) for row in rows()]))
    legacy = project.packs[-1].model_copy(deep=True)
    before, _, _ = export_pack(store, project.id, legacy.id, 1, "csv")
    old_table = list(csv.reader(io.StringIO(before.decode("utf-8-sig"))))
    assert old_table[0][0] == "Production pack"
    assert old_table[1] == ["Shot", "Start (seconds)", "End (seconds)", "Visual", "Dialogue", "On-screen text", "Sound", "Notes"]
    assert old_table[2][0] == "shot_stable_a"
    project = service.save_pack(project.id, project.version, legacy.id, 1, {"shots": [shot.model_dump(mode="json") for shot in legacy.shots]})
    assert project.packs[0] == legacy and project.packs[-1].revision == 2
    assert project.packs[-1].sheet_format == "storyboard_sheet"
    historical, _, _ = export_pack(store, project.id, legacy.id, 1, "csv")
    assert list(csv.reader(io.StringIO(historical.decode("utf-8-sig"))))[1:4] == old_table[1:4]
    current, _, _ = export_pack(store, project.id, legacy.id, 2, "csv")
    assert current.decode("utf-8-sig").startswith("Shot,Start,End,Framing / Camera")
    assert b"Production pack" not in current and b"shot_stable_a" not in current


def test_sheet_formula_text_is_neutralized_without_metadata_rows(workspace):
    store, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    shot_rows = rows()
    shot_rows[0]["notes"] = "  =HYPERLINK(\"https://invalid.example\")"
    project = service.save_pack(project.id, project.version, project.packs[-1].id, 1, {"shots": shot_rows})
    data, _, _ = export_pack(store, project.id, project.packs[-1].id, 2, "csv")
    assert list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))[1][-1].startswith("'  =")


def test_per_shot_sources_are_exact_and_unchanged_historical_links_remain(workspace):
    store, service, _, project = workspace
    def source(state):
        state.resources = [Resource(id="resource_ref", name="Synthetic source", kind="video", original_path="sources/ref.mp4", sha256="0" * 64, size_bytes=1, status="ready",
                                    evidence=[EvidenceRevision(revision=1, reviewed=True, events=[EvidenceEvent(id="event_ref", kind="visual", text="A bag opens", start_seconds=1, end_seconds=2)])])]
        state.selection.resource_ids = ["resource_ref"]
    project = store.update(project.id, project.version, source)
    project = approved_video(service, project, reference=True)
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    ref = SourceRef(resource_id="resource_ref", evidence_revision=1, event_id="event_ref", locator="1–2s", excerpt="A bag opens", start_seconds=1, end_seconds=2)
    shot_rows = rows()
    shot_rows[0]["sources"] = [ref.model_dump(mode="json")]
    shot_rows[0]["sources"][0].update(locator="Saved corrected observation", excerpt="A shortened source label", url="https://untrusted.invalid")
    project = service.save_pack(project.id, project.version, project.packs[-1].id, 1, {"shots": shot_rows})
    assert project.packs[-1].shots[0].sources == [ref]
    shot_rows[0]["sources"] = [ref.model_dump(mode="json")]
    changed = deepcopy(shot_rows)
    changed[0]["sources"][0]["start_seconds"] = 9
    with pytest.raises(WorkflowError):
        service.save_pack(project.id, project.version, project.packs[-1].id, 2, {"shots": changed})
    project = store.update(project.id, project.version, lambda state: state.resources[0].evidence.clear())
    shot_rows[0]["visual"] = "Keep the original source link on this edited shot."
    saved = service.save_pack(project.id, project.version, project.packs[-1].id, 2, {"shots": shot_rows})
    assert saved.packs[-1].shots[0].sources == [ref]


@pytest.mark.parametrize("change", ["empty_visual", "gap", "duplicate_id", "invalid_interval"])
def test_invalid_manual_rows_do_not_replace_saved_sheet(workspace, change):
    store, service, _, project = workspace
    project = approved_video(service, project)
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    shot_rows = rows()
    if change == "empty_visual":
        shot_rows[0]["visual"] = "  "
    elif change == "gap":
        shot_rows[1]["start_seconds"] = 4
    elif change == "duplicate_id":
        shot_rows[1]["id"] = shot_rows[0]["id"]
    else:
        shot_rows[1]["end_seconds"] = shot_rows[1]["start_seconds"]
    with pytest.raises(WorkflowError):
        service.save_pack(project.id, project.version, project.packs[-1].id, 1, {"shots": shot_rows})
    assert store.get(project.id) == project


def test_generated_rows_own_documents_and_pin_optional_per_shot_evidence(workspace):
    store, service, transport, project = workspace
    def source(state):
        state.resources = [Resource(id="resource_ref", name="Synthetic source", kind="video", original_path="sources/ref.mp4", sha256="0" * 64, size_bytes=1, status="ready",
                                    evidence=[EvidenceRevision(revision=1, reviewed=True, events=[EvidenceEvent(id="event_ref", kind="visual", text="A bag opens", start_seconds=1, end_seconds=2)])])]
        state.selection.resource_ids = ["resource_ref"]
    project = store.update(project.id, project.version, source)
    project = approved_video(service, project, reference=True)
    shot_rows = rows()
    shot_rows[0]["citations"] = [{"resource_id": "resource_ref", "event_id": "event_ref"}]
    transport.response = {"production_brief": "Use a mug, a bag and a desk.", "script": "A competing script must not become the sheet.",
                          "shot_list": "A competing list must not replace row actions.", "shots": shot_rows}
    saved = service.generate_pack(project.id, project.contents[0].id)
    pack = saved.packs[-1]
    assert pack.sheet_format == "storyboard_sheet" and pack.shots[0].framing_camera == "Static close-up"
    assert pack.shots[0].sources[0].evidence_revision == 1
    assert pack.shots[0].sources[0].start_seconds == 1
    assert pack.shots[0].sources[0].start_seconds != pack.shots[0].start_seconds
    assert pack.sources == pack.shots[0].sources
    assert "Ready?" in pack.script and "A competing script" not in pack.script
    assert "Place a mug beside a bag." in pack.shot_list


def test_new_creative_use_rejects_a_reference_in_an_ancestor_trash_folder(workspace):
    store, service, _, project = workspace
    def source(state):
        state.resources = [Resource(id="resource_ref", name="Synthetic source", kind="video", original_path="sources/ref.mp4", sha256="0" * 64, size_bytes=1, status="ready",
                                    folder_id="folder_references", evidence=[EvidenceRevision(revision=1, reviewed=True, events=[EvidenceEvent(id="event_ref", kind="visual", text="A bag opens", start_seconds=1, end_seconds=2)])])]
        state.selection.resource_ids = ["resource_ref"]
        next(folder for folder in state.resource_folders if folder.id == "folder_references").trashed_at = "2026-11-17T00:00:00+00:00"
    project = store.update(project.id, project.version, source)
    with pytest.raises(WorkflowError) as error:
        service.preflight_generation(project.id)
    assert error.value.code == "reference_unavailable"
    assert store.get(project.id).resources[0].evidence[0].events[0].text == "A bag opens"


def linked_inspiration(store, project, *, reviewed=False):
    def source(state):
        state.resources = [Resource(id="resource_inspiration", name="Inspiration source", kind="video", original_path="sources/inspiration.mp4", sha256="0" * 64, size_bytes=1, status="ready",
                                    evidence=[EvidenceRevision(revision=1, reviewed=reviewed, events=[EvidenceEvent(id="event_inspiration", kind="visual", text="The bag opens before the product appears", start_seconds=1, end_seconds=2)])])]
    project = store.update(project.id, project.version, source)
    ref = SourceRef(resource_id="resource_inspiration", evidence_revision=1, event_id="event_inspiration", locator="Saved insight", excerpt="A short source label", start_seconds=1, end_seconds=2)
    return project, ref


def test_linked_inspiration_survives_save_and_requires_explicit_source_review(workspace):
    store, service, transport, project = workspace
    project, ref = linked_inspiration(store, project)
    project = service.create_content(project.id, project.version, "Inspired video")
    item_id = project.contents[0].id
    assert project.contents[0].selection.resource_ids == []
    project = service.save_direction(project.id, project.version, item_id,
                                     {"title": "Bag-first opening", "concept": "Borrow the opening mechanism, not the source product claim."}, source_refs=[ref.model_dump(mode="json")])
    item = project.contents[0]
    direction = item.directions[-1]
    assert item.selection.resource_ids == [ref.resource_id] and item.selection.revision == 2
    assert direction.sources[0].evidence_revision == 1 and direction.sources[0].start_seconds == 1
    assert direction.sources[0].excerpt == "The bag opens before the product appears"
    assert direction.sources[0].locator == "1–2s" and not direction.approved
    assert not project.resources[0].evidence[0].reviewed and not transport.calls
    with pytest.raises(WorkflowError) as error:
        service.approve_direction(project.id, project.version, item_id, direction.id, 1)
    assert error.value.code == "reference_review_required"
    project = store.update(project.id, project.version, lambda state: setattr(state.resources[0].evidence[0], "reviewed", True))
    approved = service.approve_direction(project.id, project.version, item_id, direction.id, 1)
    assert approved.contents[0].approved_direction_id == direction.id
    assert approved.contents[0].directions[-1].sources == direction.sources


def test_historical_inspiration_is_not_retargeted_to_newer_evidence(workspace):
    store, service, _, project = workspace
    project, ref = linked_inspiration(store, project, reviewed=True)
    project = service.create_content(project.id, project.version, "Inspired video")
    project = service.save_direction(project.id, project.version, project.contents[0].id,
                                     {"title": "Opening", "concept": "Use a bag-first reveal."}, source_refs=[ref])
    old = project.contents[0].directions[-1].model_copy(deep=True)
    project = store.update(project.id, project.version, lambda state: state.resources[0].evidence.append(
        EvidenceRevision(revision=2, reviewed=True, events=[EvidenceEvent(id="event_inspiration", kind="visual", text="A corrected interpretation of the source", start_seconds=3, end_seconds=4)])))
    changed = service.save_direction(project.id, project.version, project.contents[0].id, {"concept": "Keep the exact earlier inspiration."},
                                     direction_id=old.id, direction_revision=1)
    current = changed.contents[0].directions[-1]
    assert current.revision == 2 and current.needs_review
    assert current.sources == old.sources and current.sources[0].evidence_revision == 1
    assert current.sources[0].start_seconds == 1
    assert current.inputs.evidence_revisions[ref.resource_id] == 1
    assert any("revision 1" in note for note in current.inputs.limitations)
    assert changed.contents[0].directions[0] == old
    with pytest.raises(WorkflowError) as error:
        service.approve_direction(project.id, changed.version, changed.contents[0].id, old.id, 2)
    assert error.value.code == "direction_inputs_outdated"
    missing = store.update(project.id, changed.version, lambda state: (state.resources[0].evidence.clear(), setattr(state.resources[0], "status", "missing")))
    retained = service.save_direction(project.id, missing.version, missing.contents[0].id, {"concept": "Retain the unavailable historical link."},
                                      direction_id=old.id, direction_revision=2)
    assert retained.contents[0].directions[-1].sources == old.sources
    assert retained.contents[0].directions[-1].needs_review


def test_source_only_direction_draft_blocks_approval_until_formal_save(workspace):
    store, service, _, project = workspace
    project, ref = linked_inspiration(store, project, reviewed=True)
    project = service.create_content(project.id, project.version, "Inspired video")
    project = service.save_direction(project.id, project.version, project.contents[0].id,
                                     {"title": "Opening", "concept": "Use a bag-first reveal."}, source_refs=[ref])
    item, direction = project.contents[0], project.contents[0].directions[-1]
    scope = f"direction-{item.id}-{direction.id}"
    project = store.update(project.id, project.version, lambda state: state.editor_drafts.update({scope: {"base_revision": 1, "source_refs": []}}))
    with pytest.raises(WorkflowError) as error:
        service.approve_direction(project.id, project.version, item.id, direction.id, 1)
    assert error.value.code == "direction_draft_pending"
    saved = service.save_direction(project.id, project.version, item.id, {"concept": direction.concept},
                                   direction_id=direction.id, direction_revision=1, source_refs=[])
    assert saved.contents[0].selection.resource_ids == [ref.resource_id]
    assert saved.contents[0].directions[-1].sources == []
    assert saved.editor_drafts[scope]["source_refs"] == []
    approved = service.approve_direction(project.id, saved.version, item.id, direction.id, 2)
    assert approved.contents[0].approved_direction_revision == 2


def test_new_original_video_does_not_inherit_unavailable_project_analysis_scope(workspace):
    store, service, transport, project = workspace
    def missing(state):
        state.resources = [Resource(id="resource_missing", name="Missing old source", kind="video", original_path="sources/missing.mp4", sha256="0" * 64, size_bytes=1, status="missing")]
        state.selection.resource_ids = ["resource_missing"]
    project = store.update(project.id, project.version, missing)
    project = approved_video(service, project)
    assert project.contents[0].selection.resource_ids == []
    assert project.selection.resource_ids == ["resource_missing"]
    assert project.contents[0].approved_direction_id
    project = service.create_manual_pack(project.id, project.version, project.contents[0].id)
    assert project.packs[-1].inputs.resource_ids == []
    assert project.packs[-1].inputs.evidence_revisions == {} and not transport.calls


def test_adding_reference_led_topic_preserves_provenance_without_binding_video_scope(workspace):
    store, service, _, project = workspace
    project, ref = linked_inspiration(store, project, reviewed=True)
    project = store.update(project.id, project.version, lambda state: setattr(state.selection, "resource_ids", [ref.resource_id]))
    preview = service.suggest_topics(project.id)
    assert preview.topic_suggestions[0].inputs.resource_ids == [ref.resource_id]
    added = service.add_topic(project.id, preview.version, preview.topic_suggestions[0].id)
    assert added.contents[0].inputs.resource_ids == [ref.resource_id]
    assert added.contents[0].selection.resource_ids == []


def test_implicit_edit_preserves_link_history_without_rebinding_cleared_scope(workspace):
    store, service, _, project = workspace
    project, ref = linked_inspiration(store, project, reviewed=True)
    project = service.create_content(project.id, project.version, "Inspired video")
    project = service.save_direction(project.id, project.version, project.contents[0].id,
                                     {"title": "Opening", "concept": "Use a bag-first reveal."}, source_refs=[ref])
    direction = project.contents[0].directions[-1]
    project = AnalysisService(store, service.settings_provider).set_selection(project.id, project.version, [], project.contents[0].id)
    changed = service.save_direction(project.id, project.version, project.contents[0].id, {"concept": "Revise the direction text."},
                                     direction_id=direction.id, direction_revision=1)
    assert changed.contents[0].selection.resource_ids == []
    assert changed.contents[0].directions[-1].sources == direction.sources
    assert changed.contents[0].directions[-1].needs_review
    assert any("current reference scope" in note for note in changed.contents[0].directions[-1].inputs.limitations)
