import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fastapi import HTTPException, status

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.api.v1.endpoints import playback as playback_module
from app.models.base import Base
from app.models.environment import EnvironmentState
from app.models.training import TrainingAlgorithm, TrainingJob, TrainingJobStatus


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide an isolated in-memory database session for each test."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _create_job(
    session: AsyncSession,
    *,
    name: str = "Playback Job",
    algorithm: TrainingAlgorithm = TrainingAlgorithm.ppo,
    status: TrainingJobStatus = TrainingJobStatus.completed,
    total_timesteps: int = 1_000,
) -> TrainingJob:
    job = TrainingJob(
        name=name,
        algorithm=algorithm,
        environment_type="standard",
        status=status,
        total_timesteps=total_timesteps,
        current_timestep=total_timesteps,
        episodes_completed=5,
    )
    session.add(job)
    await session.flush()
    return job


@dataclass(slots=True)
class _StateSpec:
    episode: int
    step: int
    offset_minutes: int = 0
    reward: float = 0.5


def _build_state(session_id: int, spec: _StateSpec, base_time: datetime) -> EnvironmentState:
    """Construct an environment state using the provided specification."""

    state = EnvironmentState(
        session_id=session_id,
        episode=spec.episode,
        step=spec.step,
        robot_x=spec.step,
        robot_y=spec.episode,
        robot_orientation=spec.step % 4,
        threat_grid={"levels": [[0.1, 0.2], [0.3, 0.4]]},
        coverage_map=None,
        suspicious_objects=None,
        action_taken=1,
        reward_received=spec.reward,
    )
    timestamp = base_time + timedelta(minutes=spec.offset_minutes)
    state.created_at = timestamp
    state.updated_at = timestamp
    return state


@pytest.mark.asyncio
async def test_list_playback_sessions_returns_empty_when_no_states(
    db_session: AsyncSession,
) -> None:
    response = await playback_module.list_playback_sessions(page=1, page_size=10, db=db_session)

    assert response.total == 0
    assert response.sessions == []


@pytest.mark.asyncio
async def test_list_playback_sessions_returns_summary_sorted_by_last_recorded(
    db_session: AsyncSession,
) -> None:
    first_job = await _create_job(db_session, name="Session A")
    second_job = await _create_job(db_session, name="Session B")

    base_time = datetime.now(tz=UTC)
    states_job_one = [
        _build_state(first_job.id, _StateSpec(episode=0, step=0, offset_minutes=0), base_time),
        _build_state(first_job.id, _StateSpec(episode=1, step=5, offset_minutes=10), base_time),
    ]
    states_job_two = [
        _build_state(second_job.id, _StateSpec(episode=0, step=1, offset_minutes=20), base_time),
    ]
    db_session.add_all(states_job_one + states_job_two)
    await db_session.commit()

    response = await playback_module.list_playback_sessions(page=1, page_size=10, db=db_session)

    assert response.total == 2
    assert len(response.sessions) == 2
    # Session B should appear first because it has the most recent state
    assert response.sessions[0].session_id == second_job.id
    assert response.sessions[0].frame_count == 1
    assert response.sessions[0].last_episode == 0
    assert response.sessions[1].session_id == first_job.id
    assert response.sessions[1].frame_count == 2
    assert response.sessions[1].first_episode == 0
    assert response.sessions[1].last_episode == 1


@pytest.mark.asyncio
async def test_get_playback_frames_returns_frames_sorted(
    db_session: AsyncSession,
) -> None:
    job = await _create_job(db_session)
    base_time = datetime.now(tz=UTC)

    states = [
        _build_state(job.id, _StateSpec(episode=2, step=3, offset_minutes=5, reward=0.7), base_time),
        _build_state(job.id, _StateSpec(episode=1, step=0, offset_minutes=2, reward=0.4), base_time),
        _build_state(job.id, _StateSpec(episode=2, step=1, offset_minutes=3, reward=0.6), base_time),
    ]
    db_session.add_all(states)
    await db_session.commit()

    response = await playback_module.get_playback_frames(
        session_id=job.id,
        page=1,
        page_size=10,
        db=db_session,
    )

    assert response.total == 3
    assert len(response.frames) == 3
    episodes = [frame.episode for frame in response.frames]
    steps = [frame.step for frame in response.frames]
    assert episodes == [1, 2, 2]
    assert steps == [0, 1, 3]
    rewards = [frame.reward_received for frame in response.frames]
    assert rewards == [0.4, 0.6, 0.7]


@pytest.mark.asyncio
async def test_get_playback_frames_returns_empty_when_session_has_no_frames(
    db_session: AsyncSession,
) -> None:
    job = await _create_job(db_session)
    response = await playback_module.get_playback_frames(
        session_id=job.id,
        page=1,
        page_size=5,
        db=db_session,
    )

    assert response.total == 0
    assert response.frames == []


@pytest.mark.asyncio
async def test_get_playback_frames_raises_for_unknown_session(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await playback_module.get_playback_frames(
            session_id=999,
            page=1,
            page_size=10,
            db=db_session,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "999" in exc_info.value.detail
