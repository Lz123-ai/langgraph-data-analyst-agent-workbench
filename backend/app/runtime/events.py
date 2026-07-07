from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


TaskStatus = Literal["queued", "running", "succeeded", "failed"]
EventType = Literal["task_started", "node_completed", "task_completed", "task_failed", "heartbeat"]


class TaskEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    task_id: str
    event_type: EventType
    status: TaskStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    node: str | None = None
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
