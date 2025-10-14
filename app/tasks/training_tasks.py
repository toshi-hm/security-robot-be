"""Celery tasks orchestrating reinforcement learning training workflows."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.training.ppo_service import PPOTrainingService
from app.db.session import SessionLocal
from app.models.training import TrainingAlgorithm, TrainingJob, TrainingJobStatus
from app.tasks.celery_app import celery_app
from app.utils.datetime import utcnow
from rl.callbacks.redis_pubsub_callback import RedisTrainingCallback
from rl.callbacks.websocket_callback import DatabaseMetricsCallback

logger = logging.getLogger(__name__)

DEFAULT_PROGRESS_INTERVAL = 250


class _NoOpRedis:
  """Fallback Redis client used when no broker is available."""

  def publish(self, channel: str, message: str) -> None:  # pragma: no cover - debug helper
    logger.debug("Redis unavailable, dropping message for channel %s", channel)


def _create_redis_client() -> Redis | _NoOpRedis:
  try:
    return Redis.from_url(settings.redis_url, decode_responses=False)
  except Exception as exc:  # pragma: no cover - connection errors logged
    logger.warning("Unable to initialise Redis client: %s", exc)
    return _NoOpRedis()


def _publish_training_event(
  redis_client: Redis | _NoOpRedis,
  session_id: int,
  payload: dict[str, Any],
  *,
  critical: bool = False,
  max_retries: int = 3,
) -> None:
  payload.setdefault("session_id", session_id)
  channel = f"training_progress_{session_id}"
  attempts = max(1, max_retries if critical else 1)
  for attempt in range(1, attempts + 1):
    try:
      redis_client.publish(channel, json.dumps(payload))
      break
    except RedisError as exc:
      log = logger.error if critical and attempt == attempts else logger.warning
      log(
        "Failed to publish training event for session %s (attempt %s/%s)",
        session_id,
        attempt,
        attempts,
        exc_info=exc,
      )
    except Exception as exc:  # pragma: no cover - defensive logging
      log = logger.error if critical and attempt == attempts else logger.warning
      log(
        "Unexpected error publishing training event for session %s (attempt %s/%s)",
        session_id,
        attempt,
        attempts,
        exc_info=exc,
      )


def _resolve_interval(value: Any, default: int) -> int:
  try:
    resolved = int(value)
  except (TypeError, ValueError):
    return default
  return resolved if resolved > 0 else default


def _get_training_job(db: Session, session_id: int) -> TrainingJob:
  job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
  if job is None:
    raise ValueError(f"Training session {session_id} not found")
  return job


def _mark_job_failed(db: Session, session_id: int) -> None:
  try:
    job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
    if job is None:
      return
    job.status = TrainingJobStatus.failed
    job.completed_at = utcnow()
    db.commit()
  except Exception as exc:  # pragma: no cover - defensive logging
    db.rollback()
    logger.warning("Unable to mark training session %s as failed", session_id, exc_info=exc)


def _update_celery_progress(task, session_id: int, meta: dict[str, Any]) -> None:
  payload = {"session_id": session_id, **meta}
  try:
    task.update_state(state="PROGRESS", meta=payload)
  except Exception as exc:  # pragma: no cover - defensive logging
    logger.debug("Failed to update Celery state for session %s", session_id, exc_info=exc)


def _validate_algorithm(job: TrainingJob, expected: TrainingAlgorithm) -> None:
  try:
    algorithm = TrainingAlgorithm(job.algorithm)
  except ValueError as exc:
    raise ValueError(f"Unsupported training algorithm: {job.algorithm}") from exc
  if algorithm != expected:
    raise ValueError(
      f"Training session {job.id} is configured for {algorithm.value}, expected {expected.value}"
    )


@celery_app.task(bind=True, name="training.run_ppo_training")
def run_ppo_training_task(self, session_id: int, config: dict[str, Any]) -> dict[str, Any]:
  """Execute a PPO training job within a Celery worker."""

  logger.info("Starting PPO training task for session %s", session_id)
  self.update_state(state="STARTED", meta={"session_id": session_id, "status": "initializing"})

  redis_client = _create_redis_client()
  db = SessionLocal()
  metrics_db = SessionLocal()

  try:
    job = _get_training_job(db, session_id)
    _validate_algorithm(job, TrainingAlgorithm.ppo)

    job.status = TrainingJobStatus.running
    job.started_at = utcnow()
    db.commit()

    total_timesteps = config.get("total_timesteps") or job.total_timesteps
    progress_interval = _resolve_interval(
      config.get("progress_update_interval"), DEFAULT_PROGRESS_INTERVAL
    )
    metrics_interval = _resolve_interval(
      config.get("metrics_update_interval"), progress_interval
    )

    def _state_hook(meta: dict[str, Any]) -> None:
      progress_meta = {"status": meta.get("status", "running")}
      if "current" in meta:
        progress_meta["current"] = meta["current"]
      if "total" in meta:
        progress_meta["total"] = meta["total"]
      if "progress" in meta:
        progress_meta["progress"] = meta["progress"]
      _update_celery_progress(self, session_id, progress_meta)

    callbacks = [
      RedisTrainingCallback(
        session_id=session_id,
        redis_client=redis_client,
        update_interval=progress_interval,
        total_timesteps=total_timesteps,
        state_hook=_state_hook,
      ),
      DatabaseMetricsCallback(
        session_id=session_id,
        db_session=metrics_db,
        update_interval=metrics_interval,
      ),
    ]

    training_service = PPOTrainingService()
    result = asyncio.run(
      training_service.start_training(
        config=config,
        callbacks=callbacks,
      )
    )

    status = result.get("status", "failed")
    if status == "completed":
      job.status = TrainingJobStatus.completed
      job.completed_at = utcnow()
      job.current_timestep = result.get("total_timesteps", total_timesteps)
      model_path = result.get("model_path")
      if model_path:
        job.model_path = model_path
      db.commit()

      _publish_training_event(
        redis_client,
        session_id,
        {
          "type": "training_complete",
          "status": TrainingJobStatus.completed.value,
          "model_path": job.model_path,
          "timestamp": utcnow().isoformat(),
        },
        critical=True,
      )
    else:
      job.status = TrainingJobStatus.failed
      job.completed_at = utcnow()
      if "total_timesteps" in result:
        job.current_timestep = result["total_timesteps"]
      db.commit()

      _publish_training_event(
        redis_client,
        session_id,
        {
          "type": "training_error",
          "status": TrainingJobStatus.failed.value,
          "error": result.get("error", "Training failed"),
          "timestamp": utcnow().isoformat(),
        },
        critical=True,
      )

    logger.info("PPO training task finished for session %s with status %s", session_id, status)
    return result

  except Exception as exc:
    logger.error("PPO training task failed for session %s", session_id, exc_info=exc)
    db.rollback()
    _mark_job_failed(db, session_id)
    _publish_training_event(
      redis_client,
      session_id,
      {
        "type": "training_error",
        "status": TrainingJobStatus.failed.value,
        "error": str(exc),
        "timestamp": utcnow().isoformat(),
      },
      critical=True,
    )
    self.update_state(
      state="FAILURE",
      meta={"session_id": session_id, "error": str(exc)},
    )
    return {"status": "failed", "session_id": session_id, "error": str(exc)}

  finally:
    try:
      metrics_db.close()
    finally:
      db.close()


@celery_app.task(bind=True, name="training.run_a3c_training")
def run_a3c_training_task(self, session_id: int, config: dict[str, Any]) -> dict[str, Any]:
  """Placeholder A3C task that records a failure until implemented."""

  logger.info("A3C training requested for session %s, but the implementation is pending", session_id)
  self.update_state(state="STARTED", meta={"session_id": session_id, "status": "initializing"})

  redis_client = _create_redis_client()
  db = SessionLocal()
  try:
    job = _get_training_job(db, session_id)
    _validate_algorithm(job, TrainingAlgorithm.a3c)
    job.status = TrainingJobStatus.failed
    job.completed_at = utcnow()
    db.commit()
  except Exception as exc:
    db.rollback()
    _mark_job_failed(db, session_id)
    logger.debug("Failed to persist A3C placeholder status for session %s", session_id, exc_info=exc)
  finally:
    db.close()

  error_message = "A3C training not yet implemented"
  _publish_training_event(
    redis_client,
    session_id,
    {
      "type": "training_error",
      "status": TrainingJobStatus.failed.value,
      "error": error_message,
      "timestamp": utcnow().isoformat(),
    },
    critical=True,
  )
  self.update_state(
    state="FAILURE",
    meta={"session_id": session_id, "error": error_message},
  )
  return {"status": "failed", "session_id": session_id, "error": error_message}


@celery_app.task(name="training.stop_training")
def stop_training_task(session_id: int) -> dict[str, Any]:
  """Mark a running training task as paused."""

  logger.info("Stop requested for training session %s", session_id)
  db = SessionLocal()
  try:
    job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
    if job is None:
      return {
        "status": "error",
        "session_id": session_id,
        "error": "Training session not found",
      }

    job.status = TrainingJobStatus.paused
    job.updated_at = utcnow()
    db.commit()

    logger.warning(
      "Training stop requested for session %s; cooperative cancellation callback pending",
      session_id,
    )
    return {
      "status": "stopped",
      "session_id": session_id,
      "message": "Training stop requested",
    }
  except Exception as exc:
    db.rollback()
    logger.error("Failed to mark training session %s as paused", session_id, exc_info=exc)
    return {
      "status": "error",
      "session_id": session_id,
      "error": str(exc),
    }
  finally:
    db.close()


@celery_app.task
def run_training_job(config: dict[str, Any]) -> dict[str, Any]:
  """Legacy compatibility wrapper for historical task names."""

  logger.warning("run_training_job is deprecated; dispatch algorithm-specific tasks instead")
  return {"status": "queued", "config": config}
