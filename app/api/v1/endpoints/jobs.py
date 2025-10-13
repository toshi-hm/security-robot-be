from fastapi import APIRouter, HTTPException, status

from app.core.training.job_manager import job_manager

router = APIRouter()


@router.get("/")
async def list_jobs() -> dict[str, list[dict[str, object]]]:
    """Return a snapshot of the queued training jobs."""

    return {"jobs": job_manager.snapshot()}


@router.get("/{session_id}")
async def get_job(session_id: int) -> dict[str, dict[str, object]]:
    """Return queue metadata for a specific training session."""

    entry = job_manager.get(session_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training session {session_id} not found in queue",
        )

    return {"job": entry}
