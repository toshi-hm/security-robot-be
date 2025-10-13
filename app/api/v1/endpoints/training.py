from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.training.job_manager import job_manager
from app.models.training import TrainingJob, TrainingJobStatus, TrainingMetric
from app.schemas.training import (
  TrainingActionResponse,
  TrainingMetricResponse,
  TrainingMetricsListResponse,
  TrainingSessionCreate,
  TrainingSessionListResponse,
  TrainingSessionResponse,
)
from app.services import TrainingService, training_dispatcher

router = APIRouter()


@router.post('/start', response_model=TrainingSessionResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_training(
  config: TrainingSessionCreate,
  db: AsyncSession = Depends(get_db),
) -> TrainingSessionResponse:
  """Create a new training job and queue it for execution."""

  service = TrainingService(db)

  try:
    job = await service.create_session(config)
  except ValueError as exc:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

  training_config = service.build_training_config(job, config)

  try:
    task_result = training_dispatcher.dispatch(job, training_config)
  except ValueError as exc:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
  except Exception as exc:  # pragma: no cover - defensive guard
    raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail='Failed to dispatch training task') from exc

  queue_payload: dict[str, Any] = {
    'session_id': job.id,
    'algorithm': job.algorithm,
    'environment_type': job.environment_type,
    'config': training_config,
  }

  task_id = getattr(task_result, 'id', None)
  if task_id is not None:
    queue_payload['task_id'] = task_id

  try:
    await job_manager.enqueue(queue_payload)
  except ValueError as exc:
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

  queued_job = await service.mark_queued(job.id)
  return TrainingSessionResponse.model_validate(queued_job, from_attributes=True)


@router.post('/{session_id}/stop', response_model=TrainingActionResponse)
async def stop_training(
  session_id: int,
  db: AsyncSession = Depends(get_db),
) -> TrainingActionResponse:
  """Stop an active training session and mark it as failed."""

  service = TrainingService(db)
  job = await service.get_session(session_id)
  if job is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'Training session {session_id} not found')

  await job_manager.stop(session_id)
  try:
    training_dispatcher.stop(session_id)
  except Exception as exc:  # pragma: no cover - defensive guard
    raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail='Failed to stop training task') from exc
  updated_job = await service.update_status(job, TrainingJobStatus.failed, mark_completed=True)
  return TrainingActionResponse(
    session_id=updated_job.id,
    status=updated_job.status,
    message=f'Training session {session_id} stopped successfully',
  )


@router.post('/{session_id}/pause', response_model=TrainingActionResponse)
async def pause_training(
  session_id: int,
  db: AsyncSession = Depends(get_db),
) -> TrainingActionResponse:
  """Temporarily pause an active training session."""

  service = TrainingService(db)
  job = await service.get_session(session_id)
  if job is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'Training session {session_id} not found')

  if job.status not in {TrainingJobStatus.running, TrainingJobStatus.queued}:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Training session is not running')

  await job_manager.stop(session_id)
  paused_job = await service.update_status(job, TrainingJobStatus.paused)
  return TrainingActionResponse(
    session_id=paused_job.id,
    status=paused_job.status,
    message=f'Training session {session_id} paused successfully',
  )


@router.post('/{session_id}/resume', response_model=TrainingSessionResponse)
async def resume_training(
  session_id: int,
  db: AsyncSession = Depends(get_db),
) -> TrainingSessionResponse:
  """Resume a paused training session by re-queuing it."""

  service = TrainingService(db)
  job = await service.get_session(session_id)
  if job is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'Training session {session_id} not found')

  if job.status != TrainingJobStatus.paused:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Only paused sessions can be resumed')

  training_config = service.build_training_config(job)

  try:
    task_result = training_dispatcher.dispatch(job, training_config)
  except ValueError as exc:
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
  except Exception as exc:  # pragma: no cover - defensive guard
    raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail='Failed to dispatch training task') from exc

  queue_payload: dict[str, Any] = {
    'session_id': job.id,
    'algorithm': job.algorithm,
    'environment_type': job.environment_type,
    'config': training_config,
  }

  task_id = getattr(task_result, 'id', None)
  if task_id is not None:
    queue_payload['task_id'] = task_id

  resume_entry = await job_manager.resume(session_id)
  if resume_entry is None:
    await job_manager.enqueue(queue_payload)
  else:
    resume_entry['payload'] = queue_payload
    if task_id is not None:
      resume_entry['task_id'] = task_id

  resumed_job = await service.update_status(job, TrainingJobStatus.queued, reset_completion=True)
  return TrainingSessionResponse.model_validate(resumed_job, from_attributes=True)


@router.get('/{session_id}/status', response_model=TrainingSessionResponse)
async def get_training_status(
  session_id: int,
  db: AsyncSession = Depends(get_db),
) -> TrainingSessionResponse:
  """Return the persisted status of a training session."""

  service = TrainingService(db)
  job = await service.get_session(session_id)
  if job is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'Training session {session_id} not found')

  return TrainingSessionResponse.model_validate(job, from_attributes=True)


@router.get('/list', response_model=TrainingSessionListResponse)
async def list_training_sessions(
  page: int = Query(1, ge=1, description='Page number (1-indexed)'),
  page_size: int = Query(20, ge=1, le=100, description='Number of sessions per page'),
  db: AsyncSession = Depends(get_db),
) -> TrainingSessionListResponse:
  """Return paginated training sessions."""

  service = TrainingService(db)
  sessions, total = await service.list_sessions(page, page_size)
  session_responses = [
    TrainingSessionResponse.model_validate(session, from_attributes=True)
    for session in sessions
  ]
  return TrainingSessionListResponse(
    total=total,
    page=page,
    page_size=page_size,
    sessions=session_responses,
  )


@router.delete('/{session_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_session(
  session_id: int,
  db: AsyncSession = Depends(get_db),
) -> Response:
  """Delete a training session and remove it from the job queue."""

  service = TrainingService(db)
  job = await service.get_session(session_id)
  if job is None:
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f'Training session {session_id} not found')

  await job_manager.discard(session_id)
  await service.delete_session(job)
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/sessions/{session_id}/metrics', response_model=TrainingMetricsListResponse)
async def get_metrics(
  session_id: int,
  page: int = Query(1, ge=1, description='Page number (1-indexed)'),
  page_size: int = Query(50, ge=1, le=500, description='Number of metrics per page'),
  db: AsyncSession = Depends(get_db),
) -> TrainingMetricsListResponse:
  """Return paginated training metrics for the specified session."""

  job = await db.get(TrainingJob, session_id)
  if job is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f'Training session {session_id} not found',
    )

  total_stmt = select(func.count()).select_from(TrainingMetric).where(TrainingMetric.job_id == session_id)
  total_result = await db.execute(total_stmt)
  total = total_result.scalar_one()

  offset = (page - 1) * page_size
  metrics_stmt = (
    select(TrainingMetric)
    .where(TrainingMetric.job_id == session_id)
    .order_by(TrainingMetric.timestamp.desc())
    .offset(offset)
    .limit(page_size)
  )
  metrics_result = await db.execute(metrics_stmt)
  metrics = [
    TrainingMetricResponse.model_validate(metric, from_attributes=True)
    for metric in metrics_result.scalars().all()
  ]

  return TrainingMetricsListResponse(
    total=total,
    page=page,
    page_size=page_size,
    metrics=metrics,
  )
