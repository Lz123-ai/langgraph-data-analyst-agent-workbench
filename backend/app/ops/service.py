from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.improvements.service import improvement_log_service
from app.ops.models import (
    AgentOpsSummary,
    AgentTaskRecord,
    EvalRunRecord,
    IdentityContext,
    NodePayloadMetricRecord,
    TokenUsageRecord,
    TraceSpanRecord,
)
from app.ops.storage import AgentOpsStorage
from app.settings import settings


class AgentOpsService:
    def __init__(self, storage: AgentOpsStorage) -> None:
        self.storage = storage

    def create_task(
        self,
        *,
        task_id: str,
        dataset_id: str,
        question: str,
        identity: IdentityContext,
        model_name: str | None = None,
        prompt_version: str | None = None,
        token_budget: int | None = None,
    ) -> AgentTaskRecord:
        now = _now()
        task = AgentTaskRecord(
            task_id=task_id,
            trace_id=uuid4().hex,
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            dataset_id=dataset_id,
            question=question,
            status="queued",
            model_name=model_name or settings.openai_model,
            prompt_version=prompt_version or settings.prompt_version,
            token_budget=token_budget or settings.default_token_budget,
            created_at=now,
            updated_at=now,
        )
        self.storage.add_task(task)
        return task

    def mark_running(self, task_id: str) -> None:
        task = self.require_task(task_id)
        now = _now()
        task.status = "running"
        task.started_at = task.started_at or now
        task.updated_at = now
        self.storage.update_task(task)

    def reset_task_for_retry(self, task_id: str) -> None:
        self.require_task(task_id)
        self.storage.reset_task_for_retry(task_id)

    def record_trace_span(
        self,
        *,
        task_id: str,
        name: str,
        span_type: str,
        status: str,
        started_at: datetime,
        ended_at: datetime | None = None,
        duration_ms: int | None = None,
        input_summary: str | None = None,
        output_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> TraceSpanRecord:
        task = self.require_task(task_id)
        span = TraceSpanRecord(
            span_id=uuid4().hex,
            trace_id=task.trace_id,
            task_id=task_id,
            span_type=span_type,  # type: ignore[arg-type]
            name=name,
            status=status,  # type: ignore[arg-type]
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            input_summary=input_summary,
            output_summary=output_summary,
            metadata=metadata or {},
            error=error,
        )
        self.storage.add_trace_span(span)
        return span

    def record_estimated_token_usage(
        self,
        *,
        task_id: str,
        node: str | None,
        prompt_text: str,
        completion_payload: Any,
    ) -> TokenUsageRecord:
        task = self.require_task(task_id)
        prompt_tokens = estimate_tokens(prompt_text)
        completion_tokens = estimate_tokens(_compact_json(completion_payload))
        return self.record_token_usage(
            task_id=task_id,
            node=node,
            model_name=task.model_name or settings.openai_model,
            prompt_version=task.prompt_version or settings.prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            source="estimated",
        )

    def record_node_payload_metric(
        self,
        *,
        task_id: str,
        node: str,
        input_summary: str,
        output_payload: Any,
    ) -> NodePayloadMetricRecord:
        task = self.require_task(task_id)
        output_text = _compact_json(output_payload)
        metric = NodePayloadMetricRecord(
            metric_id=uuid4().hex,
            trace_id=task.trace_id,
            task_id=task_id,
            node=node,
            input_chars=len(input_summary),
            output_chars=len(output_text),
            output_bytes=len(output_text.encode("utf-8")),
            output_rows=_count_payload_rows(output_payload),
            created_at=_now(),
        )
        self.storage.add_payload_metric(metric)
        return metric

    def record_token_usage(
        self,
        *,
        task_id: str,
        node: str | None,
        model_name: str,
        prompt_version: str,
        prompt_tokens: int,
        completion_tokens: int,
        source: str = "estimated",
    ) -> TokenUsageRecord:
        task = self.require_task(task_id)
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = estimate_cost(prompt_tokens, completion_tokens)
        usage = TokenUsageRecord(
            usage_id=uuid4().hex,
            trace_id=task.trace_id,
            task_id=task_id,
            node=node,
            model_name=model_name,
            prompt_version=prompt_version,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            source=source,  # type: ignore[arg-type]
            created_at=_now(),
        )
        self.storage.add_token_usage(usage)
        task.prompt_tokens += prompt_tokens
        task.completion_tokens += completion_tokens
        task.total_tokens += total_tokens
        task.estimated_cost_usd = round(task.estimated_cost_usd + estimated_cost, 8)
        task.updated_at = _now()
        self.storage.update_task(task)
        return usage

    def complete_task(self, task_id: str, final_state: dict[str, Any]) -> None:
        task = self.require_task(task_id)
        now = _now()
        task.status = "succeeded"
        task.completed_at = now
        task.duration_ms = _duration_ms(task.started_at, now)
        task.final_state = final_state
        task.updated_at = now
        self.storage.update_task(task)

    def fail_task(self, task_id: str, error: str, final_state: dict[str, Any] | None = None) -> None:
        task = self.require_task(task_id)
        now = _now()
        task.status = "failed"
        task.completed_at = now
        task.duration_ms = _duration_ms(task.started_at, now)
        task.error = error
        task.final_state = final_state
        task.updated_at = now
        self.storage.update_task(task)

    def cancel_task(self, task_id: str, final_state: dict[str, Any] | None = None) -> None:
        task = self.require_task(task_id)
        now = _now()
        task.status = "cancelled"
        task.completed_at = now
        task.duration_ms = _duration_ms(task.started_at, now)
        task.error = "Task cancelled by user."
        task.final_state = final_state
        task.updated_at = now
        self.storage.update_task(task)

    def require_task(self, task_id: str, identity: IdentityContext | None = None) -> AgentTaskRecord:
        task = self.storage.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Agent task not found.")
        if identity and (task.tenant_id != identity.tenant_id or task.user_id != identity.user_id):
            raise HTTPException(status_code=404, detail="Agent task not found.")
        return task

    def list_tasks(
        self,
        limit: int = 50,
        tenant_id: str | None = None,
        user_id: str | None = None,
    ) -> list[AgentTaskRecord]:
        return self.storage.list_tasks(
            limit=max(1, min(limit, 100)),
            tenant_id=tenant_id,
            user_id=user_id,
        )

    def delete_task(self, task_id: str, identity: IdentityContext | None = None) -> None:
        self.require_task(task_id, identity)
        self.storage.delete_task(task_id)

    def list_trace(self, task_id: str, identity: IdentityContext | None = None) -> list[TraceSpanRecord]:
        self.require_task(task_id, identity)
        return self.storage.list_trace(task_id)

    def list_token_usage(
        self,
        task_id: str | None = None,
        limit: int = 100,
        identity: IdentityContext | None = None,
    ) -> list[TokenUsageRecord]:
        if task_id:
            self.require_task(task_id, identity)
        safe_limit = max(1, min(limit, 500))
        usage = self.storage.list_token_usage(task_id=task_id, limit=500 if identity and not task_id else safe_limit)
        if identity and not task_id:
            allowed = {
                task.task_id
                for task in self.storage.list_tasks(limit=500, tenant_id=identity.tenant_id, user_id=identity.user_id)
            }
            usage = [item for item in usage if item.task_id in allowed]
        return usage[:safe_limit]

    def get_task_detail(
        self,
        task_id: str,
        identity: IdentityContext | None = None,
    ) -> tuple[AgentTaskRecord, list[TraceSpanRecord], list[TokenUsageRecord]]:
        return (
            self.require_task(task_id, identity),
            self.list_trace(task_id, identity),
            self.list_token_usage(task_id=task_id, identity=identity),
        )

    def list_payload_metrics(
        self,
        task_id: str,
        identity: IdentityContext | None = None,
    ) -> list[NodePayloadMetricRecord]:
        self.require_task(task_id, identity)
        return self.storage.list_payload_metrics(task_id)

    def summary(self, identity: IdentityContext | None = None) -> AgentOpsSummary:
        counts = self.storage.summary_counts(
            identity.tenant_id if identity else None,
            identity.user_id if identity else None,
        )
        statuses = counts["statuses"]
        latest_eval = next(iter(self.storage.list_eval_runs(limit=1)), None)
        return AgentOpsSummary(
            task_count=sum(int(value) for value in statuses.values()),
            running_count=statuses.get("running", 0),
            succeeded_count=statuses.get("succeeded", 0),
            failed_count=statuses.get("failed", 0),
            total_tokens=counts["total_tokens"],
            estimated_cost_usd=round(counts["estimated_cost_usd"], 8),
            deterministic_payload_bytes=counts["deterministic_payload_bytes"],
            latest_eval=latest_eval,
        )

    def record_eval_report(self, report: dict[str, Any], source_path: str | None = None) -> EvalRunRecord:
        summary = report.get("summary") or {}
        total = int(summary.get("total") or len(report.get("results") or []))
        passed = int(summary.get("passed") or 0)
        failed = int(summary.get("failed") or max(total - passed, 0))
        eval_run = EvalRunRecord(
            eval_run_id=uuid4().hex,
            status="succeeded" if failed == 0 else "failed",
            total=total,
            passed=passed,
            failed=failed,
            source_path=source_path,
            result_json=report,
            created_at=_now(),
        )
        self.storage.add_eval_run(eval_run)
        self._record_eval_failures_as_improvements(report)
        return eval_run

    def list_eval_runs(self, limit: int = 20) -> list[EvalRunRecord]:
        return self.storage.list_eval_runs(limit=max(1, min(limit, 100)))

    def _record_eval_failures_as_improvements(self, report: dict[str, Any]) -> None:
        for result in report.get("results") or []:
            case_id = str(result.get("id") or "unknown")
            log_id = f"eval-failure-{_safe_log_id(case_id)}"
            if result.get("passed"):
                existing = improvement_log_service.storage.get_log(log_id)
                if existing and existing.status != "resolved":
                    improvement_log_service.upsert_system_log(
                        log_id=log_id,
                        issue=existing.issue,
                        resolution=f"已通过最新批量评测，失败用例已回归通过。原处理记录：{existing.resolution}",
                        status="resolved",
                        related_question=existing.related_question,
                    )
                continue
            failures = result.get("failures") or ["未给出失败原因。"]
            issue = f"评测用例 {result.get('id', 'unknown')} 未通过。"
            resolution = "待处理：需要先复现该失败用例，再补充意图解析、工具逻辑或报告校验，并加入回归保护。失败原因：" + "；".join(
                str(item) for item in failures
            )
            improvement_log_service.upsert_system_log(
                log_id=log_id,
                issue=issue,
                resolution=resolution,
                status="open",
                related_question=result.get("question"),
            )


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    chinese_chars = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    other_chars = len(text) - chinese_chars
    return max(1, int(chinese_chars * 1.2 + other_chars / 4))


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        prompt_tokens / 1000 * settings.input_token_price_per_1k
        + completion_tokens / 1000 * settings.output_token_price_per_1k,
        8,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _duration_ms(started_at: datetime | None, ended_at: datetime) -> int | None:
    if started_at is None:
        return None
    return int((ended_at - started_at).total_seconds() * 1000)


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def _safe_log_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)[:80] or "unknown"


def _count_payload_rows(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    result = value.get("execution_result")
    if not isinstance(result, dict):
        return 0
    tables = result.get("tables") or []
    return sum(len(table.get("rows") or []) for table in tables if isinstance(table, dict))


agent_ops_service = AgentOpsService(AgentOpsStorage(settings.db_path))
