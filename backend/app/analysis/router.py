from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse

from app.analysis.schemas import (
    AnalysisCancelResponse,
    AnalysisCreateRequest,
    AnalysisTaskResponse,
    AnalysisTaskStatusResponse,
)
from app.analysis.service import analysis_service
from app.ops.models import IdentityContext
from app.runtime.sse import event_stream
from app.runtime.task_store import task_store
from app.security import identity_from_request

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/tasks", response_model=AnalysisTaskResponse)
async def create_analysis_task(
    request: AnalysisCreateRequest,
    identity: IdentityContext = Depends(identity_from_request),
) -> AnalysisTaskResponse:
    task_id = analysis_service.create_task(
        request.dataset_id,
        request.question,
        identity=identity,
    )
    return AnalysisTaskResponse(task_id=task_id, status="queued")


@router.get("/tasks/{task_id}", response_model=AnalysisTaskStatusResponse)
def get_analysis_task(
    task_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> AnalysisTaskStatusResponse:
    analysis_service.require_access(task_id, identity)
    record = analysis_service.get_status(task_id)
    return AnalysisTaskStatusResponse(**record)


@router.get("/tasks/{task_id}/events")
async def stream_analysis_events(
    task_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    after: int = Query(default=0, ge=0),
    identity: IdentityContext = Depends(identity_from_request),
) -> StreamingResponse:
    analysis_service.require_access(task_id, identity)
    task_store.get(task_id)
    cursor = after
    if last_event_id and last_event_id.isdigit():
        cursor = max(cursor, int(last_event_id))
    return StreamingResponse(
        event_stream(task_store, task_id, after_sequence=cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/tasks/{task_id}/cancel", response_model=AnalysisCancelResponse)
def cancel_analysis_task(
    task_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> AnalysisCancelResponse:
    analysis_service.require_access(task_id, identity)
    return AnalysisCancelResponse(**analysis_service.cancel_task(task_id))


@router.post("/tasks/{task_id}/retry", response_model=AnalysisTaskResponse)
def retry_analysis_task(
    task_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> AnalysisTaskResponse:
    return AnalysisTaskResponse(**analysis_service.retry_task(task_id, identity))
