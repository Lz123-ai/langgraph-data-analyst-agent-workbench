from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.improvements.models import (
    ImprovementLogCreate,
    ImprovementLogEntry,
    ImprovementLogListResponse,
    ImprovementLogUpdate,
)
from app.improvements.service import improvement_log_service
from app.ops.models import IdentityContext
from app.security import identity_from_request

router = APIRouter(prefix="/api/improvements", tags=["improvements"])


@router.post("", response_model=ImprovementLogEntry, status_code=status.HTTP_201_CREATED)
def create_improvement_log(
    payload: ImprovementLogCreate,
    identity: IdentityContext = Depends(identity_from_request),
) -> ImprovementLogEntry:
    return improvement_log_service.create_log(payload, identity)


@router.get("", response_model=ImprovementLogListResponse)
def list_improvement_logs(
    limit: int = 50,
    identity: IdentityContext = Depends(identity_from_request),
) -> ImprovementLogListResponse:
    return ImprovementLogListResponse(logs=improvement_log_service.list_logs(limit=limit, identity=identity))


@router.get("/{log_id}", response_model=ImprovementLogEntry)
def get_improvement_log(
    log_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> ImprovementLogEntry:
    return improvement_log_service.get_log(log_id, identity)


@router.patch("/{log_id}", response_model=ImprovementLogEntry)
def update_improvement_log(
    log_id: str,
    payload: ImprovementLogUpdate,
    identity: IdentityContext = Depends(identity_from_request),
) -> ImprovementLogEntry:
    return improvement_log_service.update_log(log_id, payload, identity)


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_improvement_log(
    log_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> Response:
    improvement_log_service.delete_log(log_id, identity)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
