from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobQueueEntry(BaseModel):
    """Queue metadata captured for a submitted training job."""

    session_id: int = Field(..., description="Training session identifier associated with the job.")
    task_id: str = Field(..., description="Celery task identifier for the job.")
    status: str = Field(..., description="Current queue status for the job (queued, paused, stopped, revoked).")
    forced: bool = Field(
        default=False,
        description="Whether the most recent transition was triggered forcefully (e.g. Celery revoke).",
    )
    enqueued_at: datetime = Field(..., description="Timestamp when the job was enqueued.")
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the latest metadata update, if any."
    )
    paused_at: Optional[datetime] = Field(default=None, description="Time when the job was paused.")
    resumed_at: Optional[datetime] = Field(default=None, description="Time when the job was resumed.")
    stopped_at: Optional[datetime] = Field(default=None, description="Time when the job was stopped cooperatively.")
    revoked_at: Optional[datetime] = Field(default=None, description="Time when the job was forcefully revoked.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Original payload submitted when the job was created.",
    )

    model_config = ConfigDict(extra="ignore")


class JobQueueListResponse(BaseModel):
    """Response envelope for job queue listing requests."""

    jobs: list[JobQueueEntry] = Field(default_factory=list, description="Queued training jobs.")


class JobQueueDetailResponse(BaseModel):
    """Response envelope for retrieving a single job queue entry."""

    job: JobQueueEntry
