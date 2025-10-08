from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.utils.datetime import utcnow

# Training Session Schemas

class TrainingSessionCreate(BaseModel):
  """Request schema for creating a training session."""
  name: str = Field(..., min_length=1, max_length=255, description="Training session name")
  algorithm: str = Field(..., pattern="^(ppo|a3c)$", description="RL algorithm: 'ppo' or 'a3c'")
  environment_type: str = Field(default="standard", pattern="^(standard|enhanced)$", description="Environment type")
  
  # Training parameters
  total_timesteps: int = Field(..., gt=0, description="Total training timesteps")
  
  # Environment settings
  env_width: int = Field(default=8, ge=3, le=50, description="Environment width")
  env_height: int = Field(default=8, ge=3, le=50, description="Environment height")
  
  # Reward parameters (for enhanced environment)
  coverage_weight: float = Field(default=1.5, ge=0, description="Coverage reward weight")
  exploration_weight: float = Field(default=3.0, ge=0, description="Exploration reward weight")
  diversity_weight: float = Field(default=2.0, ge=0, description="Diversity reward weight")
  
  # Additional parameters
  learning_rate: float = Field(default=0.0003, gt=0, description="Learning rate")
  batch_size: int = Field(default=64, gt=0, description="Batch size")
  num_workers: int = Field(default=1, ge=1, description="Number of workers (for A3C)")
  
  # Optional configuration
  config: Optional[dict] = Field(default=None, description="Additional configuration")


class TrainingSessionResponse(BaseModel):
  """Response schema for training session."""
  model_config = ConfigDict(from_attributes=True)
  
  id: int
  name: str
  algorithm: str
  environment_type: str
  status: str
  
  # Training parameters
  total_timesteps: int
  current_timestep: int
  episodes_completed: int
  
  # Environment settings
  env_width: int
  env_height: int
  
  # Reward parameters
  coverage_weight: float
  exploration_weight: float
  diversity_weight: float
  
  # Additional parameters
  learning_rate: float
  batch_size: int
  num_workers: int
  
  # File paths
  model_path: Optional[str] = None
  log_path: Optional[str] = None
  
  # Configuration
  config: Optional[dict] = None
  
  # Timestamps
  created_at: datetime
  updated_at: datetime
  started_at: Optional[datetime] = None
  completed_at: Optional[datetime] = None
  
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
    return self.status == 'running'
  
  @property
  def duration_seconds(self) -> Optional[float]:
    """Calculate training duration in seconds."""
    if not self.started_at:
      return None
    end_time = self.completed_at or utcnow()
    return (end_time - self.started_at).total_seconds()


class TrainingSessionUpdate(BaseModel):
  """Request schema for updating a training session."""
  current_timestep: Optional[int] = Field(default=None, ge=0)
  episodes_completed: Optional[int] = Field(default=None, ge=0)
  status: Optional[str] = Field(default=None, pattern="^(created|queued|running|paused|completed|failed)$")
  model_path: Optional[str] = None
  log_path: Optional[str] = None


# Training Metrics Schemas

class TrainingMetricCreate(BaseModel):
  """Request schema for creating a training metric."""
  job_id: int
  timestep: int = Field(..., ge=0)
  episode: Optional[int] = Field(default=None, ge=0)
  reward: float
  loss: Optional[float] = None
  
  # Environment-specific metrics
  coverage_ratio: Optional[float] = Field(default=None, ge=0, le=1)
  exploration_score: Optional[float] = Field(default=None, ge=0, le=1)
  threat_level_avg: Optional[float] = Field(default=None, ge=0, le=1)
  
  # Additional metrics
  additional_metrics: Optional[dict] = None


class TrainingMetricResponse(BaseModel):
  """Response schema for training metric."""
  model_config = ConfigDict(from_attributes=True)
  
  id: int
  job_id: int
  timestep: int
  episode: Optional[int]
  reward: float
  loss: Optional[float]
  
  # Environment-specific metrics
  coverage_ratio: Optional[float]
  exploration_score: Optional[float]
  threat_level_avg: Optional[float]
  
  # Additional metrics
  additional_metrics: Optional[dict]
  
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


# Legacy schemas for backward compatibility

class TrainingRequest(BaseModel):
  """Legacy training request schema."""
  name: str
  algorithm: str
  environment_type: str
  total_timesteps: int


class TrainingMetricsResponse(BaseModel):
  """Legacy metrics response schema."""
  session_id: str
  points: list[dict[str, float]]
