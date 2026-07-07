from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.domain import DatasetMetadata, DatasetProfile


class DatasetUploadResponse(BaseModel):
    dataset: DatasetMetadata
    profile: DatasetProfile
    preview: list[dict[str, Any]]


class DatasetDetailResponse(BaseModel):
    dataset: DatasetMetadata
    profile: DatasetProfile


class DatasetListResponse(BaseModel):
    datasets: list[DatasetMetadata]


class DatasetPreviewResponse(BaseModel):
    dataset_id: str
    columns: list[str]
    rows: list[dict[str, Any]]
