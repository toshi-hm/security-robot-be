from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class EnvironmentDefinition(BaseModel):
    id: str
    name: str
    description: str
    width: int
    height: int
    robot_vision_range: int
    features: list[str]
    observation_channels: list[str]
    action_space: dict[str, Any]
    default_config: dict[str, Any]


class RobotState(BaseModel):
    x: int
    y: int
    direction: int


class SuspiciousObject(BaseModel):
    x: int
    y: int
    spawned_at: int


class EnvironmentState(BaseModel):
    environment_id: str
    definition: EnvironmentDefinition
    observation: list[list[list[float]]]
    robot: RobotState
    threat_levels: list[list[float]]
    obstacles: list[list[bool]]
    suspicious_objects: list[SuspiciousObject]
    time_step: int
    coverage_ratio: float | None = None

    # Battery system
    battery_percentage: float | None = None
    is_charging: bool = False
    distance_to_charging_station: int | None = None
    charging_station_position: tuple[int, int] | None = None
