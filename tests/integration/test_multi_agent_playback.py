"""Integration tests for multi-agent playback API endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator

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
  num_robots: int = 1,
) -> TrainingJob:
  async def _persist() -> TrainingJob:
    async with session_maker() as session:
      job = TrainingJob(
        name=name,
        algorithm=TrainingAlgorithm.ppo,
        environment_type="standard",
        status=TrainingJobStatus.completed,
        total_timesteps=1000,
        num_robots=num_robots,
        started_at=utcnow(),
        completed_at=utcnow(),
      )
      session.add(job)
      await session.commit()
      await session.refresh(job)
      return job

  return asyncio.run(_persist())


def _create_multi_agent_states(
  session_maker: async_sessionmaker[AsyncSession],
  *,
  session_id: int,
) -> None:
  async def _persist() -> None:
    async with session_maker() as session:
      state = EnvironmentState(
        session_id=session_id,
        episode=0,
        step=1,
        robot_x=1,
        robot_y=1,
        robot_orientation=0,
        robots=[
          {"id": 0, "x": 1, "y": 1, "orientation": 0},
          {"id": 1, "x": 5, "y": 5, "orientation": 2},
        ],
        threat_grid={"levels": [[0.0]]},
        coverage_map={"counts": [[0.0]]},
        obstacles={"levels": [[False]]},
        suspicious_objects=[],
        action_taken=0,
        reward_received=1.0,
        created_at=utcnow(),
        updated_at=utcnow(),
      )
      session.add(state)
      await session.commit()

  asyncio.run(_persist())


def test_get_playback_frames_returns_multi_agent_data(
  playback_api_app: tuple[FastAPI, async_sessionmaker[AsyncSession]],
) -> None:
  app, session_maker = playback_api_app

  job = _create_job(session_maker, name="Multi-Agent Session", num_robots=2)
  _create_multi_agent_states(session_maker, session_id=job.id)

  with TestClient(app) as client:
    response = client.get(
      f"/api/v1/playback/{job.id}/frames",
      params={"page": 1, "page_size": 10},
    )

  assert response.status_code == 200
  payload = response.json()
  assert payload["total"] == 1
  frame = payload["frames"][0]

  assert "robots" in frame
  assert frame["robots"] is not None
  assert len(frame["robots"]) == 2
  assert frame["robots"][0]["x"] == 1
  assert frame["robots"][1]["x"] == 5
