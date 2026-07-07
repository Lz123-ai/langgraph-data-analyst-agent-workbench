from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.ops.models import (
    AgentOpsSummary,
    AgentTaskDetailResponse,
    AgentTaskListResponse,
    EvalRunListResponse,
    EvalRunRecord,
    TokenUsageListResponse,
    TraceListResponse,
)
from app.ops.service import agent_ops_service

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/summary", response_model=AgentOpsSummary)
def get_ops_summary() -> AgentOpsSummary:
    return agent_ops_service.summary()


@router.get("/tasks", response_model=AgentTaskListResponse)
def list_agent_tasks(limit: int = 50, tenant_id: str | None = None) -> AgentTaskListResponse:
    return AgentTaskListResponse(tasks=agent_ops_service.list_tasks(limit=limit, tenant_id=tenant_id))


@router.get("/tasks/{task_id}", response_model=AgentTaskDetailResponse)
def get_agent_task(task_id: str) -> AgentTaskDetailResponse:
    task, trace, usage = agent_ops_service.get_task_detail(task_id)
    return AgentTaskDetailResponse(task=task, trace=trace, token_usage=usage)


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_agent_task(task_id: str) -> Response:
    agent_ops_service.delete_task(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}/trace", response_model=TraceListResponse)
def list_task_trace(task_id: str) -> TraceListResponse:
    return TraceListResponse(trace=agent_ops_service.list_trace(task_id))


@router.get("/tasks/{task_id}/tokens", response_model=TokenUsageListResponse)
def list_task_tokens(task_id: str) -> TokenUsageListResponse:
    return TokenUsageListResponse(usage=agent_ops_service.list_token_usage(task_id=task_id))


@router.get("/tokens", response_model=TokenUsageListResponse)
def list_token_usage(limit: int = 100) -> TokenUsageListResponse:
    return TokenUsageListResponse(usage=agent_ops_service.list_token_usage(limit=limit))


@router.get("/eval-runs", response_model=EvalRunListResponse)
def list_eval_runs(limit: int = 20) -> EvalRunListResponse:
    return EvalRunListResponse(eval_runs=agent_ops_service.list_eval_runs(limit=limit))


@router.post("/eval-runs/import", response_model=EvalRunRecord, status_code=status.HTTP_201_CREATED)
def import_eval_run(path: str = Query(default="agent_eval/results/latest_eval.json")) -> EvalRunRecord:
    report_path = _resolve_eval_report_path(path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return agent_ops_service.record_eval_report(report, source_path=str(report_path))


def _resolve_eval_report_path(path: str) -> Path:
    root = Path(__file__).resolve().parents[3]
    report_path = (root / path).resolve()
    eval_root = (root / "agent_eval" / "results").resolve()
    if eval_root not in report_path.parents and report_path != eval_root:
        raise HTTPException(status_code=400, detail="Evaluation report path must stay under agent_eval/results.")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Evaluation report not found.")
    return report_path
