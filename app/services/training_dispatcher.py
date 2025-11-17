"""Dispatch training jobs to asynchronous workers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from celery.result import AsyncResult

from app.models.training import TrainingAlgorithm, TrainingJob
from app.tasks import training_tasks


class TrainingDispatcher:
  """Lightweight coordinator for kicking off Celery training tasks."""

  _algorithm_tasks: dict[TrainingAlgorithm, Callable[[int, dict[str, Any]], AsyncResult]] = {
    TrainingAlgorithm.ppo: training_tasks.run_ppo_training_task.delay,
    TrainingAlgorithm.a3c: training_tasks.run_a3c_training_task.delay,
  }

  def dispatch(self, job: TrainingJob, config: dict[str, Any]) -> AsyncResult:
    """Send the training request to the appropriate Celery task."""

    try:
      algorithm = TrainingAlgorithm(job.algorithm)
    except ValueError as exc:
      raise ValueError(f"Unsupported training algorithm: {job.algorithm}") from exc

    task = self._algorithm_tasks.get(algorithm)
    if task is None:
      raise ValueError(f"Unsupported training algorithm: {job.algorithm}")

    return task(job.id, config)

  def stop(self, session_id: int) -> AsyncResult:
    """Request termination of the running Celery task for the job."""

    return training_tasks.stop_training_task.delay(session_id)

  def revoke(
    self,
    task_id: str,
    *,
    terminate: bool = True,
    signal: str | None = "SIGTERM",
  ) -> AsyncResult:
    """Forcefully revoke a running Celery task by task identifier."""

    if not task_id:
      raise ValueError("task_id must be provided to revoke a Celery task")

    async_result = AsyncResult(task_id, app=training_tasks.celery_app)
    try:
      async_result.revoke(terminate=terminate, signal=signal)
    except Exception as exc:  # pragma: no cover - defensive guard
      raise RuntimeError(f"Failed to revoke Celery task {task_id}") from exc

    return async_result


training_dispatcher = TrainingDispatcher()
