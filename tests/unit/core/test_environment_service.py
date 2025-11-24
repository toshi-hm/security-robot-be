from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Any

import pytest

from app.core.environment import service as service_module
from app.core.environment.schemas import EnvironmentDefinition
from rl.environments import EnvironmentSpec


class _ActionSpace:
  def sample(self) -> int:  # pragma: no cover - used indirectly
    return 0


class TrackingEnvironment:
  """Deterministic test double exposing coverage-related attributes."""

  action_space = _ActionSpace()

  def __init__(
    self,
    *,
    width: int = 3,
    height: int = 2,
    robot_vision_range: int = 1,
  ) -> None:
    self.width = width
    self.height = height
    self.robot_vision_range = robot_vision_range
    self.robot_x = 1
    self.robot_y = 0
    self.robot_direction = 2
    self.time_step = 5

    self.threat_levels = self._grid(0.25)
    self.obstacles = self._grid(False)
    self.suspicious_objects = {(2, 1): 3, (0, 0): 1}
    self.visited_cells = [
      [True, False],
      [True, True],
      [False, False],
    ]

  def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
    self.robot_x = 1
    self.robot_y = 0
    self.robot_direction = 2
    self.time_step = 5 if seed is None else seed % 10

    observation = [[[0.0, 0.0, 0.0] for _ in range(self.height)] for _ in range(self.width)]
    for x in range(self.width):
      for y in range(self.height):
        observation[x][y][0] = self.threat_levels[x][y]
    return observation, {"seed": seed}

  def step(self, action: int):
    self.time_step += 1

    if action == 0:
      self.robot_x = max(0, self.robot_x - 1)
    elif action == 1:
      self.robot_y = min(self.height - 1, self.robot_y + 1)

    observation = [[[0.0, 0.0, 0.0] for _ in range(self.height)] for _ in range(self.width)]
    for x in range(self.width):
      for y in range(self.height):
        observation[x][y][0] = self.threat_levels[x][y]
        observation[x][y][1] = 1.0 if self.obstacles[x][y] else 0.0
    observation[self.robot_x][self.robot_y][2] = (self.robot_direction + 1) / 4.0

    return observation, float(action), False, False, {"action": action}

  def _grid(self, fill: Any) -> list[list[Any]]:
    return [[fill for _ in range(self.height)] for _ in range(self.width)]


class MinimalEnvironment:
  """Test double without optional attributes to exercise fallbacks."""

  action_space = _ActionSpace()

  def __init__(self, *, width: int = 2, height: int = 2, robot_vision_range: int = 1):
    self.width = width
    self.height = height
    self.robot_vision_range = robot_vision_range
    self.robot_x = 0
    self.robot_y = 1
    self.robot_direction = 1
    self.time_step = 0

  def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
    observation = [[[0.0, 0.0, 0.0] for _ in range(self.height)] for _ in range(self.width)]
    return observation, {}


class NonSerializableEnvironment(MinimalEnvironment):
  def __init__(self, **kwargs: Any) -> None:
    super().__init__(**kwargs)
    self.closed = False

  def step(self, action: int):
    observation = [[[0.0, 0.0, 0.0] for _ in range(self.height)] for _ in range(self.width)]
    info = {
      "set": {1, 2, 3},
      "mapping": {"nested": {"value": complex(1, 2)}},
      "sequence": (b"bytes", bytearray(b"data")),
    }
    return observation, 1.0, False, False, info

  def close(self) -> None:  # pragma: no cover - invoked indirectly
    self.closed = True


class GuardedEnvironment(TrackingEnvironment):
  def __init__(self, **kwargs: Any) -> None:
    super().__init__(**kwargs)
    self._in_step = False
    self.step_calls = 0

  def step(self, action: int):
    if self._in_step:
      raise RuntimeError("concurrent step detected")
    self._in_step = True
    try:
      self.step_calls += 1
      return super().step(action)
    finally:
      self._in_step = False


class TerminatingEnvironment(TrackingEnvironment):
  def __init__(self, **kwargs: Any) -> None:
    super().__init__(**kwargs)
    self._terminated_once = False

  def step(self, action: int):
    observation, reward, _, _, info = super().step(action)
    terminated = not self._terminated_once
    self._terminated_once = True
    return observation, reward, terminated, False, info


class NonStringInfoEnvironment(TrackingEnvironment):
  def step(self, action: int):
    observation, reward, terminated, truncated, _ = super().step(action)
    info = {1: "value", "action": action}
    return observation, reward, terminated, truncated, info


def _build_specs() -> tuple[EnvironmentSpec, EnvironmentSpec]:
  tracked_spec = EnvironmentSpec(
    id="tracked",
    name="Tracked",
    description="Env with coverage",
    factory=lambda **config: TrackingEnvironment(**config),  # type: ignore[arg-type]
    default_config={"width": 3, "height": 2, "robot_vision_range": 1},
    features=["coverage"],
    observation_channels=["threat_levels"],
    action_space={"type": "discrete"},
  )
  minimal_spec = EnvironmentSpec(
    id="minimal",
    name="Minimal",
    description="Env without optional arrays",
    factory=lambda **config: MinimalEnvironment(**config),  # type: ignore[arg-type]
    default_config={"width": 2, "height": 2, "robot_vision_range": 1},
    features=[],
    observation_channels=[],
    action_space={},
  )
  return (tracked_spec, minimal_spec)


def test_default_timeout_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(service_module, "available_environments", _build_specs)
  monkeypatch.setattr(
    service_module.settings,
    "environment_session_timeout_seconds",
    4321,
    raising=False,
  )

  service = service_module.EnvironmentService()

  assert service._session_timeout_seconds == 4321


def test_list_definitions_and_get_state(monkeypatch: pytest.MonkeyPatch) -> None:
  specs = tuple(_build_specs())
  monkeypatch.setattr(service_module, "available_environments", lambda: specs)
  service = service_module.EnvironmentService()

  definitions = asyncio.run(service.list_definitions())
  assert {definition.id for definition in definitions} == {"tracked", "minimal"}

  tracked_definition = next(definition for definition in definitions if definition.id == "tracked")
  assert isinstance(tracked_definition, EnvironmentDefinition)
  assert tracked_definition.width == 3
  assert tracked_definition.height == 2
  assert tracked_definition.robot_vision_range == 1
  assert tracked_definition.default_config == specs[0].default_config
  assert tracked_definition.default_config is not specs[0].default_config

  state = asyncio.run(service.get_state("tracked", seed=123))
  assert state.environment_id == "tracked"
  assert state.robot.x == 1
  assert state.robot.y == 0
  assert state.coverage_ratio == pytest.approx(3 / 6)
  assert [(obj.x, obj.y, obj.spawned_at) for obj in state.suspicious_objects] == [
    (0, 0, 1),
    (2, 1, 3),
  ]

  minimal_state = asyncio.run(service.get_state("minimal"))
  assert minimal_state.coverage_ratio is None
  assert minimal_state.threat_levels == [[0.0, 0.0], [0.0, 0.0]]
  assert minimal_state.obstacles == [[False, False], [False, False]]


def test_get_state_missing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(service_module, "available_environments", _build_specs)
  service = service_module.EnvironmentService()

  with pytest.raises(KeyError):
    asyncio.run(service.get_state("unknown"))


def test_refresh_registry(monkeypatch: pytest.MonkeyPatch) -> None:
  def first() -> tuple[EnvironmentSpec]:
    return (_build_specs()[0],)

  def second() -> tuple[EnvironmentSpec]:
    return (_build_specs()[1],)

  monkeypatch.setattr(service_module, "available_environments", first)
  service = service_module.EnvironmentService()
  initial_ids = {definition.id for definition in asyncio.run(service.list_definitions())}
  assert initial_ids == {"tracked"}

  monkeypatch.setattr(service_module, "available_environments", second)
  service.refresh_registry()
  refreshed_ids = {definition.id for definition in asyncio.run(service.list_definitions())}
  assert refreshed_ids == {"minimal"}


def test_environment_session_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
  specs = tuple(_build_specs())
  monkeypatch.setattr(service_module, "available_environments", lambda: specs)
  service = service_module.EnvironmentService()

  session_id, initial_state = asyncio.run(
    service.create_session("tracked", seed=7, config={"width": 3, "height": 2})
  )
  assert session_id
  assert initial_state.environment_id == "tracked"

  step_state, reward, terminated, truncated, info = asyncio.run(
    service.execute_action(session_id, 0)
  )
  assert reward == pytest.approx(0.0)
  assert not terminated
  assert not truncated
  assert info["action"] == 0
  assert step_state.robot.x == 0

  reset_state = asyncio.run(service.reset_session(session_id))
  assert reset_state.robot.x == 1

  asyncio.run(service.close_session(session_id))
  with pytest.raises(KeyError):
    asyncio.run(service.execute_action(session_id, 0))


def test_execute_action_serializes_info(monkeypatch: pytest.MonkeyPatch) -> None:
  spec = EnvironmentSpec(
    id="non-serializable",
    name="NonSerializable",
    description="",
    factory=lambda **config: NonSerializableEnvironment(**config),  # type: ignore[arg-type]
    default_config={"width": 2, "height": 2, "robot_vision_range": 1},
    features=[],
    observation_channels=[],
    action_space={"type": "discrete"},
  )
  monkeypatch.setattr(service_module, "available_environments", lambda: (spec,))
  service = service_module.EnvironmentService()

  session_id, _ = asyncio.run(service.create_session("non-serializable"))
  _, _, _, _, info = asyncio.run(service.execute_action(session_id, 0))

  assert sorted(info["set"]) == [1, 2, 3]
  assert info["mapping"] == {"nested": {"value": "(1+2j)"}}
  assert info["sequence"] == ["b'bytes'", "bytearray(b'data')"]


def test_create_session_enforces_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
  created_envs: list[NonSerializableEnvironment] = []

  def factory(**config: Any) -> NonSerializableEnvironment:
    env = NonSerializableEnvironment(**config)
    created_envs.append(env)
    return env

  spec = EnvironmentSpec(
    id="limited",
    name="Limited",
    description="",
    factory=factory,  # type: ignore[arg-type]
    default_config={"width": 2, "height": 2, "robot_vision_range": 1},
    features=[],
    observation_channels=[],
    action_space={"type": "discrete"},
  )
  monkeypatch.setattr(service_module, "available_environments", lambda: (spec,))
  service = service_module.EnvironmentService(max_sessions=1)

  session_id, _ = asyncio.run(service.create_session("limited"))
  assert session_id

  with pytest.raises(RuntimeError):
    asyncio.run(service.create_session("limited"))

  assert created_envs[-1].closed is True


def test_concurrent_actions_on_same_session(monkeypatch: pytest.MonkeyPatch) -> None:
  spec = EnvironmentSpec(
    id="guarded",
    name="Guarded",
    description="",
    factory=lambda **config: GuardedEnvironment(**config),  # type: ignore[arg-type]
    default_config={"width": 3, "height": 2, "robot_vision_range": 1},
    features=[],
    observation_channels=[],
    action_space={"type": "discrete", "n": 4},
  )
  monkeypatch.setattr(service_module, "available_environments", lambda: (spec,))
  service = service_module.EnvironmentService()

  session_id, _ = asyncio.run(service.create_session("guarded"))

  async def _run_steps() -> list[tuple[Any, float, bool, bool, dict[str, Any]]]:
    return await asyncio.gather(*[service.execute_action(session_id, 0) for _ in range(5)])  # type: ignore[no-any-return]

  results = asyncio.run(_run_steps())
  assert len(results) == 5
  env = service._sessions[session_id].environment
  assert isinstance(env, GuardedEnvironment)
  assert env.step_calls == 5


def test_session_reuse_after_terminated(monkeypatch: pytest.MonkeyPatch) -> None:
  spec = EnvironmentSpec(
    id="terminating",
    name="Terminating",
    description="",
    factory=lambda **config: TerminatingEnvironment(**config),  # type: ignore[arg-type]
    default_config={"width": 3, "height": 2, "robot_vision_range": 1},
    features=[],
    observation_channels=[],
    action_space={"type": "discrete", "n": 2},
  )
  monkeypatch.setattr(service_module, "available_environments", lambda: (spec,))
  service = service_module.EnvironmentService()

  session_id, _ = asyncio.run(service.create_session("terminating"))

  first = asyncio.run(service.execute_action(session_id, 0))
  assert first[2] is True

  second = asyncio.run(service.execute_action(session_id, 0))
  assert second[2] is False


def test_expired_session_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
  spec = EnvironmentSpec(
    id="expiring",
    name="Expiring",
    description="",
    factory=lambda **config: NonSerializableEnvironment(**config),  # type: ignore[arg-type]
    default_config={"width": 2, "height": 2, "robot_vision_range": 1},
    features=[],
    observation_channels=[],
    action_space={"type": "discrete"},
  )
  monkeypatch.setattr(service_module, "available_environments", lambda: (spec,))
  service = service_module.EnvironmentService(session_timeout_seconds=1)

  session_id, _ = asyncio.run(service.create_session("expiring"))
  session = service._sessions[session_id]
  environment = session.environment
  session.last_accessed -= timedelta(seconds=120)

  with pytest.raises(KeyError):
    asyncio.run(service.reset_session(session_id))

  assert environment.closed is True


def test_execute_action_logs_non_string_info_keys(
  monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
  spec = EnvironmentSpec(
    id="non-string-info",
    name="NonStringInfo",
    description="",
    factory=lambda **config: NonStringInfoEnvironment(**config),  # type: ignore[arg-type]
    default_config={"width": 3, "height": 2, "robot_vision_range": 1},
    features=[],
    observation_channels=[],
    action_space={"type": "discrete", "n": 3},
  )
  monkeypatch.setattr(service_module, "available_environments", lambda: (spec,))
  service = service_module.EnvironmentService()

  session_id, _ = asyncio.run(service.create_session("non-string-info"))
  caplog.set_level(logging.DEBUG, logger=service_module.__name__)

  _, _, _, _, info = asyncio.run(service.execute_action(session_id, 0))

  assert info["1"] == "value"
  assert any("Converted non-string info key" in record.message for record in caplog.records)
