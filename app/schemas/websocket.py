from typing import Optional, Literal
from datetime import datetime

from pydantic import BaseModel, Field

from app.utils.datetime import utcnow

# WebSocket Message Types

class WebSocketMessage(BaseModel):
  """Base WebSocket message schema."""
  type: str = Field(..., description="Message type")
  timestamp: datetime = Field(default_factory=utcnow)


class TrainingProgressEvent(BaseModel):
  """Training progress event message."""
  type: Literal["training_progress"] = "training_progress"
  session_id: int
  timestep: int
  episode: Optional[int] = None
  reward: float
  loss: Optional[float] = None
  
  # Environment-specific metrics
  coverage_ratio: Optional[float] = None
  exploration_score: Optional[float] = None
  threat_level_avg: Optional[float] = None
  
  # Additional data
  additional_metrics: Optional[dict] = None
  timestamp: datetime = Field(default_factory=utcnow)


class TrainingStatusEvent(BaseModel):
  """Training status change event message."""
  type: Literal["training_status"] = "training_status"
  session_id: int
  status: str  # 'created', 'queued', 'running', 'paused', 'completed', 'failed'
  message: Optional[str] = None
  timestamp: datetime = Field(default_factory=utcnow)


class TrainingErrorEvent(BaseModel):
  """Training error event message."""
  type: Literal["training_error"] = "training_error"
  session_id: int
  error_message: str
  error_type: Optional[str] = None
  timestamp: datetime = Field(default_factory=utcnow)


class EnvironmentUpdateEvent(BaseModel):
  """Environment update event message."""
  type: Literal["environment_update"] = "environment_update"
  session_id: int
  episode: int
  step: int
  robot_position: dict  # {"x": int, "y": int, "orientation": int}
  action_taken: Optional[int] = None
  reward_received: Optional[float] = None
  timestamp: datetime = Field(default_factory=utcnow)


class ConnectionAckMessage(BaseModel):
  """Connection acknowledgment message."""
  type: Literal["connection_ack"] = "connection_ack"
  client_id: str
  message: str = "Connected successfully"
  timestamp: datetime = Field(default_factory=utcnow)


class PingMessage(BaseModel):
  """Ping message for keep-alive."""
  type: Literal["ping"] = "ping"
  timestamp: datetime = Field(default_factory=utcnow)


class PongMessage(BaseModel):
  """Pong response message."""
  type: Literal["pong"] = "pong"
  timestamp: datetime = Field(default_factory=utcnow)
