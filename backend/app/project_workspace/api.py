"""Local project HTTP boundary and durable, non-replaying background operations."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
import mimetypes
import threading
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import Field

from ..storage import WorkflowError
from .models import Model, Project, Fact, ExtractedBlock, EvidenceEvent, Job, now


class Mutation(Model):
    expected_version: int = Field(ge=1)


class Create(Model):
    title: str = Field(default="Untitled project", min_length=1, max_length=200)


class Patch(Mutation):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    workspace: Literal["overview", "resources", "discover", "analysis", "content", "production"] | None = None
    active_content_id: str | None = None
    conversation_draft: str | None = Field(default=None, max_length=30000)
    editor_drafts: dict[str, dict] | None = None
    expected_editor_versions: dict[str, int] = Field(default_factory=dict)


class MessageBody(Mutation):
    text: str = Field(min_length=1, max_length=30000)
    resource_ids: list[str] = Field(default_factory=list, max_length=30)


class FactsBody(Mutation):
    facts: list[Fact] = Field(max_length=100)
    expected_draft_version: int | None = Field(default=None, ge=1)


class BlocksBody(Mutation):
    blocks: list[ExtractedBlock] = Field(max_length=4000)
    base_revision: int | None = Field(default=None, ge=1)
    expected_editor_version: int | None = Field(default=None, ge=0)


class EvidenceBody(Mutation):
    events: list[EvidenceEvent] = Field(max_length=10000)
    reviewed: bool = False
    base_revision: int | None = Field(default=None, ge=1)
    expected_editor_version: int | None = Field(default=None, ge=0)


class SelectionBody(Mutation):
    resource_ids: list[str] = Field(max_length=30)
    content_id: str | None = None
    visual_only: bool = False


class SeriesBody(Mutation):
    title: str = Field(min_length=1, max_length=200)
    concept: str = Field(default="", max_length=10000)


class ContentBody(Mutation):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    series_id: str | None = None


class GenerateBody(Mutation):
    instruction: str = Field(default="", max_length=10000)
    visual_only: bool = False


class DirectionBody(Mutation):
    title: str = Field(min_length=1, max_length=200)
    concept: str = Field(min_length=1, max_length=20000)
    hook: str = Field(default="", max_length=10000)
    narrative: str = Field(default="", max_length=20000)
    cta: str = Field(default="", max_length=10000)


class DirectionEdit(Mutation):
    revision: int = Field(ge=1)
    fields: dict[str, str]
    expected_editor_version: int | None = Field(default=None, ge=0)


class Approval(Mutation):
    revision: int = Field(ge=1)


class PackBody(Approval):
    expected_editor_version: int | None = Field(default=None, ge=0)
    production_brief: str = Field(max_length=100000)
    script: str = Field(max_length=100000)
    storyboard: str = Field(max_length=100000)
    shot_list: str = Field(max_length=100000)


class ProjectRuntime:
    def __init__(self, legacy_service):
        from .store import ProjectStore
        from .resources import ResourceService
        from .conversation import ConversationService
        from .analysis import AnalysisService
        from .planning import PlanningService
        self.legacy_service = legacy_service
        self.store = ProjectStore(legacy_service.store.path.parent)
        self.resources = ResourceService(self.store, self.settings)
        self.conversation = ConversationService(self.store, self.settings)
        self.analysis = AnalysisService(self.store, self.settings)
        self.planning = PlanningService(self.store, self.settings)
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="project-work")
        self.lock = threading.RLock()
        self.migration_errors: list[str] = []
        try:
            self.store.migrate_legacy(legacy_service)
        except (OSError, ValueError, WorkflowError):
            # Existing task APIs still expose the intact source library.
            self.migration_errors.append("Some older projects could not be imported. Their original library is intact; open the legacy workspace to inspect them.")
        self.migration_errors.extend(getattr(self.store, "migration_errors", []))

    def settings(self):
        # Read current user credentials on every operation, including after a
        # session/Keychain connection change. Never inherit a stale Luna default.
        return replace(self.legacy_service.provider_settings, vision_model="gpt-6.1-sol",
                       creative_model="gpt-6.1-sol", m2_model="gpt-6.1-sol",
                       structure_model="gpt-6.1-sol", research_model="gpt-6.1-sol")

    def submit(self, project_id, expected_version, kind, callback, *, resource_id=None, content_id=None):
        job = Job(kind=kind, resource_id=resource_id, content_id=content_id)
        with self.lock:
            def admit(project):
                if any(item.status in ("queued", "running") and item.kind == kind
                       and item.resource_id == resource_id and item.content_id == content_id for item in project.jobs):
                    raise WorkflowError("project_busy", "This operation is already running. Its progress is saved.", 409)
                project.jobs.append(job)
            admitted = self.store.update(project_id, expected_version, admit)
            try:
                self.executor.submit(self._run, project_id, job.id, callback)
            except RuntimeError as exc:
                def rejected(project):
                    queued = next(item for item in project.jobs if item.id == job.id)
                    queued.status, queued.progress = "failed", "Not started"
                    queued.error = "The application is closing. Saved work is intact; reopen and retry."
                self.store.update(project_id, None, rejected)
                raise WorkflowError("project_job_unavailable", "The application is closing. Reopen and retry.", 503) from exc
            return admitted

    def _run(self, project_id, job_id, callback):
        before_jobs = {job.id for job in self.store.get(project_id).jobs}
        def running(project):
            job = next(item for item in project.jobs if item.id == job_id)
            job.status, job.progress, job.updated_at = "running", "Processing", now()
        try:
            self.store.update(project_id, None, running)
            callback()
        except Exception as exc:
            from .speech_retry import public_failure
            code, safe = public_failure(exc)
            def failed(project):
                job = next(item for item in project.jobs if item.id == job_id)
                job.status, job.progress, job.error, job.updated_at = "failed", "Failed", safe, now()
                job.error_code = code
            self.store.update(project_id, None, failed)
        else:
            def completed(project):
                job = next(item for item in project.jobs if item.id == job_id)
                resource = next((r for r in project.resources if r.id == job.resource_id), None)
                failed_children = [child for child in project.jobs if child.id not in before_jobs
                                   and child.kind == "reference_extraction" and child.content_id == job.content_id
                                   and child.status in ("failed", "partial")]
                if job.kind == "recognize" and failed_children:
                    child = failed_children[-1]
                    job.status, job.progress, job.error = child.status, child.progress, child.error
                    job.error_code = child.error_code
                elif job.kind == "analyze" and failed_children:
                    job.status, job.progress = "partial", "Completed with source limitations"
                elif resource is not None and resource.status in ("failed", "unsupported", "missing"):
                    job.status, job.progress, job.error = "failed", "Needs attention", resource.error
                elif resource is not None and resource.status == "partial":
                    job.status, job.progress = "partial", "Completed with limitations"
                else:
                    job.status, job.progress = "succeeded", "Complete"
                job.updated_at = now()
            self.store.update(project_id, None, completed)

    def refresh(self, project_id):
        project = self.store.get(project_id)
        missing = []
        for resource in project.resources:
            try:
                path = self.store.resolve_path(project_id, resource.original_path)
                if not path.is_file():
                    raise OSError("missing original")
            except (WorkflowError, OSError):
                if resource.status != "missing":
                    missing.append(resource.id)
        if missing:
            def mark(state):
                for resource in state.resources:
                    if resource.id in missing:
                        resource.status = "missing"
                        resource.error = "The project original is missing. Relink the same file to restore it."
            return self.store.update(project_id, None, mark)
        return project


def install_project_workspace(app, legacy_service):
    runtime = ProjectRuntime(legacy_service)
    app.state.project_workspace = runtime
    legacy_service.project_workspace = runtime
    router = APIRouter(prefix="/api/projects", tags=["Projects 1.8"])

    @router.get("/capabilities")
    def capabilities():
        from ..release import release_info
        return {**release_info(), "model": "gpt-6.1-sol", "transcription_model": runtime.settings().transcription_model,
                "configured": bool(runtime.settings().api_key), "migration_errors": runtime.migration_errors,
                "library_errors": getattr(runtime.store, "library_errors", []),
                "discovery": "Reserved — awaiting Frank’s specification."}

    @router.get("", response_model=list[Project])
    def projects(trashed: bool = False):
        return [p for p in runtime.store.list(include_trashed=trashed) if bool(p.trashed_at) == trashed]

    @router.post("", response_model=Project, status_code=201)
    def create(body: Create):
        return runtime.store.create(body.title.strip() or "Untitled project")

    @router.get("/{project_id}", response_model=Project)
    def get(project_id: str):
        return runtime.refresh(project_id)

    @router.patch("/{project_id}", response_model=Project)
    def patch(project_id: str, body: Patch):
        def change(project):
            before = project.model_dump()
            for scope, expected in body.expected_editor_versions.items():
                if project.editor_draft_versions.get(scope, 0) != expected:
                    raise WorkflowError("editor_draft_conflict", "This draft changed elsewhere. Your text is retained; review the saved version before replacing it.", 409)
            values = body.model_dump(exclude_unset=True, exclude={"expected_version", "editor_drafts", "expected_editor_versions"})
            if "active_content_id" in values and values["active_content_id"] is not None and not any(c.id == values["active_content_id"] for c in project.contents):
                raise WorkflowError("content_not_found", "Choose a content item in this project.", 404)
            for key, value in values.items():
                if key != "active_content_id" and value is None:
                    continue
                setattr(project, key, value)
            if body.editor_drafts is not None:
                if any(key.startswith("conversation_") for key in body.editor_drafts):
                    raise WorkflowError("invalid_draft_scope", "This draft scope is managed by the conversation service.", 422)
                project.editor_drafts.update(body.editor_drafts)
            return project.model_dump() != before
        return runtime.store.update(project_id, body.expected_version, change)

    @router.post("/{project_id}/duplicate", response_model=Project)
    def duplicate(project_id: str, body: Mutation):
        return runtime.store.duplicate(project_id, body.expected_version)

    @router.post("/{project_id}/trash", response_model=Project)
    def trash(project_id: str, body: Mutation):
        return runtime.store.trash(project_id, body.expected_version)

    @router.post("/{project_id}/restore", response_model=Project)
    def restore(project_id: str, body: Mutation):
        return runtime.store.restore(project_id, body.expected_version)

    @router.post("/{project_id}/cache/clear", response_model=Project)
    def clear_cache(project_id: str, body: Mutation):
        return runtime.store.clear_cache(project_id, body.expected_version)

    @router.post("/{project_id}/messages", response_model=Project, status_code=202)
    def message(project_id: str, body: MessageBody):
        with runtime.lock:
            current = runtime.store.get(project_id)
            if any(j.kind == "conversation" and j.status in ("queued", "running") for j in current.jobs):
                raise WorkflowError("conversation_busy", "A reply is already in progress. Your composer draft is retained.", 409)
            _, message_id = runtime.conversation.begin_message(project_id, body.expected_version, body.text, body.resource_ids)
            try:
                return runtime.submit(project_id, None, "conversation", lambda: runtime.conversation.respond(project_id, message_id))
            except WorkflowError:
                runtime.conversation._failure(project_id, message_id, "Your message is saved. Assistance could not start; retry after reopening the project.")
                raise

    @router.post("/{project_id}/brief/draft", response_model=Project)
    def brief_draft(project_id: str, body: FactsBody):
        return runtime.conversation.save_brief_draft(project_id, body.expected_version, body.facts, expected_draft_version=body.expected_draft_version)

    @router.post("/{project_id}/brief/apply", response_model=Project)
    def brief_apply(project_id: str, body: FactsBody):
        return runtime.conversation.apply_brief(project_id, body.expected_version, body.facts, expected_draft_version=body.expected_draft_version)

    @router.post("/{project_id}/resources", response_model=Project, status_code=202)
    def upload(project_id: str, file: Annotated[UploadFile, File()], expected_version: Annotated[int, Form(ge=1)],
               role: Annotated[Literal["reference", "document", "asset"], Form()] = "reference"):
        with runtime.lock:
            state = runtime.resources.import_file(project_id, expected_version, file.filename or "upload", file.file, role=role)
            resource_id = state.resources[-1].id
            return runtime.submit(project_id, None, "extract", lambda: runtime.resources.extract(project_id, resource_id), resource_id=resource_id)

    @router.get("/{project_id}/resources/{resource_id}/file")
    def resource_file(project_id: str, resource_id: str, representation: Literal["original", "playback", "thumbnail"] = "original"):
        project = runtime.store.get(project_id)
        resource = next((item for item in project.resources if item.id == resource_id), None)
        if resource is None:
            raise WorkflowError("resource_not_found", "This resource does not belong to the project.", 404)
        path = runtime.resources.path(project_id, resource_id, representation)
        media_type = ((mimetypes.guess_type(path.name)[0] or "application/octet-stream") if representation == "thumbnail" else
                      "video/mp4" if representation == "playback" and path.suffix == ".mp4" else resource.mime_type)
        inline = resource.kind in ("video", "audio", "image") and media_type != "image/svg+xml"
        return FileResponse(path, media_type=media_type, filename=None if inline else resource.name,
                            headers={"Cache-Control": "private, max-age=0", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})

    @router.post("/{project_id}/resources/{resource_id}/extract", response_model=Project, status_code=202)
    def extract(project_id: str, resource_id: str, body: Mutation):
        return runtime.submit(project_id, body.expected_version, "extract", lambda: runtime.resources.extract(project_id, resource_id), resource_id=resource_id)

    @router.post("/{project_id}/resources/{resource_id}/recognize", response_model=Project, status_code=202)
    def recognize(project_id: str, resource_id: str, body: Mutation):
        return runtime.submit(project_id, body.expected_version, "recognize",
                              lambda: runtime.analysis.retry_reference(project_id, resource_id), resource_id=resource_id)

    @router.post("/{project_id}/resources/{resource_id}/relink", response_model=Project)
    def relink(project_id: str, resource_id: str, file: Annotated[UploadFile, File()], expected_version: Annotated[int, Form(ge=1)]):
        return runtime.resources.relink(project_id, expected_version, resource_id, file.file)

    @router.post("/{project_id}/resources/{resource_id}/blocks", response_model=Project)
    def blocks(project_id: str, resource_id: str, body: BlocksBody):
        return runtime.resources.correct_blocks(project_id, body.expected_version, resource_id, body.blocks,
                                                base_revision=body.base_revision, expected_editor_version=body.expected_editor_version)

    @router.post("/{project_id}/resources/{resource_id}/evidence", response_model=Project)
    def evidence(project_id: str, resource_id: str, body: EvidenceBody):
        return runtime.analysis.correct_evidence(project_id, body.expected_version, resource_id, body.events, body.reviewed,
                                                 base_revision=body.base_revision, expected_editor_version=body.expected_editor_version)

    @router.post("/{project_id}/resources/{resource_id}/evidence/review", response_model=Project)
    def evidence_review(project_id: str, resource_id: str, body: Mutation):
        return runtime.analysis.review_evidence(project_id, body.expected_version, resource_id)

    @router.post("/{project_id}/selection", response_model=Project)
    def selection(project_id: str, body: SelectionBody):
        return runtime.analysis.set_selection(project_id, body.expected_version, body.resource_ids, body.content_id)

    @router.post("/{project_id}/analyze", response_model=Project, status_code=202)
    def analyze(project_id: str, body: SelectionBody):
        return runtime.submit(project_id, body.expected_version, "analyze", lambda: runtime.analysis.analyze(project_id, body.resource_ids, body.content_id, visual_only=body.visual_only), content_id=body.content_id)

    @router.post("/{project_id}/series", response_model=Project)
    def series(project_id: str, body: SeriesBody):
        return runtime.planning.create_series(project_id, body.expected_version, body.title, body.concept)

    @router.post("/{project_id}/contents", response_model=Project)
    def contents(project_id: str, body: ContentBody):
        return runtime.planning.create_content(project_id, body.expected_version, body.title, body.description, body.series_id)

    @router.post("/{project_id}/concepts/generate", response_model=Project, status_code=202)
    def concepts(project_id: str, body: GenerateBody):
        runtime.planning.preflight_generation(project_id, instruction=body.instruction, visual_only=body.visual_only)
        return runtime.submit(project_id, body.expected_version, "concepts", lambda: runtime.planning.generate_concepts(project_id, None, body.instruction, visual_only=body.visual_only))

    @router.post("/{project_id}/contents/{content_id}/directions/generate", response_model=Project, status_code=202)
    def directions_generate(project_id: str, content_id: str, body: GenerateBody):
        runtime.planning.preflight_generation(project_id, content_id, body.instruction, visual_only=body.visual_only)
        return runtime.submit(project_id, body.expected_version, "directions", lambda: runtime.planning.generate_directions(project_id, content_id, body.instruction, visual_only=body.visual_only), content_id=content_id)

    @router.post("/{project_id}/contents/{content_id}/directions", response_model=Project)
    def direction_create(project_id: str, content_id: str, body: DirectionBody):
        return runtime.planning.save_direction(project_id, body.expected_version, content_id, body.model_dump(exclude={"expected_version"}))

    @router.post("/{project_id}/contents/{content_id}/directions/{direction_id}/edit", response_model=Project)
    def direction_edit(project_id: str, content_id: str, direction_id: str, body: DirectionEdit):
        return runtime.planning.save_direction(project_id, body.expected_version, content_id, body.fields,
                                                direction_id=direction_id, direction_revision=body.revision,
                                                expected_editor_version=body.expected_editor_version)

    @router.post("/{project_id}/contents/{content_id}/directions/{direction_id}/approve", response_model=Project)
    def approve(project_id: str, content_id: str, direction_id: str, body: Approval):
        return runtime.planning.approve_direction(project_id, body.expected_version, content_id, direction_id, body.revision)

    @router.post("/{project_id}/contents/{content_id}/production/generate", response_model=Project, status_code=202)
    def production(project_id: str, content_id: str, body: Mutation):
        return runtime.submit(project_id, body.expected_version, "production", lambda: runtime.planning.generate_pack(project_id, content_id), content_id=content_id)

    @router.post("/{project_id}/contents/{content_id}/production/manual", response_model=Project)
    def production_manual(project_id: str, content_id: str, body: Mutation):
        return runtime.planning.create_manual_pack(project_id, body.expected_version, content_id)

    @router.post("/{project_id}/packs/{pack_id}", response_model=Project)
    def pack_save(project_id: str, pack_id: str, body: PackBody):
        return runtime.planning.save_pack(project_id, body.expected_version, pack_id, body.revision,
                                         body.model_dump(exclude={"expected_version", "revision", "expected_editor_version"}),
                                         expected_editor_version=body.expected_editor_version)

    @router.get("/{project_id}/packs/{pack_id}/export")
    def pack_export(project_id: str, pack_id: str, revision: Annotated[int, Query(ge=1)], format: Literal["markdown", "csv", "docx", "html"] = "markdown"):
        from .exports import export_pack
        data, mime, filename = export_pack(runtime.store, project_id, pack_id, revision, format)
        filename = Path(filename).name.replace('"', "").replace("\r", "").replace("\n", "")
        disposition = "inline" if format == "html" else "attachment"
        return Response(data, media_type=mime, headers={"Content-Disposition": f'{disposition}; filename="{filename}"', "X-Content-Type-Options": "nosniff"})

    app.include_router(router)
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application) as state:
            try:
                yield state
            finally:
                runtime.executor.shutdown(wait=False, cancel_futures=True)

    app.router.lifespan_context = lifespan
    return runtime
