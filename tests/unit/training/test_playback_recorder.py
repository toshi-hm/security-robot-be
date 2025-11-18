"""Tests for the playback recording wrapper used during training."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.training.playback_recorder import MAX_BUFFER_SIZE, wrap_environment_for_playback
from app.models.base import Base
from app.models.environment import EnvironmentState


class _DummyEnv:
  """Minimal environment exposing the attributes required by the wrapper."""

  action_space: Any = None
  observation_space: Any = None

  def __init__(self) -> None:
    self.reset()
    self.closed = False

  def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
    del seed, options
    self.time_step = 0
    self.robot_x = 1
    self.robot_y = 2
    self.robot_direction = 3
    self.threat_levels = [[0.1, 0.2], [0.3, 0.4]]
    self.last_patrolled = [[0, 0], [0, 0]]
    self.suspicious_objects = {(1, 2): 7}
    return [[0.0]], {}

  def step(self, action: int):
    self.time_step += 1
    self.robot_x += 1
    self.robot_y += 1
    self.robot_direction = (self.robot_direction + 1) % 4
    self.threat_levels[0][0] += 0.1
    self.last_patrolled[0][0] = self.time_step
    self.suspicious_objects[(2, 3)] = self.time_step
    reward = 1.5
    terminated = self.time_step >= 2
    return [[1.0]], reward, terminated, False, {}

  def close(self) -> None:
    self.closed = True


@pytest.fixture()
def session_factory() -> sessionmaker[Session]:
  engine = create_engine("sqlite:///:memory:", future=True)
  Base.metadata.create_all(engine)
  factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
  yield factory
  engine.dispose()


def _fetch_states(factory: sessionmaker[Session]) -> list[EnvironmentState]:
  session = factory()
  try:
    return session.query(EnvironmentState).order_by(EnvironmentState.id).all()
  finally:
    session.close()


def test_playback_wrapper_persists_frames(session_factory: sessionmaker[Session]) -> None:
  env = _DummyEnv()
  wrapped = wrap_environment_for_playback(
    env,
    session_id=42,
    session_factory=session_factory,
    options={"record_interval": 1, "buffer_size": 2},
  )

  wrapped.reset()
  wrapped.step(0)
  wrapped.step(1)
  wrapped.close()

  states = _fetch_states(session_factory)

  assert len(states) == 3

  initial, first_step, second_step = states

  assert initial.session_id == 42
  assert initial.step == 0
  assert initial.action_taken is None
  assert initial.reward_received is None

  assert first_step.step == 1
  assert first_step.action_taken == 0
  assert pytest.approx(first_step.reward_received or 0.0) == 1.5
  assert first_step.coverage_map == {"counts": [[1, 0], [0, 0]]}
  assert first_step.threat_grid == {"levels": [[0.2, 0.2], [0.3, 0.4]]}

  assert second_step.step == 2
  assert second_step.action_taken == 1
  assert second_step.reward_received == pytest.approx(1.5)
  assert second_step.suspicious_objects is not None
  assert any(obj.get("spawn_time") == 2 for obj in second_step.suspicious_objects)


def test_wrap_environment_rejects_invalid_session_id(
  session_factory: sessionmaker[Session],
) -> None:
  env = _DummyEnv()

  with pytest.raises(ValueError):
    wrap_environment_for_playback(env, session_id=0, session_factory=session_factory)


def test_wrapper_caps_buffer_size(session_factory: sessionmaker[Session]) -> None:
  env = _DummyEnv()

  wrapped = wrap_environment_for_playback(
    env,
    session_id=1,
    session_factory=session_factory,
    options={"buffer_size": MAX_BUFFER_SIZE * 10},
  )

  assert wrapped._recorder.buffer_size == MAX_BUFFER_SIZE


def test_wrapper_handles_missing_attributes(session_factory: sessionmaker[Session]) -> None:
  class MinimalEnv:
    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
      del seed, options
      return [[0.0]], {}

    def step(self, action: int):
      del action
      return [[0.1]], 1.0, True, False, {}

  env = MinimalEnv()
  wrapped = wrap_environment_for_playback(env, session_id=1, session_factory=session_factory)

  wrapped.reset()
  wrapped.step(0)
  wrapped.close()

  states = _fetch_states(session_factory)
  assert states[0].robot_x == -1
  assert states[0].robot_y == -1
  assert states[0].robot_orientation == 0


def test_recorder_flushes_on_buffer_capacity(session_factory: sessionmaker[Session]) -> None:
  env = _DummyEnv()
  wrapped = wrap_environment_for_playback(
    env,
    session_id=7,
    session_factory=session_factory,
    options={"buffer_size": 2, "record_on_reset": False},
  )

  wrapped.reset()
  wrapped.step(0)

  states_after_first_step = _fetch_states(session_factory)
  assert len(states_after_first_step) == 0

  wrapped.step(1)

  states_after_second_step = _fetch_states(session_factory)
  assert len(states_after_second_step) == 2

  wrapped.close()


def test_recorder_clears_buffer_after_session_error(session_factory: sessionmaker[Session]) -> None:
  class FailingSession(Session):
    def bulk_insert_mappings(self, *args, **kwargs):  # type: ignore[override]
      raise RuntimeError("boom")

  base_session = session_factory()
  bind = base_session.get_bind()
  base_session.close()

  failing_factory = sessionmaker(
    bind=bind,
    class_=FailingSession,
    autoflush=False,
    expire_on_commit=False,
  )

  env = _DummyEnv()
  wrapped = wrap_environment_for_playback(
    env,
    session_id=9,
    session_factory=failing_factory,
    options={"buffer_size": 1},
  )

  wrapped.reset()

  # Recording should swallow the error and clear the buffer
  wrapped.step(0)

  # Close should not raise even though flush previously failed
  wrapped.close()

  assert _fetch_states(session_factory) == []


def test_wrapper_copies_metadata(session_factory: sessionmaker[Session]) -> None:
  class EnvWithMetadata:
    def __init__(self):
      self.metadata = {"render_modes": ["human", "rgb_array"], "custom_key": "value"}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
      return [[0.0]], {}

    def step(self, action: int):
      return [[0.0]], 0.0, False, False, {}

  env = EnvWithMetadata()
  original_metadata = env.metadata.copy()

  wrapped = wrap_environment_for_playback(env, session_id=1, session_factory=session_factory)

  # Wrapper should have a copy of metadata, not the same object
  assert wrapped.metadata is not env.metadata
  assert wrapped.metadata == original_metadata

  # Modifying wrapper's metadata should not affect env's metadata
  wrapped.metadata["new_key"] = "new_value"
  assert "new_key" not in env.metadata
  assert env.metadata == original_metadata

  wrapped.close()
