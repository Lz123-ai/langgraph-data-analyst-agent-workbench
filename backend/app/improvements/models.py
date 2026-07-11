from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ImprovementStatus = Literal["open", "resolved", "monitoring"]


class ImprovementLogCreate(BaseModel):
    issue: str = Field(min_length=2, max_length=1000)
    resolution: str = Field(min_length=2, max_length=2000)
    status: ImprovementStatus = "resolved"
    dataset_id: str | None = Field(default=None, max_length=64)
    related_question: str | None = Field(default=None, max_length=1000)


class ImprovementLogUpdate(BaseModel):
    issue: str | None = Field(default=None, min_length=2, max_length=1000)
    resolution: str | None = Field(default=None, min_length=2, max_length=2000)
    status: ImprovementStatus | None = None
    dataset_id: str | None = Field(default=None, max_length=64)
    related_question: str | None = Field(default=None, max_length=1000)


class ImprovementLogEntry(BaseModel):
    log_id: str
    tenant_id: str = "system"
    user_id: str = "system"
    issue: str
    resolution: str
    status: ImprovementStatus
    dataset_id: str | None = None
    related_question: str | None = None
    created_at: datetime
    updated_at: datetime


class ImprovementLogListResponse(BaseModel):
    logs: list[ImprovementLogEntry]
