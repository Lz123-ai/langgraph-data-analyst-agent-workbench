from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.runtime.events import TaskEvent
from app.runtime.task_store import TaskStore


def format_sse(event: TaskEvent) -> str:
    data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    event_id = f"id: {event.sequence_id}\n" if event.sequence_id is not None else ""
    return f"{event_id}event: {event.event_type}\ndata: {data}\n\n"


async def event_stream(store: TaskStore, task_id: str, after_sequence: int = 0) -> AsyncIterator[str]:
    """Replay persisted events and then tail new events without consuming them."""
    cursor = max(0, after_sequence)
    heartbeat_elapsed = 0.0
    while True:
        events = store.list_events(task_id, after_sequence=cursor)
        if events:
            heartbeat_elapsed = 0.0
            for event in events:
                if event.sequence_id is not None:
                    cursor = event.sequence_id
                yield format_sse(event)
                if event.event_type in {"task_completed", "task_failed", "task_cancelled"}:
                    return
            continue

        record = store.get(task_id)
        if record.status in {"succeeded", "failed", "cancelled"}:
            return
        await asyncio.sleep(0.25)
        heartbeat_elapsed += 0.25
        if heartbeat_elapsed >= 15:
            heartbeat_elapsed = 0.0
            yield format_sse(
                TaskEvent(
                    task_id=task_id,
                    event_type="heartbeat",
                    status=record.status,
                    message="任务仍在执行中。",
                )
            )
