from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.datasets.models import DatasetDetailResponse, DatasetListResponse, DatasetPreviewResponse, DatasetUploadResponse
from app.datasets.service import dataset_service

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetUploadResponse:
    dataset, profile, preview = await dataset_service.save_upload(file)
    return DatasetUploadResponse(dataset=dataset, profile=profile, preview=preview)


@router.get("", response_model=DatasetListResponse)
def list_datasets() -> DatasetListResponse:
    return DatasetListResponse(datasets=dataset_service.list_datasets())


@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(dataset_id: str) -> DatasetDetailResponse:
    dataset, profile = dataset_service.get_dataset(dataset_id)
    return DatasetDetailResponse(dataset=dataset, profile=profile)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(dataset_id: str, limit: int = 20) -> DatasetPreviewResponse:
    columns, rows = dataset_service.preview(dataset_id, limit=max(1, min(limit, 100)))
    return DatasetPreviewResponse(dataset_id=dataset_id, columns=columns, rows=rows)
