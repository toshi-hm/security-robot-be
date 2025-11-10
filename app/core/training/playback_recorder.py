"""Helpers for recording environment playback frames during training."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

import gymnasium as gym
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.environment import EnvironmentState

logger = logging.getLogger(__name__)


DEFAULT_RECORD_INTERVAL = 1
DEFAULT_BUFFER_SIZE = 64
MAX_BUFFER_SIZE = 1024
UNKNOWN_POSITION = -1

ATTR_MAPPING = {
    "robot_x": ("robot_x", UNKNOWN_POSITION),
    "robot_y": ("robot_y", UNKNOWN_POSITION),
    "robot_orientation": ("robot_direction", 0),
}


def _copy_grid(grid: Any) -> list[list[Any]]:
    """Return a JSON-serialisable deep copy of a 2D grid-like object."""

    if hasattr(grid, "tolist"):
        try:
            return list(grid.tolist())
        except Exception:  # pragma: no cover - defensive logging
            logger.debug("Failed to convert grid with tolist(); falling back", exc_info=True)

    rows: list[list[Any]] = []
    for row in list(grid or []):
        row_list: list[Any] = []
        for value in list(row or []):
            if isinstance(value, int | float):
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
        if isinstance(key, tuple | list) and len(key) >= 2:
            x, y = key[:2]
        else:
            x, y = key, None
        payload: dict[str, Any] = {"x": int(x) if isinstance(x, int | float) else x}
        if isinstance(y, int | float):
            payload["y"] = int(y)
        elif y is not None:
            payload["y"] = y

        if isinstance(value, dict):
            for attr, attr_value in value.items():
                payload[attr] = attr_value
        elif isinstance(value, int | float):
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
    statement_timeout_ms: int | None = None
    _buffer: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.buffer_size = max(1, min(int(self.buffer_size), MAX_BUFFER_SIZE))
        if self.statement_timeout_ms is not None and self.statement_timeout_ms <= 0:
            self.statement_timeout_ms = None

    def record(self, payload: dict[str, Any]) -> None:
        self._buffer.append(payload)
        if len(self._buffer) >= max(1, self.buffer_size):
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        session = self.session_factory()
        try:
            if (
                self.statement_timeout_ms is not None
                and (bind := session.get_bind()) is not None
                and bind.dialect.name == "postgresql"
            ):
                session.execute(
                    text("SET LOCAL statement_timeout = :timeout"),
                    {"timeout": self.statement_timeout_ms},
                )
            session.bulk_insert_mappings(EnvironmentState, list(self._buffer))
            session.commit()
            self._buffer.clear()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to persist playback frames",
                exc_info=exc,
                extra={
                    "buffer_size": len(self._buffer),
                    "session_id": self._buffer[0].get("session_id") if self._buffer else None,
                },
            )
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


class PlaybackRecordingWrapper(gym.Wrapper):
    """Proxy environment that records state snapshots for playback."""

    def __init__(
        self,
        env: Any,
        *,
        session_id: int,
        session_factory: Callable[[], Session],
        record_interval: int = DEFAULT_RECORD_INTERVAL,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        statement_timeout_ms: int | None = None,
        record_on_reset: bool = True,
    ) -> None:
        if session_id <= 0:
            raise ValueError(f"Invalid session_id: {session_id}")

        # Initialize Wrapper manually to support non-Gymnasium environments
        # This allows wrapping of any duck-typed environment
        self.env = env
        # Copy standard attributes from wrapped environment
        # Use getattr with defaults to support environments without these attributes
        self.action_space = getattr(env, "action_space", None)
        self.observation_space = getattr(env, "observation_space", None)
        # Create a copy to avoid sharing mutable dict with wrapped environment
        self.metadata = getattr(env, "metadata", {}).copy()

        self._session_id = session_id
        self._record_interval = max(1, record_interval)
        self._record_on_reset = record_on_reset
        self._recorder = _PlaybackRecorder(
            session_factory,
            buffer_size=buffer_size,
            statement_timeout_ms=statement_timeout_ms,
        )
        self._episode = -1
        self._step_in_episode = 0
        self._steps_since_record = 0

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------
    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        observation, info = self.env.reset(seed=seed, options=options)

        self._episode += 1
        self._step_in_episode = 0
        self._steps_since_record = 0

        if self._record_on_reset:
            self._record_snapshot(
                observation=observation,
                action=None,
                reward=None,
                step=0,
            )

        return observation, info

    def step(self, action: Any):
        observation, reward, terminated, truncated, info = self.env.step(action)

        self._step_in_episode += 1
        self._steps_since_record += 1
        step_value = getattr(self.env, "time_step", self._step_in_episode)

        should_record = (
            self._steps_since_record >= self._record_interval or bool(terminated) or bool(truncated)
        )

        if should_record:
            self._record_snapshot(
                observation=observation,
                action=action,
                reward=reward,
                step=step_value,
                info=info,
            )
            self._steps_since_record = 0

        return observation, reward, terminated, truncated, info

    def close(self) -> None:
        try:
            self._recorder.flush()
        finally:
            # Safely close the wrapped environment if it has a close method
            if hasattr(self.env, "close") and callable(self.env.close):
                self.env.close()

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
        info: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "session_id": self._session_id,
            "episode": self._episode,
            "step": int(step),
            "threat_grid": {"levels": _copy_grid(getattr(self.env, "threat_levels", []))},
            "coverage_map": None,
            "suspicious_objects": _copy_mapping(getattr(self.env, "suspicious_objects", None)),
            "action_taken": self._normalise_action(action),
            "reward_received": float(reward) if reward is not None else None,
        }

        # Extract battery information from info dict if available
        if info:
            if "battery_percentage" in info:
                payload["battery_percentage"] = info["battery_percentage"]
            if "is_charging" in info:
                payload["is_charging"] = info["is_charging"]
            if "distance_to_charging_station" in info:
                payload["distance_to_charging_station"] = info["distance_to_charging_station"]
            if "charging_station_position" in info:
                pos = info["charging_station_position"]
                if isinstance(pos, tuple | list) and len(pos) == 2:
                    payload["charging_station_position_x"] = int(pos[0])
                    payload["charging_station_position_y"] = int(pos[1])

        for payload_key, (source_attr, default) in ATTR_MAPPING.items():
            value = getattr(self.env, source_attr, default)
            if isinstance(value, int | float):
                payload[payload_key] = int(value)
            else:
                payload[payload_key] = value

        coverage_source = None
        if hasattr(self.env, "visit_count"):
            coverage_source = self.env.visit_count
        elif hasattr(self.env, "last_patrolled"):
            coverage_source = self.env.last_patrolled
        if coverage_source is not None:
            payload["coverage_map"] = {"counts": _copy_grid(coverage_source)}

        if payload["reward_received"] is None and isinstance(reward, int | float):
            payload["reward_received"] = float(reward)

        self._recorder.record(payload)

    def _normalise_action(self, action: Any) -> int | None:
        if action is None:
            return None
        if isinstance(action, int | float):
            return int(action)
        if isinstance(action, list | tuple) and action:
            return self._normalise_action(action[0])
        if hasattr(action, "item"):
            try:
                return int(action.item())
            except Exception:  # pragma: no cover - defensive logging
                logger.debug("Failed to normalise action value %r", action, exc_info=True)
                return None
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.env, name)


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
    statement_timeout = options.get("statement_timeout_ms")
    statement_timeout_ms = (
        int(statement_timeout)
        if statement_timeout is not None and int(statement_timeout) > 0
        else None
    )

    return PlaybackRecordingWrapper(
        env,
        session_id=session_id,
        session_factory=session_factory,
        record_interval=max(1, record_interval),
        buffer_size=max(1, min(buffer_size, MAX_BUFFER_SIZE)),
        statement_timeout_ms=statement_timeout_ms,
        record_on_reset=record_on_reset,
    )


__all__ = [
    "PlaybackRecordingWrapper",
    "wrap_environment_for_playback",
    "DEFAULT_RECORD_INTERVAL",
    "DEFAULT_BUFFER_SIZE",
]
