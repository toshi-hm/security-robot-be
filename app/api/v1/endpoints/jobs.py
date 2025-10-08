from fastapi import APIRouter

from app.core.training.job_manager import job_manager

router = APIRouter()


@router.get('/')
async def list_jobs():
  """Return a snapshot of the queued training jobs."""

  return {'jobs': job_manager.snapshot()}
