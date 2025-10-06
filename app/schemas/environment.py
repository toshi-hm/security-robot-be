from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.core.environment.schemas import EnvironmentState as CoreEnvironmentState


# Environment State Snapshot Schemas

class EnvironmentStateCreate(BaseModel):
  """Request schema for creating an environment state snapshot."""
  session_id: int
  episode: int = Field(..., ge=0)
  step: int = Field(..., ge=0)
  
  # Robot state
  robot_x: int = Field(..., ge=0)
  robot_y: int = Field(..., ge=0)
  robot_orientation: int = Field(..., ge=0, le=3, description="0=North, 1=East, 2=South, 3=West")
  
  # Environment state
  threat_grid: dict = Field(..., description="2D array of threat levels")
  coverage_map: Optional[dict] = Field(default=None, description="2D array of visit counts")
  suspicious_objects: Optional[dict] = Field(default=None, description="List of suspicious objects")
  
  # Action information
  action_taken: Optional[int] = Field(default=None, ge=0, le=3, description="0=Up, 1=Right, 2=Down, 3=Left")
  reward_received: Optional[float] = None


class EnvironmentStateResponse(BaseModel):
  """Response schema for environment state snapshot."""
  model_config = ConfigDict(from_attributes=True)
  
  id: int
  session_id: int
  episode: int
  step: int
  
  # Robot state
  robot_x: int
  robot_y: int
  robot_orientation: int
  
  # Environment state
  threat_grid: dict
  coverage_map: Optional[dict]
  suspicious_objects: Optional[dict]
  
  # Action information
  action_taken: Optional[int]
  reward_received: Optional[float]
  
  # Timestamps
  created_at: datetime
  updated_at: datetime


class EnvironmentStatesListResponse(BaseModel):
  """Response schema for paginated environment states."""
  total: int
  page: int
  page_size: int
  states: list[EnvironmentStateResponse]


# Environment Configuration Schemas

class EnvironmentDefinitionCreate(BaseModel):
  """Request schema for creating an environment definition."""
  name: str = Field(..., min_length=1, max_length=100)
  description: str = Field(default="", max_length=255)
  config: dict = Field(default_factory=dict)


class EnvironmentDefinitionResponse(BaseModel):
  """Response schema for environment definition."""
  model_config = ConfigDict(from_attributes=True)
  
  id: int
  name: str
  description: str
  config: dict
  created_at: datetime
  updated_at: datetime


# Legacy schema for backward compatibility

class LegacyEnvironmentStateResponse(BaseModel):
  """Legacy environment state response schema."""
  data: CoreEnvironmentState
