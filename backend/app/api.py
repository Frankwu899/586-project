"""Local HTTP boundary; editor drafts use their own independent version channel."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, UploadFile, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .media import MediaError
from .models import (M2ApplyRequest, M2ApplyResult, M2DiscardRequest, M2Draft, M2DraftUpdate,
                     Nonempty, TaskState, VersionRef, EditorDraft, EditorDraftUpdate, EditorDiscardRequest)
from .m2_assistance_models import M2AdoptRequest, M2AssistanceRequest, M2AssistanceResponse
from .service import WorkflowService
from .storage import WorkflowError


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CreateTask(Request):
    title: Nonempty


class Mutation(Request):
    expected_version: Annotated[int, Field(ge=1)]


class LanguageMutation(Mutation):
    generation_language: Literal["English", "Chinese"]


class SaveBrief(Mutation):
    brief: dict[str, Any]


class Recognize(Mutation):
    video_id: str | None = None


class AnalysisMutation(Mutation):
    analysis_ref: VersionRef


class CorrectAnalysis(AnalysisMutation):
    expected_editor_version: Annotated[int, Field(ge=1)] | None = None
    event_edits: list[dict[str, Any]] = Field(default_factory=list)
    segment_edits: list[dict[str, Any]] = Field(default_factory=list)


class Inputs(Mutation):
    brief_ref: VersionRef | None = None
    analysis_ref: VersionRef | None = None


class GenerateDirections(Inputs):
    use_reference: bool = True


class ManualDirection(Mutation):
    brief_ref: VersionRef
    fields: dict[str, str]


class OperationRequest(Request):
    operation: Literal["recognize", "directions", "refine", "production"]
    payload: dict[str, Any]


class DirectionMutation(Inputs):
    direction_revision: Annotated[int, Field(ge=1)]


class RefineDirection(DirectionMutation):
    instruction: Annotated[str, Field(min_length=1, max_length=10000)]


class ChooseDirection(Mutation):
    direction_revision: Annotated[int, Field(ge=1)]


class EditDirection(ChooseDirection):
    expected_editor_version: Annotated[int, Field(ge=1)] | None = None
    fields: dict[str, Any]


class GenerateOutputs(Inputs):
    direction_ref: VersionRef


class EditOutputs(Mutation):
    expected_editor_version: Annotated[int, Field(ge=1)] | None = None
    production_brief_ref: VersionRef
    storyboard_ref: VersionRef
    brief_fields: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] | None = None


def create_app(data_dir: Path | None = None, *, service: WorkflowService | None = None) -> FastAPI:
    app = FastAPI(title="Video Anatomy", version="0.7.0")
    svc = service or WorkflowService(Path(data_dir or os.getenv("VIDEO_ANATOMY_DATA_DIR", ".local-data")))
    app.state.service = svc

    @app.exception_handler(WorkflowError)
    async def workflow_error(_request, error):
        return JSONResponse(status_code=error.status, content={"error": {"code": error.code, "message": error.message, "retryable": error.retryable}})

    @app.exception_handler(MediaError)
    async def media_error(_request, error):
        status = 404 if error.code == "missing_media" else 422
        return JSONResponse(status_code=status, content={"error": {"code": error.code, "message": error.message, "retryable": False}})

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def invalid_request(_request, error):
        details = "; ".join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in error.errors())
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": details, "retryable": False}})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "schema_version": "0.7.0",
                "real_analysis": "configured" if svc.provider_settings.api_key else "unconfigured",
                "creative_generation": "provider_for_real_tasks" if svc.provider_settings.api_key else "unconfigured_for_real_tasks",
                "sample_workflow": "available_offline"}

    @app.get("/api/config")
    def config():
        settings = svc.media.settings
        return {"max_upload_bytes": settings.max_bytes, "max_duration_seconds": settings.max_duration_seconds, "max_width": settings.max_width, "max_height": settings.max_height, "supported_extensions": [".mp4"], "supported_video_codecs": ["h264", "hevc"], "supported_audio_codecs": ["aac"], "sample_refinement": "make it presenter-free",
                "language_assumption": "Source English/Chinese/mixed OCR and speech are preserved; live accuracy requires evaluation.",
                "analysis_output_language": svc.provider_settings.analysis_language,
                "creative_output_language": svc.provider_settings.creative_language}

    @app.get("/api/tasks", response_model=list[TaskState])
    def list_tasks():
        return svc.store.list()

    @app.post("/api/tasks", response_model=TaskState, status_code=201)
    def create_task(body: CreateTask):
        return svc.create(body.title)

    @app.get("/api/tasks/{task_id}", response_model=TaskState)
    def open_task(task_id: str):
        return svc.store.get(task_id)

    @app.post("/api/tasks/{task_id}/language", response_model=TaskState)
    def language(task_id: str, body: LanguageMutation):
        return svc.set_language(task_id, body.expected_version, body.generation_language)

    @app.get("/api/tasks/{task_id}/editors/{scope}", response_model=EditorDraft)
    def editor(task_id: str, scope: str):
        return svc.store.get_editor_draft(task_id, scope)

    @app.post("/api/tasks/{task_id}/editors/{scope}", response_model=EditorDraft)
    def editor_save(task_id: str, scope: str, body: EditorDraftUpdate):
        return svc.store.save_editor_draft(task_id, scope, body)

    @app.post("/api/tasks/{task_id}/editors/{scope}/discard", response_model=EditorDraft)
    def editor_discard(task_id: str, scope: str, body: EditorDiscardRequest):
        return svc.store.discard_editor_draft(task_id, scope, body.expected_draft_version)

    @app.post("/api/tasks/{task_id}/videos/{video_id}/delete", response_model=TaskState)
    def delete_video(task_id: str, video_id: str, body: Mutation):
        return svc.delete_video(task_id, body.expected_version, video_id)

    @app.post("/api/tasks/{task_id}/brief", response_model=TaskState)
    def brief(task_id: str, body: SaveBrief):
        if set(body.brief) & {"task_id", "brief_id", "revision", "schema_version", "created_at", "updated_at"}:
            raise WorkflowError("immutable_brief_field", "Brief identity, revision, and timestamps are managed by the server.", 422)
        return svc.save_brief(task_id, body.expected_version, body.brief)

    @app.get("/api/tasks/{task_id}/m2/draft", response_model=M2Draft)
    def m2_draft(task_id: str):
        return svc.store.get_m2_draft(task_id)

    @app.post("/api/tasks/{task_id}/m2/draft", response_model=M2Draft)
    def m2_save(task_id: str, body: M2DraftUpdate):
        return svc.store.save_m2_draft(task_id, body)

    @app.post("/api/tasks/{task_id}/m2/apply", response_model=M2ApplyResult)
    def m2_apply(task_id: str, body: M2ApplyRequest):
        return svc.apply_m2(task_id, body)

    @app.post("/api/tasks/{task_id}/m2/discard", response_model=M2Draft)
    def m2_discard(task_id: str, body: M2DiscardRequest):
        return svc.store.discard_m2_draft(task_id, body.expected_draft_version)

    @app.post("/api/tasks/{task_id}/m2/assist", response_model=M2AssistanceResponse)
    def m2_assist(task_id: str, body: M2AssistanceRequest):
        return svc.assist_m2(task_id, body)

    @app.post("/api/tasks/{task_id}/m2/adopt", response_model=M2Draft)
    def m2_adopt(task_id: str, body: M2AdoptRequest):
        return svc.store.adopt_m2_proposals(task_id, body)

    @app.post("/api/tasks/{task_id}/sample", response_model=TaskState)
    def sample(task_id: str, body: Mutation):
        return svc.load_sample(task_id, body.expected_version)

    @app.post("/api/tasks/{task_id}/video", response_model=TaskState)
    def upload(task_id: str, file: Annotated[UploadFile, File()], expected_version: Annotated[int, Form(ge=1)], source_url: Annotated[str | None, Form()] = None):
        return svc.upload(task_id, expected_version, file.filename or "upload.mp4", file.file, source_url)

    @app.get("/api/tasks/{task_id}/media/{video_id}")
    def media(task_id: str, video_id: str):
        state = svc.store.get(task_id)
        video = next((v for v in state.videos if v.video_id == video_id), None)
        if video is None:
            raise WorkflowError("video_not_found", "This video does not belong to the task.", 404)
        if video.deleted_at is not None:
            raise WorkflowError("video_deleted", "This reference media was deleted. Its historical observations are retained.", 410)
        return FileResponse(svc.media.playback_path_for(video), media_type="video/mp4", headers={"Cache-Control": "private, max-age=0"})

    @app.post("/api/tasks/{task_id}/recognize", response_model=TaskState)
    def recognize(task_id: str, body: Recognize):
        return svc.recognize(task_id, body.expected_version, body.video_id)

    @app.post("/api/tasks/{task_id}/analysis/correct", response_model=TaskState)
    def correct(task_id: str, body: CorrectAnalysis):
        return svc.correct_analysis(task_id, body.expected_version, body.analysis_ref, body.event_edits, body.segment_edits, body.expected_editor_version)

    @app.post("/api/tasks/{task_id}/analysis/confirm", response_model=TaskState)
    def confirm(task_id: str, body: AnalysisMutation):
        return svc.confirm_analysis(task_id, body.expected_version, body.analysis_ref)

    @app.post("/api/tasks/{task_id}/directions/generate", response_model=TaskState)
    def directions(task_id: str, body: GenerateDirections):
        return svc.generate_directions(task_id, body.expected_version, body.brief_ref, body.analysis_ref, use_reference=body.use_reference)

    @app.post("/api/tasks/{task_id}/directions/manual", response_model=TaskState)
    def manual_direction(task_id: str, body: ManualDirection):
        return svc.create_manual_direction(task_id, body.expected_version, body.brief_ref, body.fields)

    @app.post("/api/tasks/{task_id}/directions/{direction_id}/edit", response_model=TaskState)
    def direction_edit(task_id: str, direction_id: str, body: EditDirection):
        return svc.edit_direction(task_id, body.expected_version, direction_id, body.direction_revision, body.fields, body.expected_editor_version)

    @app.post("/api/tasks/{task_id}/directions/{direction_id}/refine", response_model=TaskState)
    def direction_refine(task_id: str, direction_id: str, body: RefineDirection):
        return svc.refine_direction(task_id, body.expected_version, direction_id, body.direction_revision, body.brief_ref, body.analysis_ref, body.instruction)

    @app.post("/api/tasks/{task_id}/directions/{direction_id}/select", response_model=TaskState)
    def direction_choose(task_id: str, direction_id: str, body: ChooseDirection):
        return svc.choose_direction(task_id, body.expected_version, direction_id, body.direction_revision)

    @app.post("/api/tasks/{task_id}/directions/{direction_id}/approve", response_model=TaskState)
    def direction_approve(task_id: str, direction_id: str, body: DirectionMutation):
        return svc.approve_direction(task_id, body.expected_version, direction_id, body.direction_revision, body.brief_ref, body.analysis_ref)

    @app.post("/api/tasks/{task_id}/outputs/generate", response_model=TaskState)
    def outputs(task_id: str, body: GenerateOutputs):
        return svc.generate_outputs(task_id, body.expected_version, body.direction_ref, body.brief_ref, body.analysis_ref)

    @app.post("/api/tasks/{task_id}/outputs/edit", response_model=TaskState)
    def outputs_edit(task_id: str, body: EditOutputs):
        return svc.edit_outputs(task_id, body.expected_version, body.production_brief_ref, body.storyboard_ref, body.brief_fields, body.rows, body.expected_editor_version)

    @app.get("/api/tasks/{task_id}/export/{kind}")
    def export(task_id: str, kind: str, output_id: str | None = None, revision: Annotated[int | None, Query(ge=1)] = None):
        text, filename = svc.export(task_id, kind, output_id, revision, with_filename=True)
        content_type = "text/csv" if kind == "storyboard.csv" else "text/markdown"
        return Response(content=text, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Content-Type-Options": "nosniff"})

    from .background_jobs import BackgroundOperations
    from .content_region import create_content_region_router
    from .media_repair import create_media_repair_router
    from .structure_api import install_structure_api

    operation_models = {"recognize": Recognize, "directions": GenerateDirections,
                        "refine": RefineDirection, "production": GenerateOutputs}

    def execute_operation(task_id, operation, payload):
        values = dict(payload)
        direction_id = values.pop("direction_id", None) if operation == "refine" else None
        body = operation_models[operation].model_validate(values)
        if operation == "recognize":
            return recognize(task_id, body)
        if operation == "directions":
            return directions(task_id, body)
        if operation == "refine":
            return direction_refine(task_id, direction_id, body)
        return outputs(task_id, body)

    operations = BackgroundOperations(svc.store, execute_operation)
    app.state.operations = operations

    @app.post("/api/tasks/{task_id}/operations", status_code=202)
    def start_operation(task_id: str, body: OperationRequest):
        values = dict(body.payload)
        if body.operation == "refine":
            if not isinstance(values.pop("direction_id", None), str):
                raise WorkflowError("direction_required", "Choose the direction to refine.", 422)
        operation_models[body.operation].model_validate(values)
        return operations.submit(task_id, body.operation, body.payload)

    @app.get("/api/tasks/{task_id}/operations")
    def list_operations(task_id: str):
        return operations.list(task_id)

    @app.get("/api/tasks/{task_id}/operations/{operation_id}")
    def get_operation(task_id: str, operation_id: str):
        return operations.get(task_id, operation_id)

    app.include_router(create_content_region_router(svc))
    app.include_router(create_media_repair_router(svc))
    install_structure_api(app, svc)
    return app


def __getattr__(name):
    # Uvicorn's `backend.app.api:app` remains supported, but importing the
    # factory from a packaged launcher must not create a second data store
    # relative to the (possibly read-only) application bundle.
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
