from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# Celery Job Status Schemas

class JobStatusResponse(BaseModel):
  """Response schema for Celery job status."""
  job_id: str = Field(..., description="Celery task ID")
  status: str = Field(..., description="Job status: PENDING, STARTED, SUCCESS, FAILURE, RETRY")
  result: Optional[dict] = Field(default=None, description="Job result if completed")
  error: Optional[str] = Field(default=None, description="Error message if failed")
  progress: Optional[dict] = Field(default=None, description="Progress information")
  created_at: Optional[datetime] = None
  started_at: Optional[datetime] = None
  completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
  """Response schema for list of jobs."""
  total: int
  jobs: list[JobStatusResponse]


class JobCancelRequest(BaseModel):
  """Request schema for canceling a job."""
  job_id: str = Field(..., description="Celery task ID to cancel")
  terminate: bool = Field(default=False, description="Whether to terminate forcefully")


class JobCancelResponse(BaseModel):
  """Response schema for job cancellation."""
  job_id: str
  status: str
  message: str


# Legacy schema for backward compatibility

class JobStatus(BaseModel):
  """Legacy job status schema."""
  job_id: str
  status: str
