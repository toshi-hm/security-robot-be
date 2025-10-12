"""Services that expose RL environment metadata and snapshots."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral
from typing import Any
from uuid import uuid4

from app.core.environment.schemas import (
    EnvironmentDefinition,
    EnvironmentState,
    RobotState,
    SuspiciousObject,
)
from rl.environments import EnvironmentSpec, available_environments


@dataclass(slots=True)
class _EnvironmentSession:
    """Tracked environment session for interactive usage."""

    id: str
    spec: EnvironmentSpec
    environment: Any


class EnvironmentService:
    def __init__(self, *, max_sessions: int = 128) -> None:
        self._registry: dict[str, EnvironmentSpec] = {
            spec.id: spec for spec in available_environments()
        }
        self._sessions: dict[str, _EnvironmentSession] = {}
        self._lock = asyncio.Lock()
        self._max_sessions = int(max_sessions)

    async def list_definitions(self) -> list[EnvironmentDefinition]:
        return [self._build_definition(spec) for spec in self._registry.values()]

    async def get_state(
        self, environment_id: str, *, seed: int | None = None
    ) -> EnvironmentState:
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

        overrides = dict(config or {})
        environment = spec.create(**overrides)
        observation, _ = environment.reset(seed=seed)
        state = self._build_state(spec, environment, observation)

        session = _EnvironmentSession(id=uuid4().hex, spec=spec, environment=environment)
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

    async def reset_session(
        self, session_id: str, *, seed: int | None = None
    ) -> EnvironmentState:
        """Reset an existing environment session."""

        session = await self._get_session(session_id)
        observation, _ = session.environment.reset(seed=seed)
        return self._build_state(session.spec, session.environment, observation)

    async def execute_action(
        self, session_id: str, action: int
    ) -> tuple[EnvironmentState, float, bool, bool, dict[str, Any]]:
        """Execute an action against a live environment session."""

        if not isinstance(action, Integral):
            raise ValueError("action must be an integer")

        session = await self._get_session(session_id)

        action_space = getattr(session.environment, "action_space", None)
        if action_space is not None and hasattr(action_space, "n"):
            if action < 0 or action >= int(action_space.n):
                raise ValueError("action is out of bounds for the environment")
        elif action < 0:
            raise ValueError("action must be non-negative")

        observation, reward, terminated, truncated, info = session.environment.step(
            int(action)
        )
        state = self._build_state(session.spec, session.environment, observation)

        if info is None:
            info_payload: dict[str, Any] = {}
        elif isinstance(info, Mapping):
            info_payload = {
                str(key): self._json_safe(value) for key, value in dict(info).items()
            }
        else:
            info_payload = {"details": self._json_safe(info)}

        return state, float(reward), bool(terminated), bool(truncated), info_payload

    async def close_session(self, session_id: str) -> None:
        """Dispose of an interactive environment session."""

        async with self._lock:
            session = self._sessions.pop(session_id, None)

        if session is None:
            raise KeyError(session_id)

        close = getattr(session.environment, "close", None)
        if callable(close):
            close()

    async def _get_session(self, session_id: str) -> _EnvironmentSession:
        async with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session

    def refresh_registry(self) -> None:
        self._registry = {spec.id: spec for spec in available_environments()}

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
                visited_count = sum(
                    1 for column in visited_grid for cell in column if cell
                )
                coverage_ratio = visited_count / total_cells

        suspicious_list = sorted(
            [
                SuspiciousObject(x=coords[0], y=coords[1], spawned_at=spawn_time)
                for coords, spawn_time in suspicious.items()
            ],
            key=lambda obj: (obj.x, obj.y),
        )

        return EnvironmentState(
            environment_id=spec.id,
            definition=definition,
            observation=self._to_list(observation),
            robot=RobotState(
                x=int(env.robot_x), y=int(env.robot_y), direction=int(env.robot_direction)
            ),
            threat_levels=threat_levels,
            obstacles=obstacles,
            suspicious_objects=suspicious_list,
            time_step=int(getattr(env, "time_step", 0)),
            coverage_ratio=coverage_ratio,
        )

    @staticmethod
    def _to_list(value: Any) -> Any:
        if hasattr(value, "tolist"):
            return value.tolist()
        return value

    def _json_safe(self, value: Any, *, _depth: int = 0) -> Any:
        if _depth > 10:
            return str(value)

        if value is None or isinstance(value, (bool, int, float, str)):
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
                str(key): self._json_safe(sub_value, _depth=_depth + 1)
                for key, sub_value in value.items()
            }

        if isinstance(value, (set, frozenset)):
            return [self._json_safe(item, _depth=_depth + 1) for item in value]

        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
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
            result = [[fill_value for _ in range(height)] for _ in range(width)]

        if transform is None:
            return result

        return [[transform(cell) for cell in column] for column in result]


environment_service = EnvironmentService()

