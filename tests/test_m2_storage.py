"""Editor persistence, transaction races, exact content identity and honest migration."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import threading

import pytest
from pydantic import ValidationError

from backend.app import models as m
from backend.app.m2_migration import migrate_v04_task
from backend.app.storage import TaskStore, WorkflowError


@pytest.fixture
def store(tmp_path):
    store = TaskStore(tmp_path)
    store.create(m.TaskState(task=m.CreativeTask(task_id="task_m2", title="Manual input test")))
    return store


def save(store, *, fields=None, claims=None, source_notes=None, draft=None):
    draft = draft or store.get_m2_draft("task_m2")
    return store.save_m2_draft("task_m2", m.M2DraftUpdate(expected_draft_version=draft.draft_version,
        fields=fields if fields is not None else draft.fields, claims=claims if claims is not None else draft.claims,
        source_notes=source_notes if source_notes is not None else draft.source_notes))


def complete(store):
    return save(store, fields=m.M2Fields(brand_company="LumaCup", product="travel tumbler", target_audience="office commuters",
        platform="TikTok", communication_goal="demonstrate everyday usefulness", target_duration_seconds=20),
        claims=[m.M2Claim(claim_id="claim_cup", statement="Up to 6 hours", qualification="indoor test", supporting_notes="Supplied test note",
                         source_urls=["https://example.com/support"], confirmed_for_use=True)])


def request(store):
    draft, task = store.get_m2_draft("task_m2"), store.get("task_m2")
    return m.M2ApplyRequest(expected_draft_version=draft.draft_version, expected_version=task.task.version, based_on_brief=task.task.current_brief)


def apply(store, invalidate=lambda state: None):
    return store.apply_m2_draft("task_m2", request(store), invalidate)


def test_partial_restart_and_notes_never_write_task_version(store):
    task = store.get("task_m2")
    draft = save(store, fields=m.M2Fields(brand_company="品牌", product="混合 cup"), source_notes="Keep 原文 exactly\n")
    reopened = TaskStore(store.path.parent)
    assert reopened.get_m2_draft("task_m2") == draft
    assert reopened.get("task_m2") == task
    assert not task.briefs and draft.has_pending_inputs
    assert "target_audience" in draft.missing_fields


def test_notes_are_not_pending_and_no_input_defaults(store):
    draft = save(store, source_notes="Supplied facts only")
    assert not draft.has_pending_inputs
    assert draft.fields == m.M2Fields()
    assert set(draft.missing_fields) == {"brand_company", "product", "target_audience", "platform", "communication_goal", "target_duration_seconds", "confirmed_selling_point"}


def test_stale_draft_save_and_apply_preserve_latest_input(store):
    original = store.get_m2_draft("task_m2")
    latest = save(store, fields=m.M2Fields(brand_company="Newer brand"))
    with pytest.raises(WorkflowError, match="local text") as error:
        save(store, fields=m.M2Fields(brand_company="Old delayed value"), draft=original)
    assert error.value.code == "m2_draft_conflict"
    with pytest.raises(WorkflowError) as error:
        store.apply_m2_draft("task_m2", m.M2ApplyRequest(expected_draft_version=original.draft_version, expected_version=1, based_on_brief=None), lambda state: None)
    assert error.value.code == "m2_draft_conflict"
    assert store.get_m2_draft("task_m2") == latest
    assert not store.get("task_m2").briefs


@pytest.mark.parametrize("field", ["brand_company", "product", "target_audience", "platform", "communication_goal"])
def test_unknown_placeholders_do_not_pass_apply(store, field):
    draft = complete(store)
    setattr(draft.fields, field, "not sure")
    save(store, fields=draft.fields)
    with pytest.raises(WorkflowError) as error:
        apply(store)
    assert error.value.code == "m2_incomplete" and field in error.value.message
    assert not store.get("task_m2").briefs


@pytest.mark.parametrize("value", [0, -1, True, "20", float("nan"), float("inf")])
def test_duration_is_explicit_positive_finite(value):
    with pytest.raises(ValidationError):
        m.M2Fields(target_duration_seconds=value)


def test_apply_excludes_unconfirmed_claims_and_checkpoints_exclusions(store):
    draft = complete(store)
    draft.claims.append(m.M2Claim(claim_id="claim_later", statement="For later"))
    save(store, claims=draft.claims)
    result = apply(store)
    assert result.changed and result.task.task.version == 2
    assert result.task.briefs[0].selling_points == ["Up to 6 hours"]
    assert result.task.briefs[0].claim_details[0].qualification == "indoor test"
    assert len(result.draft.claims) == 2 and not result.draft.has_pending_inputs
    store.m2_ready("task_m2")


def test_wording_or_qualification_edit_clears_confirmation_without_mutating_applied(store):
    complete(store)
    result = apply(store)
    draft = result.draft
    draft.claims[0].qualification = "a different test"
    draft = save(store, claims=draft.claims)
    assert not draft.claims[0].confirmed_for_use
    assert store.get("task_m2") == result.task
    with pytest.raises(WorkflowError) as error:
        apply(store)
    assert error.value.code == "m2_unconfirmed_claims"
    draft.claims[0].confirmed_for_use = True
    save(store, claims=draft.claims)
    changed = apply(store)
    assert changed.changed and len(changed.task.briefs) == 2
    assert changed.task.briefs[0].claim_details[0].qualification == "indoor test"
    assert changed.task.briefs[1].claim_details[0].qualification == "a different test"


def test_noop_and_duplicate_apply_preserve_task_and_never_call_invalidate(store):
    complete(store)
    original_request = request(store)
    first = store.apply_m2_draft("task_m2", original_request, lambda state: None)
    retry = store.apply_m2_draft("task_m2", original_request, lambda state: pytest.fail("duplicate invalidation"))
    assert not retry.changed and retry.task == first.task
    saved = save(store, source_notes="Notes alone do not invalidate")
    assert not saved.has_pending_inputs
    no_op = apply(store, lambda state: pytest.fail("no-op invalidation"))
    assert not no_op.changed and no_op.task == first.task


@pytest.mark.parametrize("field,value", [("prohibited_claims", ["Do not claim dishwasher safety"]), ("approved_messages", ["Made for your commute"]),
    ("available_footage", "none available"), ("presenters", "none"), ("locations", "office"), ("tone", "plain"), ("production_limits", "one camera")])
def test_every_optional_provider_field_is_meaningful(store, field, value):
    complete(store)
    original = apply(store)
    draft = original.draft
    setattr(draft.fields, field, value)
    save(store, fields=draft.fields)
    result = apply(store)
    assert result.changed and len(result.task.briefs) == 2
    assert getattr(result.task.briefs[-1], field) == value


def test_support_and_urls_are_part_of_semantic_payload(store):
    complete(store)
    apply(store)
    draft = store.get_m2_draft("task_m2")
    draft.claims[0].supporting_notes = "Extra supplied support"
    draft.claims[0].source_urls = ["https://example.com/new"]
    save(store, claims=draft.claims)
    result = apply(store)
    assert result.changed and result.task.briefs[-1].claim_details[0].supporting_notes == "Extra supplied support"


def test_apply_rollback_keeps_task_and_checkpoint_consistent(store):
    complete(store)
    before, draft = store.get("task_m2"), store.get_m2_draft("task_m2")
    def fail(state):
        state.task.title = "Mutation which must roll back"
        raise RuntimeError("injected transaction failure")
    with pytest.raises(RuntimeError):
        apply(store, fail)
    assert store.get("task_m2") == before and store.get_m2_draft("task_m2") == draft


def test_concurrent_double_apply_creates_one_revision(store):
    complete(store)
    req = request(store)
    barrier = threading.Barrier(2)
    def run():
        barrier.wait()
        return store.apply_m2_draft("task_m2", req, lambda state: None)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: run(), range(2)))
    assert sorted(result.changed for result in results) == [False, True]
    assert len(store.get("task_m2").briefs) == 1


def test_pending_gate_is_atomic_with_admission_but_completion_remains_independent(store):
    complete(store)
    apply(store)
    admitted = store.update("task_m2", store.get("task_m2").task.version, lambda state: setattr(state.task, "title", "Admitted creative work"), require_m2_ready=True)
    draft = store.get_m2_draft("task_m2")
    draft.fields.tone = "New pending tone"
    save(store, fields=draft.fields)
    with pytest.raises(WorkflowError) as error:
        store.update("task_m2", admitted.task.version, lambda state: setattr(state.task, "title", "Must not admit"), require_m2_ready=True)
    assert error.value.code == "m2_pending_changes"
    completed = store.update("task_m2", admitted.task.version, lambda state: setattr(state.task, "title", "Earlier work completed"))
    assert completed.task.title == "Earlier work completed"
    assert store.get_m2_draft("task_m2").has_pending_inputs


def test_discard_restores_applied_or_only_clears_new_input(store):
    complete(store)
    before = store.get("task_m2")
    draft = store.get_m2_draft("task_m2")
    discarded = store.discard_m2_draft("task_m2", draft.draft_version)
    assert discarded.fields == m.M2Fields() and not discarded.claims
    assert store.get("task_m2") == before
    complete(store)
    applied = apply(store)
    changed = save(store, fields=m.M2Fields(brand_company="Unapplied"))
    restored = store.discard_m2_draft("task_m2", changed.draft_version)
    assert restored.fields.product == "travel tumbler" and not restored.has_pending_inputs
    assert store.get("task_m2") == applied.task


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///tmp/private", "https://user:pass@example.com", "https://example.com/with space"])
def test_unsafe_claim_links_rejected(url):
    with pytest.raises(ValidationError):
        m.M2Claim(claim_id="claim_link", source_urls=[url])


def test_legacy_migration_preserves_all_history_and_has_separate_review_gate(tmp_path):
    payload = json.loads((Path(__file__).resolve().parents[1] / "examples/v0.4.sample-task.json").read_text())
    original = deepcopy(payload)
    state = migrate_v04_task(payload)
    assert payload == original
    converted = state.model_dump(mode="json")
    converted["task"]["version"] -= 1
    for record in [converted["task"], *(record for values in converted.values() if isinstance(values, list) for record in values)]:
        record["schema_version"] = "0.4.0"
    for brief in converted["briefs"]:
        details = brief.pop("claim_details")
        assert [detail["statement"] for detail in details] == brief["selling_points"]
        assert all(detail["confirmation_origin"] == "legacy_unrecorded" for detail in details)
    assert converted["task"].pop("generation_language") is None
    for video in converted["videos"]:
        assert video.pop("deleted_at") is None
    for direction in converted["directions"]:
        assert direction.pop("auxiliary_status") == "current"
        assert direction.pop("structure_handoff_id") is None
    for output in [*converted["production_briefs"], *converted["storyboards"]]:
        assert output.pop("bundle_id") is None
    assert converted == original
    raw = json.dumps(payload, ensure_ascii=False, indent=3)
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        db.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, version INTEGER, payload TEXT)")
        db.execute("INSERT INTO tasks VALUES(?,?,?)", (state.task.task_id, payload["task"]["version"], raw))
    store = TaskStore(tmp_path)
    migrated = store.get(state.task.task_id)
    draft = store.get_m2_draft(state.task.task_id)
    assert migrated == state and draft.legacy_review_required and not draft.has_pending_inputs
    assert not any(claim.confirmed_for_use for claim in draft.claims)
    with pytest.raises(WorkflowError) as error:
        store.m2_ready(state.task.task_id)
    assert error.value.code == "m2_legacy_review_required"
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT original_payload FROM task_migration_archive").fetchone()[0] == raw
        assert db.execute("SELECT COUNT(*) FROM m2_drafts").fetchone()[0] == 1
    assert TaskStore(tmp_path).get(state.task.task_id) == state


def test_legacy_migration_failure_rolls_back_task_archive_and_draft(tmp_path):
    payload = json.loads((Path(__file__).resolve().parents[1] / "examples/v0.4.sample-task.json").read_text())
    payload["analyses"][-1]["corrections"][0]["before"] = "Invalid historical replay"
    raw = json.dumps(payload)
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        db.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, version INTEGER, payload TEXT)")
        db.execute("INSERT INTO tasks VALUES(?,?,?)", (payload["task"]["task_id"], payload["task"]["version"], raw))
    with pytest.raises(ValueError, match="before-value"):
        TaskStore(tmp_path)
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        assert db.execute("SELECT payload FROM tasks").fetchone()[0] == raw
        assert db.execute("SELECT COUNT(*) FROM task_migration_archive").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM m2_drafts").fetchone()[0] == 0


def test_valid_legacy_long_input_migrates_without_truncation(tmp_path):
    payload = json.loads((Path(__file__).resolve().parents[1] / "examples/v0.4.sample-task.json").read_text())
    payload["briefs"][-1]["brand_company"] = "Long original品牌" * 1000
    payload["briefs"][-1]["approved_messages"] = [f"Approved {index}" for index in range(60)]
    raw = json.dumps(payload)
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        db.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, version INTEGER, payload TEXT)")
        db.execute("INSERT INTO tasks VALUES(?,?,?)", (payload["task"]["task_id"], payload["task"]["version"], raw))
    store = TaskStore(tmp_path)
    draft = store.get_m2_draft(payload["task"]["task_id"])
    assert draft.fields.brand_company == payload["briefs"][-1]["brand_company"]
    assert draft.fields.approved_messages == payload["briefs"][-1]["approved_messages"]


def test_optional_blank_is_unspecified_and_explicit_none_is_preserved(store):
    draft = complete(store)
    draft.fields.locations = "   "
    draft.fields.available_footage = "none available"
    draft.claims[0].supporting_notes = ""
    save(store, fields=draft.fields, claims=draft.claims)
    brief = apply(store).task.briefs[-1]
    assert brief.locations is None
    assert brief.available_footage == "none available"
    assert brief.claim_details[0].supporting_notes is None


def test_proposal_batch_adopts_once_atomically_and_rejects_stale_or_permission_fields(store):
    draft = save(store, fields=m.M2Fields(brand_company="Existing brand"), source_notes="Brand: Supplied brand\nClaim: Up to 6 hours, indoor test")
    original_task = store.get("task_m2")
    batch = {"source_draft_version": draft.draft_version, "request_id": "request_batch", "candidates": [
        {"candidate_id": "candidate_brand", "target": "brand_company", "value": "Explicitly edited brand",
         "origin": "extracted", "source_excerpt": "Supplied brand"},
        {"candidate_id": "candidate_audience", "target": "target_audience", "value": "office commuters",
         "origin": "suggested", "source_excerpt": None},
        {"candidate_id": "candidate_claim", "target": "claim", "value": {"statement": "Up to 6 hours, indoor test"},
         "origin": "extracted", "source_excerpt": "Up to 6 hours, indoor test"},
    ]}
    result = store.adopt_m2_proposals("task_m2", batch)
    assert result.draft_version == draft.draft_version + 1
    assert result.fields.brand_company == "Explicitly edited brand"
    assert result.fields.target_audience == "office commuters"
    assert result.fields.platform is None
    assert result.source_notes == draft.source_notes
    assert result.claims[0].statement == "Up to 6 hours, indoor test"
    assert not result.claims[0].confirmed_for_use
    assert result.claims[0].claim_id.startswith("claim_")
    assert store.get("task_m2") == original_task
    with pytest.raises(WorkflowError) as error:
        store.adopt_m2_proposals("task_m2", batch)
    assert error.value.code == "m2_stale_proposal"
    assert store.get_m2_draft("task_m2") == result
    invalid = deepcopy(batch)
    invalid["source_draft_version"] = result.draft_version
    invalid["candidates"][-1]["value"]["confirmed_for_use"] = True
    with pytest.raises(ValidationError):
        store.adopt_m2_proposals("task_m2", invalid)
    assert store.get_m2_draft("task_m2") == result
    assert store.get("task_m2") == original_task


def test_reviewed_legacy_apply_creates_next_revision_and_only_then_invalidates(tmp_path):
    from backend.app.service import invalidate

    payload = json.loads((Path(__file__).resolve().parents[1] / "examples/v0.4.sample-task.json").read_text())
    task_id = payload["task"]["task_id"]
    raw = json.dumps(payload, ensure_ascii=False)
    with sqlite3.connect(tmp_path / "tasks.sqlite3") as db:
        db.execute("CREATE TABLE tasks(id TEXT PRIMARY KEY, version INTEGER, payload TEXT)")
        db.execute("INSERT INTO tasks VALUES(?,?,?)", (task_id, payload["task"]["version"], raw))
    store = TaskStore(tmp_path)
    previous = store.get(task_id)
    original_briefs = deepcopy(previous.briefs)
    assert previous.task.selected_direction is not None
    assert any(output.currentness == "current" for output in previous.production_briefs)
    draft = store.get_m2_draft(task_id)
    for claim in draft.claims:
        claim.confirmed_for_use = True
    saved = store.save_m2_draft(task_id, m.M2DraftUpdate(expected_draft_version=draft.draft_version,
        fields=draft.fields, claims=draft.claims, source_notes=draft.source_notes))
    assert store.get(task_id) == previous
    with pytest.raises(WorkflowError) as error:
        store.m2_ready(task_id)
    assert error.value.code == "m2_legacy_review_required"
    req = m.M2ApplyRequest(expected_draft_version=saved.draft_version,
        expected_version=previous.task.version, based_on_brief=previous.task.current_brief)
    result = store.apply_m2_draft(task_id, req, invalidate)
    assert result.changed
    assert result.task.task.version == previous.task.version + 1
    assert result.task.briefs[:-1] == original_briefs
    assert result.task.briefs[-1].revision == original_briefs[-1].revision + 1
    assert result.task.briefs[-1].selling_points == original_briefs[-1].selling_points
    assert all(claim.confirmation_origin == "user_confirmed" for claim in result.task.briefs[-1].claim_details)
    assert [claim.claim_id for claim in result.task.briefs[-1].claim_details] == [claim.claim_id for claim in original_briefs[-1].claim_details]
    assert result.task.task.selected_direction is None
    assert all(output.currentness == "outdated" for output in result.task.production_briefs + result.task.storyboards)
    assert result.task.analyses == previous.analyses
    assert not result.draft.legacy_review_required and not result.draft.has_pending_inputs
    store.m2_ready(task_id)
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT original_payload FROM task_migration_archive").fetchone()[0] == raw


def test_compatibility_noop_retains_reviewed_excluded_claims_and_notes(store):
    draft = complete(store)
    draft.claims.insert(0, m.M2Claim(claim_id="claim_for_later", statement="A retained alternative", qualification="Needs user review"))
    save(store, claims=draft.claims, source_notes="Recoverable source notes")
    applied = apply(store)
    fields = applied.task.briefs[-1].model_dump(mode="json", exclude={"brief_id", "task_id", "revision", "schema_version", "created_at", "updated_at"})
    result = store.save_applied_brief("task_m2", applied.task.task.version, fields,
        lambda state: pytest.fail("A compatibility no-op must not invalidate"))
    assert not result.changed and result.task == applied.task
    assert result.draft.claims == applied.draft.claims
    assert result.draft.source_notes == applied.draft.source_notes
    assert result.draft.reviewed_input_checkpoint == applied.draft.reviewed_input_checkpoint
    assert not result.draft.has_pending_inputs
