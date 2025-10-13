from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.main as main_module
from app.api.deps import get_db
from app.api.v1.endpoints import training as training_module
from app.core.training.job_manager import JobManager
from app.db import database as database_module
from app.db import session as session_module
from app.main import create_app
from app.models.training import TrainingJob, TrainingJobStatus


@pytest.fixture()
def training_api_app(monkeypatch: pytest.MonkeyPatch) -> tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager]:
    """Provide a FastAPI app wired to an in-memory database and fresh job manager."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    monkeypatch.setattr(database_module, "database_engine", engine)
    monkeypatch.setattr(main_module, "database_engine", engine)
    monkeypatch.setattr(session_module, "async_session", session_maker)

    job_manager = JobManager()
    monkeypatch.setattr(training_module, "job_manager", job_manager)

    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield app, session_maker, job_manager

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def _load_job(session_maker: async_sessionmaker[AsyncSession], job_id: int) -> TrainingJob | None:
    async def _get() -> TrainingJob | None:
        async with session_maker() as session:
            return await session.get(TrainingJob, job_id)

    return asyncio.run(_get())


def test_start_training_creates_session_and_enqueues_job(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager]
) -> None:
    app, session_maker, job_manager = training_api_app

    payload = {
        "name": "Integration job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 500,
        "env_width": 8,
        "env_height": 8,
        "coverage_weight": 1.5,
        "exploration_weight": 3.0,
        "diversity_weight": 2.0,
        "learning_rate": 0.0003,
        "batch_size": 64,
        "num_workers": 1,
        "config": {"seed": 123},
    }

    with TestClient(app) as client:
        response = client.post("/api/v1/training/start", json=payload)

    assert response.status_code == 202
    body = response.json()
    assert body["name"] == payload["name"]
    assert body["status"] == TrainingJobStatus.queued.value

    job = _load_job(session_maker, body["id"])
    assert job is not None
    assert job.status is TrainingJobStatus.queued

    queue_entries = job_manager.snapshot()
    assert len(queue_entries) == 1
    assert queue_entries[0]["session_id"] == body["id"]


def test_pause_unknown_session_returns_not_found(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager]
) -> None:
    app, _, _ = training_api_app

    with TestClient(app) as client:
        response = client.post("/api/v1/training/999/pause")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"].startswith("Training session 999 not found")


def test_resume_requires_paused_status(
    training_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession], JobManager]
) -> None:
    app, _, _ = training_api_app

    payload = {
        "name": "Queued job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 200,
        "env_width": 6,
        "env_height": 6,
        "coverage_weight": 1.0,
        "exploration_weight": 2.5,
        "diversity_weight": 1.5,
        "learning_rate": 0.0005,
        "batch_size": 32,
        "num_workers": 1,
        "config": None,
    }

    with TestClient(app) as client:
        start_response = client.post("/api/v1/training/start", json=payload)
        assert start_response.status_code == 202
        session_id = start_response.json()["id"]

        resume_response = client.post(f"/api/v1/training/{session_id}/resume")

    assert resume_response.status_code == 400
    error = resume_response.json()
    assert "paused" in error["detail"].lower()
