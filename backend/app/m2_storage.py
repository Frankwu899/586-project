"""Independent editor versioning and atomic formal-input transactions in SQLite."""
from __future__ import annotations

from typing import Callable

from . import models as m
from .m2_domain import (brief_payload, build_brief, current_brief, draft_from_state,
                        refresh_draft, require_ready, structured_checkpoint)
from .workflow_errors import WorkflowError


class M2StoreMixin:
    def _m2_state(self, db, task_id):
        row = db.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise WorkflowError("task_not_found", "This task does not exist.", 404)
        return self._read_state(db, task_id, row[0])

    def _m2_draft(self, db, state):
        row = db.execute("SELECT payload FROM m2_drafts WHERE task_id = ?", (state.task.task_id,)).fetchone()
        if row:
            draft = refresh_draft(m.M2Draft.model_validate_json(row[0]))
            # Loading the explicitly synthetic sample may supply its first brief
            # after the empty editor was opened. Never replace partial input.
            if state.task.mode == "sample" and draft.based_on_brief is None and state.task.current_brief is not None and not draft.has_pending_inputs and draft.fields == m.M2Fields() and not draft.claims:
                draft = draft_from_state(state, draft_version=draft.draft_version + 1, source_notes=draft.source_notes)
                self._write_m2(db, draft)
            return draft
        draft = draft_from_state(state)
        self._write_m2(db, draft)
        return draft

    def _write_m2(self, db, draft, last_apply_request=None):
        draft = refresh_draft(m.M2Draft.model_validate(draft.model_dump()))
        db.execute("""INSERT INTO m2_drafts(task_id, version, payload, last_apply_request)
            VALUES (?, ?, ?, ?) ON CONFLICT(task_id) DO UPDATE SET
            version=excluded.version, payload=excluded.payload, last_apply_request=excluded.last_apply_request""",
            (draft.task_id, draft.draft_version, draft.model_dump_json(), last_apply_request))

    def get_m2_draft(self, task_id: str) -> m.M2Draft:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._m2_draft(db, self._m2_state(db, task_id))

    def _check_draft_version(self, draft, expected):
        if draft.draft_version != expected:
            raise WorkflowError("m2_draft_conflict", "These inputs changed. Your local text is retained; reload the saved draft before retrying.")

    def save_m2_draft(self, task_id: str, request: m.M2DraftUpdate) -> m.M2Draft:
        request = m.M2DraftUpdate.model_validate(request)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._m2_state(db, task_id)
            draft = self._m2_draft(db, state)
            self._check_draft_version(draft, request.expected_draft_version)
            previous = {claim.claim_id: claim for claim in draft.claims}
            draft.fields = request.fields.model_copy(deep=True)
            draft.claims = [claim.model_copy(deep=True) for claim in request.claims]
            for claim in draft.claims:
                old = previous.get(claim.claim_id)
                if old and (old.statement != claim.statement or old.qualification != claim.qualification):
                    # Editing and rechecking in the same unacknowledged request
                    # cannot carry permission from old wording to new wording.
                    claim.confirmed_for_use = False
            draft.source_notes = request.source_notes
            draft.draft_version += 1
            draft.updated_at = m.utc_now()
            self._write_m2(db, draft)
            return refresh_draft(draft)

    def adopt_m2_proposals(self, task_id, request):
        from uuid import uuid4
        from .m2_assistance_models import M2AdoptRequest
        request = M2AdoptRequest.model_validate(request)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._m2_state(db, task_id)
            draft = self._m2_draft(db, state)
            if draft.draft_version != request.source_draft_version:
                raise WorkflowError("m2_stale_proposal", "These suggestions use an older draft. Your newer edits are intact; rerun assistance.")
            fields = draft.fields.model_dump()
            for candidate in request.candidates:
                if candidate.target == "claim":
                    draft.claims.append(m.M2Claim(claim_id="claim_" + uuid4().hex[:20],
                        **candidate.value.model_dump(), confirmed_for_use=False))
                else:
                    fields[candidate.target] = candidate.value
            draft.fields = m.M2Fields.model_validate(fields)
            draft.draft_version += 1
            draft.updated_at = m.utc_now()
            self._write_m2(db, draft)
            return refresh_draft(draft)

    def discard_m2_draft(self, task_id: str, expected_draft_version: int) -> m.M2Draft:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._m2_state(db, task_id)
            previous = self._m2_draft(db, state)
            self._check_draft_version(previous, expected_draft_version)
            draft = draft_from_state(state, draft_version=previous.draft_version + 1)
            self._write_m2(db, draft)
            return draft

    def _apply_m2(self, db, state, draft, invalidate: Callable[[m.TaskState], None], request_key=None):
        brief = build_brief(state, draft)
        previous = current_brief(state)
        changed = previous is None or brief_payload(previous) != brief_payload(brief)
        if changed:
            state.briefs.append(brief)
            state.task.current_brief = m.VersionRef(id=brief.brief_id, revision=brief.revision)
            invalidate(state)
            state.task.version += 1
            state.task.updated_at = m.utc_now()
            state = m.validate_state(state)
            db.execute("UPDATE tasks SET version=?, payload=? WHERE id=?", (state.task.version, state.model_dump_json(), state.task.task_id))
        draft.based_on_brief = state.task.current_brief
        draft.reviewed_input_checkpoint = structured_checkpoint(draft.fields, draft.claims)
        draft.legacy_review_required = False
        draft.draft_version += 1
        draft.updated_at = m.utc_now()
        self._write_m2(db, draft, request_key)
        return m.M2ApplyResult(changed=changed, draft=refresh_draft(draft), task=state)

    def apply_m2_draft(self, task_id: str, request: m.M2ApplyRequest,
                       invalidate: Callable[[m.TaskState], None]) -> m.M2ApplyResult:
        request = m.M2ApplyRequest.model_validate(request)
        request_key = request.model_dump_json()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._m2_state(db, task_id)
            draft = self._m2_draft(db, state)
            last = db.execute("SELECT last_apply_request FROM m2_drafts WHERE task_id=?", (task_id,)).fetchone()[0]
            # Exact retry after a committed Apply is idempotent, including when
            # its response was lost. Any later draft save clears this key.
            if last == request_key and not draft.has_pending_inputs and draft.based_on_brief == state.task.current_brief:
                return m.M2ApplyResult(changed=False, draft=draft, task=state)
            self._check_draft_version(draft, request.expected_draft_version)
            if state.task.version != request.expected_version:
                raise WorkflowError("version_conflict", "This task changed. Refresh its current state and retry Apply inputs.")
            if request.based_on_brief != state.task.current_brief or draft.based_on_brief != state.task.current_brief:
                raise WorkflowError("m2_draft_conflict", "The applied inputs changed. Reload or discard this draft before applying.")
            return self._apply_m2(db, state, draft, invalidate, request_key)

    def save_applied_brief(self, task_id: str, expected_version: int, fields: dict,
                           invalidate: Callable[[m.TaskState], None]) -> m.M2ApplyResult:
        """Compatibility endpoint with the same validation/no-op transaction.

        Old clients must explicitly supply confirmed claim metadata. They may
        not replace an independently edited draft through this older endpoint.
        """
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._m2_state(db, task_id)
            if state.task.version != expected_version:
                raise WorkflowError("version_conflict", "This task changed. Reopen it and retry your edit.")
            draft = self._m2_draft(db, state)
            if draft.has_pending_inputs:
                raise WorkflowError("m2_pending_changes", "Apply or discard the independently saved input draft before using the compatibility brief endpoint.")
            if not fields.get("claim_details"):
                raise WorkflowError("m2_unconfirmed_claims", "Explicit user-confirmed claim_details are required; the legacy brief route cannot infer permission.", 422)
            previous = current_brief(state)
            brief = m.BrandTaskBrief(brief_id=previous.brief_id if previous else "brief_compat", task_id=task_id, **fields)
            if any(detail.confirmation_origin != "user_confirmed" for detail in brief.claim_details):
                raise WorkflowError("m2_unconfirmed_claims", "Explicit user-confirmed claim_details are required; the legacy brief route cannot infer permission.", 422)
            if previous is not None and brief_payload(previous) == brief_payload(brief):
                # A compatibility no-op must retain reviewed excluded rows and
                # their original ordering, not erase saved "for later" work.
                return self._apply_m2(db, state, draft, invalidate)
            draft.fields = m.M2Fields(**{key: getattr(brief, key) for key in m.M2Fields.model_fields})
            draft.claims = [m.M2Claim(**detail.model_dump(exclude={"confirmation_origin"}), confirmed_for_use=True) for detail in brief.claim_details]
            return self._apply_m2(db, state, draft, invalidate)

    def _require_m2_ready(self, db, state):
        require_ready(state, self._m2_draft(db, state))

    def m2_ready(self, task_id: str) -> None:
        """Read-only convenience; use update(require_m2_ready=True) for admission."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._require_m2_ready(db, self._m2_state(db, task_id))
