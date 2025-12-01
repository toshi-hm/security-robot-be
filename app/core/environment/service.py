"""Services that expose RL environment metadata and snapshots."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from numbers import Integral
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.environment.schemas import (
  EnvironmentDefinition,
  EnvironmentState,
  RobotState,
  SuspiciousObject,
)
from rl.environments import EnvironmentSpec, available_environments

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _EnvironmentSession:
  """Tracked environment session for interactive usage."""

  id: str
  spec: EnvironmentSpec
  environment: Any
  last_accessed: datetime
  timeout_seconds: int
  lock: asyncio.Lock
  closed: bool = False


class EnvironmentService:
  def __init__(
    self,
    *,
    max_sessions: int = 128,
    session_timeout_seconds: int | None = None,
  ) -> None:
    self._registry: dict[str, EnvironmentSpec] = {
      spec.id: spec for spec in available_environments()
    }
    self._sessions: dict[str, _EnvironmentSession] = {}
    self._lock = asyncio.Lock()
    self._max_sessions = int(max_sessions)
    default_timeout = settings.environment_session_timeout_seconds
    timeout = default_timeout if session_timeout_seconds is None else session_timeout_seconds
    self._session_timeout_seconds = int(timeout)

  async def list_definitions(self) -> list[EnvironmentDefinition]:
    return [self._build_definition(spec) for spec in self._registry.values()]

  async def get_state(self, environment_id: str, *, seed: int | None = None) -> EnvironmentState:
    try:
      spec = self._registry[environment_id]
    except KeyError as exc:
      raise KeyError(environment_id) from exc

    env = spec.create()
    observation, _ = env.reset(seed=seed)

    return self._build_state(spec, env, observation)

  async def create_session(
    self,
    environment_id: str,
    *,
    seed: int | None = None,
    config: dict[str, Any] | None = None,
  ) -> tuple[str, EnvironmentState]:
    """Instantiate an interactive environment session."""

    try:
      spec = self._registry[environment_id]
    except KeyError as exc:
      raise KeyError(environment_id) from exc

    await self._cleanup_expired_sessions()

    overrides = dict(config or {})
    environment = spec.create(**overrides)
    observation, _ = environment.reset(seed=seed)
    state = self._build_state(spec, environment, observation)

    session = _EnvironmentSession(
      id=uuid4().hex,
      spec=spec,
      environment=environment,
      last_accessed=datetime.now(tz=UTC),
      timeout_seconds=self._session_timeout_seconds,
      lock=asyncio.Lock(),
    )
    try:
      async with self._lock:
        if len(self._sessions) >= self._max_sessions:
          raise RuntimeError("environment session capacity exceeded")
        self._sessions[session.id] = session
    except RuntimeError:
      close = getattr(environment, "close", None)
      if callable(close):
        close()
      raise

    return session.id, state

  async def reset_session(self, session_id: str, *, seed: int | None = None) -> EnvironmentState:
    """Reset an existing environment session."""

    await self._cleanup_expired_sessions()

    async with self._lock:
      session = self._sessions.get(session_id)
      if session is None or session.closed:
        raise KeyError(session_id)
      session_lock = session.lock

    async with session_lock:
      if session.closed:
        raise KeyError(session_id)
      observation, _ = session.environment.reset(seed=seed)
      session.last_accessed = datetime.now(tz=UTC)
      spec = session.spec
      environment = session.environment

    return self._build_state(spec, environment, observation)

  async def execute_action(
    self, session_id: str, action: int
  ) -> tuple[EnvironmentState, float, bool, bool, dict[str, Any]]:
    """Execute an action against a live environment session."""

    if not isinstance(action, Integral):
      raise ValueError("action must be an integer")

    await self._cleanup_expired_sessions()

    async with self._lock:
      session = self._sessions.get(session_id)
      if session is None or session.closed:
        raise KeyError(session_id)
      session_lock = session.lock

    async with session_lock:
      if session.closed:
        raise KeyError(session_id)

      action_space = getattr(session.environment, "action_space", None)
      if action_space is not None and hasattr(action_space, "n"):
        if action < 0 or action >= int(action_space.n):
          raise ValueError("action is out of bounds for the environment")
      elif action < 0:
        raise ValueError("action must be non-negative")

      observation, reward, terminated, truncated, info = session.environment.step(int(action))
      session.last_accessed = datetime.now(tz=UTC)
      spec = session.spec
      environment = session.environment

    state = self._build_state(spec, environment, observation)

    if info is None:
      info_payload: dict[str, Any] = {}
    elif isinstance(info, Mapping):
      info_payload = {}
      for key, value in dict(info).items():
        if isinstance(key, str):
          info_payload[key] = self._json_safe(value)
        else:
          converted_key = str(key)
          logger.debug("Converted non-string info key %r to %r", key, converted_key)
          info_payload[converted_key] = self._json_safe(value)
    else:
      info_payload = {"details": self._json_safe(info)}

    return state, float(reward), bool(terminated), bool(truncated), info_payload

  async def close_session(self, session_id: str) -> None:
    """Dispose of an interactive environment session."""

    async with self._lock:
      session = self._sessions.pop(session_id, None)
      if session is not None:
        session.closed = True

    if session is None:
      raise KeyError(session_id)

    async with session.lock:
      self._close_environment(session)

  async def _get_session(self, session_id: str) -> _EnvironmentSession:
    await self._cleanup_expired_sessions()

    async with self._lock:
      session = self._sessions.get(session_id)
      if session is None or session.closed:
        raise KeyError(session_id)
      return session

  async def _cleanup_expired_sessions(self) -> None:
    """Remove expired environment sessions.

    ロック取得順序は常に「グローバルロック → セッションロック」となるよう統一しており、
    `_sessions` 辞書から取り除いた後に各セッションロックを取得することで、
    `execute_action` / `reset_session` との間でのデッドロックを防いでいる。
    """

    now = datetime.now(tz=UTC)
    expired_sessions: list[tuple[str, _EnvironmentSession]] = []

    async with self._lock:
      for session_id, session in list(self._sessions.items()):
        if (now - session.last_accessed).total_seconds() > session.timeout_seconds:
          session.closed = True
          expired_sessions.append((session_id, session))
          self._sessions.pop(session_id)

    for session_id, session in expired_sessions:
      logger.debug("Cleaning up expired environment session %s", session_id)
      async with session.lock:
        self._close_environment(session)

  def refresh_registry(self) -> None:
    self._registry = {spec.id: spec for spec in available_environments()}

  def _close_environment(self, session: _EnvironmentSession) -> None:
    close = getattr(session.environment, "close", None)
    if callable(close):
      try:
        close()
      except Exception:  # pragma: no cover - defensive cleanup
        logger.exception("Error while closing environment for session %s", session.id)

  def _build_definition(self, spec: EnvironmentSpec) -> EnvironmentDefinition:
    config = dict(spec.default_config)
    width = int(config.get("width", 0))
    height = int(config.get("height", 0))
    robot_vision_range = int(config.get("robot_vision_range", 0))

    return EnvironmentDefinition(
      id=spec.id,
      name=spec.name,
      description=spec.description,
      width=width,
      height=height,
      robot_vision_range=robot_vision_range,
      features=list(spec.features),
      observation_channels=list(spec.observation_channels),
      action_space=dict(spec.action_space),
      default_config=config,
    )

  def _build_state(
    self,
    spec: EnvironmentSpec,
    env: Any,
    observation: Any,
  ) -> EnvironmentState:
    definition = self._build_definition(spec)

    threat_levels = self._ensure_nested_list(
      getattr(env, "threat_levels", None),
      width=definition.width,
      height=definition.height,
      fill_value=0.0,
    )
    obstacles = self._ensure_nested_list(
      getattr(env, "obstacles", None),
      width=definition.width,
      height=definition.height,
      fill_value=False,
      transform=bool,
    )
    suspicious = getattr(env, "suspicious_objects", {})

    coverage_ratio = None
    if hasattr(env, "visited_cells"):
      visited_grid = self._ensure_nested_list(
        env.visited_cells,
        width=definition.width,
        height=definition.height,
        fill_value=False,
        transform=bool,
      )
      total_cells = definition.width * definition.height
      if total_cells:
        visited_count = sum(1 for column in visited_grid for cell in column if cell)
        coverage_ratio = visited_count / total_cells

    suspicious_list = sorted(
      [
        SuspiciousObject(x=coords[0], y=coords[1], spawned_at=spawn_time)
        for coords, spawn_time in suspicious.items()
      ],
      key=lambda obj: (obj.x, obj.y),
    )

    # Extract battery system information
    battery_percentage = getattr(env, "battery_percentage", None)
    is_charging = getattr(env, "is_charging", False)
    charging_stations = getattr(env, "charging_stations", [])
    charging_station_x = getattr(env, "charging_station_x", None)
    charging_station_y = getattr(env, "charging_station_y", None)

    # Backward compatibility for single station envs or if charging_stations not set
    if not charging_stations and charging_station_x is not None and charging_station_y is not None:
        charging_stations = [(int(charging_station_x), int(charging_station_y))]

    # Calculate distance to charging station if position is available
    distance_to_charging_station = None
    charging_station_position = None
    if charging_stations:
      charging_station_position = charging_stations[0]
      robot_x = int(env.robot_x)
      robot_y = int(env.robot_y)
      # Distance to nearest station
      distance_to_charging_station = min(
          abs(robot_x - sx) + abs(robot_y - sy) for sx, sy in charging_stations
      )

    return EnvironmentState(
      environment_id=spec.id,
      definition=definition,
      observation=self._to_list(observation),
      robot=RobotState(x=int(env.robot_x), y=int(env.robot_y), direction=int(env.robot_direction)),
      threat_levels=threat_levels,
      obstacles=obstacles,
      suspicious_objects=suspicious_list,
      time_step=int(getattr(env, "time_step", 0)),
      coverage_ratio=coverage_ratio,
      battery_percentage=battery_percentage,
      is_charging=is_charging,
      distance_to_charging_station=distance_to_charging_station,
      charging_station_position=charging_station_position,
      charging_stations=charging_stations,
    )

  @staticmethod
  def _to_list(value: Any) -> Any:
    if hasattr(value, "tolist"):
      return value.tolist()
    return value

  def _json_safe(self, value: Any, *, _depth: int = 0) -> Any:
    if _depth > 10:
      return str(value)

    if value is None or isinstance(value, bool | int | float | str):
      return value

    if hasattr(value, "item") and callable(value.item):
      try:
        return self._json_safe(value.item(), _depth=_depth + 1)
      except Exception:  # pragma: no cover - defensive fallback
        pass

    if hasattr(value, "tolist"):
      try:
        return self._json_safe(value.tolist(), _depth=_depth + 1)
      except Exception:  # pragma: no cover - defensive fallback
        pass

    if isinstance(value, Mapping):
      return {
        str(key): self._json_safe(sub_value, _depth=_depth + 1) for key, sub_value in value.items()
      }

    if isinstance(value, set | frozenset):
      return [self._json_safe(item, _depth=_depth + 1) for item in value]

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
      return [self._json_safe(item, _depth=_depth + 1) for item in value]

    return str(value)

  def _ensure_nested_list(
    self,
    value: Any,
    *,
    width: int,
    height: int,
    fill_value: Any,
    transform: Any | None = None,
  ) -> list[list[Any]]:
    if hasattr(value, "tolist"):
      result = value.tolist()
    elif isinstance(value, list):
      result = value
    else:
      # Initialize grid[y][x] (row-major): height rows, width columns
      result = [[fill_value for _ in range(width)] for _ in range(height)]

    if transform is None:
      return result  # type: ignore[no-any-return]

    return [[transform(cell) for cell in column] for column in result]


environment_service = EnvironmentService()
