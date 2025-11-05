"""Pydantic schemas for playback APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.training import TrainingAlgorithm, TrainingJobStatus
from app.schemas.environment import EnvironmentStateResponse


class PlaybackSessionSummary(BaseModel):
    """Summary information about a session that has playback frames."""

    model_config = ConfigDict(use_enum_values=True)

    session_id: int = Field(..., description="Training session identifier")
    name: str = Field(..., description="Display name of the training job")
    algorithm: TrainingAlgorithm = Field(..., description="Training algorithm used")
    environment_type: str = Field(..., description="Environment variant (standard/enhanced)")
    status: TrainingJobStatus = Field(..., description="Current job status")
    total_timesteps: int = Field(..., description="Configured total timesteps")
    current_timestep: int = Field(..., description="Latest recorded timestep")
    episodes_completed: int = Field(..., description="Number of completed episodes")
    frame_count: int = Field(..., description="Number of recorded playback frames")
    first_episode: int | None = Field(None, description="Lowest episode index with frames")
    last_episode: int | None = Field(None, description="Highest episode index with frames")
    first_recorded_at: datetime | None = Field(
        None, description="Timestamp of the first recorded frame"
    )
    last_recorded_at: datetime | None = Field(
        None, description="Timestamp of the most recent frame"
    )
    last_step: int | None = Field(None, description="Highest step value among recorded frames")
    created_at: datetime | None = Field(None, description="Job creation timestamp")
    started_at: datetime | None = Field(None, description="Training start timestamp")
    completed_at: datetime | None = Field(None, description="Training completion timestamp")


class PlaybackSessionListResponse(BaseModel):
    """Paginated list of playback-enabled sessions."""

    total: int
    page: int
    page_size: int
    sessions: list[PlaybackSessionSummary]


class PlaybackFramesListResponse(BaseModel):
    """Paginated playback frame data for a session."""

    total: int
    page: int
    page_size: int
    frames: list[EnvironmentStateResponse]


__all__ = [
    "PlaybackSessionSummary",
    "PlaybackSessionListResponse",
    "PlaybackFramesListResponse",
]
