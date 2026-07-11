from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.runtime.events import TaskEvent, TaskStatus
from app.settings import settings


@dataclass
class TaskRecord:
    task_id: str
    dataset_id: str
    question: str
    status: TaskStatus = "queued"
    final_state: dict[str, Any] | None = None
    error: str | None = None
    cancel_requested: bool = False


class TaskStore:
    """SQLite-backed runtime task and append-only event store.

    Events are read by sequence number, so multiple SSE subscribers and reconnects
    never compete for a single in-memory queue.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_tasks (
                    task_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    final_state_json TEXT,
                    error TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_events (
                    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    node TEXT,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_events_task_seq ON task_events(task_id, sequence_id)")

    def create(self, dataset_id: str, question: str) -> TaskRecord:
        task_id = uuid4().hex
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_tasks (
                    task_id, dataset_id, question, status, final_state_json, error,
                    cancel_requested, created_at, updated_at
                ) VALUES (?, ?, ?, 'queued', NULL, NULL, 0, ?, ?)
                """,
                (task_id, dataset_id, question, now, now),
            )
        return self.get(task_id)

    def get(self, task_id: str) -> TaskRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runtime_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Analysis task not found.")
        return TaskRecord(
            task_id=row["task_id"],
            dataset_id=row["dataset_id"],
            question=row["question"],
            status=row["status"],
            final_state=_loads(row["final_state_json"]),
            error=row["error"],
            cancel_requested=bool(row["cancel_requested"]),
        )

    async def publish(self, event: TaskEvent) -> TaskEvent:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_events (
                    event_id, task_id, event_type, status, timestamp, node, message, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.task_id,
                    event.event_type,
                    event.status,
                    event.timestamp.isoformat(),
                    event.node,
                    event.message,
                    json.dumps(event.payload, ensure_ascii=False, default=str),
                ),
            )
            sequence_id = int(cursor.lastrowid)
            conn.execute(
                "UPDATE runtime_tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (event.status, _now(), event.task_id),
            )
        return event.model_copy(update={"sequence_id": sequence_id})

    def list_events(self, task_id: str, after_sequence: int = 0, limit: int = 100) -> list[TaskEvent]:
        self.get(task_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_events
                WHERE task_id = ? AND sequence_id > ?
                ORDER BY sequence_id ASC LIMIT ?
                """,
                (task_id, max(0, after_sequence), max(1, min(limit, 500))),
            ).fetchall()
        return [
            TaskEvent(
                sequence_id=row["sequence_id"],
                event_id=row["event_id"],
                task_id=row["task_id"],
                event_type=row["event_type"],
                status=row["status"],
                timestamp=row["timestamp"],
                node=row["node"],
                message=row["message"],
                payload=_loads(row["payload_json"]) or {},
            )
            for row in rows
        ]

    def request_cancel(self, task_id: str) -> TaskRecord:
        record = self.get(task_id)
        if record.status in {"succeeded", "failed", "cancelled"}:
            return record
        with self._connect() as conn:
            conn.execute(
                "UPDATE runtime_tasks SET cancel_requested = 1, updated_at = ? WHERE task_id = ?",
                (_now(), task_id),
            )
        return self.get(task_id)

    def is_cancel_requested(self, task_id: str) -> bool:
        return self.get(task_id).cancel_requested

    def set_final_state(self, task_id: str, final_state: dict[str, Any]) -> None:
        self._finish(task_id, "succeeded", final_state, None)

    def set_error(self, task_id: str, error: str, final_state: dict[str, Any] | None = None) -> None:
        self._finish(task_id, "failed", final_state, error)

    def set_cancelled(self, task_id: str, final_state: dict[str, Any] | None = None) -> None:
        self._finish(task_id, "cancelled", final_state, "Task cancelled by user.")

    def _finish(
        self,
        task_id: str,
        status: TaskStatus,
        final_state: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        self.get(task_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runtime_tasks
                SET status = ?, final_state_json = ?, error = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status, _dumps(final_state), error, _now(), task_id),
            )

    def prepare_incomplete_for_resume(self) -> list[TaskRecord]:
        """Reset interrupted tasks to queued so a new process can rerun them safely."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runtime_tasks WHERE status IN ('queued', 'running')").fetchall()
            now = _now()
            conn.execute(
                """
                UPDATE runtime_tasks
                SET status = 'queued', error = NULL, cancel_requested = 0, updated_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
        return [
            TaskRecord(
                task_id=row["task_id"],
                dataset_id=row["dataset_id"],
                question=row["question"],
                status="queued",
                final_state=_loads(row["final_state_json"]),
                error=None,
                cancel_requested=False,
            )
            for row in rows
        ]

    def reset_for_retry(self, task_id: str) -> TaskRecord:
        record = self.get(task_id)
        if record.status not in {"failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Only failed or cancelled tasks can be retried.")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runtime_tasks
                SET status = 'queued', final_state_json = NULL, error = NULL,
                    cancel_requested = 0, updated_at = ?
                WHERE task_id = ?
                """,
                (_now(), task_id),
            )
        return self.get(task_id)

    def cleanup_expired(self, retention_days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, retention_days))).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT task_id FROM runtime_tasks WHERE updated_at < ? AND status IN ('succeeded', 'failed', 'cancelled')",
                (cutoff,),
            ).fetchall()
            task_ids = [row["task_id"] for row in rows]
            for task_id in task_ids:
                conn.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
                conn.execute("DELETE FROM runtime_tasks WHERE task_id = ?", (task_id,))
        return len(task_ids)

    def delete_task(self, task_id: str) -> None:
        record = self.get(task_id)
        if record.status in {"queued", "running"}:
            raise HTTPException(status_code=409, detail="Cancel the running task before deleting it.")
        with self._connect() as conn:
            conn.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM runtime_tasks WHERE task_id = ?", (task_id,))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str | None:
    return json.dumps(value, ensure_ascii=False, default=str) if value is not None else None


def _loads(value: str | None) -> Any:
    return json.loads(value) if value else None


task_store = TaskStore(settings.db_path)
