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
from app.settings import settings

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
        self._background_tasks: dict[str, asyncio.Task[None]] = {}
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_tasks)

    def create_task(self, dataset_id: str, question: str, identity: IdentityContext | None = None) -> str:
        identity = identity or IdentityContext()
        metadata, _ = self.datasets.get_dataset(dataset_id, identity)
        record = self.tasks.create(dataset_id=dataset_id, question=question)
        self.ops.create_task(
            task_id=record.task_id,
            dataset_id=dataset_id,
            question=question,
            identity=identity,
        )
        initial_state = self._build_initial_state(dataset_id, metadata.file_path, question)
        self._schedule_task(record.task_id, initial_state)
        return record.task_id

    def _build_initial_state(self, dataset_id: str, file_path: str, question: str) -> AnalysisState:
        return {
            "dataset_id": dataset_id,
            "file_path": file_path,
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

    def _schedule_task(self, task_id: str, initial_state: AnalysisState, *, event_type: str = "task_started") -> None:
        background = asyncio.create_task(self._run_task(task_id, initial_state, event_type=event_type))
        self._background_tasks[task_id] = background
        background.add_done_callback(lambda _: self._background_tasks.pop(task_id, None))

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        record = self.tasks.request_cancel(task_id)
        background = self._background_tasks.get(task_id)
        if background and not background.done():
            background.cancel()
        return {"task_id": task_id, "status": record.status if record.status in {"succeeded", "failed", "cancelled"} else "cancelling"}

    def retry_task(self, task_id: str, identity: IdentityContext) -> dict[str, str]:
        self.require_access(task_id, identity)
        if task_id in self._background_tasks:
            raise HTTPException(status_code=409, detail="Task is already running.")
        record = self.tasks.reset_for_retry(task_id)
        metadata, _ = self.datasets.get_dataset(record.dataset_id, identity)
        self.ops.reset_task_for_retry(task_id)
        initial_state = self._build_initial_state(record.dataset_id, metadata.file_path, record.question)
        self._schedule_task(task_id, initial_state, event_type="task_retried")
        return {"task_id": task_id, "status": "queued"}

    def resume_incomplete(self) -> int:
        records = self.tasks.prepare_incomplete_for_resume()
        resumed = 0
        for record in records:
            try:
                task = self.ops.require_task(record.task_id)
            except HTTPException:
                self.tasks.set_error(record.task_id, "Persistent AgentOps task metadata is missing.")
                continue
            identity = IdentityContext(tenant_id=task.tenant_id, user_id=task.user_id)
            try:
                metadata, _ = self.datasets.get_dataset(record.dataset_id, identity)
            except HTTPException:
                message = "Dataset is unavailable; interrupted task cannot be resumed."
                self.tasks.set_error(record.task_id, message)
                self.ops.fail_task(record.task_id, message)
                continue
            self.ops.reset_task_for_retry(record.task_id)
            initial_state = self._build_initial_state(record.dataset_id, metadata.file_path, record.question)
            self._schedule_task(record.task_id, initial_state, event_type="task_resumed")
            resumed += 1
        return resumed

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

    def require_access(self, task_id: str, identity: IdentityContext) -> None:
        task = self.ops.require_task(task_id)
        if task.tenant_id != identity.tenant_id or task.user_id != identity.user_id:
            raise HTTPException(status_code=404, detail="Analysis task not found.")

    async def _run_task(self, task_id: str, initial_state: AnalysisState, *, event_type: str = "task_started") -> None:
        try:
            async with asyncio.timeout(settings.task_timeout_seconds):
                async with self._semaphore:
                    await self._run_task_inner(task_id, initial_state, event_type=event_type)
        except asyncio.CancelledError:
            await self._mark_cancelled(task_id, initial_state)
        except TimeoutError:
            await self._mark_failed(task_id, initial_state, f"Task timed out after {settings.task_timeout_seconds} seconds.")

    async def _run_task_inner(self, task_id: str, initial_state: AnalysisState, *, event_type: str = "task_started") -> None:
        resumed = event_type == "task_resumed"
        final_state: dict[str, Any] = dict(initial_state)
        task_started_at = _now()
        node_started_at = task_started_at
        self.ops.mark_running(task_id)
        await self.tasks.publish(
            TaskEvent(
                task_id=task_id,
                event_type=event_type,  # type: ignore[arg-type]
                status="running",
                node=None,
                message="服务重启后已自动恢复分析任务。" if resumed else "分析任务已开始。",
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
                    if self.tasks.is_cancel_requested(task_id):
                        raise asyncio.CancelledError
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
                    self.ops.record_node_payload_metric(
                        task_id=task_id,
                        node=node_name,
                        input_summary=input_summary,
                        output_payload=partial,
                    )
                    llm_usage = partial.get("llm_usage")
                    if isinstance(llm_usage, dict) and llm_usage.get("source") == "provider":
                        self.ops.record_token_usage(
                            task_id=task_id,
                            node=node_name,
                            model_name=str(llm_usage.get("model_name") or settings.openai_model),
                            prompt_version=settings.prompt_version,
                            prompt_tokens=int(llm_usage.get("prompt_tokens") or 0),
                            completion_tokens=int(llm_usage.get("completion_tokens") or 0),
                            source="provider",
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

    async def _mark_cancelled(self, task_id: str, initial_state: AnalysisState) -> None:
        try:
            current = self.tasks.get(task_id)
        except HTTPException:
            return
        if current.status in {"succeeded", "failed", "cancelled"}:
            return
        final_state = dict(current.final_state or initial_state)
        final_state["errors"] = [*(final_state.get("errors") or []), "Task cancelled by user."]
        self.tasks.set_cancelled(task_id, final_state)
        self.ops.cancel_task(task_id, final_state)
        await self.tasks.publish(
            TaskEvent(
                task_id=task_id,
                event_type="task_cancelled",
                status="cancelled",
                node=final_state.get("current_step"),
                message="分析任务已取消。",
                payload={"errors": final_state["errors"], "current_step": final_state.get("current_step")},
            )
        )

    async def _mark_failed(self, task_id: str, initial_state: AnalysisState, message: str) -> None:
        try:
            current = self.tasks.get(task_id)
        except HTTPException:
            return
        if current.status in {"succeeded", "failed", "cancelled"}:
            return
        final_state = dict(current.final_state or initial_state)
        final_state["errors"] = [*(final_state.get("errors") or []), message]
        self.tasks.set_error(task_id, message, final_state)
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
    event_payload = _event_payload(payload)
    if not settings.trace_include_sample_data:
        event_payload = _redact_trace_payload(event_payload)
    compact = json.dumps(event_payload, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(compact) > 600:
        return compact[:597] + "..."
    return compact


def _redact_trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "dataset_preview" and isinstance(value, list):
            redacted[key] = {"redacted": True, "row_count": len(value)}
        elif key == "profile" and isinstance(value, dict):
            redacted[key] = {
                "row_count": value.get("row_count"),
                "column_count": value.get("column_count"),
                "columns": [item.get("name") for item in value.get("columns", []) if isinstance(item, dict)],
            }
        elif key == "execution_result" and isinstance(value, dict):
            redacted[key] = {
                "kind": value.get("kind"),
                "source": value.get("source"),
                "tables": [
                    {"name": table.get("name"), "row_count": len(table.get("rows") or [])}
                    for table in value.get("tables", [])
                    if isinstance(table, dict)
                ],
            }
        elif key == "report_markdown" and isinstance(value, str):
            redacted[key] = {"redacted": True, "characters": len(value)}
        else:
            redacted[key] = value
    return redacted


def _raise_if_token_budget_exceeded(task_id: str, ops: AgentOpsService) -> None:
    task = ops.require_task(task_id)
    if task.token_budget and task.total_tokens > task.token_budget:
        raise RuntimeError(f"Token budget exceeded: {task.total_tokens}/{task.token_budget}.")


analysis_service = AnalysisService(dataset_service, task_store, agent_ops_service)
