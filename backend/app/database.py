from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

CURRENT_SCHEMA_VERSION = 4


def record_schema_version(db_path: Path) -> None:
    """Maintain a lightweight schema ledger for the local SQLite adapter."""
    with sqlite3.connect(db_path, timeout=10) as conn:
        current = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if current > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {current} is newer than supported version {CURRENT_SCHEMA_VERSION}."
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        if current < CURRENT_SCHEMA_VERSION:
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (CURRENT_SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
            )
            conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
