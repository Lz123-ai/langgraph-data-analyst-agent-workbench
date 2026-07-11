from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.domain import DatasetMetadata, DatasetProfile


class DatasetStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    row_count INTEGER NOT NULL,
                    column_count INTEGER NOT NULL,
                    columns_json TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tenant_id TEXT NOT NULL DEFAULT 'local',
                    user_id TEXT NOT NULL DEFAULT 'local-user'
                )
                """
            )
            existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(datasets)").fetchall()}
            if "tenant_id" not in existing_columns:
                conn.execute("ALTER TABLE datasets ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'local'")
            if "user_id" not in existing_columns:
                conn.execute("ALTER TABLE datasets ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local-user'")

    def add_dataset(self, metadata: DatasetMetadata, profile: DatasetProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO datasets (
                    dataset_id, original_filename, stored_filename, file_path, file_type,
                    size_bytes, row_count, column_count, columns_json, profile_json, created_at,
                    tenant_id, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.dataset_id,
                    metadata.original_filename,
                    metadata.stored_filename,
                    metadata.file_path,
                    metadata.file_type,
                    metadata.size_bytes,
                    metadata.row_count,
                    metadata.column_count,
                    json.dumps(metadata.columns),
                    profile.model_dump_json(),
                    metadata.created_at.isoformat(),
                    metadata.tenant_id,
                    metadata.user_id,
                ),
            )

    def get_dataset(self, dataset_id: str) -> tuple[DatasetMetadata, DatasetProfile] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_models(row)

    def list_datasets(self, tenant_id: str | None = None, user_id: str | None = None) -> list[DatasetMetadata]:
        clauses: list[str] = []
        params: list[str] = []
        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(tenant_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM datasets {where} ORDER BY created_at DESC", params).fetchall()
        return [self._row_to_models(row)[0] for row in rows]

    def delete_dataset(self, dataset_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))
        return cursor.rowcount > 0

    def list_expired(self, older_than: datetime) -> list[DatasetMetadata]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM datasets WHERE created_at < ? ORDER BY created_at ASC",
                (older_than.astimezone(timezone.utc).isoformat(),),
            ).fetchall()
        return [self._row_to_models(row)[0] for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def _row_to_models(self, row: sqlite3.Row) -> tuple[DatasetMetadata, DatasetProfile]:
        metadata = DatasetMetadata(
            dataset_id=row["dataset_id"],
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            file_path=row["file_path"],
            file_type=row["file_type"],
            size_bytes=row["size_bytes"],
            row_count=row["row_count"],
            column_count=row["column_count"],
            columns=json.loads(row["columns_json"]),
            created_at=row["created_at"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
        )
        profile = DatasetProfile.model_validate_json(row["profile_json"])
        return metadata, profile
