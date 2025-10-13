"""Dispatch training jobs to asynchronous workers."""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult

from app.models.training import TrainingJob
from app.tasks import training_tasks


class TrainingDispatcher:
  """Lightweight coordinator for kicking off Celery training tasks."""

  def dispatch(self, job: TrainingJob, config: dict[str, Any]) -> AsyncResult:
    """Send the training request to the appropriate Celery task."""

    if job.algorithm == 'ppo':
      return training_tasks.run_ppo_training_task.delay(job.id, config)
    if job.algorithm == 'a3c':
      return training_tasks.run_a3c_training_task.delay(job.id, config)
    raise ValueError(f'Unsupported training algorithm: {job.algorithm}')

  def stop(self, session_id: int) -> AsyncResult:
    """Request termination of the running Celery task for the job."""

    return training_tasks.stop_training_task.delay(session_id)


training_dispatcher = TrainingDispatcher()

