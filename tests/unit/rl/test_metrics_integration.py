from unittest.mock import MagicMock

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from app.core.training.playback_recorder import PlaybackRecordingWrapper
from rl.callbacks.redis_pubsub_callback import RedisTrainingCallback


class MockEnv(gym.Env):
  def __init__(self):
    self.observation_space = spaces.Box(low=0, high=1, shape=(1, 5, 5), dtype=np.float32)
    self.action_space = spaces.Discrete(4)
    self.threat_levels = [[0.0]]
    self.obstacles = [[False]]
    self.suspicious_objects = {}
    self.robot_x = 0
    self.robot_y = 0
    self.robot_direction = 0
    self.time_step = 0

  def reset(self, seed=None, options=None):
    return np.zeros((1, 5, 5), dtype=np.float32), {}

  def step(self, action):
    self.time_step += 1
    info = {"coverage_ratio": 0.5, "exploration_score": 0.8, "battery_percentage": 90.0}
    return np.zeros((1, 5, 5), dtype=np.float32), 1.0, False, False, info

  def close(self):
    pass


def test_playback_recorder_captures_metrics():
  mock_env = MockEnv()
  session_factory = MagicMock()
  recorder = PlaybackRecordingWrapper(
    mock_env, session_id=1, session_factory=session_factory, record_interval=1
  )

  recorder.reset()
  recorder.step(0)

  # Check buffer in recorder
  assert len(recorder._recorder._buffer) > 0
  last_frame = recorder._recorder._buffer[-1]

  assert "coverage_ratio" in last_frame
  assert last_frame["coverage_ratio"] == 0.5
  assert "exploration_score" in last_frame
  assert last_frame["exploration_score"] == 0.8


def test_redis_callback_publishes_metrics():
  redis_client = MagicMock()
  callback = RedisTrainingCallback(session_id=1, redis_client=redis_client, update_interval=1)

  # Mock model and logger
  callback.model = MagicMock()
  callback.model.logger = MagicMock()
  callback.model.logger.name_to_value = {}

  # Simulate a step with metrics
  callback.locals = {
    "infos": [{"coverage_ratio": 0.6, "exploration_score": 0.9}],
    "rewards": [1.0],
    "dones": [False],
  }

  callback._on_step()

  # Check if publish was called
  assert redis_client.publish.called

  # Inspect the payload
  call_args = redis_client.publish.call_args
  import json

  payload = json.loads(call_args[0][1])

  assert payload["type"] == "training_progress"
  assert payload["coverage_ratio"] == 0.6
  assert payload["exploration_score"] == 0.9
