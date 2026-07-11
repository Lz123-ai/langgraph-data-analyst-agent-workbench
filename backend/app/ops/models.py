from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OpsTaskStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
TraceStatus = Literal["running", "succeeded", "failed"]
SpanType = Literal["task", "node", "tool", "llm", "system"]


class IdentityContext(BaseModel):
    tenant_id: str = Field(default="local", min_length=1, max_length=64)
    user_id: str = Field(default="local-user", min_length=1, max_length=64)


class AgentTaskRecord(BaseModel):
    task_id: str
    trace_id: str
    tenant_id: str
    user_id: str
    dataset_id: str
    question: str
    status: OpsTaskStatus
    model_name: str | None = None
    prompt_version: str | None = None
    token_budget: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error: str | None = None
    final_state: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class TraceSpanRecord(BaseModel):
    span_id: str
    trace_id: str
    task_id: str
    parent_span_id: str | None = None
    span_type: SpanType
    name: str
    status: TraceStatus
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class TokenUsageRecord(BaseModel):
    usage_id: str
    trace_id: str
    task_id: str
    node: str | None = None
    model_name: str
    prompt_version: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    source: Literal["estimated", "provider"] = "estimated"
    created_at: datetime


class NodePayloadMetricRecord(BaseModel):
    metric_id: str
    trace_id: str
    task_id: str
    node: str
    input_chars: int
    output_chars: int
    output_bytes: int
    output_rows: int = 0
    created_at: datetime


class EvalRunRecord(BaseModel):
    eval_run_id: str
    status: Literal["succeeded", "failed"]
    total: int
    passed: int
    failed: int
    source_path: str | None = None
    result_json: dict[str, Any]
    created_at: datetime


class AgentOpsSummary(BaseModel):
    task_count: int
    running_count: int
    succeeded_count: int
    failed_count: int
    total_tokens: int
    estimated_cost_usd: float
    deterministic_payload_bytes: int = 0
    latest_eval: EvalRunRecord | None = None


class AgentTaskListResponse(BaseModel):
    tasks: list[AgentTaskRecord]


class AgentTaskDetailResponse(BaseModel):
    task: AgentTaskRecord
    trace: list[TraceSpanRecord]
    token_usage: list[TokenUsageRecord]
    payload_metrics: list[NodePayloadMetricRecord] = Field(default_factory=list)


class TraceListResponse(BaseModel):
    trace: list[TraceSpanRecord]


class TokenUsageListResponse(BaseModel):
    usage: list[TokenUsageRecord]


class EvalRunListResponse(BaseModel):
    eval_runs: list[EvalRunRecord]


class ModelRuntimeStatusResponse(BaseModel):
    enabled: bool
    provider: str
    model: str
    base_url_configured: bool
    api_key_configured: bool
    configuration_error: str | None = None


class ModelSmokeTestResponse(BaseModel):
    ok: bool
    provider: str
    model: str
