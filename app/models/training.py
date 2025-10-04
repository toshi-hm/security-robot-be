from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Enum as SqlEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TrainingJobStatus(str, Enum):
  queued = 'queued'
  running = 'running'
  completed = 'completed'
  failed = 'failed'


class TrainingJob(Base):
  algorithm: Mapped[str] = mapped_column(String(50))
  status: Mapped[TrainingJobStatus] = mapped_column(SqlEnum(TrainingJobStatus, name='training_job_status'), default=TrainingJobStatus.queued)
  total_steps: Mapped[int] = mapped_column(default=0)
  started_at: Mapped[Optional[datetime]] = mapped_column(default=None)
  finished_at: Mapped[Optional[datetime]] = mapped_column(default=None)

  metrics: Mapped[list['TrainingMetric']] = relationship(back_populates='job')


class TrainingMetric(Base):
  job_id: Mapped[int] = mapped_column(ForeignKey('trainingjob.id'))
  step: Mapped[int] = mapped_column()
  reward: Mapped[float] = mapped_column()
  loss: Mapped[float] = mapped_column()

  job: Mapped[TrainingJob] = relationship(back_populates='metrics')
