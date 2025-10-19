"""Database models for environment metadata and playback frames."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
  from app.models.training import TrainingJob


class EnvironmentDefinition(Base):
  """Persistent metadata describing available environments."""

  name: Mapped[str] = mapped_column(String(100))
  description: Mapped[str] = mapped_column(String(255), default='')
  config: Mapped[dict] = mapped_column(JSON, default=dict)


class EnvironmentState(Base):
  """Environment state snapshot for playback and historical analysis."""

  session_id: Mapped[int] = mapped_column(
    ForeignKey('trainingjob.id', ondelete='CASCADE'), index=True
  )
  job: Mapped['TrainingJob'] = relationship(back_populates='states')

  # Step information
  episode: Mapped[int] = mapped_column(index=True)
  step: Mapped[int] = mapped_column(index=True)

  # Robot state
  robot_x: Mapped[int] = mapped_column()
  robot_y: Mapped[int] = mapped_column()
  robot_orientation: Mapped[int] = mapped_column()  # 0-3: North, East, South, West

  # Environment state (JSON)
  threat_grid: Mapped[dict] = mapped_column(JSON)  # 2D array of threat levels
  coverage_map: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
  suspicious_objects: Mapped[Optional[dict]] = mapped_column(JSON, default=None)

  # Action information
  action_taken: Mapped[Optional[int]] = mapped_column(default=None)  # 0-3: Up, Right, Down, Left
  reward_received: Mapped[Optional[float]] = mapped_column(default=None)
