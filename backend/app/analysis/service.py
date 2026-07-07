from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.datasets.service import DatasetService, dataset_service
from app.graph.state import AnalysisState
from app.graph.workflow import build_analysis_workflow
from app.ops.models import IdentityContext
from app.ops.service import AgentOpsService, agent_ops_service
from app.runtime.events import TaskEvent
from app.runtime.task_store import TaskStore, task_store


EVENT_PAYLOAD_KEYS = {
    "current_step",
    "profile",
    "question_understanding",
    "analysis_plan",
    "execution_path",
    "sql_queries",
    "generated_code",
    "execution_result",
    "charts",
    "insights",
    "review_notes",
    "report_markdown",
    "errors",
    "needs_clarification",
    "dataset_preview",
    "sub_questions",
}


class AnalysisService:
    def __init__(self, datasets: DatasetService, tasks: TaskStore, ops: AgentOpsService) -> None:
        self.datasets = datasets
        self.tasks = tasks
        self.ops = ops
        self.workflow = build_analysis_workflow()

    def create_task(self, dataset_id: str, question: str, identity: IdentityContext | None = None) -> str:
        metadata, _ = self.datasets.get_dataset(dataset_id)
        record = self.tasks.create(dataset_id=dataset_id, question=question)
        self.ops.create_task(
            task_id=record.task_id,
            dataset_id=dataset_id,
            question=question,
            identity=identity or IdentityContext(),
        )
        initial_state: AnalysisState = {
            "dataset_id": dataset_id,
            "file_path": metadata.file_path,
            "user_question": question,
            "profile": None,
            "messages": [],
            "analysis_plan": None,
            "execution_path": None,
            "sql_queries": [],
            "generated_code": [],
            "execution_result": None,
            "charts": [],
            "insights": [],
            "review_notes": [],
            "report_markdown": None,
            "errors": [],
            "needs_clarification": False,
            "current_step": "queued",
            "dataset_preview": [],
            "sub_questions": [],
        }
        asyncio.create_task(self._run_task(record.task_id, initial_state))
        return record.task_id

    def get_status(self, task_id: str) -> dict[str, Any]:
        ops_task = self.ops.require_task(task_id)
        final_state = ops_task.final_state
        try:
            runtime_record = self.tasks.get(task_id)
            final_state = runtime_record.final_state or final_state
            status = runtime_record.status
            error = runtime_record.error or ops_task.error
        except HTTPException:
            status = ops_task.status
            error = ops_task.error
        return {
            "task_id": ops_task.task_id,
            "trace_id": ops_task.trace_id,
            "tenant_id": ops_task.tenant_id,
            "user_id": ops_task.user_id,
            "dataset_id": ops_task.dataset_id,
            "question": ops_task.question,
            "status": status,
            "total_tokens": ops_task.total_tokens,
            "estimated_cost_usd": ops_task.estimated_cost_usd,
            "error": error,
            "final_state": final_state,
        }

    async def _run_task(self, task_id: str, initial_state: AnalysisState) -> None:
        final_state: dict[str, Any] = dict(initial_state)
        task_started_at = _now()
        node_started_at = task_started_at
        self.ops.mark_running(task_id)
        await self.tasks.publish(
            TaskEvent(
                task_id=task_id,
                event_type="task_started",
                status="running",
                node=None,
                message="分析任务已开始。",
                payload={"dataset_id": initial_state["dataset_id"], "question": initial_state["user_question"]},
            )
        )
        try:
            async for update in self.workflow.astream(initial_state, stream_mode="updates"):
                for node_name, partial in update.items():
                    if not isinstance(partial, dict):
                        continue
                    node_ended_at = _now()
                    duration_ms = _duration_ms(node_started_at, node_ended_at)
                    input_summary = _state_summary(final_state)
                    final_state.update(partial)
                    self.ops.record_trace_span(
                        task_id=task_id,
                        name=node_name,
                        span_type="node",
                        status="succeeded",
                        started_at=node_started_at,
                        ended_at=node_ended_at,
                        duration_ms=duration_ms,
                        input_summary=input_summary,
                        output_summary=_payload_summary(partial),
                        metadata={"payload_keys": sorted(partial.keys())},
                    )
                    self.ops.record_estimated_token_usage(
                        task_id=task_id,
                        node=node_name,
                        prompt_text=f"{initial_state['user_question']}\n{input_summary}",
                        completion_payload=partial,
                    )
                    _raise_if_token_budget_exceeded(task_id, self.ops)
                    await self.tasks.publish(
                        TaskEvent(
                            task_id=task_id,
                            event_type="node_completed",
                            status="running",
                            node=node_name,
                            message=f"节点 {_node_label(node_name)} 已完成。",
                            payload=_event_payload(partial),
                        )
                    )
                    node_started_at = node_ended_at

            self.tasks.set_final_state(task_id, final_state)
            task_ended_at = _now()
            self.ops.record_trace_span(
                task_id=task_id,
                name="analysis_task",
                span_type="task",
                status="succeeded",
                started_at=task_started_at,
                ended_at=task_ended_at,
                duration_ms=_duration_ms(task_started_at, task_ended_at),
                input_summary=f"dataset_id={initial_state['dataset_id']}; question={initial_state['user_question']}",
                output_summary=_state_summary(final_state),
            )
            self.ops.complete_task(task_id, final_state)
            await self.tasks.publish(
                TaskEvent(
                    task_id=task_id,
                    event_type="task_completed",
                    status="succeeded",
                    node=None,
                    message="分析任务已完成。",
                    payload=_event_payload(final_state),
                )
            )
        except Exception as exc:
            message = _readable_error(exc)
            final_state["errors"] = [*(final_state.get("errors") or []), message]
            self.tasks.set_error(task_id, message, final_state)
            task_ended_at = _now()
            self.ops.record_trace_span(
                task_id=task_id,
                name=str(final_state.get("current_step") or "analysis_task"),
                span_type="task",
                status="failed",
                started_at=task_started_at,
                ended_at=task_ended_at,
                duration_ms=_duration_ms(task_started_at, task_ended_at),
                input_summary=f"dataset_id={initial_state['dataset_id']}; question={initial_state['user_question']}",
                output_summary=_state_summary(final_state),
                error=message,
            )
            self.ops.fail_task(task_id, message, final_state)
            await self.tasks.publish(
                TaskEvent(
                    task_id=task_id,
                    event_type="task_failed",
                    status="failed",
                    node=final_state.get("current_step"),
                    message=message,
                    payload={"errors": final_state["errors"], "current_step": final_state.get("current_step")},
                )
            )


def _event_payload(state_update: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state_update.items() if key in EVENT_PAYLOAD_KEYS}


def _readable_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


def _node_label(node_name: str) -> str:
    labels = {
        "load_dataset": "读取数据集",
        "profile_dataset": "生成数据画像",
        "understand_question": "理解问题",
        "plan_analysis": "规划分析",
        "choose_execution_path": "选择执行路径",
        "run_sql_analysis": "执行 DuckDB SQL",
        "run_pandas_analysis": "执行 pandas/scipy",
        "generate_charts": "生成图表",
        "generate_insights": "生成洞察",
        "review_answer": "复核结论",
        "generate_report": "生成报告",
    }
    return labels.get(node_name, node_name)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _duration_ms(started_at: datetime, ended_at: datetime) -> int:
    return int((ended_at - started_at).total_seconds() * 1000)


def _state_summary(state: dict[str, Any]) -> str:
    parts = [
        f"step={state.get('current_step')}",
        f"path={state.get('execution_path')}",
        f"errors={len(state.get('errors') or [])}",
    ]
    result = state.get("execution_result")
    if isinstance(result, dict):
        parts.append(f"result={result.get('kind')}")
    return "; ".join(parts)


def _payload_summary(payload: dict[str, Any]) -> str:
    compact = json.dumps(_event_payload(payload), ensure_ascii=False, default=str, separators=(",", ":"))
    if len(compact) > 600:
        return compact[:597] + "..."
    return compact


def _raise_if_token_budget_exceeded(task_id: str, ops: AgentOpsService) -> None:
    task = ops.require_task(task_id)
    if task.token_budget and task.total_tokens > task.token_budget:
        raise RuntimeError(f"Token budget exceeded: {task.total_tokens}/{task.token_budget}.")


analysis_service = AnalysisService(dataset_service, task_store, agent_ops_service)
