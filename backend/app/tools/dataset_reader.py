from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi import HTTPException

from app.settings import settings

SUPPORTED_CSV = {".csv"}
SUPPORTED_EXCEL = {".xlsx", ".xls"}
SUPPORTED_EXTENSIONS = SUPPORTED_CSV | SUPPORTED_EXCEL


def assert_upload_path(file_path: str | Path) -> Path:
    resolved = Path(file_path).resolve()
    upload_root = settings.upload_dir.resolve()
    if not resolved.is_relative_to(upload_root):
        raise HTTPException(status_code=403, detail="Dataset path is outside the upload directory.")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found.")
    return resolved


def detect_file_type(file_path: str | Path) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix in SUPPORTED_CSV:
        return "csv"
    if suffix in SUPPORTED_EXCEL:
        return "excel"
    raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")


def read_dataframe(file_path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    path = assert_upload_path(file_path)
    file_type = detect_file_type(path)
    read_limit = nrows if nrows is not None else settings.max_dataset_rows + 1
    if file_type == "csv":
        try:
            df = pd.read_csv(path, nrows=read_limit)
        except UnicodeDecodeError:
            df = pd.read_csv(path, nrows=read_limit, encoding="utf-8-sig")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unable to read CSV file: {exc}") from exc
    else:
        try:
            df = pd.read_excel(path, nrows=read_limit, engine="openpyxl")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Unable to read Excel file: {exc}") from exc

    df.columns = [str(column).strip() for column in df.columns]
    if any(not column for column in df.columns):
        raise HTTPException(status_code=400, detail="Dataset contains an empty column name.")
    if len(df.columns) > settings.max_dataset_columns:
        raise HTTPException(
            status_code=413,
            detail=f"Dataset has {len(df.columns)} columns; limit is {settings.max_dataset_columns}.",
        )
    if nrows is None and len(df) > settings.max_dataset_rows:
        raise HTTPException(
            status_code=413,
            detail=f"Dataset exceeds the {settings.max_dataset_rows}-row limit.",
        )
    return df


def preview_dataframe(file_path: str | Path, limit: int = 20) -> pd.DataFrame:
    return read_dataframe(file_path, nrows=max(1, limit))
