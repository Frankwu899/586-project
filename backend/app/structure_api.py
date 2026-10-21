"""Mount the independent Structure API without changing canonical task records."""
from fastapi import APIRouter

from .structure_models import (AdoptRequest, AnalyzeRequest, FeedbackRequest,
                               Handoff, HandoffRequest, Workspace)
from .structure_service import StructureService


def install_structure_api(app, workflow, *, service=None):
    service = service or StructureService(workflow)
    app.state.structure_service = service
    router = APIRouter(prefix="/api/tasks/{task_id}/structure", tags=["Structure"])

    @router.get("", response_model=Workspace | None)
    def get_structure(task_id: str):
        return service.get(task_id)

    @router.post("/analyze", response_model=Workspace, status_code=202)
    def analyze(task_id: str, body: AnalyzeRequest):
        return service.analyze(task_id, body)

    @router.post("/feedback", response_model=Workspace, status_code=202)
    def feedback(task_id: str, body: FeedbackRequest):
        return service.feedback(task_id, body)

    @router.post("/proposals/{proposal_id}/adopt", response_model=Workspace)
    def adopt(task_id: str, proposal_id: str, body: AdoptRequest):
        return service.adopt(task_id, proposal_id, body)

    @router.post("/handoff", response_model=Handoff)
    def handoff(task_id: str, body: HandoffRequest):
        return service.handoff(task_id, body)

    @router.get("/handoff", response_model=Handoff | None)
    def get_handoff(task_id: str):
        return service.get_handoff(task_id)

    app.include_router(router)
    return service
