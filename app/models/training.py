from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.utils.datetime import utcnow

if TYPE_CHECKING:
    from app.models.environment import EnvironmentState


class TrainingAlgorithm(str, Enum):
    ppo = "ppo"
    a3c = "a3c"


class TrainingJobStatus(str, Enum):
    created = "created"
    queued = "queued"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class TrainingJob(Base):
    # Basic information
    name: Mapped[str] = mapped_column(String(255))
    algorithm: Mapped[TrainingAlgorithm] = mapped_column(
        SqlEnum(TrainingAlgorithm, name="training_algorithm"),
        nullable=False,
    )
    environment_type: Mapped[str] = mapped_column(
        String(20), default="standard"
    )  # 'standard' or 'enhanced'
    status: Mapped[TrainingJobStatus] = mapped_column(
        SqlEnum(TrainingJobStatus, name="training_job_status"), default=TrainingJobStatus.created
    )

    # Training parameters
    total_timesteps: Mapped[int] = mapped_column(default=0)
    current_timestep: Mapped[int] = mapped_column(default=0)
    episodes_completed: Mapped[int] = mapped_column(default=0)

    # Environment settings
    env_width: Mapped[int] = mapped_column(default=8)
    env_height: Mapped[int] = mapped_column(default=8)

    # Reward parameters (for enhanced environment)
    coverage_weight: Mapped[float] = mapped_column(default=1.5)
    exploration_weight: Mapped[float] = mapped_column(default=3.0)
    diversity_weight: Mapped[float] = mapped_column(default=2.0)

    # Additional parameters
    learning_rate: Mapped[float] = mapped_column(default=0.0003)
    batch_size: Mapped[int] = mapped_column(default=64)
    num_workers: Mapped[int] = mapped_column(default=1)  # For A3C

    # File paths
    model_path: Mapped[str | None] = mapped_column(String(512), default=None)
    log_path: Mapped[str | None] = mapped_column(String(512), default=None)

    # Configuration (JSON)
    config: Mapped[dict | None] = mapped_column(JSON, default=None)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )

    # Relationships
    metrics: Mapped[list[TrainingMetric]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    states: Mapped[list[EnvironmentState]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class TrainingMetric(Base):
    # Foreign key
    job_id: Mapped[int] = mapped_column(ForeignKey("trainingjob.id", ondelete="CASCADE"))

    # Metrics
    timestep: Mapped[int] = mapped_column()
    episode: Mapped[int | None] = mapped_column(default=None)
    reward: Mapped[float] = mapped_column()
    loss: Mapped[float | None] = mapped_column(default=None)

    # Environment-specific metrics
    coverage_ratio: Mapped[float | None] = mapped_column(default=None)
    exploration_score: Mapped[float | None] = mapped_column(default=None)
    threat_level_avg: Mapped[float | None] = mapped_column(default=None)

    # Additional metrics (JSON)
    additional_metrics: Mapped[dict | None] = mapped_column(JSON, default=None)

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationship
    job: Mapped[TrainingJob] = relationship(back_populates="metrics")
