from __future__ import annotations

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.analysis.schemas import AnalysisCreateRequest, AnalysisTaskResponse, AnalysisTaskStatusResponse
from app.ops.models import IdentityContext
from app.analysis.service import analysis_service
from app.runtime.sse import event_stream
from app.runtime.task_store import task_store

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/tasks", response_model=AnalysisTaskResponse)
async def create_analysis_task(
    request: AnalysisCreateRequest,
    x_tenant_id: str = Header(default="local"),
    x_user_id: str = Header(default="local-user"),
) -> AnalysisTaskResponse:
    task_id = analysis_service.create_task(
        request.dataset_id,
        request.question,
        identity=IdentityContext(tenant_id=x_tenant_id, user_id=x_user_id),
    )
    return AnalysisTaskResponse(task_id=task_id, status="queued")


@router.get("/tasks/{task_id}", response_model=AnalysisTaskStatusResponse)
def get_analysis_task(task_id: str) -> AnalysisTaskStatusResponse:
    record = analysis_service.get_status(task_id)
    return AnalysisTaskStatusResponse(**record)


@router.get("/tasks/{task_id}/events")
async def stream_analysis_events(task_id: str) -> StreamingResponse:
    task_store.get(task_id)
    return StreamingResponse(
        event_stream(task_store, task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
