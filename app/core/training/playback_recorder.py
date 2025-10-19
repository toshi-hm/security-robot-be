"""Helpers for recording environment playback frames during training."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.environment import EnvironmentState


logger = logging.getLogger(__name__)


DEFAULT_RECORD_INTERVAL = 1
DEFAULT_BUFFER_SIZE = 64


def _copy_grid(grid: Any) -> list[list[Any]]:
  """Return a JSON-serialisable deep copy of a 2D grid-like object."""

  rows: list[list[Any]] = []
  for row in list(grid or []):
    row_list: list[Any] = []
    for value in list(row or []):
      if isinstance(value, (int, float)):
        row_list.append(value)
      else:
        try:
          row_list.append(float(value))
        except (TypeError, ValueError):
          row_list.append(value)
    rows.append(row_list)
  return rows


def _copy_mapping(mapping: Any) -> list[dict[str, Any]] | None:
  """Convert a mapping of tuple keys to dictionaries for persistence."""

  if mapping is None:
    return None
  try:
    items = list(mapping.items())
  except AttributeError:
    return None

  serialised: list[dict[str, Any]] = []
  for key, value in items:
    if isinstance(key, (tuple, list)) and len(key) >= 2:
      x, y = key[:2]
    else:
      x, y = key, None
    payload: dict[str, Any] = {"x": int(x) if isinstance(x, (int, float)) else x}
    if isinstance(y, (int, float)):
      payload["y"] = int(y)
    elif y is not None:
      payload["y"] = y

    if isinstance(value, dict):
      for attr, attr_value in value.items():
        payload[attr] = attr_value
    elif isinstance(value, (int, float)):
      payload["spawn_time"] = int(value)
    else:
      payload["value"] = value

    serialised.append(payload)

  return serialised


@dataclass(slots=True)
class _PlaybackRecorder:
  """Accumulates playback frames before persisting them to the database."""

  session_factory: Callable[[], Session]
  buffer_size: int = DEFAULT_BUFFER_SIZE
  _buffer: list[dict[str, Any]] = field(default_factory=list, init=False)

  def record(self, payload: dict[str, Any]) -> None:
    self._buffer.append(payload)
    if len(self._buffer) >= max(1, self.buffer_size):
      self.flush()

  def flush(self) -> None:
    if not self._buffer:
      return
    session = self.session_factory()
    try:
      session.bulk_insert_mappings(EnvironmentState, list(self._buffer))
      session.commit()
      self._buffer.clear()
    except Exception as exc:  # pragma: no cover - defensive logging
      logger.warning("Failed to persist playback frames", exc_info=exc)
      try:
        session.rollback()
      except Exception:  # pragma: no cover - defensive logging
        logger.debug("Rollback failed when flushing playback frames", exc_info=True)
      self._buffer.clear()
    finally:
      try:
        session.close()
      except Exception:  # pragma: no cover - defensive logging
        logger.debug("Failed to close playback recorder session", exc_info=True)


class PlaybackRecordingWrapper:
  """Proxy environment that records state snapshots for playback."""

  def __init__(
    self,
    env: Any,
    *,
    session_id: int,
    session_factory: Callable[[], Session],
    record_interval: int = DEFAULT_RECORD_INTERVAL,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
    record_on_reset: bool = True,
  ) -> None:
    self._env = env
    self._session_id = session_id
    self._record_interval = max(1, record_interval)
    self._record_on_reset = record_on_reset
    self._recorder = _PlaybackRecorder(session_factory, buffer_size)
    self._episode = -1
    self._step_in_episode = 0
    self._steps_since_record = 0

    self.action_space = getattr(env, "action_space", None)
    self.observation_space = getattr(env, "observation_space", None)
    self.metadata = getattr(env, "metadata", {})

  # ------------------------------------------------------------------
  # Gymnasium API
  # ------------------------------------------------------------------
  def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
    result = self._env.reset(seed=seed, options=options)

    self._episode += 1
    self._step_in_episode = 0
    self._steps_since_record = 0

    if self._record_on_reset:
      observation = result[0] if isinstance(result, tuple) else result
      self._record_snapshot(
        observation=observation,
        action=None,
        reward=None,
        step=0,
      )

    return result

  def step(self, action: Any):
    observation, reward, terminated, truncated, info = self._env.step(action)

    self._step_in_episode += 1
    self._steps_since_record += 1
    step_value = getattr(self._env, "time_step", self._step_in_episode)

    should_record = (
      self._steps_since_record >= self._record_interval
      or bool(terminated)
      or bool(truncated)
    )

    if should_record:
      self._record_snapshot(
        observation=observation,
        action=action,
        reward=reward,
        step=step_value,
      )
      self._steps_since_record = 0

    return observation, reward, terminated, truncated, info

  def close(self) -> None:
    try:
      self._recorder.flush()
    finally:
      close = getattr(self._env, "close", None)
      if callable(close):
        close()

  # ------------------------------------------------------------------
  # Internal helpers
  # ------------------------------------------------------------------
  def _record_snapshot(
    self,
    *,
    observation: Any,
    action: Any,
    reward: Any,
    step: int,
  ) -> None:
    payload: dict[str, Any] = {
      "session_id": self._session_id,
      "episode": self._episode,
      "step": int(step),
      "robot_x": int(getattr(self._env, "robot_x", 0)),
      "robot_y": int(getattr(self._env, "robot_y", 0)),
      "robot_orientation": int(getattr(self._env, "robot_direction", 0)),
      "threat_grid": {"levels": _copy_grid(getattr(self._env, "threat_levels", []))},
      "coverage_map": None,
      "suspicious_objects": _copy_mapping(getattr(self._env, "suspicious_objects", None)),
      "action_taken": self._normalise_action(action),
      "reward_received": float(reward) if reward is not None else None,
    }

    coverage_source = None
    if hasattr(self._env, "visit_count"):
      coverage_source = getattr(self._env, "visit_count")
    elif hasattr(self._env, "last_patrolled"):
      coverage_source = getattr(self._env, "last_patrolled")
    if coverage_source is not None:
      payload["coverage_map"] = {"counts": _copy_grid(coverage_source)}

    if payload["reward_received"] is None and isinstance(reward, (int, float)):
      payload["reward_received"] = float(reward)

    self._recorder.record(payload)

  def _normalise_action(self, action: Any) -> int | None:
    if action is None:
      return None
    if isinstance(action, (int, float)):
      return int(action)
    if isinstance(action, (list, tuple)) and action:
      return self._normalise_action(action[0])
    if hasattr(action, "item"):
      try:
        return int(action.item())
      except Exception:  # pragma: no cover - defensive logging
        logger.debug("Failed to normalise action value %r", action, exc_info=True)
        return None
    return None

  def __getattr__(self, name: str) -> Any:
    return getattr(self._env, name)


def wrap_environment_for_playback(
  env: Any,
  *,
  session_id: int,
  session_factory: Callable[[], Session],
  options: dict[str, Any] | None = None,
) -> PlaybackRecordingWrapper:
  """Return a playback-enabled environment wrapper for the provided env."""

  options = dict(options or {})
  record_interval = int(options.get("record_interval", DEFAULT_RECORD_INTERVAL))
  buffer_size = int(options.get("buffer_size", DEFAULT_BUFFER_SIZE))
  record_on_reset = bool(options.get("record_on_reset", True))

  return PlaybackRecordingWrapper(
    env,
    session_id=session_id,
    session_factory=session_factory,
    record_interval=max(1, record_interval),
    buffer_size=max(1, buffer_size),
    record_on_reset=record_on_reset,
  )


__all__ = [
  "PlaybackRecordingWrapper",
  "wrap_environment_for_playback",
  "DEFAULT_RECORD_INTERVAL",
  "DEFAULT_BUFFER_SIZE",
]
