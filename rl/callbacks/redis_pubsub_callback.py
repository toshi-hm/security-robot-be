"""Stable-Baselines3 callback that publishes training updates via Redis."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from redis.exceptions import RedisError
from stable_baselines3.common.callbacks import BaseCallback

if TYPE_CHECKING:  # pragma: no cover - imported for typing only
  from app.models.training import TrainingJobStatus


def _load_training_status_enum() -> type[TrainingJobStatus] | None:
  try:
    from app.models.training import TrainingJobStatus
  except Exception:  # pragma: no cover - avoid import errors during optional use
    return None
  return TrainingJobStatus


logger = logging.getLogger(__name__)


ProgressHook = Callable[[dict[str, Any]], None]


class TrainingCancelled(RuntimeError):
  """Raised when an external signal requests that training stop early."""

  pass


class RedisTrainingCallback(BaseCallback):
  """Emit training progress messages to Redis Pub/Sub consumers."""

  def __init__(
    self,
    session_id: int,
    redis_client: Any,
    *,
    update_interval: int = 100,
    total_timesteps: int | None = None,
    state_hook: ProgressHook | None = None,
    verbose: int = 0,
    max_retries: int = 3,
    critical_statuses: Sequence[str] | None = None,
    status_getter: Callable[[], TrainingJobStatus | None] | None = None,
    status_check_interval: int | None = None,
  ) -> None:
    super().__init__(verbose)
    self._session_id = session_id
    self._redis = redis_client
    self._update_interval = max(1, update_interval)
    self._total_timesteps = total_timesteps
    self._state_hook = state_hook
    self._max_retries = max(1, max_retries)
    self._critical_statuses = set(critical_statuses or ("completed", "failed", "paused"))
    self._status_getter = status_getter
    self._status_check_interval = max(1, status_check_interval or self._update_interval)
    self._status_check_counter = 0

    self._channel = f"training_progress_{session_id}"
    self._episode_rewards: list[float] = []
    self._episode_lengths: list[int] = []
    self._current_episode_reward = 0.0
    self._current_episode_length = 0

  # ------------------------------------------------------------------
  # Stable-Baselines3 callback interface
  # ------------------------------------------------------------------
  def _on_training_start(self) -> None:
    self._publish_status("running", "Training started")
    self._emit_state_update({"status": "running", "current": 0})

  def _on_step(self) -> bool:
    rewards = self.locals.get("rewards", [0.0])
    dones = self.locals.get("dones", [False])

    reward = float(rewards[0]) if rewards else 0.0
    self._current_episode_reward += reward
    self._current_episode_length += 1

    if dones and dones[0]:
      self._episode_rewards.append(self._current_episode_reward)
      self._episode_lengths.append(self._current_episode_length)
      self._current_episode_reward = 0.0
      self._current_episode_length = 0

    if self.n_calls % self._update_interval == 0:
      self._publish_progress()

    self._status_check_counter += 1
    if self._status_getter and self._status_check_counter >= self._status_check_interval:
      self._status_check_counter = 0
      self._enforce_status()

    return True

  def _on_training_end(self) -> None:
    self._publish_status("completed", "Training completed successfully")
    self._emit_state_update({"status": "completed", "current": self.num_timesteps})

  # ------------------------------------------------------------------
  # Redis helpers
  # ------------------------------------------------------------------
  def _publish_progress(self) -> None:
    mean_reward = float(np.mean(self._episode_rewards[-10:])) if self._episode_rewards else 0.0
    loss = None
    if hasattr(self.model, "logger") and getattr(self.model.logger, "name_to_value", None):
      loss_val = self.model.logger.name_to_value.get("train/loss")
      if loss_val is not None:
        loss = float(loss_val)

    payload: dict[str, Any] = {
      "type": "training_progress",
      "session_id": self._session_id,
      "timestep": self.num_timesteps,
      "episode": len(self._episode_rewards),
      "reward": mean_reward,
      "loss": loss,
      "additional_metrics": {
        "episode_length": (
          int(np.mean(self._episode_lengths[-10:])) if self._episode_lengths else 0
        ),
        "total_episodes": len(self._episode_rewards),
      },
    }

    self._publish(payload)

    progress_meta: dict[str, Any] = {
      "session_id": self._session_id,
      "current": self.num_timesteps,
    }
    if self._total_timesteps:
      progress_meta["total"] = self._total_timesteps
      progress_meta["progress"] = min(1.0, self.num_timesteps / float(self._total_timesteps))

    self._emit_state_update(progress_meta)

    if self.verbose > 0:
      logger.info(
        "Published Redis progress update for session %s at timestep %s",
        self._session_id,
        self.num_timesteps,
      )

  def _publish_status(self, status: str, message: str) -> None:
    payload = {
      "type": "training_status",
      "session_id": self._session_id,
      "status": status,
      "message": message,
    }
    self._publish(payload)

  def _publish(self, payload: dict[str, Any]) -> None:
    is_critical_status = (
      payload.get("type") == "training_status" and payload.get("status") in self._critical_statuses
    )
    attempts = self._max_retries if is_critical_status else 1

    for attempt in range(1, attempts + 1):
      try:
        message = json.dumps(payload)
        self._redis.publish(self._channel, message)
        break
      except RedisError as exc:
        log = logger.error if is_critical_status and attempt == attempts else logger.warning
        log(
          "Failed to publish training event for session %s (attempt %s/%s)",
          self._session_id,
          attempt,
          attempts,
          exc_info=exc,
        )
      except Exception as exc:  # pragma: no cover - defensive logging
        log = logger.error if is_critical_status and attempt == attempts else logger.warning
        log(
          "Unexpected error publishing training event for session %s (attempt %s/%s)",
          self._session_id,
          attempt,
          attempts,
          exc_info=exc,
        )

  def _emit_state_update(self, meta: dict[str, Any]) -> None:
    if not self._state_hook:
      return

    progress_meta = meta.copy()
    if self._total_timesteps and "total" not in progress_meta:
      progress_meta["total"] = self._total_timesteps
    try:
      self._state_hook(progress_meta)
    except Exception as exc:  # pragma: no cover - defensive logging
      logger.debug("Failed to notify Celery state hook", exc_info=exc)

  def _enforce_status(self) -> None:
    try:
      status = self._status_getter() if self._status_getter else None
    except Exception as exc:  # pragma: no cover - defensive logging
      logger.debug("Failed to obtain external training status", exc_info=exc)
      return

    if status is None:
      return

    status_enum = self._normalise_status(status)
    training_status_enum = _load_training_status_enum()
    if training_status_enum is None or status_enum is None:
      return

    if status_enum == training_status_enum.paused:
      self._publish_status("paused", "Training paused by user request")
      self._emit_state_update({"status": "paused", "current": self.num_timesteps})
      raise TrainingCancelled("Training paused")

  def _normalise_status(self, status: object) -> TrainingJobStatus | None:
    TrainingJobStatus = _load_training_status_enum()
    if TrainingJobStatus is None:
      return None

    if isinstance(status, TrainingJobStatus):
      return status

    if isinstance(status, str):
      try:
        return TrainingJobStatus(status)
      except ValueError:
        return None

    if hasattr(status, "value"):
      try:
        return TrainingJobStatus(status.value)
      except (ValueError, TypeError):
        return None

    return None


__all__ = ["RedisTrainingCallback", "TrainingCancelled"]
