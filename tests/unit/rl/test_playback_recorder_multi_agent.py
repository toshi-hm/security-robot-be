"""Unit tests for multi-agent playback recorder."""

from unittest.mock import MagicMock, patch

import gymnasium as gym

from app.core.training.playback_recorder import wrap_environment_for_playback


class MockMultiAgentEnv(gym.Env):
  def __init__(self):
    self.robot_positions = [(1, 1), (2, 2)]
    self.robot_directions = [0, 1]
    self.threat_levels = [[0]]
    self.obstacles = [[0]]
    self.visit_count = [[0]]
    self.time_step = 1
    self.charging_stations = [(0, 0), (5, 5)]

  def step(self, action):
    return {}, 0, False, False, {}

  def reset(self, **kwargs):
    return {}, {}


@patch("app.core.training.playback_recorder._PlaybackRecorder")
def test_playback_recorder_captures_multi_agent_state(mock_recorder_cls):
  env = MockMultiAgentEnv()
  mock_session_factory = MagicMock()

  mock_recorder_instance = mock_recorder_cls.return_value

  wrapped_env = wrap_environment_for_playback(
    env, session_id=123, session_factory=mock_session_factory, options={"record_interval": 1}
  )

  wrapped_env.step(0)

  # Verify record was called
  assert mock_recorder_instance.record.called
  call_args = mock_recorder_instance.record.call_args
  payload = call_args[0][0]

  assert "robots" in payload
  assert len(payload["robots"]) == 2
  assert payload["robots"][0] == {
    "id": 0,
    "x": 1,
    "y": 1,
    "orientation": 0,
    "battery_percentage": 100.0,
    "is_charging": False,
  }
  assert payload["robots"][1] == {
    "id": 1,
    "x": 2,
    "y": 2,
    "orientation": 1,
    "battery_percentage": 100.0,
    "is_charging": False,
  }

  assert "charging_stations" in payload
  assert payload["charging_stations"] == [{"x": 0, "y": 0}, {"x": 5, "y": 5}]
