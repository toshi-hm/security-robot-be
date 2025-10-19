from __future__ import annotations

"""API endpoints for playback data management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.environment import EnvironmentStateResponse
from app.schemas.playback import (
  PlaybackFramesListResponse,
  PlaybackSessionListResponse,
  PlaybackSessionSummary,
)
from app.services import PlaybackService

router = APIRouter()


@router.get('/sessions', response_model=PlaybackSessionListResponse)
async def list_playback_sessions(
  page: int = Query(1, ge=1, description='Page number (1-indexed)'),
  page_size: int = Query(20, ge=1, le=100, description='Number of sessions per page'),
  db: AsyncSession = Depends(get_db),
) -> PlaybackSessionListResponse:
  """Return sessions that have recorded playback frames."""

  service = PlaybackService(db)
  aggregates, total = await service.list_sessions(page, page_size)

  sessions = [
    PlaybackSessionSummary(
      session_id=aggregate.job.id,
      name=aggregate.job.name,
      algorithm=aggregate.job.algorithm,
      environment_type=aggregate.job.environment_type,
      status=aggregate.job.status,
      total_timesteps=aggregate.job.total_timesteps,
      current_timestep=aggregate.job.current_timestep,
      episodes_completed=aggregate.job.episodes_completed,
      frame_count=aggregate.frame_count,
      first_episode=aggregate.first_episode,
      last_episode=aggregate.last_episode,
      first_recorded_at=aggregate.first_recorded_at,
      last_recorded_at=aggregate.last_recorded_at,
      last_step=aggregate.last_step,
      created_at=aggregate.job.created_at,
      started_at=aggregate.job.started_at,
      completed_at=aggregate.job.completed_at,
    )
    for aggregate in aggregates
  ]

  return PlaybackSessionListResponse(
    total=total,
    page=page,
    page_size=page_size,
    sessions=sessions,
  )


@router.get('/{session_id}/frames', response_model=PlaybackFramesListResponse)
async def get_playback_frames(
  session_id: int,
  page: int = Query(1, ge=1, description='Page number (1-indexed)'),
  page_size: int = Query(200, ge=1, le=1000, description='Number of frames per page'),
  db: AsyncSession = Depends(get_db),
) -> PlaybackFramesListResponse:
  """Return recorded playback frames for a training session."""

  service = PlaybackService(db)
  job = await service.get_job(session_id)
  if job is None:
    raise HTTPException(
      status.HTTP_404_NOT_FOUND,
      detail=f'Training session {session_id} not found',
    )

  frames, total = await service.list_frames(session_id, page, page_size)
  payload = [
    EnvironmentStateResponse.model_validate(frame, from_attributes=True)
    for frame in frames
  ]

  return PlaybackFramesListResponse(
    total=total,
    page=page,
    page_size=page_size,
    frames=payload,
  )
