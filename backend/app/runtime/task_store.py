from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.runtime.events import TaskEvent, TaskStatus


@dataclass
class TaskRecord:
    task_id: str
    dataset_id: str
    question: str
    status: TaskStatus = "queued"
    queue: asyncio.Queue[TaskEvent] = field(default_factory=asyncio.Queue)
    final_state: dict[str, Any] | None = None
    error: str | None = None


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    def create(self, dataset_id: str, question: str) -> TaskRecord:
        task_id = uuid4().hex
        record = TaskRecord(task_id=task_id, dataset_id=dataset_id, question=question)
        self._tasks[task_id] = record
        return record

    def get(self, task_id: str) -> TaskRecord:
        record = self._tasks.get(task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Analysis task not found.")
        return record

    async def publish(self, event: TaskEvent) -> None:
        record = self.get(event.task_id)
        record.status = event.status
        await record.queue.put(event)

    def set_final_state(self, task_id: str, final_state: dict[str, Any]) -> None:
        record = self.get(task_id)
        record.final_state = final_state
        record.status = "succeeded"

    def set_error(self, task_id: str, error: str, final_state: dict[str, Any] | None = None) -> None:
        record = self.get(task_id)
        record.error = error
        record.status = "failed"
        if final_state is not None:
            record.final_state = final_state


task_store = TaskStore()
