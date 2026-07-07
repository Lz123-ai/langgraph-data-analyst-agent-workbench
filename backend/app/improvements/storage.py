from __future__ import annotations

import sqlite3
from pathlib import Path

from app.improvements.models import ImprovementLogEntry


class ImprovementLogStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS improvement_logs (
                    log_id TEXT PRIMARY KEY,
                    issue TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dataset_id TEXT,
                    related_question TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def add_log(self, entry: ImprovementLogEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO improvement_logs (
                    log_id, issue, resolution, status, dataset_id,
                    related_question, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.log_id,
                    entry.issue,
                    entry.resolution,
                    entry.status,
                    entry.dataset_id,
                    entry.related_question,
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                ),
            )

    def get_log(self, log_id: str) -> ImprovementLogEntry | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM improvement_logs WHERE log_id = ?", (log_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_model(row)

    def upsert_log(self, entry: ImprovementLogEntry) -> None:
        existing = self.get_log(entry.log_id)
        if existing is None:
            self.add_log(entry)
            return

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE improvement_logs
                SET issue = ?,
                    resolution = ?,
                    status = ?,
                    dataset_id = ?,
                    related_question = ?,
                    updated_at = ?
                WHERE log_id = ?
                """,
                (
                    entry.issue,
                    entry.resolution,
                    entry.status,
                    entry.dataset_id,
                    entry.related_question,
                    entry.updated_at.isoformat(),
                    entry.log_id,
                ),
            )

    def update_log(self, entry: ImprovementLogEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE improvement_logs
                SET issue = ?,
                    resolution = ?,
                    status = ?,
                    dataset_id = ?,
                    related_question = ?,
                    updated_at = ?
                WHERE log_id = ?
                """,
                (
                    entry.issue,
                    entry.resolution,
                    entry.status,
                    entry.dataset_id,
                    entry.related_question,
                    entry.updated_at.isoformat(),
                    entry.log_id,
                ),
            )

    def list_logs(self, limit: int = 50) -> list[ImprovementLogEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM improvement_logs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def delete_log(self, log_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM improvement_logs WHERE log_id = ?", (log_id,))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_model(self, row: sqlite3.Row) -> ImprovementLogEntry:
        return ImprovementLogEntry(
            log_id=row["log_id"],
            issue=row["issue"],
            resolution=row["resolution"],
            status=row["status"],
            dataset_id=row["dataset_id"],
            related_question=row["related_question"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
