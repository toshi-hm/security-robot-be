import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.api.v1.endpoints import training as training_module
from app.models.base import Base
from app.models.training import TrainingJob, TrainingJobStatus, TrainingMetric
from app.schemas.training import TrainingSessionCreate
from app.core.training.job_manager import JobManager


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Create an isolated in-memory database session for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def job_manager_stub(monkeypatch: pytest.MonkeyPatch) -> JobManager:
    """Provide a fresh in-memory job manager for each test."""

    manager = JobManager()
    monkeypatch.setattr(training_module, "job_manager", manager)
    return manager


def _session_payload(**overrides: object) -> TrainingSessionCreate:
    """Build a valid training session payload with optional overrides."""

    base: dict[str, object] = {
        "name": "Queue job",
        "algorithm": "ppo",
        "environment_type": "standard",
        "total_timesteps": 1_000,
        "env_width": 8,
        "env_height": 8,
        "coverage_weight": 1.5,
        "exploration_weight": 3.0,
        "diversity_weight": 2.0,
        "learning_rate": 0.0003,
        "batch_size": 64,
        "num_workers": 1,
        "config": {"seed": 42},
    }
    base.update(overrides)
    return TrainingSessionCreate(**base)


async def _create_job(session: AsyncSession) -> TrainingJob:
    job = TrainingJob(
        name="Test Job",
        algorithm="ppo",
        environment_type="standard",
        status=TrainingJobStatus.running,
        total_timesteps=1000,
        current_timestep=200,
        episodes_completed=10,
    )
    session.add(job)
    await session.flush()
    return job


async def _create_metrics(session: AsyncSession, job_id: int, count: int = 3) -> None:
    now = datetime.now(UTC)
    metrics = [
        TrainingMetric(
            job_id=job_id,
            timestep=100 * idx,
            episode=idx,
            reward=1.5 * idx,
            loss=0.01 * idx,
            timestamp=now - timedelta(minutes=idx),
        )
        for idx in range(count)
    ]
    session.add_all(metrics)
    await session.commit()


@pytest.mark.asyncio
async def test_start_training_enqueues_job_and_returns_response(
    db_session: AsyncSession,
    job_manager_stub: JobManager,
) -> None:
    config = _session_payload(total_timesteps=500, coverage_weight=2.0)

    response = await training_module.start_training(config=config, db=db_session)

    assert response.status == TrainingJobStatus.queued
    queue_entries = job_manager_stub.snapshot()
    assert len(queue_entries) == 1
    entry = queue_entries[0]
    assert entry["session_id"] == response.id
    assert entry["payload"]["config"]["total_timesteps"] == config.total_timesteps

    persisted = await db_session.get(TrainingJob, response.id)
    assert persisted is not None
    assert persisted.status is TrainingJobStatus.queued


@pytest.mark.asyncio
async def test_start_training_bubbles_service_validation_error(
    db_session: AsyncSession,
    job_manager_stub: JobManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _session_payload()

    class RejectingTrainingService:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        async def create_session(self, *_: object, **__: object) -> TrainingJob:
            raise ValueError("invalid configuration")

    monkeypatch.setattr(training_module, "TrainingService", RejectingTrainingService)

    with pytest.raises(HTTPException) as excinfo:
        await training_module.start_training(config=config, db=db_session)

    assert excinfo.value.status_code == status.HTTP_400_BAD_REQUEST
    assert job_manager_stub.snapshot() == []


@pytest.mark.asyncio
async def test_pause_training_requires_active_status(
    db_session: AsyncSession,
) -> None:
    job = await _create_job(db_session)
    job.status = TrainingJobStatus.completed
    await db_session.commit()

    with pytest.raises(HTTPException) as excinfo:
        await training_module.pause_training(session_id=job.id, db=db_session)

    assert excinfo.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_pause_training_updates_status_and_queue(
    db_session: AsyncSession,
    job_manager_stub: JobManager,
) -> None:
    job = await _create_job(db_session)
    await db_session.commit()
    await job_manager_stub.enqueue({"session_id": job.id})

    response = await training_module.pause_training(session_id=job.id, db=db_session)

    assert response.status == TrainingJobStatus.paused
    refreshed = await db_session.get(TrainingJob, job.id)
    assert refreshed is not None
    assert refreshed.status is TrainingJobStatus.paused
    entry = job_manager_stub.snapshot()[0]
    assert entry["status"] == "stopped"
    assert entry["session_id"] == job.id


@pytest.mark.asyncio
async def test_resume_training_requeues_existing_job(
    db_session: AsyncSession,
    job_manager_stub: JobManager,
) -> None:
    job = await _create_job(db_session)
    job.status = TrainingJobStatus.paused
    job.completed_at = datetime.now(UTC)
    await db_session.commit()

    await job_manager_stub.enqueue({"session_id": job.id})
    await job_manager_stub.stop(job.id)

    response = await training_module.resume_training(session_id=job.id, db=db_session)

    assert response.status == TrainingJobStatus.queued
    refreshed = await db_session.get(TrainingJob, job.id)
    assert refreshed is not None
    assert refreshed.status is TrainingJobStatus.queued
    assert refreshed.completed_at is None

    entry = job_manager_stub.snapshot()[0]
    assert entry["status"] == "queued"
    assert entry["payload"]["session_id"] == job.id


@pytest.mark.asyncio
async def test_resume_training_enqueues_when_missing_from_queue(
    db_session: AsyncSession,
    job_manager_stub: JobManager,
) -> None:
    job = await _create_job(db_session)
    job.status = TrainingJobStatus.paused
    await db_session.commit()

    response = await training_module.resume_training(session_id=job.id, db=db_session)

    assert response.status == TrainingJobStatus.queued
    entry = job_manager_stub.snapshot()[0]
    assert entry["session_id"] == job.id


@pytest.mark.asyncio
async def test_stop_training_marks_job_failed_and_updates_queue(
    db_session: AsyncSession,
    job_manager_stub: JobManager,
) -> None:
    job = await _create_job(db_session)
    await db_session.commit()
    await job_manager_stub.enqueue({"session_id": job.id})

    response = await training_module.stop_training(session_id=job.id, db=db_session)

    assert response.status == TrainingJobStatus.failed
    refreshed = await db_session.get(TrainingJob, job.id)
    assert refreshed is not None
    assert refreshed.status is TrainingJobStatus.failed
    assert refreshed.completed_at is not None
    entry = job_manager_stub.snapshot()[0]
    assert entry["status"] == "stopped"


@pytest.mark.asyncio
async def test_get_training_status_returns_serialized_job(
    db_session: AsyncSession,
) -> None:
    job = await _create_job(db_session)
    await db_session.commit()

    response = await training_module.get_training_status(session_id=job.id, db=db_session)

    assert response.id == job.id
    assert response.status == job.status


@pytest.mark.asyncio
async def test_list_training_sessions_returns_latest_first(
    db_session: AsyncSession,
) -> None:
    first = await _create_job(db_session)
    second = await _create_job(db_session)
    third = await _create_job(db_session)
    await db_session.commit()

    response = await training_module.list_training_sessions(
        page=1,
        page_size=2,
        db=db_session,
    )

    assert response.total == 3
    assert len(response.sessions) == 2
    assert response.sessions[0].id == third.id
    assert response.sessions[1].id == second.id


@pytest.mark.asyncio
async def test_delete_training_session_removes_from_db_and_queue(
    db_session: AsyncSession,
    job_manager_stub: JobManager,
) -> None:
    job = await _create_job(db_session)
    await db_session.commit()
    await job_manager_stub.enqueue({"session_id": job.id})

    response = await training_module.delete_training_session(session_id=job.id, db=db_session)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    deleted = await db_session.get(TrainingJob, job.id)
    assert deleted is None
    assert job_manager_stub.snapshot() == []


@pytest.mark.asyncio
async def test_get_metrics_returns_paginated_data(db_session: AsyncSession) -> None:
    job = await _create_job(db_session)
    await _create_metrics(db_session, job.id, count=3)

    response = await training_module.get_metrics(
        session_id=job.id,
        page=1,
        page_size=2,
        db=db_session,
    )

    assert response.total == 3
    assert response.page == 1
    assert response.page_size == 2
    # Metrics should be returned in descending timestamp order
    assert len(response.metrics) == 2
    timestamps = [metric.timestamp for metric in response.metrics]
    assert timestamps == sorted(timestamps, reverse=True)


@pytest.mark.asyncio
async def test_get_metrics_raises_when_session_missing(db_session: AsyncSession) -> None:
    with pytest.raises(HTTPException) as excinfo:
        await training_module.get_metrics(session_id=999, db=db_session)

    assert excinfo.value.status_code == 404
    assert "not found" in excinfo.value.detail.lower()


@pytest.mark.asyncio
async def test_get_metrics_respects_page_offset(db_session: AsyncSession) -> None:
    job = await _create_job(db_session)
    await _create_metrics(db_session, job.id, count=5)

    response = await training_module.get_metrics(
        session_id=job.id,
        page=2,
        page_size=2,
        db=db_session,
    )

    assert response.total == 5
    assert response.page == 2
    assert len(response.metrics) == 2

    # Ensure returned metrics correspond to proper offset by checking timesteps
    metric_timesteps = [metric.timestep for metric in response.metrics]

    stmt = (
        select(TrainingMetric)
        .where(TrainingMetric.job_id == job.id)
        .order_by(TrainingMetric.timestamp.desc())
        .offset(2)
        .limit(2)
    )
    result = await db_session.execute(stmt)
    expected_timesteps = [metric.timestep for metric in result.scalars().all()]

    assert metric_timesteps == expected_timesteps


@pytest.mark.asyncio
async def test_training_metric_timestamp_is_timezone_aware(db_session: AsyncSession) -> None:
    job = await _create_job(db_session)

    metric = TrainingMetric(
        job_id=job.id,
        timestep=1,
        reward=1.0,
    )
    db_session.add(metric)
    await db_session.flush()

    assert metric.timestamp.tzinfo is UTC


@pytest.mark.asyncio
async def test_training_job_audit_timestamps_are_timezone_aware(db_session: AsyncSession) -> None:
    job = await _create_job(db_session)

    assert job.created_at.tzinfo is UTC
    assert job.updated_at.tzinfo is UTC
