"""Integration tests for the file management API endpoints."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.main as main_module
from app.api.deps import get_db
from app.db import database as database_module
from app.db import session as session_module
from app.main import create_app


@pytest.fixture()
def file_api_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Provide a FastAPI app backed by an in-memory DB and temp storage."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(database_module, "database_engine", engine)
    monkeypatch.setattr(main_module, "database_engine", engine)
    monkeypatch.setattr(session_module, "async_session", session_maker)

    from app.core.files import storage as storage_module

    monkeypatch.setattr(storage_module, "STORAGE_ROOT", tmp_path)
    storage_module.STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield app, tmp_path

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def test_upload_and_download_round_trip(file_api_app: tuple[FastAPI, Path]) -> None:
    app, storage_root = file_api_app

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/files/",
            data={
                "file_type": "model",
                "training_job_id": "7",
                "description": "Integration upload",
                "metadata": "{\"version\": \"1.2.3\"}",
            },
            files={"file": ("checkpoint.zip", b"binary-data", "application/zip")},
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["original_filename"] == "checkpoint.zip"
        assert payload["training_job_id"] == 7

        stored_path = storage_root / payload["file_path"]
        assert stored_path.exists()
        assert stored_path.read_bytes() == b"binary-data"

        download = client.get(f"/api/v1/files/{payload['id']}/download")
        assert download.status_code == 200
        assert download.content == b"binary-data"
        assert download.headers["content-type"] == "application/zip"
        assert "attachment" in download.headers["content-disposition"].lower()
        assert "checkpoint.zip" in download.headers["content-disposition"]


def test_download_missing_record_returns_not_found(file_api_app: tuple[FastAPI, Path]) -> None:
    app, _ = file_api_app

    with TestClient(app) as client:
        response = client.get("/api/v1/files/999/download")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body, f"Expected 'detail' key in error response, got: {body}"
    assert "not found" in body["detail"].lower()


def test_download_missing_binary_returns_not_found(file_api_app: tuple[FastAPI, Path]) -> None:
    app, storage_root = file_api_app

    with TestClient(app) as client:
        upload = client.post(
            "/api/v1/files/",
            data={"file_type": "log"},
            files={"file": ("run.log", b"log-bytes", "text/plain")},
        )
        assert upload.status_code == 201
        payload = upload.json()

        missing_path = storage_root / payload["file_path"]
        assert missing_path.exists()
        missing_path.unlink()

        response = client.get(f"/api/v1/files/{payload['id']}/download")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body, f"Expected 'detail' key in error response, got: {body}"
    assert "missing" in body["detail"].lower()
