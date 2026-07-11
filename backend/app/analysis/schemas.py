from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalysisCreateRequest(BaseModel):
    dataset_id: str
    question: str = Field(min_length=2, max_length=1000)


class AnalysisTaskResponse(BaseModel):
    task_id: str
    status: str


class AnalysisCancelResponse(BaseModel):
    task_id: str
    status: str


class AnalysisTaskStatusResponse(BaseModel):
    task_id: str
    trace_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    dataset_id: str
    question: str
    status: str
    total_tokens: int = 0
    estimated_cost_usd: float = 0
    error: str | None = None
    final_state: dict[str, Any] | None = None
