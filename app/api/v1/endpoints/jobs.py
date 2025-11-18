from app.core.training.job_manager import job_manager
from app.schemas.jobs import JobQueueDetailResponse, JobQueueEntry, JobQueueListResponse
from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/", response_model=JobQueueListResponse)
async def list_jobs() -> JobQueueListResponse:
  """Return a snapshot of the queued training jobs."""

  entries = [JobQueueEntry.model_validate(entry) for entry in job_manager.snapshot()]
  return JobQueueListResponse(jobs=entries)


@router.get("/{session_id}", response_model=JobQueueDetailResponse)
async def get_job(session_id: int) -> JobQueueDetailResponse:
  """Return queue metadata for a specific training session."""

  entry = job_manager.get(session_id)
  if entry is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"Training session {session_id} not found in queue",
    )

  return JobQueueDetailResponse(job=JobQueueEntry.model_validate(entry))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(session_id: int) -> None:
  """Remove a job entry from the in-memory queue manager."""

  entry = job_manager.get(session_id)
  if entry is None:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"Training session {session_id} not found in queue",
    )

  await job_manager.discard(session_id)
