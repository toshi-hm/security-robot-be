"""Pydantic models representing WebSocket payloads."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.utils.datetime import utcnow


class WebSocketMessage(BaseModel):
  """Base WebSocket message schema."""

  type: str = Field(..., description="Message type")
  timestamp: datetime = Field(default_factory=utcnow)


class TrainingProgressEvent(WebSocketMessage):
  """Training progress event message."""
  type: Literal["training_progress"] = "training_progress"
  session_id: int
  timestep: int
  episode: int | None = None
  reward: float
  loss: float | None = None

  # Environment-specific metrics
  coverage_ratio: float | None = None
  exploration_score: float | None = None
  threat_level_avg: float | None = None

  # Additional data
  additional_metrics: dict[str, Any] | None = None


class TrainingStatusEvent(WebSocketMessage):
  """Training status change event message."""
  type: Literal["training_status"] = "training_status"
  session_id: int
  status: str  # 'created', 'queued', 'running', 'paused', 'completed', 'failed'
  message: str | None = None


class TrainingErrorEvent(WebSocketMessage):
  """Training error event message."""
  type: Literal["training_error"] = "training_error"
  session_id: int
  error_message: str
  error_type: str | None = None


class EnvironmentUpdateEvent(WebSocketMessage):
  """Environment update event message."""
  type: Literal["environment_update"] = "environment_update"
  session_id: int
  episode: int
  step: int
  robot_position: dict[str, int]  # {"x": int, "y": int, "orientation": int}
  action_taken: int | None = None
  reward_received: float | None = None


class ConnectionAckMessage(WebSocketMessage):
  """Connection acknowledgment message."""
  type: Literal["connection_ack"] = "connection_ack"
  client_id: str
  message: str = "Connected successfully"


class PingMessage(WebSocketMessage):
  """Ping message for keep-alive."""
  type: Literal["ping"] = "ping"


class PongMessage(WebSocketMessage):
  """Pong response message."""
  type: Literal["pong"] = "pong"
