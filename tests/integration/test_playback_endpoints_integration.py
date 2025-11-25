"""Integration tests for playback API endpoints using the FastAPI test client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.db import database as database_module
from app.db import session as session_module
import app.main as main_module
from app.main import create_app
from app.models import Base
from app.models.environment import EnvironmentState
from app.models.training import TrainingAlgorithm, TrainingJob, TrainingJobStatus
from app.utils.datetime import utcnow
from fastapi import FastAPI


@pytest.fixture()
def playback_api_app(
  monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[FastAPI, async_sessionmaker[AsyncSession]], None, None]:
  """Create a FastAPI app backed by an in-memory database for playback tests."""

  engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
  session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

  monkeypatch.setattr(database_module, "database_engine", engine)
  monkeypatch.setattr(main_module, "database_engine", engine)
  monkeypatch.setattr(session_module, "async_session", session_maker)

  async def _create_schema() -> None:
    async with engine.begin() as conn:
      await conn.run_sync(Base.metadata.create_all)

  asyncio.run(_create_schema())

  app = create_app()

  async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with session_maker() as session:
      yield session

  app.dependency_overrides[get_db] = override_get_db

  yield app, session_maker

  app.dependency_overrides.clear()
  asyncio.run(engine.dispose())


def _create_job(
  session_maker: async_sessionmaker[AsyncSession],
  *,
  name: str,
  status: TrainingJobStatus = TrainingJobStatus.completed,
  algorithm: TrainingAlgorithm = TrainingAlgorithm.ppo,
  environment_type: str = "standard",
  total_timesteps: int = 1_000,
  current_timestep: int = 500,
  episodes_completed: int = 10,
  started_at: datetime | None = None,
  completed_at: datetime | None = None,
) -> TrainingJob:
  async def _persist() -> TrainingJob:
    async with session_maker() as session:
      job = TrainingJob(
        name=name,
        algorithm=algorithm,
        environment_type=environment_type,
        status=status,
        total_timesteps=total_timesteps,
        current_timestep=current_timestep,
        episodes_completed=episodes_completed,
        started_at=started_at or utcnow(),
        completed_at=completed_at or utcnow(),
      )
      session.add(job)
      await session.commit()
      await session.refresh(job)
      return job

  return asyncio.run(_persist())


def _create_states(
  session_maker: async_sessionmaker[AsyncSession],
  *,
  session_id: int,
  specs: list[tuple[int, int, datetime]],
) -> None:
  async def _persist() -> None:
    async with session_maker() as session:
      for episode, step, timestamp in specs:
        state = EnvironmentState(
          session_id=session_id,
          episode=episode,
          step=step,
          robot_x=step,
          robot_y=episode,
          robot_orientation=step % 4,
          threat_grid={"levels": [[float(step)]]},
          coverage_map={"counts": [[float(episode)]]},
          obstacles={"levels": [[False]]},
          suspicious_objects=[],
          action_taken=step % 5,
          reward_received=step * 0.1,
          created_at=timestamp,
          updated_at=timestamp,
        )
        session.add(state)
      await session.commit()

  asyncio.run(_persist())


def test_list_playback_sessions_returns_paginated_summaries(
  playback_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
  app, session_maker = playback_api_app

  now = datetime.now(tz=UTC)
  older = now - timedelta(minutes=30)

  first_job = _create_job(
    session_maker,
    name="Older session",
    current_timestep=200,
    episodes_completed=4,
    started_at=older - timedelta(minutes=10),
    completed_at=older,
  )
  second_job = _create_job(
    session_maker,
    name="Newer session",
    current_timestep=300,
    episodes_completed=6,
    started_at=now - timedelta(minutes=20),
    completed_at=now - timedelta(minutes=5),
  )

  _create_states(
    session_maker,
    session_id=first_job.id,
    specs=[
      (0, 0, older - timedelta(minutes=5)),
      (1, 3, older - timedelta(minutes=1)),
    ],
  )
  _create_states(
    session_maker,
    session_id=second_job.id,
    specs=[
      (0, 1, now - timedelta(minutes=4)),
      (0, 2, now - timedelta(minutes=3)),
      (1, 0, now - timedelta(minutes=2)),
    ],
  )

  with TestClient(app) as client:
    response = client.get("/api/v1/playback/sessions", params={"page": 1, "page_size": 10})

  assert response.status_code == 200
  payload = response.json()
  assert payload["total"] == 2
  assert payload["page"] == 1
  assert payload["page_size"] == 10

  sessions = payload["sessions"]
  assert [session["session_id"] for session in sessions] == [second_job.id, first_job.id]
  assert sessions[0]["frame_count"] == 3
  assert sessions[0]["last_episode"] == 1
  assert sessions[1]["frame_count"] == 2
  assert sessions[1]["first_episode"] == 0


def test_get_playback_frames_returns_sorted_frames(
  playback_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
  app, session_maker = playback_api_app
  now = datetime.now(tz=UTC)

  job = _create_job(session_maker, name="Frame session", episodes_completed=2)
  _create_states(
    session_maker,
    session_id=job.id,
    specs=[
      (1, 2, now - timedelta(minutes=10)),
      (0, 1, now - timedelta(minutes=12)),
      (1, 1, now - timedelta(minutes=11)),
    ],
  )

  with TestClient(app) as client:
    response = client.get(
      f"/api/v1/playback/{job.id}/frames",
      params={"page": 1, "page_size": 10},
    )

  assert response.status_code == 200
  payload = response.json()
  assert payload["total"] == 3
  assert [frame["episode"] for frame in payload["frames"]] == [0, 1, 1]
  assert [frame["step"] for frame in payload["frames"]] == [1, 1, 2]
  assert payload["frames"][0]["obstacles"] == {"levels": [[False]]}


def test_get_playback_frames_returns_empty_payload_when_no_states(
  playback_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
  app, session_maker = playback_api_app

  job = _create_job(session_maker, name="Empty session", episodes_completed=0)

  with TestClient(app) as client:
    response = client.get(
      f"/api/v1/playback/{job.id}/frames",
      params={"page": 1, "page_size": 5},
    )

  assert response.status_code == 200
  payload = response.json()
  assert payload["total"] == 0
  assert payload["frames"] == []


def test_get_playback_frames_returns_not_found_for_unknown_session(
  playback_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
  app, _ = playback_api_app

  with TestClient(app) as client:
    response = client.get(
      "/api/v1/playback/999/frames",
      params={"page": 1, "page_size": 5},
    )

  assert response.status_code == 404
  payload = response.json()
  assert "not found" in payload["detail"].lower()
