from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse

from app.llm.health import model_runtime_status, run_model_smoke_test
from app.observability import metrics
from app.ops.models import (
    AgentOpsSummary,
    AgentTaskDetailResponse,
    AgentTaskListResponse,
    EvalRunListResponse,
    EvalRunRecord,
    IdentityContext,
    ModelRuntimeStatusResponse,
    ModelSmokeTestResponse,
    TokenUsageListResponse,
    TraceListResponse,
)
from app.ops.service import agent_ops_service
from app.runtime.task_store import task_store
from app.security import identity_from_request

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/model-status", response_model=ModelRuntimeStatusResponse)
def get_model_status(_: IdentityContext = Depends(identity_from_request)) -> ModelRuntimeStatusResponse:
    return ModelRuntimeStatusResponse(**model_runtime_status())


@router.post("/model-smoke-test", response_model=ModelSmokeTestResponse)
def model_smoke_test(_: IdentityContext = Depends(identity_from_request)) -> ModelSmokeTestResponse:
    return ModelSmokeTestResponse(**run_model_smoke_test())


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def get_metrics(_: IdentityContext = Depends(identity_from_request)) -> PlainTextResponse:
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/summary", response_model=AgentOpsSummary)
def get_ops_summary(identity: IdentityContext = Depends(identity_from_request)) -> AgentOpsSummary:
    return agent_ops_service.summary(identity)


@router.get("/tasks", response_model=AgentTaskListResponse)
def list_agent_tasks(
    limit: int = 50,
    identity: IdentityContext = Depends(identity_from_request),
) -> AgentTaskListResponse:
    return AgentTaskListResponse(
        tasks=agent_ops_service.list_tasks(
            limit=limit,
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
        )
    )


@router.get("/tasks/{task_id}", response_model=AgentTaskDetailResponse)
def get_agent_task(
    task_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> AgentTaskDetailResponse:
    task, trace, usage = agent_ops_service.get_task_detail(task_id, identity)
    return AgentTaskDetailResponse(
        task=task,
        trace=trace,
        token_usage=usage,
        payload_metrics=agent_ops_service.list_payload_metrics(task_id, identity),
    )


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_agent_task(
    task_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> Response:
    agent_ops_service.require_task(task_id, identity)
    try:
        task_store.delete_task(task_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    agent_ops_service.delete_task(task_id, identity)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}/trace", response_model=TraceListResponse)
def list_task_trace(
    task_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> TraceListResponse:
    return TraceListResponse(trace=agent_ops_service.list_trace(task_id, identity))


@router.get("/tasks/{task_id}/tokens", response_model=TokenUsageListResponse)
def list_task_tokens(
    task_id: str,
    identity: IdentityContext = Depends(identity_from_request),
) -> TokenUsageListResponse:
    return TokenUsageListResponse(usage=agent_ops_service.list_token_usage(task_id=task_id, identity=identity))


@router.get("/tokens", response_model=TokenUsageListResponse)
def list_token_usage(
    limit: int = 100,
    identity: IdentityContext = Depends(identity_from_request),
) -> TokenUsageListResponse:
    return TokenUsageListResponse(usage=agent_ops_service.list_token_usage(limit=limit, identity=identity))


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
