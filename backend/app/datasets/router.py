from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.datasets.models import (
    DatasetDetailResponse,
    DatasetListResponse,
    DatasetPreviewResponse,
    DatasetUploadResponse,
)
from app.datasets.service import dataset_service
from app.ops.models import IdentityContext
from app.security import identity_from_request

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    identity: IdentityContext = Depends(identity_from_request),
) -> DatasetUploadResponse:
    dataset, profile, preview = await dataset_service.save_upload(file, identity)
    return DatasetUploadResponse(dataset=dataset, profile=profile, preview=preview)


@router.get("", response_model=DatasetListResponse)
def list_datasets(identity: IdentityContext = Depends(identity_from_request)) -> DatasetListResponse:
    return DatasetListResponse(datasets=dataset_service.list_datasets(identity))


@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(
    dataset_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> DatasetDetailResponse:
    dataset, profile = dataset_service.get_dataset(dataset_id, identity)
    return DatasetDetailResponse(dataset=dataset, profile=profile)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    dataset_id: str,
    limit: int = 20,
    identity: IdentityContext = Depends(identity_from_request),
) -> DatasetPreviewResponse:
    columns, rows = dataset_service.preview(dataset_id, limit=max(1, min(limit, 100)), identity=identity)
    return DatasetPreviewResponse(dataset_id=dataset_id, columns=columns, rows=rows)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_dataset(
    dataset_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> Response:
    dataset_service.delete_dataset(dataset_id, identity)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
