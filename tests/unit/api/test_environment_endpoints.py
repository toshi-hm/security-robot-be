from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import environment as environment_module
from app.core.environment.schemas import (
    EnvironmentDefinition,
    EnvironmentState,
    RobotState,
    SuspiciousObject,
)


class StubEnvironmentService:
    def __init__(self, definitions: list[EnvironmentDefinition], state: EnvironmentState):
        self._definitions = definitions
        self._state = state

    async def list_definitions(self) -> list[EnvironmentDefinition]:
        return list(self._definitions)

    async def get_state(self, environment_id: str, *, seed: int | None = None) -> EnvironmentState:
        if environment_id != self._state.environment_id:
            raise KeyError(environment_id)
        return self._state


def _sample_state() -> EnvironmentState:
    definition = EnvironmentDefinition(
        id="tracked",
        name="Tracked",
        description="",
        width=2,
        height=2,
        robot_vision_range=1,
        features=["coverage"],
        observation_channels=["threat"],
        action_space={"type": "discrete"},
        default_config={"width": 2, "height": 2},
    )
    return EnvironmentState(
        environment_id="tracked",
        definition=definition,
        observation=[[[0.0, 0.0, 0.0] for _ in range(2)] for _ in range(2)],
        robot=RobotState(x=1, y=0, direction=2),
        threat_levels=[[0.1, 0.2], [0.3, 0.4]],
        obstacles=[[False, True], [False, False]],
        suspicious_objects=[SuspiciousObject(x=0, y=1, spawned_at=3)],
        time_step=7,
        coverage_ratio=0.5,
    )


def test_list_environments_success(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = asyncio.run(environment_module.list_environments())
    assert payload["data"][0].id == "tracked"


def test_get_environment_state_success(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = asyncio.run(environment_module.get_environment_state("tracked"))
    assert payload["data"].environment_id == "tracked"
    assert payload["data"].coverage_ratio == pytest.approx(0.5)


def test_get_environment_state_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(environment_module.get_environment_state("unknown"))

    assert excinfo.value.status_code == 404
    assert "not found" in excinfo.value.detail.lower()
