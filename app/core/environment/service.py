"""Services that expose RL environment metadata and snapshots."""

from __future__ import annotations

from typing import Any

from app.core.environment.schemas import (
    EnvironmentDefinition,
    EnvironmentState,
    RobotState,
    SuspiciousObject,
)
from rl.environments import EnvironmentSpec, available_environments


class EnvironmentService:
    def __init__(self) -> None:
        self._registry: dict[str, EnvironmentSpec] = {
            spec.id: spec for spec in available_environments()
        }

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

