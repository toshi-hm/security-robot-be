"""Service layer helpers for playback-related database operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.environment import EnvironmentState
from app.models.training import TrainingJob
from app.schemas.environment import EnvironmentStateCreate


@dataclass(slots=True)
class PlaybackSessionAggregate:
  """Aggregate information about recorded playback frames for a session."""

  job: TrainingJob
  frame_count: int
  first_episode: int | None
  last_episode: int | None
  first_recorded_at: datetime | None
  last_recorded_at: datetime | None
  last_step: int | None


class PlaybackService:
  """Encapsulate playback queries and mutations against the database."""

  def __init__(self, db: AsyncSession) -> None:
    self._db = db

  async def get_job(self, session_id: int) -> TrainingJob | None:
    """Return the training job associated with a session id."""

    return await self._db.get(TrainingJob, session_id)

  async def list_sessions(
    self, page: int, page_size: int
  ) -> tuple[list[PlaybackSessionAggregate], int]:
    """List sessions that have at least one recorded playback frame."""

    summary = (
      select(
        EnvironmentState.session_id.label('session_id'),
        func.count(EnvironmentState.id).label('frame_count'),
        func.min(EnvironmentState.episode).label('first_episode'),
        func.max(EnvironmentState.episode).label('last_episode'),
        func.min(EnvironmentState.created_at).label('first_recorded_at'),
        func.max(EnvironmentState.created_at).label('last_recorded_at'),
        func.max(EnvironmentState.step).label('last_step'),
      )
      .group_by(EnvironmentState.session_id)
      .subquery()
    )

    total_stmt = select(func.count()).select_from(summary)
    total_result = await self._db.execute(total_stmt)
    total = total_result.scalar_one_or_none() or 0

    if total == 0:
      return [], 0

    offset = (page - 1) * page_size
    records_stmt = (
      select(
        TrainingJob,
        summary.c.frame_count,
        summary.c.first_episode,
        summary.c.last_episode,
        summary.c.first_recorded_at,
        summary.c.last_recorded_at,
        summary.c.last_step,
      )
      .join(summary, TrainingJob.id == summary.c.session_id)
      .order_by(summary.c.last_recorded_at.desc(), TrainingJob.id.desc())
      .offset(offset)
      .limit(page_size)
    )

    records_result = await self._db.execute(records_stmt)
    aggregates: list[PlaybackSessionAggregate] = []
    for row in records_result.all():
      job: TrainingJob = row[0]
      aggregates.append(
        PlaybackSessionAggregate(
          job=job,
          frame_count=int(row.frame_count),
          first_episode=row.first_episode,
          last_episode=row.last_episode,
          first_recorded_at=row.first_recorded_at,
          last_recorded_at=row.last_recorded_at,
          last_step=row.last_step,
        )
      )

    return aggregates, total

  async def list_frames(
    self, session_id: int, page: int, page_size: int
  ) -> tuple[list[EnvironmentState], int]:
    """Return paginated playback frames for the given session."""

    total_stmt = (
      select(func.count())
      .select_from(EnvironmentState)
      .where(EnvironmentState.session_id == session_id)
    )
    total_result = await self._db.execute(total_stmt)
    total = total_result.scalar_one_or_none() or 0

    if total == 0:
      return [], 0

    offset = (page - 1) * page_size
    frames_stmt = (
      select(EnvironmentState)
      .where(EnvironmentState.session_id == session_id)
      .order_by(
        EnvironmentState.episode.asc(),
        EnvironmentState.step.asc(),
        EnvironmentState.id.asc(),
      )
      .offset(offset)
      .limit(page_size)
    )
    frames_result = await self._db.execute(frames_stmt)
    frames = list(frames_result.scalars().all())
    return frames, total

  async def record_state(self, payload: EnvironmentStateCreate) -> EnvironmentState:
    """Persist a new playback frame for a training session."""

    state = EnvironmentState(
      session_id=payload.session_id,
      episode=payload.episode,
      step=payload.step,
      robot_x=payload.robot_x,
      robot_y=payload.robot_y,
      robot_orientation=payload.robot_orientation,
      threat_grid=payload.threat_grid,
      coverage_map=payload.coverage_map,
      suspicious_objects=payload.suspicious_objects,
      action_taken=payload.action_taken,
      reward_received=payload.reward_received,
    )
    self._db.add(state)
    await self._db.commit()
    await self._db.refresh(state)
    return state


__all__ = ["PlaybackService", "PlaybackSessionAggregate"]
