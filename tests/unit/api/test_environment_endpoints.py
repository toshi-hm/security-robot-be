from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi import status

from app.api.v1.endpoints import environment as environment_module
from app.core.environment.schemas import (
    EnvironmentDefinition,
    EnvironmentState,
    RobotState,
    SuspiciousObject,
)
from app.schemas.environment import (
    EnvironmentActionRequest,
    EnvironmentSessionCreate,
    EnvironmentSessionResetRequest,
)


class StubEnvironmentService:
    def __init__(self, definitions: list[EnvironmentDefinition], state: EnvironmentState):
        self._definitions = definitions
        self._state = state
        self.closed: list[str] = []

    async def list_definitions(self) -> list[EnvironmentDefinition]:
        return list(self._definitions)

    async def get_state(self, environment_id: str, *, seed: int | None = None) -> EnvironmentState:
        if environment_id != self._state.environment_id:
            raise KeyError(environment_id)
        return self._state

    async def create_session(
        self,
        environment_id: str,
        *,
        seed: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> tuple[str, EnvironmentState]:
        if environment_id != self._state.environment_id:
            raise KeyError(environment_id)
        return "session-1", self._state

    async def reset_session(self, session_id: str, *, seed: int | None = None) -> EnvironmentState:
        if session_id != "session-1":
            raise KeyError(session_id)
        return self._state

    async def execute_action(
        self, session_id: str, action: int
    ) -> tuple[EnvironmentState, float, bool, bool, dict[str, Any]]:
        if session_id != "session-1":
            raise KeyError(session_id)
        if action < 0 or action > 5:
            raise ValueError("invalid action")
        return self._state, 1.5, False, False, {"action": action}

    async def close_session(self, session_id: str) -> None:
        if session_id != "session-1":
            raise KeyError(session_id)
        self.closed.append(session_id)


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


def test_create_environment_session(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = EnvironmentSessionCreate(environment_id="tracked")
    response = asyncio.run(environment_module.create_environment_session(payload))
    assert response["data"].session_id == "session-1"
    assert response["data"].state.environment_id == "tracked"


def test_create_environment_session_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = EnvironmentSessionCreate(environment_id="unknown")
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(environment_module.create_environment_session(payload))

    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND


def test_create_environment_session_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()

    class LimitedService(StubEnvironmentService):
        async def create_session(
            self,
            environment_id: str,
            *,
            seed: int | None = None,
            config: dict[str, Any] | None = None,
        ) -> tuple[str, EnvironmentState]:
            raise RuntimeError("capacity exceeded")

    service = LimitedService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = EnvironmentSessionCreate(environment_id="tracked")
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(environment_module.create_environment_session(payload))

    assert excinfo.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_reset_environment_session(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = EnvironmentSessionResetRequest(seed=123)
    response = asyncio.run(
        environment_module.reset_environment_session("session-1", payload)
    )
    assert response["data"].session_id == "session-1"


def test_reset_environment_session_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(environment_module.reset_environment_session("missing", None))

    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND


def test_perform_environment_action(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = EnvironmentActionRequest(action=2)
    response = asyncio.run(
        environment_module.perform_environment_action("session-1", payload)
    )
    result = response["data"]
    assert result.reward == pytest.approx(1.5)
    assert result.info["action"] == 2


def test_perform_environment_action_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    payload = EnvironmentActionRequest(action=1)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(environment_module.perform_environment_action("unknown", payload))
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND

    payload = EnvironmentActionRequest(action=6)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(environment_module.perform_environment_action("session-1", payload))
    assert excinfo.value.status_code == status.HTTP_400_BAD_REQUEST


def test_close_environment_session(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _sample_state()
    service = StubEnvironmentService([state.definition], state)
    monkeypatch.setattr(environment_module, "environment_service", service)

    response = asyncio.run(environment_module.close_environment_session("session-1"))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert service.closed == ["session-1"]

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(environment_module.close_environment_session("missing"))
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND
