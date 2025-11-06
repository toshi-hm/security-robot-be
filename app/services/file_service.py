"""Service layer responsible for file metadata persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.core.files.service import FileStorageService, file_storage_service
from app.models.files import FileMetadata


class FileService:
    """Coordinate file storage operations with database persistence."""

    def __init__(self, db: AsyncSession, storage: FileStorageService | None = None):
        self._db = db
        self._storage = storage or file_storage_service

    async def save_upload(
        self,
        *,
        upload: UploadFile,
        file_type: str,
        training_job_id: int | None,
        description: str | None,
        metadata: dict[str, Any] | None,
    ) -> FileMetadata:
        filename, relative_path, file_size, content_type = await self._storage.save_upload(
            upload,
            file_type=file_type,
        )

        stored_file_type = Path(relative_path).parts[0] if Path(relative_path).parts else file_type

        record = FileMetadata(
            filename=filename,
            original_filename=upload.filename or filename,
            file_path=relative_path,
            file_size=file_size,
            file_type=stored_file_type,
            content_type=content_type,
            training_job_id=training_job_id,
            description=description,
            metadata_=metadata,
        )

        self._db.add(record)
        await self._db.commit()
        await self._db.refresh(record)
        return record

    async def list_files(self, page: int, page_size: int) -> tuple[list[FileMetadata], int]:
        total_stmt = select(func.count()).select_from(FileMetadata)
        total_result = await self._db.execute(total_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        records_stmt = (
            select(FileMetadata)
            .order_by(FileMetadata.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        records_result = await self._db.execute(records_stmt)
        records = records_result.scalars().all()
        return records, total

    async def get_file(self, file_id: int) -> FileMetadata | None:
        return await self._db.get(FileMetadata, file_id)

    async def delete_file(self, record: FileMetadata) -> None:
        self._storage.delete(record.file_path)
        await self._db.delete(record)
        await self._db.commit()

    def resolve_path(self, record: FileMetadata) -> str:
        return str(self._storage.resolve(record.file_path))


__all__ = ["FileService"]
