from typing import Optional

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EnvironmentDefinition(Base):
  name: Mapped[str] = mapped_column(String(100))
  description: Mapped[str] = mapped_column(String(255), default='')
  config: Mapped[dict] = mapped_column(JSON, default=dict)


class EnvironmentState(Base):
  """Environment state snapshot for playback."""
  
  # Foreign key
  session_id: Mapped[int] = mapped_column(ForeignKey('trainingjob.id', ondelete='CASCADE'))
  
  # Step information
  episode: Mapped[int] = mapped_column()
  step: Mapped[int] = mapped_column()
  
  # Robot state
  robot_x: Mapped[int] = mapped_column()
  robot_y: Mapped[int] = mapped_column()
  robot_orientation: Mapped[int] = mapped_column()  # 0-3: North, East, South, West
  
  # Environment state (JSON)
  threat_grid: Mapped[dict] = mapped_column(JSON)  # 2D array of threat levels
  coverage_map: Mapped[Optional[dict]] = mapped_column(JSON, default=None)  # 2D array of visit counts
  suspicious_objects: Mapped[Optional[dict]] = mapped_column(JSON, default=None)  # List of objects
  
  # Action information
  action_taken: Mapped[Optional[int]] = mapped_column(default=None)  # 0-3: Up, Right, Down, Left
  reward_received: Mapped[Optional[float]] = mapped_column(default=None)
