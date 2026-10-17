"""Versioned workflow operations. Adapters receive saved immutable input snapshots."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import replace
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


def _fail_job(state, job, error):
    """Close a failed operation and its saved, uninterpreted refinement request."""
    job.status, job.error = "failed", error
    job.updated_at = now()
    feedback_ref = job.input_refs.get("feedback") if job.operation == "refine" else None
    if feedback_ref is not None:
        feedback = find(state.feedback, feedback_ref)
        if feedback.status == "pending":
            feedback.status = "not_interpreted"
            feedback.explanation = f"Refinement was not applied ({error.code}): {error.message} The original instruction is retained."
            feedback.updated_at = job.updated_at


class WorkflowService:
    def __init__(self, root: Path, recognition=None, creative=None, media=None, *,
                 real_recognition=None, real_creative=None, provider_settings=None,
                 m2_assistance=None):
        from .adapters import SampleCreativeAdapter, SampleRecognitionAdapter, UnconfiguredRecognitionAdapter
        from .media import MediaStore
        from .providers.config import ProviderSettings
        from .providers.creative import OpenAICreativeAdapter
        from .providers.recognition import ProviderRecognitionAdapter
        from .providers.m2 import build_m2_assistance
        self.store = TaskStore(root)
        self.media = media or MediaStore(root / "media")
        self.provider_settings = provider_settings or replace(ProviderSettings.from_env(), cache_dir=root / "provider-cache")
        self.sample_recognition = recognition or SampleRecognitionAdapter()
        self.real_recognition = real_recognition or (
            ProviderRecognitionAdapter(settings=self.provider_settings, media_store=self.media)
            if self.provider_settings.api_key else UnconfiguredRecognitionAdapter())
        self.creative = creative or SampleCreativeAdapter()
        self.real_creative = real_creative or OpenAICreativeAdapter(self.provider_settings)
        self.m2_assistance = m2_assistance or build_m2_assistance(self.provider_settings)
        self._recover_interrupted_jobs()

    def _creative_execute(self, context, job_id, operation):
        adapter = self.creative if context["task_mode"] == "sample" else self.real_creative
        if hasattr(adapter, "for_language"):
            adapter = adapter.for_language(context["generation_language"])
        if hasattr(adapter, "diagnostics_context"):
            adapter.diagnostics_context = {"job_id": job_id, "source_sha256": context["source_sha256"],
                                           "analysis_id": context["analysis"].analysis_id,
                                           "analysis_revision": context["analysis"].revision}
        args = [context["brief"], context["analysis"]]
        if operation != "generate_directions":
            args.append(context["direction"])
        if operation == "refine_direction":
            args.append(context["feedback"])
        return getattr(adapter, operation)(*args)

    def _record_job_outcome(self, state, job_id):
        """Associate attempts with authoritative committed references, including regeneration.

        Adapter candidates can be rejected as stale or receive stable output IDs
        during persistence. Only this record claims that results were committed.
        """
        folder = self.provider_settings.cache_dir
        if state.task.mode == "sample" or folder is None:
            return
        job = next(item for item in state.jobs if item.job_id == job_id)
        outputs = []
        if job.result_ref:
            outputs.append({"type": job.result_type, **job.result_ref.model_dump()})
            if job.operation == "production" and state.task.current_storyboard:
                outputs.append({"type": "storyboard", **state.task.current_storyboard.model_dump()})
        record = {"record_type": "persisted_job_result", "job_id": job_id,
                  "task_id": state.task.task_id, "task_version": state.task.version,
                  "status": job.status, "output_refs": outputs,
                  "failure_code": job.error.code if job.error else None,
                  "recorded_at": now().isoformat()}
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / "runs.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
        except OSError:
            # Diagnostics cannot undo an already committed workflow result.
            self.diagnostics_write_failed = True

    def _recover_interrupted_jobs(self):
        # The documented demo runs one backend worker. Restart ends any old jobs.
        for stored in self.store.list():
            if any(job.status in ("pending", "running") for job in stored.jobs):
                def recover(state):
                    for job in state.jobs:
                        if job.status in ("pending", "running"):
                            _fail_job(state, job, m.ErrorInfo(code="interrupted_job", message="The backend stopped before this job completed. Saved work is intact; retry the operation.", retryable=True))
                self._update(stored.task.task_id, None, recover)

    def create(self, title):
        return self.store.create(m.TaskState(task=m.CreativeTask(task_id=uid("task"), title=title)))

    def _require_language(self, state):
        if state.task.generation_language is None:
            raise WorkflowError("generation_language_required", "Choose English or Chinese before generating or approving creative work.", 422)

    def set_language(self, task_id, version, language):
        if language not in ("English", "Chinese"):
            raise WorkflowError("invalid_generation_language", "Choose English or Chinese.", 422)
        def change(state):
            if state.task.generation_language == language:
                return False
            state.task.generation_language = language
            # Old records had no explicit language choice. They stay available
            # as historical material; their approval is not transferred.
            invalidate(state)
            if state.task.current_analysis:
                state.task.progress = "directions"
        return self._update(task_id, version, change, require_editors_clear=("*",))

    def _remove_media_files(self, video):
        """Only storage-generated basenames under the media root are eligible."""
        root = self.media.root.resolve()
        for storage_id in (video.storage_id, video.playback.storage_id if video.playback else None):
            if storage_id:
                path = root / storage_id
                if path.parent == root and path.resolve().parent == root:
                    path.unlink(missing_ok=True)

    def delete_video(self, task_id, version, video_id):
        deleted = []
        def change(state):
            video = next((item for item in state.videos if item.video_id == video_id), None)
            if video is None:
                raise WorkflowError("video_not_found", "This video does not belong to the task.", 404)
            deleted.append(video)
            if video.deleted_at is not None:
                return False
            video.deleted_at = video.updated_at = now()
            analysis_ids = {item.analysis_id for item in state.analyses if item.video_id == video_id}
            for direction_id in {item.direction_id for item in state.directions if item.analysis_ref.id in analysis_ids}:
                invalidate(state, direction_id)
            if state.task.current_video_id == video_id:
                state.task.current_video_id = None
                state.task.current_analysis = None
                state.task.progress = "analysis"
        state = self._update(task_id, version, change, require_editors_clear=("*",))
        # The tombstone is committed first, so media becomes inaccessible even
        # if disk cleanup is interrupted. A repeated delete retries cleanup.
        self._remove_media_files(deleted[0])
        return state

    def _update(self, task_id, version, mutate, *, require_m2_ready=False, preserve_m2_inputs=False, require_editors_clear=(), editor_checkpoint=None, capture_editor_versions=None, expected_editor_versions=None):
        def apply(state):
            changed = mutate(state)
            if changed is not False:
                state.task.updated_at = now()
            return changed
        return self.store.update(task_id, version, apply, require_m2_ready=require_m2_ready,
                                 preserve_m2_inputs=preserve_m2_inputs, require_editors_clear=require_editors_clear, editor_checkpoint=editor_checkpoint, capture_editor_versions=capture_editor_versions, expected_editor_versions=expected_editor_versions)

    def save_brief(self, task_id, version, fields):
        # Compatibility callers use the same confirmation, equality and atomic
        # checkpoint rules as the editor, never an alternate revision pathway.
        return self.store.save_applied_brief(task_id, version, fields, invalidate).task

    def apply_m2(self, task_id, request):
        return self.store.apply_m2_draft(task_id, request, invalidate)

    def assist_m2(self, task_id, request):
        from .providers.m2 import validate_assistance_response
        from .providers.base import ProviderError
        draft = self.store.get_m2_draft(task_id)
        if draft.draft_version != request.draft_version:
            raise WorkflowError("m2_stale_proposal", "Your inputs changed. Run extraction again.")
        try:
            response = self.m2_assistance.assist(request, draft)
            response = validate_assistance_response(response, request, draft)
        except ProviderError as exc:
            raise WorkflowError(exc.code, exc.message, 422, exc.retryable) from exc
        except Exception as exc:
            raise WorkflowError("m2_assistance_failed", "Couldn’t extract details. Your input is saved; continue editing or try again.", 422, True) from exc
        if self.store.get_m2_draft(task_id).draft_version != draft.draft_version:
            raise WorkflowError("m2_stale_proposal", "Your inputs changed. Run extraction again.")
        return response

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
        return self._update(task_id, version, change, preserve_m2_inputs=True)

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
        try:
            return self._update(task_id, version, change, require_editors_clear=("*",))
        except Exception:
            self._remove_media_files(video)
            raise

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

    def _run(self, task_id, version, operation, prepare, execute, finish, *, editor_scopes=("analysis",)):
        """Persist every job transition and reject results after any intervening write."""
        context = {}
        editor_versions = {}
        job_id = uid("job")
        def pending(state):
            context.update(prepare(state))
            if operation != "analyze":
                self._require_language(state)
            context["generation_language"] = state.task.generation_language
            context["task_mode"] = state.task.mode
            video = next((v for v in state.videos if v.video_id == state.task.current_video_id), None)
            context["source_sha256"] = video.content_sha256 if video else None
            state.jobs.append(m.ProcessingJob(job_id=job_id, task_id=task_id, operation=operation, status="pending", input_refs=context.get("input_refs", {}), video_id=state.task.current_video_id, attempt=1 + sum(j.operation == operation for j in state.jobs)))
        queued = self._update(task_id, version, pending, require_m2_ready=operation != "analyze", require_editors_clear=editor_scopes, capture_editor_versions=editor_versions)
        def running(state):
            next(j for j in state.jobs if j.job_id == job_id).status = "running"
        try:
            active = self._update(task_id, queued.task.version, running)
        except WorkflowError as conflict:
            if conflict.code != "version_conflict":
                raise
            def canceled(state):
                job = next(j for j in state.jobs if j.job_id == job_id)
                _fail_job(state, job, m.ErrorInfo(code="stale_result", message="This task changed before the job could start. Saved edits were preserved; retry the operation.", retryable=True))
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
                _fail_job(state, job, m.ErrorInfo(code="stale_result", message="Inputs changed while this job ran. Its result was discarded; saved edits were preserved.", retryable=True))
                return
            if error:
                _fail_job(state, job, error)
                return
            finish(state, result, context, job)
            if job.status != "failed":
                job.status = "succeeded"
        try:
            saved = self._update(task_id, None, complete, expected_editor_versions=editor_versions)
        except (ValueError, WorkflowError, TypeError, AttributeError, IndexError) as failure:
            editor_changed = isinstance(failure, WorkflowError) and failure.code == "editor_input_changed"
            # An invalid adapter result must not leave a running job or persist invalid records.
            def invalid(state):
                job = next(j for j in state.jobs if j.job_id == job_id)
                _fail_job(state, job, m.ErrorInfo(code="stale_result" if editor_changed else "invalid_adapter_result", message="An editor draft changed while this operation ran. Its result was discarded; saved edits are intact." if editor_changed else "The adapter returned data that failed the shared contract. No generated content was saved."))
            saved = self._update(task_id, None, invalid)
        self._record_job_outcome(saved, job_id)
        return saved

    def recognize(self, task_id, version, video_id=None):
        from .adapters import RecognitionRequest
        def prepare(state):
            if video_id is not None and video_id != state.task.current_video_id:
                raise WorkflowError("mismatched_video", "Recognition must use this task's current video.")
            video = next((v for v in state.videos if v.video_id == state.task.current_video_id), None)
            if video is None or video.deleted_at is not None or video.intake_status != "ready":
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
        return self._run(task_id, version, "analyze", prepare, execute, finish, editor_scopes=("*",))

    def correct_analysis(self, task_id, version, analysis_ref, event_edits, segment_edits, expected_editor_version=None):
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
            for kind, edits, records, key, allowed in (("event", event_edits, edited.events, "event_id", {"text", "description", "visual_details"}), ("segment", segment_edits, edited.segments, "segment_id", {"roles"})):
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
                        if kind == "event" and ((field == "text" and target.kind not in ("speech", "on_screen_text")) or (field in {"description", "visual_details"} and target.kind != "visual_action")):
                            raise WorkflowError("unsupported_content_correction", "Only recognized speech/on-screen text and visual-action descriptions or structured labels can be corrected.", 422)
                        before, after = getattr(target, field), edit[field]
                        if field == "description" and isinstance(after, str):
                            after = after.strip()
                        if field == "visual_details":
                            try:
                                after = m.validate_visual_details_correction(before, after).model_dump(mode="json")
                            except ValueError as exc:
                                raise WorkflowError("invalid_visual_correction", str(exc), 422) from exc
                            before = before.model_dump(mode="json")
                        if before != after:
                            setattr(target, field, m.VisualDetails.model_validate(after) if field == "visual_details" else after)
                            changes.append(m.Correction(target_type=kind, target_id=target_id, field=field, before=before, after=after))
            if not changes:
                return False
            # Role interpretations can be invalid after content changes; they are not editable facts.
            for segment in edited.segments:
                segment.interpretation = None
            edited.corrections.extend(changes)
            edited = m.AnalysisResult.model_validate(edited.model_dump())
            state.analyses.append(edited)
            state.task.current_analysis = ref(edited)
            state.task.progress = "review"
            invalidate(state)
        return self._update(task_id, version, change, editor_checkpoint=("analysis", expected_editor_version))

    def confirm_analysis(self, task_id, version, analysis_ref):
        def change(state):
            if state.task.current_analysis != analysis_ref:
                raise WorkflowError("outdated_analysis", "Confirm the current analysis revision.")
            analysis = find(state.analyses, analysis_ref)
            if analysis.status != "succeeded":
                raise WorkflowError("analysis_not_succeeded", "Only successful analysis can be confirmed. Resolve failed extraction before using partial observations for creative work.")
            if analysis.video_id != state.task.current_video_id:
                raise WorkflowError("mismatched_analysis", "The analysis must match the current video.")
            if analysis.frame_count is None:
                raise WorkflowError("frame_timing_unavailable", "This archived analysis has no frame timing. Upload and analyze the source video again before confirming it.")
            analysis.review = m.ReviewState(user_confirmed=True, confirmed_at=now())
            analysis.updated_at = now()
            state.task.progress = "directions"
        return self._update(task_id, version, change, require_editors_clear=("analysis",))

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
        return self._run(task_id, version, "directions", prepare, lambda c, job_id: self._creative_execute(c, job_id, "generate_directions"), finish, editor_scopes=("*",))

    def edit_direction(self, task_id, version, direction_id, revision, fields, expected_editor_version=None):
        def change(state):
            direction_ref = m.VersionRef(id=direction_id, revision=revision)
            old = find(state.directions, direction_ref)
            self._direction(state, direction_ref, old.brief_ref, old.analysis_ref)
            if not fields or set(fields) - {"core_message", "hook", "narrative", "cta"}:
                raise WorkflowError("invalid_direction_edit", "Edit message, Hook, narrative, or CTA.", 422)
            edited = old.model_copy(deep=True)
            edited.auxiliary_status = "needs_review"
            edited.revision += 1
            edited.created_at = edited.updated_at = now()
            edited.approval_status, edited.approved_at = "draft", None
            for name, value in fields.items():
                setattr(edited, name, value)
            edited = m.CreativeDirection.model_validate(edited.model_dump())
            if all(getattr(old, key) == getattr(edited, key) for key in fields):
                return False
            invalidate(state, direction_id)
            state.directions.append(edited)
            state.task.chosen_direction = ref(edited)
        return self._update(task_id, version, change, editor_checkpoint=("direction-" + direction_id, expected_editor_version))

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
                feedback.explanation = "The adapter did not interpret this instruction. It remains saved in feedback history; no new draft was generated."
                job.result_ref, job.result_type = ref(feedback), "feedback"
                return
            if (direction.direction_id != direction_id or direction.task_id != task_id or direction.revision != revision + 1 or direction.approval_status != "draft" or direction.approved_at is not None or direction.currentness != "current" or direction.brief_ref != brief_ref or direction.analysis_ref != analysis_ref or direction.feedback_refs != [*context["direction"].feedback_refs, ref(feedback)]):
                raise ValueError("Refinement must produce the next unapproved draft")
            invalidate(state, direction_id)
            state.directions.append(direction)
            state.task.chosen_direction = ref(direction)
            feedback.status, feedback.resulting_direction = "applied", ref(direction)
            feedback.explanation = "The saved instruction produced a new draft. Review and explicitly approve this revision."
            job.result_ref, job.result_type = ref(direction), "direction"
        return self._run(task_id, version, "refine", prepare, lambda c, job_id: self._creative_execute(c, job_id, "refine_direction"), finish, editor_scopes=("analysis", "direction-" + direction_id))

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
            self._require_language(state)
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
        return self._update(task_id, version, change, require_m2_ready=True, require_editors_clear=("analysis", "direction-" + direction_id))

    def generate_outputs(self, task_id, version, direction_ref, brief_ref, analysis_ref):
        def prepare(state):
            brief, analysis, direction = self._direction(state, direction_ref, brief_ref, analysis_ref, approved=True)
            return {"brief": brief, "analysis": analysis, "direction": direction, "input_refs": {"brief": brief_ref, "analysis": analysis_ref, "direction": direction_ref}}
        def finish(state, outputs, context, job):
            production, storyboard = outputs
            bundle_id = uid("bundle")
            for output in (production, storyboard):
                output.bundle_id = bundle_id
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
        return self._run(task_id, version, "production", prepare, lambda c, job_id: self._creative_execute(c, job_id, "generate_production"), finish, editor_scopes=("analysis", "direction-" + direction_ref.id, "production"))

    def edit_outputs(self, task_id, version, production_brief_ref, storyboard_ref, brief_fields, rows, expected_editor_version=None):
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
            brief = m.ProductionCreativeBrief.model_validate(brief.model_dump())
            story = m.TextStoryboard.model_validate(story.model_dump())
            if brief.model_dump() == old_brief.model_dump() and story.model_dump() == old_story.model_dump():
                return False
            brief.bundle_id = story.bundle_id = uid("bundle")
            for updated, old, history in ((brief, old_brief, state.production_briefs), (story, old_story, state.storyboards)):
                old.currentness = "outdated"
                updated.revision = max(o.revision for o in history) + 1
                updated.edited = True
                updated.created_at = updated.updated_at = now()
                history.append(type(updated).model_validate(updated.model_dump()))
            state.task.current_production_brief, state.task.current_storyboard = ref(brief), ref(story)
        return self._update(task_id, version, change, editor_checkpoint=("production", expected_editor_version))

    def export(self, task_id, kind, output_id=None, revision=None, *, with_filename=False):
        state = self.store.get(task_id)
        if (output_id is None) != (revision is None):
            raise WorkflowError("invalid_export_reference", "Supply both output_id and revision for a historical export.", 422)
        requested = m.VersionRef(id=output_id, revision=revision) if output_id is not None else None
        if requested is None and self.store.get_editor_draft(task_id, "production").has_pending_changes:
            raise WorkflowError("editor_pending_changes", "Save the production draft before exporting the current output.")
        deleted = {video.video_id for video in state.videos if video.deleted_at is not None}
        def evidence_note(item):
            return " [reference media deleted]" if item.video_id in deleted else ""
        def status_label(output):
            return "HISTORICAL VERSION / does not reflect latest inputs" if output.currentness == "outdated" else "current"
        def document(text, output):
            history = "historical-" if output.currentness == "outdated" else ""
            stem, extension = kind.rsplit(".", 1)
            filename = f"{history}{stem}-{output.output_id}-r{output.revision}.{extension}"
            return (text, filename) if with_filename else text
        if kind == "brief.md":
            output = find(state.production_briefs, requested or state.task.current_production_brief)
            lines = [f"# {md(output.title)}", "", f"Origin: {md(output.origin.kind)} — {md(output.origin.description)}", f"Status: {status_label(output)}; output {output.output_id} revision {output.revision}", context_line(output), ""]
            for title, value in (("Core message", output.core_message), ("Hook", output.hook), ("Narrative", output.narrative), ("CTA", output.cta), ("Production notes", "\n".join(output.production_notes))):
                lines.extend([f"## {title}", "", md(value), ""])
            lines.extend(["## Reference evidence", "", *[md(f"{e.event_id} ({e.analysis_id} revision {e.analysis_revision}, video {e.video_id}): {e.reason}{evidence_note(e)}") for e in output.evidence]])
            return document("\n".join(lines), output)
        if kind == "storyboard.csv":
            output = find(state.storyboards, requested or state.task.current_storyboard)
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(["origin", "status", "output_id", "revision", "input_versions", "row_id", "planned_start_seconds", "planned_end_seconds", "visual", "dialogue", "on_screen_text", "sound", "cta", "reference_evidence"])
            for row in output.rows:
                values = [output.origin.kind, status_label(output), output.output_id, output.revision, context_line(output), row.row_id, row.start_seconds, row.end_seconds, row.visual, row.dialogue, row.on_screen_text, row.sound, row.cta, "; ".join(f"{e.analysis_id}@{e.analysis_revision}/{e.video_id}/{e.event_id}: {e.reason}{evidence_note(e)}" for e in row.evidence) or "Original production suggestion (no reference citation)"]
                writer.writerow([csv_safe(value) for value in values])
            return document(stream.getvalue(), output)
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
