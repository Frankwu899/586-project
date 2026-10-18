"""Independent, recoverable M5/M6/M7 drafts and atomic admission checkpoints."""
from __future__ import annotations

from . import models as m
from .workflow_errors import WorkflowError

DIRECTION_FIELDS = ("core_message", "hook", "narrative", "cta")
PRODUCTION_FIELDS = ("title", *DIRECTION_FIELDS, "production_notes")


def _record(records, reference):
    if reference is None:
        return None
    for record in records:
        identity = next((getattr(record, name) for name in ("analysis_id", "direction_id", "output_id") if hasattr(record, name)), None)
        if identity == reference.id and record.revision == reference.revision:
            return record
    return None


def editor_snapshot(state, scope):
    """Return current immutable refs and the complete editable form payload."""
    if scope == "idea":
        return {}, {key: "" for key in DIRECTION_FIELDS}
    if scope == "analysis":
        record = _record(state.analyses, state.task.current_analysis)
        if record is not None:
            return {"analysis": state.task.current_analysis}, {"events": [x.model_dump(mode="json") for x in record.events], "segments": [x.model_dump(mode="json") for x in record.segments]}
    elif scope == "production":
        brief = _record(state.production_briefs, state.task.current_production_brief)
        story = _record(state.storyboards, state.task.current_storyboard)
        if brief is not None and story is not None:
            return {"production_brief": state.task.current_production_brief, "storyboard": state.task.current_storyboard}, {"brief_fields": brief.model_dump(mode="json", include=set(PRODUCTION_FIELDS)), "rows": [x.model_dump(mode="json") for x in story.rows]}
    elif scope.startswith("direction-"):
        records = [item for item in state.directions if item.direction_id == scope.removeprefix("direction-")]
        if records:
            record = max(records, key=lambda item: item.revision)
            return {"direction": m.VersionRef(id=record.direction_id, revision=record.revision)}, record.model_dump(mode="json", include=set(DIRECTION_FIELDS))
    else:
        raise WorkflowError("invalid_editor_scope", "Choose the analysis, direction or production editor.", 422)
    return {}, {}


def editor_content(scope, content):
    """Compare only editable leaves, excluding cleared generated interpretations."""
    if not content:
        return {}
    def nonempty(value):
        return value.strip() if isinstance(value, str) else value
    def details(value):
        if value is None:
            return None
        try:
            return m.VisualDetails.model_validate(value).model_dump(mode="json")
        except ValueError:
            # Incomplete text is valid draft work, but cannot become a formal
            # observation until the canonical model accepts it.
            return value
    if scope == "analysis":
        return {"events": [{"event_id": item.get("event_id"), "text": item.get("text"), "description": nonempty(item.get("description")), "visual_details": details(item.get("visual_details"))} for item in content.get("events", [])],
                "segments": [{key: item.get(key) for key in ("segment_id", "roles")} for item in content.get("segments", [])]}
    if scope == "production":
        return {"brief_fields": {key: nonempty(value) if key != "production_notes" else value for key, value in content["brief_fields"].items()},
                "rows": [{**row, "visual": nonempty(row.get("visual"))} for row in content["rows"]]}
    return {key: nonempty(value) for key, value in content.items()}


class EditorStoreMixin:
    def _write_editor(self, db, draft):
        db.execute("""INSERT INTO editor_drafts(task_id,scope,version,payload) VALUES(?,?,?,?)
            ON CONFLICT(task_id,scope) DO UPDATE SET version=excluded.version,payload=excluded.payload""",
            (draft.task_id, draft.scope, draft.draft_version, draft.model_dump_json()))

    def _editor_draft(self, db, state, scope):
        # Validating here also constrains callers that bypass the HTTP boundary.
        scope = m.EditorDraft(task_id=state.task.task_id, scope=scope).scope
        refs, content = editor_snapshot(state, scope)
        row = db.execute("SELECT payload FROM editor_drafts WHERE task_id=? AND scope=?", (state.task.task_id, scope)).fetchone()
        if row is None:
            draft = m.EditorDraft(task_id=state.task.task_id, scope=scope, base_refs=refs, content=content)
            self._write_editor(db, draft)
            return draft
        draft = m.EditorDraft.model_validate_json(row[0])
        if draft.base_refs != refs:
            if draft.has_pending_changes:
                draft.conflict = True
            else:
                draft = m.EditorDraft(task_id=state.task.task_id, scope=scope, draft_version=draft.draft_version + 1, base_refs=refs, content=content)
            self._write_editor(db, draft)
        return draft

    def get_editor_draft(self, task_id, scope):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._editor_draft(db, self._m2_state(db, task_id), scope)

    def _check_editor_version(self, draft, expected):
        if draft.draft_version != expected:
            raise WorkflowError("editor_draft_conflict", "This saved draft changed. Your local text is retained; reload the saved draft before retrying.")

    def save_editor_draft(self, task_id, scope, request):
        request = m.EditorDraftUpdate.model_validate(request)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._m2_state(db, task_id)
            draft = self._editor_draft(db, state, scope)
            self._check_editor_version(draft, request.expected_draft_version)
            if request.base_refs != draft.base_refs:
                raise WorkflowError("editor_base_conflict", "The editor source changed. Keep your local changes and reload before retrying.")
            allowed = {"events", "segments"} if scope == "analysis" else {"brief_fields", "rows"} if scope == "production" else set(DIRECTION_FIELDS)
            if set(request.content) != allowed:
                raise WorkflowError("invalid_editor_content", "The saved draft must contain the complete editor fields.", 422)
            if scope == "analysis" and any(not isinstance(request.content[key], list) or any(not isinstance(item, dict) for item in request.content[key]) for key in allowed):
                raise WorkflowError("invalid_editor_content", "Analysis draft events and segments must be lists of observations.", 422)
            if scope == "production" and (not isinstance(request.content["brief_fields"], dict) or not isinstance(request.content["rows"], list) or any(not isinstance(row, dict) for row in request.content["rows"])):
                raise WorkflowError("invalid_editor_content", "Production draft must contain brief fields and storyboard rows.", 422)
            draft.content = request.content
            refs, formal = editor_snapshot(state, scope)
            draft.conflict = refs != draft.base_refs
            draft.has_pending_changes = draft.conflict or editor_content(scope, formal) != editor_content(scope, draft.content)
            draft.draft_version += 1
            draft.updated_at = m.utc_now()
            self._write_editor(db, draft)
            return draft

    def discard_editor_draft(self, task_id, scope, expected):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = self._m2_state(db, task_id)
            previous = self._editor_draft(db, state, scope)
            self._check_editor_version(previous, expected)
            refs, content = editor_snapshot(state, scope)
            draft = m.EditorDraft(task_id=task_id, scope=scope, draft_version=previous.draft_version + 1, base_refs=refs, content=content)
            self._write_editor(db, draft)
            return draft

    def _editor_scopes(self, db, state, scopes):
        if "*" in scopes:
            return sorted({"analysis", "production", *("direction-" + item.direction_id for item in state.directions), *[row[0] for row in db.execute("SELECT scope FROM editor_drafts WHERE task_id=?", (state.task.task_id,)).fetchall()]})
        return list(scopes)

    def _require_editors_clear(self, db, state, scopes, capture=None):
        for scope in self._editor_scopes(db, state, scopes):
            draft = self._editor_draft(db, state, scope)
            if draft.has_pending_changes or draft.conflict:
                raise WorkflowError("editor_pending_changes", "Apply/save or discard the pending " + scope + " draft before continuing.")
            if capture is not None:
                capture[scope] = draft.draft_version

    def _editor_commit_before(self, db, state, scope, expected):
        draft = self._editor_draft(db, state, scope)
        if expected is not None:
            self._check_editor_version(draft, expected)
        elif draft.has_pending_changes:
            raise WorkflowError("editor_pending_changes", "Save the current editor draft with its version before changing the formal record.")
        if draft.conflict:
            raise WorkflowError("editor_base_conflict", "The formal source changed. Your draft is retained; reload or discard it before applying.")
        return draft

    def _editor_commit_after(self, db, state, previous):
        refs, content = editor_snapshot(state, previous.scope)
        if previous.has_pending_changes and editor_content(previous.scope, content) != editor_content(previous.scope, previous.content):
            raise WorkflowError("editor_content_conflict", "The submitted edit does not match the saved draft. Save the latest draft and retry.")
        draft = m.EditorDraft(task_id=state.task.task_id, scope=previous.scope, draft_version=previous.draft_version + 1, base_refs=refs, content=content)
        self._write_editor(db, draft)
