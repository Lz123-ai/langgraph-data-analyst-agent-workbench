from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.improvements.defaults import DEFAULT_IMPROVEMENT_LOGS
from app.improvements.models import ImprovementLogCreate, ImprovementLogEntry, ImprovementLogUpdate
from app.improvements.storage import ImprovementLogStorage
from app.settings import settings


class ImprovementLogService:
    def __init__(self, storage: ImprovementLogStorage) -> None:
        self.storage = storage

    def create_log(self, payload: ImprovementLogCreate) -> ImprovementLogEntry:
        now = datetime.now(timezone.utc)
        entry = ImprovementLogEntry(
            log_id=uuid4().hex,
            issue=payload.issue.strip(),
            resolution=payload.resolution.strip(),
            status=payload.status,
            dataset_id=payload.dataset_id.strip() if payload.dataset_id else None,
            related_question=payload.related_question.strip() if payload.related_question else None,
            created_at=now,
            updated_at=now,
        )
        self.storage.add_log(entry)
        return entry

    def list_logs(self, limit: int = 50) -> list[ImprovementLogEntry]:
        return self.storage.list_logs(limit=max(1, min(limit, 100)))

    def get_log(self, log_id: str) -> ImprovementLogEntry:
        entry = self.storage.get_log(log_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Improvement log not found.")
        return entry

    def update_log(self, log_id: str, payload: ImprovementLogUpdate) -> ImprovementLogEntry:
        entry = self.get_log(log_id)
        update = payload.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)
        updated = ImprovementLogEntry(
            log_id=entry.log_id,
            issue=(update.get("issue", entry.issue) or "").strip(),
            resolution=(update.get("resolution", entry.resolution) or "").strip(),
            status=update.get("status", entry.status),
            dataset_id=_optional_strip(update["dataset_id"]) if "dataset_id" in update else entry.dataset_id,
            related_question=_optional_strip(update["related_question"])
            if "related_question" in update
            else entry.related_question,
            created_at=entry.created_at,
            updated_at=now,
        )
        self.storage.update_log(updated)
        return updated

    def delete_log(self, log_id: str) -> None:
        self.get_log(log_id)
        self.storage.delete_log(log_id)

    def upsert_system_log(
        self,
        *,
        log_id: str,
        issue: str,
        resolution: str,
        status: str = "open",
        dataset_id: str | None = None,
        related_question: str | None = None,
    ) -> ImprovementLogEntry:
        existing = self.storage.get_log(log_id)
        now = datetime.now(timezone.utc)
        entry = ImprovementLogEntry(
            log_id=log_id,
            issue=issue.strip(),
            resolution=resolution.strip(),
            status=status,  # type: ignore[arg-type]
            dataset_id=_optional_strip(dataset_id),
            related_question=_optional_strip(related_question),
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.storage.upsert_log(entry)
        return entry

    def seed_default_logs(self) -> int:
        synced = 0
        now = datetime.now(timezone.utc)
        for item in DEFAULT_IMPROVEMENT_LOGS:
            existing = self.storage.get_log(item.log_id)
            created_at = existing.created_at if existing else now
            entry = ImprovementLogEntry(
                log_id=item.log_id,
                issue=item.issue,
                resolution=item.resolution,
                status=item.status,
                dataset_id=None,
                related_question=item.related_question,
                created_at=created_at,
                updated_at=now,
            )
            if _is_same_log(existing, entry):
                continue
            self.storage.upsert_log(entry)
            synced += 1
        return synced


def _is_same_log(existing: ImprovementLogEntry | None, entry: ImprovementLogEntry) -> bool:
    if existing is None:
        return False
    return (
        existing.issue == entry.issue
        and existing.resolution == entry.resolution
        and existing.status == entry.status
        and existing.dataset_id == entry.dataset_id
        and existing.related_question == entry.related_question
    )


def _optional_strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


improvement_log_service = ImprovementLogService(ImprovementLogStorage(settings.db_path))
