from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.datasets.profiler import profile_dataframe
from app.datasets.storage import DatasetStorage
from app.domain import DatasetMetadata
from app.settings import settings
from app.tools.dataset_reader import SUPPORTED_EXTENSIONS, detect_file_type, preview_dataframe, read_dataframe
from app.tools.serialization import dataframe_to_records


class DatasetService:
    def __init__(self, storage: DatasetStorage) -> None:
        self.storage = storage

    async def save_upload(self, upload: UploadFile) -> tuple[DatasetMetadata, object, list[dict]]:
        settings.ensure_directories()
        original_filename = Path(upload.filename or "dataset.csv").name
        suffix = Path(original_filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported.")

        dataset_id = uuid4().hex
        stored_filename = f"{dataset_id}{suffix}"
        file_path = (settings.upload_dir / stored_filename).resolve()
        if not file_path.is_relative_to(settings.upload_dir.resolve()):
            raise HTTPException(status_code=400, detail="Invalid upload path.")

        size = 0
        try:
            with file_path.open("wb") as target:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(status_code=413, detail="Uploaded file exceeds the size limit.")
                    target.write(chunk)

            df = read_dataframe(file_path)
            profile = profile_dataframe(df, dataset_id=dataset_id)
            metadata = DatasetMetadata(
                dataset_id=dataset_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=str(file_path),
                file_type=detect_file_type(file_path),
                size_bytes=size,
                row_count=profile.row_count,
                column_count=profile.column_count,
                columns=[column.name for column in profile.columns],
                created_at=datetime.now(timezone.utc),
            )
            self.storage.add_dataset(metadata, profile)
            preview = dataframe_to_records(df, limit=20)
            return metadata, profile, preview
        except HTTPException:
            file_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"Failed to process dataset: {exc}") from exc

    def get_dataset(self, dataset_id: str):
        result = self.storage.get_dataset(dataset_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Dataset not found.")
        return result

    def list_datasets(self):
        return self.storage.list_datasets()

    def preview(self, dataset_id: str, limit: int = 20):
        metadata, _ = self.get_dataset(dataset_id)
        df = preview_dataframe(metadata.file_path, limit=limit)
        return metadata.columns, dataframe_to_records(df, limit=limit)


dataset_service = DatasetService(DatasetStorage(settings.db_path))
