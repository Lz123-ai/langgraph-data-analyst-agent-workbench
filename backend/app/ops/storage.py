from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ops.models import AgentTaskRecord, EvalRunRecord, TokenUsageRecord, TraceSpanRecord


class AgentOpsStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    model_name TEXT,
                    prompt_version TEXT,
                    token_budget INTEGER,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL NOT NULL DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT,
                    duration_ms INTEGER,
                    error TEXT,
                    final_state_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_trace_spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    span_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_ms INTEGER,
                    input_summary TEXT,
                    output_summary TEXT,
                    metadata_json TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_usage (
                    usage_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    node TEXT,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_runs (
                    eval_run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    failed INTEGER NOT NULL,
                    source_path TEXT,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_task(self, task: AgentTaskRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_tasks (
                    task_id, trace_id, tenant_id, user_id, dataset_id, question, status,
                    model_name, prompt_version, token_budget, prompt_tokens, completion_tokens,
                    total_tokens, estimated_cost_usd, started_at, completed_at, duration_ms,
                    error, final_state_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _task_values(task),
            )

    def update_task(self, task: AgentTaskRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE agent_tasks
                SET trace_id = ?,
                    tenant_id = ?,
                    user_id = ?,
                    dataset_id = ?,
                    question = ?,
                    status = ?,
                    model_name = ?,
                    prompt_version = ?,
                    token_budget = ?,
                    prompt_tokens = ?,
                    completion_tokens = ?,
                    total_tokens = ?,
                    estimated_cost_usd = ?,
                    started_at = ?,
                    completed_at = ?,
                    duration_ms = ?,
                    error = ?,
                    final_state_json = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (
                    task.trace_id,
                    task.tenant_id,
                    task.user_id,
                    task.dataset_id,
                    task.question,
                    task.status,
                    task.model_name,
                    task.prompt_version,
                    task.token_budget,
                    task.prompt_tokens,
                    task.completion_tokens,
                    task.total_tokens,
                    task.estimated_cost_usd,
                    _dt(task.started_at),
                    _dt(task.completed_at),
                    task.duration_ms,
                    task.error,
                    _json(task.final_state),
                    _dt(task.updated_at),
                    task.task_id,
                ),
            )

    def get_task(self, task_id: str) -> AgentTaskRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_tasks(self, limit: int = 50, tenant_id: str | None = None) -> list[AgentTaskRecord]:
        params: list[Any] = []
        where = ""
        if tenant_id:
            where = "WHERE tenant_id = ?"
            params.append(tenant_id)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM agent_tasks {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def delete_task(self, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM token_usage WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM agent_trace_spans WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM agent_tasks WHERE task_id = ?", (task_id,))

    def add_trace_span(self, span: TraceSpanRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_trace_spans (
                    span_id, trace_id, task_id, parent_span_id, span_type, name, status,
                    started_at, ended_at, duration_ms, input_summary, output_summary,
                    metadata_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    span.span_id,
                    span.trace_id,
                    span.task_id,
                    span.parent_span_id,
                    span.span_type,
                    span.name,
                    span.status,
                    _dt(span.started_at),
                    _dt(span.ended_at),
                    span.duration_ms,
                    span.input_summary,
                    span.output_summary,
                    _json(span.metadata),
                    span.error,
                ),
            )

    def list_trace(self, task_id: str) -> list[TraceSpanRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_trace_spans WHERE task_id = ? ORDER BY started_at ASC",
                (task_id,),
            ).fetchall()
        return [self._row_to_span(row) for row in rows]

    def add_token_usage(self, usage: TokenUsageRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO token_usage (
                    usage_id, trace_id, task_id, node, model_name, prompt_version,
                    prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd,
                    source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usage.usage_id,
                    usage.trace_id,
                    usage.task_id,
                    usage.node,
                    usage.model_name,
                    usage.prompt_version,
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                    usage.estimated_cost_usd,
                    usage.source,
                    _dt(usage.created_at),
                ),
            )

    def list_token_usage(self, task_id: str | None = None, limit: int = 100) -> list[TokenUsageRecord]:
        params: list[Any] = []
        where = ""
        if task_id:
            where = "WHERE task_id = ?"
            params.append(task_id)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM token_usage {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_usage(row) for row in rows]

    def add_eval_run(self, eval_run: EvalRunRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO eval_runs (
                    eval_run_id, status, total, passed, failed, source_path,
                    result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_run.eval_run_id,
                    eval_run.status,
                    eval_run.total,
                    eval_run.passed,
                    eval_run.failed,
                    eval_run.source_path,
                    _json(eval_run.result_json),
                    _dt(eval_run.created_at),
                ),
            )

    def list_eval_runs(self, limit: int = 20) -> list[EvalRunRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_eval_run(row) for row in rows]

    def summary_counts(self) -> dict[str, Any]:
        with self._connect() as conn:
            status_rows = conn.execute("SELECT status, COUNT(*) AS count FROM agent_tasks GROUP BY status").fetchall()
            token_row = conn.execute(
                "SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens, "
                "COALESCE(SUM(estimated_cost_usd), 0) AS estimated_cost_usd FROM token_usage"
            ).fetchone()
        statuses = {row["status"]: int(row["count"]) for row in status_rows}
        return {
            "statuses": statuses,
            "total_tokens": int(token_row["total_tokens"]) if token_row else 0,
            "estimated_cost_usd": float(token_row["estimated_cost_usd"]) if token_row else 0.0,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_task(self, row: sqlite3.Row) -> AgentTaskRecord:
        return AgentTaskRecord(
            task_id=row["task_id"],
            trace_id=row["trace_id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            dataset_id=row["dataset_id"],
            question=row["question"],
            status=row["status"],
            model_name=row["model_name"],
            prompt_version=row["prompt_version"],
            token_budget=row["token_budget"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            estimated_cost_usd=row["estimated_cost_usd"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
            error=row["error"],
            final_state=_loads(row["final_state_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_span(self, row: sqlite3.Row) -> TraceSpanRecord:
        return TraceSpanRecord(
            span_id=row["span_id"],
            trace_id=row["trace_id"],
            task_id=row["task_id"],
            parent_span_id=row["parent_span_id"],
            span_type=row["span_type"],
            name=row["name"],
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_ms=row["duration_ms"],
            input_summary=row["input_summary"],
            output_summary=row["output_summary"],
            metadata=_loads(row["metadata_json"]) or {},
            error=row["error"],
        )

    def _row_to_usage(self, row: sqlite3.Row) -> TokenUsageRecord:
        return TokenUsageRecord(
            usage_id=row["usage_id"],
            trace_id=row["trace_id"],
            task_id=row["task_id"],
            node=row["node"],
            model_name=row["model_name"],
            prompt_version=row["prompt_version"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            estimated_cost_usd=row["estimated_cost_usd"],
            source=row["source"],
            created_at=row["created_at"],
        )

    def _row_to_eval_run(self, row: sqlite3.Row) -> EvalRunRecord:
        return EvalRunRecord(
            eval_run_id=row["eval_run_id"],
            status=row["status"],
            total=row["total"],
            passed=row["passed"],
            failed=row["failed"],
            source_path=row["source_path"],
            result_json=_loads(row["result_json"]) or {},
            created_at=row["created_at"],
        )


def _task_values(task: AgentTaskRecord) -> tuple[Any, ...]:
    return (
        task.task_id,
        task.trace_id,
        task.tenant_id,
        task.user_id,
        task.dataset_id,
        task.question,
        task.status,
        task.model_name,
        task.prompt_version,
        task.token_budget,
        task.prompt_tokens,
        task.completion_tokens,
        task.total_tokens,
        task.estimated_cost_usd,
        _dt(task.started_at),
        _dt(task.completed_at),
        task.duration_ms,
        task.error,
        _json(task.final_state),
        _dt(task.created_at),
        _dt(task.updated_at),
    )


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)
