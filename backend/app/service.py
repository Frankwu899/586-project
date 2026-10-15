"""Versioned workflow operations. Adapters receive saved immutable input snapshots."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import models as m
from .storage import TaskStore, WorkflowError


def now():
    return datetime.now(timezone.utc)


def uid(prefix):
    return f"{prefix}_{uuid4().hex}"


def ref(record):
    for field in ("brief_id", "analysis_id", "direction_id", "output_id", "feedback_id"):
        if hasattr(record, field):
            return m.VersionRef(id=getattr(record, field), revision=record.revision)
    raise ValueError("Record has no revision identity")


def find(records, wanted):
    if wanted is not None:
        for record in records:
            if ref(record) == wanted:
                return record
    raise WorkflowError("revision_not_found", "The requested revision does not belong to this task.")


def invalidate(state, direction_id=None):
    for direction in state.directions:
        if direction_id is None or direction.direction_id == direction_id:
            direction.currentness = "outdated"
            direction.approval_status = "draft"
            direction.approved_at = None
    if state.task.selected_direction and (direction_id is None or state.task.selected_direction.id == direction_id):
        state.task.selected_direction = None
    if state.task.chosen_direction and (direction_id is None or state.task.chosen_direction.id == direction_id):
        state.task.chosen_direction = None
    for output in [*state.production_briefs, *state.storyboards]:
        if direction_id is None or output.direction_ref.id == direction_id:
            output.currentness = "outdated"


class WorkflowService:
    def __init__(self, root: Path, recognition=None, creative=None, media=None):
        from .adapters import SampleCreativeAdapter, SampleRecognitionAdapter, UnconfiguredRecognitionAdapter
        from .media import MediaStore
        self.store = TaskStore(root)
        self.media = media or MediaStore(root / "media")
        self.sample_recognition = recognition or SampleRecognitionAdapter()
        self.real_recognition = UnconfiguredRecognitionAdapter()
        self.creative = creative or SampleCreativeAdapter()
        self._recover_interrupted_jobs()

    def _recover_interrupted_jobs(self):
        # The documented demo runs one backend worker. Restart ends any old jobs.
        for stored in self.store.list():
            if any(job.status in ("pending", "running") for job in stored.jobs):
                def recover(state):
                    for job in state.jobs:
                        if job.status in ("pending", "running"):
                            job.status = "failed"
                            job.error = m.ErrorInfo(code="interrupted_job", message="The backend stopped before this job completed. Saved work is intact; retry the operation.", retryable=True)
                            job.updated_at = now()
                self._update(stored.task.task_id, None, recover)

    def create(self, title):
        return self.store.create(m.TaskState(task=m.CreativeTask(task_id=uid("task"), title=title)))

    def _update(self, task_id, version, mutate):
        def apply(state):
            mutate(state)
            state.task.updated_at = now()
        return self.store.update(task_id, version, apply)

    def save_brief(self, task_id, version, fields):
        def change(state):
            previous = find(state.briefs, state.task.current_brief) if state.task.current_brief else None
            brief = m.BrandTaskBrief(brief_id=previous.brief_id if previous else uid("brief"), revision=previous.revision + 1 if previous else 1, task_id=task_id, **fields)
            state.briefs.append(brief)
            state.task.current_brief = ref(brief)
            invalidate(state)
        return self._update(task_id, version, change)

    def load_sample(self, task_id, version):
        from .sample import sample_brief
        before = self.store.get(task_id)
        if before.task.version != version:
            raise WorkflowError("version_conflict", "This task changed. Reopen it before loading the sample.")
        if before.videos:
            raise WorkflowError("sample_requires_empty_task", "Create a new task to load the dedicated synthetic reference.")
        video = self.media.create_sample(task_id)
        def change(state):
            state.task.mode = "sample"
            state.videos.append(video)
            state.task.current_video_id = video.video_id
            if not state.task.current_brief:
                brief = sample_brief(task_id)
                state.briefs.append(brief)
                state.task.current_brief = ref(brief)
            state.task.progress = "analysis"
        return self._update(task_id, version, change)

    def upload(self, task_id, version, filename, stream, source_url=None):
        before = self.store.get(task_id)
        if before.task.version != version:
            raise WorkflowError("version_conflict", "This task changed. Reopen it before uploading.")
        video = self.media.save_upload(task_id, filename, stream, source_url=source_url)
        def change(state):
            state.videos.append(video)
            state.task.current_video_id = video.video_id
            state.task.current_analysis = None
            state.task.mode = "real"
            state.task.progress = "analysis"
            invalidate(state)
        return self._update(task_id, version, change)

    def _inputs(self, state, brief_ref, analysis_ref):
        if state.task.current_brief != brief_ref or state.task.current_analysis != analysis_ref:
            raise WorkflowError("outdated_inputs", "Use this task's current brief and analysis revisions.")
        brief = find(state.briefs, brief_ref)
        analysis = find(state.analyses, analysis_ref)
        if analysis.task_id != state.task.task_id or analysis.video_id != state.task.current_video_id:
            raise WorkflowError("mismatched_analysis", "The analysis does not match this task's current video.")
        if analysis.status != "succeeded":
            raise WorkflowError("analysis_not_succeeded", "Recognition must finish successfully before creative generation.")
        if analysis.frame_count is None:
            raise WorkflowError("frame_timing_unavailable", "This archived analysis has no frame timing. Upload and analyze the source video again before generating creative work.")
        if not analysis.review.user_confirmed:
            raise WorkflowError("analysis_unconfirmed", "Use this reviewed analysis before generating or refining a direction.")
        return brief, analysis

    def _direction(self, state, direction_ref, brief_ref, analysis_ref, approved=False):
        brief, analysis = self._inputs(state, brief_ref, analysis_ref)
        direction = find(state.directions, direction_ref)
        if direction.currentness != "current" or direction.brief_ref != brief_ref or direction.analysis_ref != analysis_ref:
            raise WorkflowError("outdated_direction", "This direction is outdated. Generate or approve a current draft.")
        if approved and (direction.approval_status != "approved" or state.task.selected_direction != direction_ref):
            raise WorkflowError("direction_unapproved", "Explicitly approve this exact direction revision before generating production materials.")
        return brief, analysis, direction

    def _run(self, task_id, version, operation, prepare, execute, finish):
        """Persist every job transition and reject results after any intervening write."""
        context = {}
        job_id = uid("job")
        def pending(state):
            context.update(prepare(state))
            state.jobs.append(m.ProcessingJob(job_id=job_id, task_id=task_id, operation=operation, status="pending", input_refs=context.get("input_refs", {}), video_id=state.task.current_video_id, attempt=1 + sum(j.operation == operation for j in state.jobs)))
        queued = self._update(task_id, version, pending)
        def running(state):
            next(j for j in state.jobs if j.job_id == job_id).status = "running"
        try:
            active = self._update(task_id, queued.task.version, running)
        except WorkflowError as conflict:
            if conflict.code != "version_conflict":
                raise
            def canceled(state):
                job = next(j for j in state.jobs if j.job_id == job_id)
                job.status = "failed"
                job.error = m.ErrorInfo(code="stale_result", message="This task changed before the job could start. Saved edits were preserved; retry the operation.", retryable=True)
            return self._update(task_id, None, canceled)
        result, error = None, None
        try:
            result = execute(context, job_id)
        except Exception as exc:
            # No provider secrets, raw response bodies, or stack traces enter task records.
            error = m.ErrorInfo(code=getattr(exc, "code", "generation_failed"), message=getattr(exc, "message", "Generation failed. Review the inputs and retry."), retryable=getattr(exc, "retryable", False))
        def complete(state):
            job = next(j for j in state.jobs if j.job_id == job_id)
            job.updated_at = now()
            if state.task.version != active.task.version:
                job.status = "failed"
                job.error = m.ErrorInfo(code="stale_result", message="Inputs changed while this job ran. Its result was discarded; saved edits were preserved.", retryable=True)
                return
            if error:
                job.status, job.error = "failed", error
                return
            finish(state, result, context, job)
            if job.status != "failed":
                job.status = "succeeded"
        try:
            return self._update(task_id, None, complete)
        except (ValueError, WorkflowError, TypeError, AttributeError, IndexError):
            # An invalid adapter result must not leave a running job or persist invalid records.
            def invalid(state):
                job = next(j for j in state.jobs if j.job_id == job_id)
                job.status = "failed"
                job.error = m.ErrorInfo(code="invalid_adapter_result", message="The adapter returned data that failed the shared contract. No generated content was saved.")
            return self._update(task_id, None, invalid)

    def recognize(self, task_id, version, video_id=None):
        from .adapters import RecognitionRequest
        def prepare(state):
            if video_id is not None and video_id != state.task.current_video_id:
                raise WorkflowError("mismatched_video", "Recognition must use this task's current video.")
            video = next((v for v in state.videos if v.video_id == state.task.current_video_id), None)
            if video is None or video.intake_status != "ready":
                raise WorkflowError("video_unavailable", "Upload a valid video or load the dedicated sample first.")
            self.media.path_for(video)
            return {"video": video, "task_mode": state.task.mode}
        def execute(context, job_id):
            adapter = self.sample_recognition if context["task_mode"] == "sample" else self.real_recognition
            return adapter.analyze(RecognitionRequest(task_id=task_id, video=context["video"], job_id=job_id, task_mode=context["task_mode"], media_path=self.media.path_for(context["video"])))
        def finish(state, analysis, context, job):
            analysis = m.AnalysisResult.model_validate(analysis.model_dump())
            if analysis.revision != 1 or analysis.original_revision != 1 or analysis.review.user_confirmed or analysis.corrections or any(a.analysis_id == analysis.analysis_id for a in state.analyses):
                raise ValueError("Recognition must return a new unreviewed original result")
            if analysis.status not in {"succeeded", "partial", "failed"}:
                raise ValueError("A completed recognition call must return a terminal result")
            if analysis.task_id != task_id or analysis.video_id != context["video"].video_id:
                raise WorkflowError("invalid_adapter_result", "Recognition returned another task or video.")
            state.analyses.append(analysis)
            state.task.current_analysis = ref(analysis)
            state.task.progress = "review"
            invalidate(state)
            if analysis.status == "failed":
                job.status, job.error = "failed", analysis.error
            else:
                job.result_ref, job.result_type = ref(analysis), "analysis"
                job.partial_coverage = analysis.status == "partial"
        return self._run(task_id, version, "analyze", prepare, execute, finish)

    def correct_analysis(self, task_id, version, analysis_ref, event_edits, segment_edits):
        def change(state):
            if state.task.current_analysis != analysis_ref:
                raise WorkflowError("outdated_analysis", "Correct the current analysis revision.")
            original = find(state.analyses, analysis_ref)
            if original.status not in ("succeeded", "partial"):
                raise WorkflowError("analysis_not_succeeded", "Only completed observations can be corrected.")
            edited = original.model_copy(deep=True)
            edited.revision = max(a.revision for a in state.analyses if a.analysis_id == original.analysis_id) + 1
            edited.created_at = edited.updated_at = now()
            edited.review = m.ReviewState()
            changes = []
            seen = set()
            for kind, edits, records, key, allowed in (("event", event_edits, edited.events, "event_id", {"text", "description"}), ("segment", segment_edits, edited.segments, "segment_id", {"roles"})):
                for edit in edits:
                    if set(edit) - (allowed | {key}):
                        raise WorkflowError("immutable_analysis_field", "Observation IDs, timing, kind, lane, evidence links, and interpretations cannot be edited.", 422)
                    target_id = edit.get(key)
                    if (kind, target_id) in seen:
                        raise WorkflowError("duplicate_edit", "Each observation or section may be edited only once per request.", 422)
                    seen.add((kind, target_id))
                    target = next((record for record in records if getattr(record, key) == target_id), None)
                    if target is None:
                        raise WorkflowError("unknown_analysis_target", "The edit target does not exist in this analysis revision.", 422)
                    for field in allowed & edit.keys():
                        if kind == "event" and ((field == "text" and target.kind not in ("speech", "on_screen_text")) or (field == "description" and target.kind != "visual_action")):
                            raise WorkflowError("unsupported_content_correction", "Only recognized speech/on-screen text and visual-action descriptions can be corrected.", 422)
                        before, after = getattr(target, field), edit[field]
                        if before != after:
                            setattr(target, field, after)
                            changes.append(m.Correction(target_type=kind, target_id=target_id, field=field, before=before, after=after))
            if not changes:
                raise WorkflowError("empty_correction", "Change recognized text, an observation description, or section roles before saving.", 422)
            # Role interpretations can be invalid after content changes; they are not editable facts.
            for segment in edited.segments:
                segment.interpretation = None
            edited.corrections.extend(changes)
            edited = m.AnalysisResult.model_validate(edited.model_dump())
            state.analyses.append(edited)
            state.task.current_analysis = ref(edited)
            state.task.progress = "review"
            invalidate(state)
        return self._update(task_id, version, change)

    def confirm_analysis(self, task_id, version, analysis_ref):
        def change(state):
            if state.task.current_analysis != analysis_ref:
                raise WorkflowError("outdated_analysis", "Confirm the current analysis revision.")
            analysis = find(state.analyses, analysis_ref)
            if analysis.status != "succeeded":
                raise WorkflowError("analysis_not_succeeded", "Only successful analysis can be confirmed. Explicit partial runs are not supported by this skeleton.")
            if analysis.video_id != state.task.current_video_id:
                raise WorkflowError("mismatched_analysis", "The analysis must match the current video.")
            if analysis.frame_count is None:
                raise WorkflowError("frame_timing_unavailable", "This archived analysis has no frame timing. Upload and analyze the source video again before confirming it.")
            analysis.review = m.ReviewState(user_confirmed=True, confirmed_at=now())
            analysis.updated_at = now()
            state.task.progress = "directions"
        return self._update(task_id, version, change)

    def generate_directions(self, task_id, version, brief_ref, analysis_ref):
        def prepare(state):
            brief, analysis = self._inputs(state, brief_ref, analysis_ref)
            return {"brief": brief, "analysis": analysis, "input_refs": {"brief": brief_ref, "analysis": analysis_ref}}
        def finish(state, directions, context, job):
            if len(directions) != 2 or len({d.direction_id for d in directions}) != 2:
                raise ValueError("Exactly two distinct directions are required")
            for direction in directions:
                if (direction.task_id != task_id or direction.revision != 1 or direction.approval_status != "draft" or direction.approved_at is not None or direction.currentness != "current" or direction.feedback_refs or direction.brief_ref != context["input_refs"]["brief"] or direction.analysis_ref != context["input_refs"]["analysis"] or any(d.direction_id == direction.direction_id for d in state.directions)):
                    raise ValueError("Generated directions must be new current unapproved drafts tied to saved inputs")
            invalidate(state)
            state.directions.extend(directions)
            state.task.progress = "directions"
            job.result_ref, job.result_type = ref(directions[0]), "direction"
        return self._run(task_id, version, "directions", prepare, lambda c, _: self.creative.generate_directions(c["brief"], c["analysis"]), finish)

    def edit_direction(self, task_id, version, direction_id, revision, fields):
        def change(state):
            direction_ref = m.VersionRef(id=direction_id, revision=revision)
            old = find(state.directions, direction_ref)
            self._direction(state, direction_ref, old.brief_ref, old.analysis_ref)
            if not fields or set(fields) - {"core_message", "hook", "narrative", "cta"}:
                raise WorkflowError("invalid_direction_edit", "Edit message, Hook, narrative, or CTA.", 422)
            edited = old.model_copy(deep=True)
            edited.revision += 1
            edited.created_at = edited.updated_at = now()
            edited.approval_status, edited.approved_at = "draft", None
            for name, value in fields.items():
                setattr(edited, name, value)
            edited = m.CreativeDirection.model_validate(edited.model_dump())
            invalidate(state, direction_id)
            state.directions.append(edited)
            state.task.chosen_direction = ref(edited)
        return self._update(task_id, version, change)

    def refine_direction(self, task_id, version, direction_id, revision, brief_ref, analysis_ref, instruction):
        def prepare(state):
            brief, analysis, direction = self._direction(state, m.VersionRef(id=direction_id, revision=revision), brief_ref, analysis_ref)
            feedback = m.CreativeFeedback(feedback_id=uid("feedback"), task_id=task_id, instruction=instruction, target_direction=ref(direction), brief_ref=brief_ref, analysis_ref=analysis_ref, status="pending")
            state.feedback.append(feedback)
            return {"brief": brief, "analysis": analysis, "direction": direction, "feedback": feedback, "input_refs": {"brief": brief_ref, "analysis": analysis_ref, "direction": ref(direction), "feedback": ref(feedback)}}
        def finish(state, direction, context, job):
            feedback = find(state.feedback, ref(context["feedback"]))
            if direction is None:
                feedback.status = "not_interpreted"
                feedback.explanation = "Sample refinement did not interpret this instruction. It is saved as a user production note; no new draft was generated. Supported example: make it presenter-free."
                job.result_ref, job.result_type = ref(feedback), "feedback"
                return
            if (direction.direction_id != direction_id or direction.task_id != task_id or direction.revision != revision + 1 or direction.approval_status != "draft" or direction.approved_at is not None or direction.currentness != "current" or direction.brief_ref != brief_ref or direction.analysis_ref != analysis_ref or direction.feedback_refs != [*context["direction"].feedback_refs, ref(feedback)]):
                raise ValueError("Refinement must produce the next unapproved draft")
            invalidate(state, direction_id)
            state.directions.append(direction)
            state.task.chosen_direction = ref(direction)
            feedback.status, feedback.resulting_direction = "applied", ref(direction)
            feedback.explanation = "Deterministic sample refinement applied: presenter-free production. Review and explicitly approve this new draft."
            job.result_ref, job.result_type = ref(direction), "direction"
        return self._run(task_id, version, "refine", prepare, lambda c, _: self.creative.refine_direction(c["brief"], c["analysis"], c["direction"], c["feedback"]), finish)

    def choose_direction(self, task_id, version, direction_id, revision):
        def change(state):
            chosen = m.VersionRef(id=direction_id, revision=revision)
            self._direction(state, chosen, state.task.current_brief, state.task.current_analysis)
            if state.task.selected_direction is not None and state.task.selected_direction != chosen:
                state.task.selected_direction = None
                for direction in state.directions:
                    if direction.approval_status == "approved":
                        direction.approval_status, direction.approved_at = "draft", None
                for output in [*state.production_briefs, *state.storyboards]:
                    output.currentness = "outdated"
            state.task.chosen_direction = chosen
        return self._update(task_id, version, change)

    def approve_direction(self, task_id, version, direction_id, revision, brief_ref, analysis_ref):
        def change(state):
            selected = m.VersionRef(id=direction_id, revision=revision)
            _, _, direction = self._direction(state, selected, brief_ref, analysis_ref)
            # A different approved choice makes earlier materials historical immediately.
            if state.task.selected_direction != selected:
                for output in [*state.production_briefs, *state.storyboards]:
                    output.currentness = "outdated"
            for other in state.directions:
                if other.approval_status == "approved" and ref(other) != selected:
                    other.approval_status, other.approved_at = "draft", None
            direction.approval_status, direction.approved_at = "approved", now()
            direction.updated_at = now()
            state.task.selected_direction = selected
            state.task.chosen_direction = selected
            state.task.progress = "production"
        return self._update(task_id, version, change)

    def generate_outputs(self, task_id, version, direction_ref, brief_ref, analysis_ref):
        def prepare(state):
            brief, analysis, direction = self._direction(state, direction_ref, brief_ref, analysis_ref, approved=True)
            return {"brief": brief, "analysis": analysis, "direction": direction, "input_refs": {"brief": brief_ref, "analysis": analysis_ref, "direction": direction_ref}}
        def finish(state, outputs, context, job):
            production, storyboard = outputs
            for output in (production, storyboard):
                if (output.task_id != task_id or output.direction_ref != context["input_refs"]["direction"] or output.brief_ref != context["input_refs"]["brief"] or output.analysis_ref != context["input_refs"]["analysis"] or output.currentness != "current" or output.edited):
                    raise ValueError("Generated outputs must be fresh drafts tied to the exact approved input snapshot")
            for output in [*state.production_briefs, *state.storyboards]:
                output.currentness = "outdated"
            # Stable output IDs with monotonically increasing revisions preserve manual drafts.
            for output, history in ((production, state.production_briefs), (storyboard, state.storyboards)):
                if history:
                    output.output_id = history[-1].output_id
                    output.revision = max(item.revision for item in history) + 1
                history.append(output)
            state.task.current_production_brief, state.task.current_storyboard = ref(production), ref(storyboard)
            job.result_ref, job.result_type = ref(production), "production_brief"
        return self._run(task_id, version, "production", prepare, lambda c, _: self.creative.generate_production(c["brief"], c["analysis"], c["direction"]), finish)

    def edit_outputs(self, task_id, version, production_brief_ref, storyboard_ref, brief_fields, rows):
        def change(state):
            if state.task.current_production_brief != production_brief_ref or state.task.current_storyboard != storyboard_ref:
                raise WorkflowError("outdated_output", "Edit the latest saved production materials.")
            old_brief, old_story = find(state.production_briefs, production_brief_ref), find(state.storyboards, storyboard_ref)
            if set(brief_fields) - {"title", "core_message", "hook", "narrative", "cta", "production_notes"}:
                raise WorkflowError("invalid_output_edit", "Only production brief text can be edited.", 422)
            if not brief_fields and rows is None:
                raise WorkflowError("empty_edit", "Change production text before saving.", 422)
            brief, story = old_brief.model_copy(deep=True), old_story.model_copy(deep=True)
            for field, value in brief_fields.items():
                setattr(brief, field, value)
            if rows is not None:
                if [r.get("row_id") for r in rows] != [r.row_id for r in old_story.rows]:
                    raise WorkflowError("immutable_storyboard_rows", "Keep storyboard row IDs and order unchanged.", 422)
                for row, previous in zip(rows, old_story.rows):
                    for field in ("start_seconds", "end_seconds", "evidence"):
                        if row.get(field) != previous.model_dump(mode="json")[field]:
                            raise WorkflowError("immutable_storyboard_timing", "Only storyboard text can be edited; planned timing and evidence links are fixed.", 422)
                story.rows = [m.StoryboardRow.model_validate(row) for row in rows]
            for updated, old, history in ((brief, old_brief, state.production_briefs), (story, old_story, state.storyboards)):
                old.currentness = "outdated"
                updated.revision = max(o.revision for o in history) + 1
                updated.edited = True
                updated.created_at = updated.updated_at = now()
                history.append(type(updated).model_validate(updated.model_dump()))
            state.task.current_production_brief, state.task.current_storyboard = ref(brief), ref(story)
        return self._update(task_id, version, change)

    def export(self, task_id, kind):
        state = self.store.get(task_id)
        if kind == "brief.md":
            output = find(state.production_briefs, state.task.current_production_brief)
            lines = [f"# {md(output.title)}", "", f"Origin: {md(output.origin.kind)} — {md(output.origin.description)}", f"Status: {output.currentness}; output {output.output_id} revision {output.revision}", context_line(output), ""]
            for title, value in (("Core message", output.core_message), ("Hook", output.hook), ("Narrative", output.narrative), ("CTA", output.cta), ("Production notes", "\n".join(output.production_notes))):
                lines.extend([f"## {title}", "", md(value), ""])
            lines.extend(["## Reference evidence", "", *[md(f"{e.event_id} ({e.analysis_id} revision {e.analysis_revision}, video {e.video_id}): {e.reason}") for e in output.evidence]])
            return "\n".join(lines)
        if kind == "storyboard.csv":
            output = find(state.storyboards, state.task.current_storyboard)
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(["origin", "status", "output_id", "revision", "input_versions", "row_id", "planned_start_seconds", "planned_end_seconds", "visual", "dialogue", "on_screen_text", "sound", "cta", "reference_evidence"])
            for row in output.rows:
                values = [output.origin.kind, output.currentness, output.output_id, output.revision, context_line(output), row.row_id, row.start_seconds, row.end_seconds, row.visual, row.dialogue, row.on_screen_text, row.sound, row.cta, "; ".join(f"{e.analysis_id}@{e.analysis_revision}/{e.video_id}/{e.event_id}: {e.reason}" for e in row.evidence)]
                writer.writerow([csv_safe(value) for value in values])
            return stream.getvalue()
        raise WorkflowError("export_not_found", "Choose brief.md or storyboard.csv.", 404)


def context_line(output):
    return f"Task {output.task_id}; brief {output.brief_ref.id}@{output.brief_ref.revision}; analysis {output.analysis_ref.id}@{output.analysis_ref.revision}; direction {output.direction_ref.id}@{output.direction_ref.revision}; feedback " + ", ".join(f"{f.id}@{f.revision}" for f in output.feedback_refs)


def csv_safe(value):
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def md(value):
    # Export readable text without allowing user strings to inject active HTML/links.
    value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for character in "\\`*_{}[]()#+!|":
        value = value.replace(character, "\\" + character)
    return value
