"""Database models for environment metadata and playback frames."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
  from app.models.training import TrainingJob


class EnvironmentDefinition(Base):
  """Persistent metadata describing available environments."""

  name: Mapped[str] = mapped_column(String(100))
  description: Mapped[str] = mapped_column(String(255), default="")
  config: Mapped[dict] = mapped_column(JSON, default=dict)


class EnvironmentState(Base):
  """Environment state snapshot for playback and historical analysis."""

  session_id: Mapped[int] = mapped_column(
    ForeignKey("trainingjob.id", ondelete="CASCADE"), index=True
  )
  job: Mapped[TrainingJob] = relationship(back_populates="states")

  # Step information
  episode: Mapped[int] = mapped_column(index=True)
  step: Mapped[int] = mapped_column(index=True)

  # Robot state
  robot_x: Mapped[int] = mapped_column()
  robot_y: Mapped[int] = mapped_column()
  robot_orientation: Mapped[int] = mapped_column()  # 0-3: North, East, South, West
  robots: Mapped[list | None] = mapped_column(JSON, default=None)  # Multi-agent state
  charging_stations: Mapped[list | None] = mapped_column(JSON, default=None)

  # Environment state (JSON)
  threat_grid: Mapped[dict] = mapped_column(JSON)  # 2D array of threat levels
  coverage_map: Mapped[dict | None] = mapped_column(JSON, default=None)
  obstacles: Mapped[dict | None] = mapped_column(JSON, default=None)
  suspicious_objects: Mapped[list | None] = mapped_column(JSON, default=None)

  # Action information
  action_taken: Mapped[int | None] = mapped_column(default=None)  # 0-3: Up, Right, Down, Left
  reward_received: Mapped[float | None] = mapped_column(default=None)

  # Metrics
  coverage_ratio: Mapped[float | None] = mapped_column(default=None)
  exploration_score: Mapped[float | None] = mapped_column(default=None)

  # Battery system
  battery_percentage: Mapped[float | None] = mapped_column(default=None)
  is_charging: Mapped[bool] = mapped_column(default=False)
  distance_to_charging_station: Mapped[int | None] = mapped_column(default=None)
  charging_station_position_x: Mapped[int | None] = mapped_column(default=None)
  charging_station_position_y: Mapped[int | None] = mapped_column(default=None)
