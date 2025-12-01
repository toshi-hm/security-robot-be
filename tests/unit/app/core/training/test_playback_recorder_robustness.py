
from typing import Any
import unittest
from unittest.mock import MagicMock

import gymnasium as gym
import numpy as np

from app.core.training.playback_recorder import PlaybackRecordingWrapper


class MockEnv(gym.Env):
  def __init__(self):
    self.observation_space = gym.spaces.Discrete(1)
    self.action_space = gym.spaces.Discrete(1)
    self.robot_positions: Any = []
    self.robot_directions: Any = []

  def reset(self, seed=None, options=None):
    return 0, {}

  def step(self, action):
    return 0, 0, False, False, {}


class TestPlaybackRecorderRobustness(unittest.TestCase):
  def setUp(self):
    self.env = MockEnv()
    self.session_factory = MagicMock()
    self.wrapper = PlaybackRecordingWrapper(
      self.env, session_id=1, session_factory=self.session_factory, record_on_reset=False
    )

  def test_robot_positions_numpy_array(self):
    """Test that numpy arrays for robot_positions are handled correctly."""
    self.env.robot_positions = np.array([[1, 2], [3, 4]])
    self.env.robot_directions = [0, 1]

    # Trigger record
    self.wrapper._record_snapshot(observation=None, action=None, reward=0, step=0)

    # Check buffer
    payload = self.wrapper._recorder._buffer[-1]
    self.assertIn("robots", payload)
    self.assertEqual(len(payload["robots"]), 2)
    self.assertEqual(payload["robots"][0]["x"], 1)
    self.assertEqual(payload["robots"][1]["x"], 3)

  def test_mismatched_lengths(self):
    """Test mismatched lengths of positions and directions."""
    self.env.robot_positions = [(1, 2), (3, 4)]
    self.env.robot_directions = [0]  # Only one direction

    self.wrapper._record_snapshot(observation=None, action=None, reward=0, step=0)

    payload = self.wrapper._recorder._buffer[-1]
    self.assertEqual(len(payload["robots"]), 2)
    # Second robot should have default direction 0
    self.assertEqual(payload["robots"][1]["orientation"], 0)

  def test_invalid_positions(self):
    """Test invalid entries in robot_positions."""
    self.env.robot_positions = [(1, 2), None, "invalid", (3,)]
    self.env.robot_directions = [0, 0, 0, 0]

    self.wrapper._record_snapshot(observation=None, action=None, reward=0, step=0)

    payload = self.wrapper._recorder._buffer[-1]
    # Only the first valid position should be recorded
    self.assertEqual(len(payload["robots"]), 1)
    self.assertEqual(payload["robots"][0]["x"], 1)

  def test_none_attributes(self):
    """Test None attributes."""
    self.env.robot_positions = None
    self.env.robot_directions = None

    self.wrapper._record_snapshot(observation=None, action=None, reward=0, step=0)

    payload = self.wrapper._recorder._buffer[-1]
    self.assertNotIn("robots", payload)


if __name__ == "__main__":
  unittest.main()
