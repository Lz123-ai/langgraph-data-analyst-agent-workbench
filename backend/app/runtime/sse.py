from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.runtime.events import TaskEvent
from app.runtime.task_store import TaskStore


def format_sse(event: TaskEvent) -> str:
    data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"event: {event.event_type}\ndata: {data}\n\n"


async def event_stream(store: TaskStore, task_id: str) -> AsyncIterator[str]:
    record = store.get(task_id)
    while True:
        try:
            event = await asyncio.wait_for(record.queue.get(), timeout=15)
            yield format_sse(event)
            if event.event_type in {"task_completed", "task_failed"}:
                break
        except asyncio.TimeoutError:
            heartbeat = TaskEvent(
                task_id=task_id,
                event_type="heartbeat",
                status=record.status,
                message="任务仍在执行中。",
            )
            yield format_sse(heartbeat)
