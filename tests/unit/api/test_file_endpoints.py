"""Unit tests for the file management API endpoints."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.datastructures import Headers, UploadFile

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.api.v1.endpoints import files as files_module
from app.models.base import Base
from app.models.files import FileMetadata


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Provide an isolated in-memory database session for each test."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def patch_storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure file storage writes into a temporary directory for tests."""

    from app.core.files import storage

    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path)
    storage.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


async def _create_upload(
    filename: str, data: bytes, content_type: str = "application/octet-stream"
) -> UploadFile:
    headers = Headers({"content-type": content_type})
    return UploadFile(filename=filename, file=BytesIO(data), headers=headers)


@pytest.mark.asyncio
async def test_upload_file_persists_metadata_and_binary(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    upload = await _create_upload("model.zip", b"fake-binary-data", "application/zip")

    response = await files_module.upload_file(
        file=upload,
        file_type="model",
        training_job_id=42,
        description="PPO checkpoint",
        metadata='{"version": "1.0"}',
        db=db_session,
    )

    assert response.original_filename == "model.zip"
    assert response.file_type == "model"
    assert response.training_job_id == 42
    assert response.file_size == len(b"fake-binary-data")

    stored_path = Path(tmp_path, response.file_path)
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"fake-binary-data"

    stmt = select(FileMetadata).where(FileMetadata.id == response.id)
    result = await db_session.execute(stmt)
    metadata = result.scalar_one()
    assert metadata.metadata_ == {"version": "1.0"}
    assert metadata.description == "PPO checkpoint"


@pytest.mark.asyncio
async def test_list_files_returns_paginated_results(db_session: AsyncSession) -> None:
    uploads = [
        await _create_upload(f"file_{idx}.txt", f"payload-{idx}".encode(), "text/plain")
        for idx in range(3)
    ]

    for upload in uploads:
        await files_module.upload_file(
            file=upload,
            file_type="log",
            training_job_id=None,
            description=None,
            metadata=None,
            db=db_session,
        )

    response = await files_module.list_files(page=1, page_size=2, db=db_session)

    assert response.total == 3
    assert response.page == 1
    assert response.page_size == 2
    assert len(response.files) == 2

    timestamps = [entry.created_at for entry in response.files]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.asyncio
async def test_delete_file_removes_binary_and_metadata(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    upload = await _create_upload("log.txt", b"log-data", "text/plain")
    created = await files_module.upload_file(
        file=upload,
        file_type="log",
        training_job_id=None,
        description=None,
        metadata=None,
        db=db_session,
    )

    stored_path = Path(tmp_path, created.file_path)
    assert stored_path.exists()

    response = await files_module.delete_file(file_id=created.id, db=db_session)

    assert response.id == created.id
    assert response.filename == created.filename

    assert not stored_path.exists()

    stmt = select(FileMetadata).where(FileMetadata.id == created.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_file_metadata_raises_for_missing_entry(db_session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as excinfo:
        await files_module.get_file_metadata(file_id=999, db=db_session)

    assert excinfo.value.status_code == 404
    assert "not found" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_upload_file_validates_metadata_json(db_session: AsyncSession) -> None:
    upload = await _create_upload("config.json", b"{}", "application/json")

    with pytest.raises(HTTPException) as excinfo:
        await files_module.upload_file(
            file=upload,
            file_type="config",
            training_job_id=None,
            description=None,
            metadata="not-json",
            db=db_session,
        )

    assert excinfo.value.status_code == 400
    assert "metadata" in excinfo.value.detail.lower()
