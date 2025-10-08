from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.training import TrainingJob, TrainingMetric
from app.schemas.training import TrainingMetricResponse, TrainingMetricsListResponse

router = APIRouter()


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
