"""Task-local input semantics shared by storage and the API boundary."""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from . import models as m
from .workflow_errors import WorkflowError

REQUIRED_FIELDS = ("brand_company", "product", "target_audience", "platform", "communication_goal", "target_duration_seconds")
_UNDECIDED = {"not sure", "not sure yet", "unknown", "undecided", "not decided", "not provided", "i'm not sure", "i’m not sure", "i'm not sure yet", "i’m not sure yet", "tbd", "n/a", "?", "不知道", "不确定", "未定"}


def missing_fields(fields: m.M2Fields, claims: list[m.M2Claim]) -> list[str]:
    missing = []
    for name in REQUIRED_FIELDS:
        value = getattr(fields, name)
        if value is None or isinstance(value, str) and (not value.strip() or value.strip().lower() in _UNDECIDED):
            missing.append(name)
    if not any(claim.confirmed_for_use and claim.statement.strip() and claim.statement.strip().lower() not in _UNDECIDED for claim in claims):
        missing.append("confirmed_selling_point")
    return missing


def structured_checkpoint(fields: m.M2Fields, claims: list[m.M2Claim]) -> str:
    payload = {"fields": fields.model_dump(mode="json"), "claims": [claim.model_dump(mode="json") for claim in claims]}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def refresh_draft(draft: m.M2Draft) -> m.M2Draft:
    draft.has_pending_inputs = structured_checkpoint(draft.fields, draft.claims) != draft.reviewed_input_checkpoint
    draft.missing_fields = missing_fields(draft.fields, draft.claims)
    return draft


def current_brief(state: m.TaskState) -> m.BrandTaskBrief | None:
    ref = state.task.current_brief
    return next((brief for brief in state.briefs if ref and (brief.brief_id, brief.revision) == (ref.id, ref.revision)), None)


def draft_from_state(state: m.TaskState, *, draft_version: int = 1, source_notes: str = "") -> m.M2Draft:
    brief = current_brief(state)
    fields = m.M2Fields(**{key: getattr(brief, key) for key in m.M2Fields.model_fields}) if brief else m.M2Fields()
    claims = [m.M2Claim(**detail.model_dump(exclude={"confirmation_origin"}), confirmed_for_use=detail.confirmation_origin == "user_confirmed") for detail in brief.claim_details] if brief else []
    return refresh_draft(m.M2Draft(task_id=state.task.task_id, draft_version=draft_version, based_on_brief=state.task.current_brief,
        fields=fields, claims=claims, source_notes=source_notes, reviewed_input_checkpoint=structured_checkpoint(fields, claims),
        legacy_review_required=bool(brief and any(detail.confirmation_origin == "legacy_unrecorded" for detail in brief.claim_details))))


def build_brief(state: m.TaskState, draft: m.M2Draft) -> m.BrandTaskBrief:
    missing = missing_fields(draft.fields, draft.claims)
    if "confirmed_selling_point" in missing:
        raise WorkflowError("m2_unconfirmed_claims", "Confirm at least one usable selling point before applying inputs. Missing: " + ", ".join(missing), 422)
    if missing:
        raise WorkflowError("m2_incomplete", "Complete these inputs before applying: " + ", ".join(missing), 422)
    previous = current_brief(state)
    details = []
    for claim in draft.claims:
        if not claim.confirmed_for_use:
            continue
        content = claim.model_dump(exclude={"confirmed_for_use"})
        for key in ("qualification", "supporting_notes"):
            if isinstance(content[key], str) and not content[key].strip():
                content[key] = None
        details.append(m.ClaimDetail(**content, confirmation_origin="user_confirmed"))
    fields = draft.fields.model_dump()
    for key in ("available_footage", "presenters", "locations", "tone", "production_limits"):
        if isinstance(fields[key], str) and not fields[key].strip():
            fields[key] = None
    return m.BrandTaskBrief(brief_id=previous.brief_id if previous else "brief_" + uuid4().hex[:20],
        revision=previous.revision + 1 if previous else 1, task_id=state.task.task_id,
        **fields, selling_points=[detail.statement for detail in details], claim_details=details)


def brief_payload(brief: m.BrandTaskBrief) -> dict:
    return brief.model_dump(mode="json", exclude={"schema_version", "brief_id", "revision", "task_id", "created_at", "updated_at"})


def require_ready(state: m.TaskState, draft: m.M2Draft) -> None:
    brief = current_brief(state)
    if not brief:
        raise WorkflowError("m2_incomplete", "Apply complete Brand & task inputs first. Missing: " + ", ".join(draft.missing_fields))
    if draft.legacy_review_required or any(detail.confirmation_origin != "user_confirmed" for detail in brief.claim_details):
        raise WorkflowError("m2_legacy_review_required", "Review these legacy inputs, confirm usable claims and Apply inputs before new creative work.")
    if draft.has_pending_inputs:
        raise WorkflowError("m2_pending_changes", "Review and Apply inputs, or discard your pending structured edits, before continuing.")
