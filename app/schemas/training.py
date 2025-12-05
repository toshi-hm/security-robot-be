from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.training import TrainingAlgorithm
from app.utils.datetime import utcnow

# Training Session Schemas


class TrainingSessionCreate(BaseModel):
  """Request schema for creating a training session."""

  name: str = Field(..., min_length=1, max_length=255, description="Training session name")
  algorithm: TrainingAlgorithm = Field(..., description="RL algorithm: 'ppo' or 'a3c'")
  environment_type: str = Field(
    default="standard", pattern="^(standard|enhanced)$", description="Environment type"
  )

  # Training parameters
  total_timesteps: int = Field(..., gt=0, description="Total training timesteps")

  # Environment settings
  env_width: int = Field(default=8, ge=3, le=50, description="Environment width")
  env_height: int = Field(default=8, ge=3, le=50, description="Environment height")
  num_robots: int = Field(default=1, ge=1, le=10, description="Number of robots (1-10)")

  # Reward parameters (for enhanced environment)
  coverage_weight: float = Field(default=1.5, ge=0, description="Coverage reward weight")
  exploration_weight: float = Field(default=3.0, ge=0, description="Exploration reward weight")
  diversity_weight: float = Field(default=2.0, ge=0, description="Diversity reward weight")

  # Additional parameters
  learning_rate: float = Field(default=0.0003, gt=0, description="Learning rate")
  batch_size: int = Field(default=64, gt=0, description="Batch size")
  num_workers: int = Field(default=1, ge=1, description="Number of workers (for A3C)")

  # Parallel Training & Advanced Policy
  num_envs: int = Field(default=1, ge=1, le=32, description="Number of parallel environments")
  policy_type: str = Field(
    default="MlpPolicy", pattern="^(MlpPolicy|CnnPolicy)$", description="Policy network type"
  )

  # Optional configuration
  config: dict | None = Field(default=None, description="Additional configuration")


class TrainingSessionResponse(BaseModel):
  """Response schema for training session."""

  model_config = ConfigDict(from_attributes=True)

  id: int
  name: str
  algorithm: TrainingAlgorithm
  environment_type: str
  status: str

  # Training parameters
  total_timesteps: int
  current_timestep: int
  episodes_completed: int

  # Environment settings
  env_width: int
  env_height: int
  num_robots: int | None = None

  # Reward parameters
  coverage_weight: float
  exploration_weight: float
  diversity_weight: float

  # Additional parameters
  learning_rate: float
  batch_size: int
  num_workers: int
  num_envs: int = 1
  policy_type: str = "MlpPolicy"

  # File paths
  model_path: str | None = None
  log_path: str | None = None

  # Configuration
  config: dict | None = None

  # Timestamps
  created_at: datetime
  updated_at: datetime
  started_at: datetime | None = None
  completed_at: datetime | None = None

  # Computed fields
  @property
  def progress_percentage(self) -> float:
    """Calculate training progress percentage."""
    if self.total_timesteps == 0:
      return 0.0
    return (self.current_timestep / self.total_timesteps) * 100.0

  @property
  def is_running(self) -> bool:
    """Check if training is currently running."""
    return self.status == "running"

  @property
  def duration_seconds(self) -> float | None:
    """Calculate training duration in seconds."""
    if not self.started_at:
      return None
    end_time = self.completed_at or utcnow()
    return (end_time - self.started_at).total_seconds()


class TrainingSessionUpdate(BaseModel):
  """Request schema for updating a training session."""

  current_timestep: int | None = Field(default=None, ge=0)
  episodes_completed: int | None = Field(default=None, ge=0)
  status: str | None = Field(
    default=None, pattern="^(created|queued|running|paused|completed|failed)$"
  )
  model_path: str | None = None
  log_path: str | None = None


# Training Metrics Schemas


class TrainingMetricCreate(BaseModel):
  """Request schema for creating a training metric."""

  job_id: int
  timestep: int = Field(..., ge=0)
  episode: int | None = Field(default=None, ge=0)
  reward: float
  loss: float | None = None

  # Environment-specific metrics
  coverage_ratio: float | None = Field(default=None, ge=0, le=1)
  exploration_score: float | None = Field(default=None, ge=0, le=1)
  threat_level_avg: float | None = Field(default=None, ge=0, le=1)

  # Additional metrics
  additional_metrics: dict | None = None


class TrainingMetricResponse(BaseModel):
  """Response schema for training metric."""

  model_config = ConfigDict(from_attributes=True)

  id: int
  job_id: int
  timestep: int
  episode: int | None
  reward: float
  loss: float | None

  # Environment-specific metrics
  coverage_ratio: float | None
  exploration_score: float | None
  threat_level_avg: float | None

  # Additional metrics
  additional_metrics: dict | None

  # Timestamp
  timestamp: datetime
  created_at: datetime
  updated_at: datetime


class TrainingMetricsListResponse(BaseModel):
  """Response schema for paginated training metrics."""

  total: int
  page: int
  page_size: int
  metrics: list[TrainingMetricResponse]


class TrainingSessionListResponse(BaseModel):
  """Paginated response for training sessions."""

  total: int
  page: int
  page_size: int
  sessions: list[TrainingSessionResponse]


class TrainingActionResponse(BaseModel):
  """Standard response payload for training control actions."""

  session_id: int
  status: str
  message: str
  celery_task_id: str | None = None
  queue_task_id: str | None = None
  revoked_task_id: str | None = None
  forced: bool = False
  stopped_at: datetime | None = None
  paused_at: datetime | None = None
  revoked_at: datetime | None = None
  resumed_at: datetime | None = None


# Legacy schemas for backward compatibility


class TrainingRequest(BaseModel):
  """Legacy training request schema."""

  name: str
  algorithm: TrainingAlgorithm
  environment_type: str
  total_timesteps: int


class TrainingMetricsResponse(BaseModel):
  """Legacy metrics response schema."""

  session_id: str
  points: list[dict[str, float]]
