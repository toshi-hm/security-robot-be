import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.api.v1.endpoints import training as training_module
from app.models.base import Base
from app.models.training import TrainingJob, TrainingJobStatus, TrainingMetric


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
    now = datetime.now(timezone.utc)
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

    assert metric.timestamp.tzinfo is timezone.utc


@pytest.mark.asyncio
async def test_training_job_audit_timestamps_are_timezone_aware(db_session: AsyncSession) -> None:
    job = await _create_job(db_session)

    assert job.created_at.tzinfo is timezone.utc
    assert job.updated_at.tzinfo is timezone.utc
