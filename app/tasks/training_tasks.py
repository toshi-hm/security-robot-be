"""Celery tasks orchestrating reinforcement learning training workflows."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

import torch

from app.core.config import settings
from app.core.training.a3c_service import A3CTrainingService
from app.core.training.ppo_service import PPOTrainingService
from app.db.session import SessionLocal
from app.models.training import (
  TrainingAlgorithm,
  TrainingJob,
  TrainingJobStatus,
  TrainingMetric,
)
from app.tasks.celery_app import celery_app
from app.utils.datetime import utcnow
from rl.callbacks.redis_pubsub_callback import RedisTrainingCallback
from rl.callbacks.websocket_callback import DatabaseMetricsCallback

try:  # pragma: no cover - optional dependency guard
  from gymnasium import error as gym_error
except ImportError:  # pragma: no cover - exercised when gymnasium is absent
  gym_error = None


if gym_error is not None:
  GymEnvironmentError = gym_error.Error
else:  # pragma: no cover - fallback used when gymnasium is absent
  class GymEnvironmentError(Exception):
    """Placeholder used when gymnasium is not installed."""

    pass

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
    db.rollback()
  except Exception:  # pragma: no cover - defensive logging
    logger.debug("Rollback before marking training session %s as failed was skipped", session_id)

  try:
    job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
    if job is None:
      return
    job.status = TrainingJobStatus.failed
    job.completed_at = utcnow()
    db.commit()
  except Exception as exc:  # pragma: no cover - defensive logging
    try:
      db.rollback()
    except Exception:
      logger.debug(
        "Secondary rollback while marking training session %s as failed was skipped",
        session_id,
      )
    logger.warning("Unable to mark training session %s as failed", session_id, exc_info=exc)


def _record_metric(
  db: Session,
  session_id: int,
  timestep: int,
  metrics: dict[str, Any],
) -> None:
  try:
    metric = TrainingMetric(
      job_id=session_id,
      timestep=timestep,
      episode=metrics.get("episode"),
      reward=float(metrics.get("reward", 0.0)),
      loss=metrics.get("loss"),
      additional_metrics=metrics.get("additional_metrics"),
    )
    db.add(metric)
    db.commit()
  except Exception as exc:
    try:
      db.rollback()
    except Exception:
      logger.debug("Secondary rollback while recording metric for session %s", session_id)
    logger.debug("Failed to persist training metric for session %s", session_id, exc_info=exc)


def _make_training_status_probe(session_id: int):
  def _probe() -> TrainingJobStatus | None:
    session = SessionLocal()
    try:
      result = (
        session.query(TrainingJob.status)
        .filter(TrainingJob.id == session_id)
        .first()
      )
      return result[0] if result else None
    finally:
      session.close()

  return _probe


def _handle_a3c_failure(
  task: Any,
  db: Session,
  redis_client: Redis | _NoOpRedis,
  session_id: int,
  message: str,
  exc: Exception,
) -> dict[str, Any]:
  logger.error("A3C training task failed for session %s: %s", session_id, message, exc_info=exc)
  _mark_job_failed(db, session_id)
  _publish_training_event(
    redis_client,
    session_id,
    {
      "type": "training_error",
      "status": TrainingJobStatus.failed.value,
      "error": message,
      "timestamp": utcnow().isoformat(),
    },
    critical=True,
  )
  try:
    task.update_state(
      state="FAILURE",
      meta={"session_id": session_id, "error": message},
    )
  except Exception as state_exc:  # pragma: no cover - defensive logging
    logger.debug(
      "Failed to update Celery failure state for session %s", session_id, exc_info=state_exc
    )
  return {"status": "failed", "session_id": session_id, "error": message}


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
        status_getter=_make_training_status_probe(session_id),
        status_check_interval=progress_interval,
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
    elif status == "paused":
      job.status = TrainingJobStatus.paused
      job.updated_at = utcnow()
      if "total_timesteps" in result:
        job.current_timestep = result["total_timesteps"]
      db.commit()

      _publish_training_event(
        redis_client,
        session_id,
        {
          "type": "training_paused",
          "status": TrainingJobStatus.paused.value,
          "timestamp": utcnow().isoformat(),
          "current_timestep": job.current_timestep,
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
    for session in (metrics_db, db):
      try:
        session.close()
      except Exception:
        logger.debug("Failed to close database session for training task", exc_info=True)


@celery_app.task(bind=True, name="training.run_a3c_training")
def run_a3c_training_task(self, session_id: int, config: dict[str, Any]) -> dict[str, Any]:
  """Execute a custom A3C training job inside a Celery worker."""

  logger.info("Starting A3C training task for session %s", session_id)
  self.update_state(state="STARTED", meta={"session_id": session_id, "status": "initializing"})

  redis_client = _create_redis_client()
  db = SessionLocal()
  metrics_db = SessionLocal()

  try:
    job = _get_training_job(db, session_id)
    _validate_algorithm(job, TrainingAlgorithm.a3c)

    job.status = TrainingJobStatus.running
    job.started_at = utcnow()
    db.commit()

    total_timesteps = config.get("total_timesteps") or job.total_timesteps
    progress_interval = _resolve_interval(
      config.get("progress_update_interval"),
      DEFAULT_PROGRESS_INTERVAL,
    )
    metrics_interval = _resolve_interval(
      config.get("metrics_update_interval"),
      progress_interval,
    )

    last_progress_emit = 0

    def _progress_callback(timestep: int, metrics: dict[str, Any]) -> None:
      nonlocal last_progress_emit
      if timestep <= last_progress_emit and not metrics.get("force_emit"):
        return
      if timestep - last_progress_emit < progress_interval and not metrics.get("force_emit"):
        return

      last_progress_emit = timestep

      payload = {
        "type": "training_progress",
        "session_id": session_id,
        "timestep": timestep,
        "episode": metrics.get("episode"),
        "reward": metrics.get("reward"),
        "loss": metrics.get("loss"),
        "additional_metrics": metrics.get("additional_metrics"),
      }
      _publish_training_event(redis_client, session_id, payload)

      progress_meta: dict[str, Any] = {"status": "running", "current": timestep}
      if total_timesteps:
        progress_meta["total"] = total_timesteps
        progress_meta["progress"] = min(1.0, timestep / float(total_timesteps))
      _update_celery_progress(self, session_id, progress_meta)

      if metrics_db and (timestep % metrics_interval == 0 or metrics.get("force_emit")):
        _record_metric(metrics_db, session_id, timestep, metrics)

    service = A3CTrainingService()
    result = asyncio.run(
      service.start_training(
        config={**config, "session_id": session_id},
        progress_callback=_progress_callback,
      )
    )

    status = result.get("status", "failed")
    if status == "completed":
      job.status = TrainingJobStatus.completed
      job.completed_at = utcnow()
      job.current_timestep = result.get("total_timesteps", total_timesteps)
      job.episodes_completed = result.get("episodes_completed", job.episodes_completed)
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

    logger.info("A3C training task finished for session %s with status %s", session_id, status)
    return result | {"session_id": session_id}

  except torch.cuda.OutOfMemoryError as exc:
    torch.cuda.empty_cache()

    def _format_oom_message() -> str:
      suffix = ""
      if torch.cuda.is_available():
        try:
          device = torch.cuda.current_device()
        except Exception:  # pragma: no cover - defensive logging
          device = None
        if device is not None:
          suffix = f" on device {device}"
      return f"CUDA out of memory encountered during A3C training{suffix}"

    return _handle_a3c_failure(
      self,
      db,
      redis_client,
      session_id,
      _format_oom_message(),
      exc,
    )

  except GymEnvironmentError as exc:  # type: ignore[misc]
    return _handle_a3c_failure(
      self,
      db,
      redis_client,
      session_id,
      f"Environment initialisation failed: {exc}",
      exc,
    )

  except Exception as exc:
    return _handle_a3c_failure(
      self,
      db,
      redis_client,
      session_id,
      str(exc),
      exc,
    )

  finally:
    for session in (metrics_db, db):
      try:
        session.close()
      except Exception:
        logger.debug("Failed to close database session for A3C training task", exc_info=True)


@celery_app.task(name="training.stop_training")
def stop_training_task(session_id: int) -> dict[str, Any]:
  """Mark a running training task as paused."""

  logger.info("Stop requested for training session %s", session_id)
  redis_client = _create_redis_client()
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

    _publish_training_event(
      redis_client,
      session_id,
      {
        "type": "training_stop_requested",
        "status": TrainingJobStatus.paused.value,
        "timestamp": utcnow().isoformat(),
      },
      critical=True,
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
