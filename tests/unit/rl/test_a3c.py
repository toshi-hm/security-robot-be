from __future__ import annotations

import asyncio
from typing import List, Tuple

import numpy as np
import pytest
import torch
from gymnasium import spaces

from app.core.training.a3c_service import A3CTrainingService
from rl.algorithms.a3c.network import A3CNetwork
from rl.algorithms.a3c.trainer import A3CTrainer
from rl.algorithms.a3c.worker import compute_gae


class _DummyEnv:
  """Minimal deterministic environment for exercising the A3C stack."""

  def __init__(self) -> None:
    self.action_space = spaces.Discrete(2)
    self.observation_space = spaces.Box(low=0, high=1, shape=(2, 2, 1), dtype=np.float32)
    self._step_count = 0

  def reset(self, *, seed: int | None = None, options: dict | None = None) -> Tuple[np.ndarray, dict]:
    self._step_count = 0
    return np.zeros(self.observation_space.shape, dtype=np.float32), {}

  def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
    self._step_count += 1
    reward = 1.0 if action == 1 else 0.5
    terminated = self._step_count >= 3
    obs = np.zeros(self.observation_space.shape, dtype=np.float32)
    return obs, reward, terminated, False, {}

  def close(self) -> None:  # pragma: no cover - no resources to release
    pass


def _dummy_env_factory() -> _DummyEnv:
  return _DummyEnv()


def test_a3c_network_shapes() -> None:
  network = A3CNetwork(input_dim=12, action_dim=4)
  sample = torch.zeros(12)
  action_probs, value = network(sample)
  assert action_probs.shape == (1, 4)
  assert value.shape == (1,)
  torch.testing.assert_close(action_probs.sum(), torch.tensor(1.0), rtol=1e-5, atol=1e-6)


def test_compute_gae_matches_expected() -> None:
  rewards = [torch.tensor(1.0), torch.tensor(0.5)]
  values = [torch.tensor(0.2), torch.tensor(0.3)]
  next_value = torch.tensor(0.1)
  dones = [False, True]

  returns, advantages = compute_gae(
    rewards,
    values,
    next_value,
    dones,
    gamma=0.99,
    lam=0.95,
  )

  assert returns.shape == torch.Size([2])
  assert advantages.shape == torch.Size([2])
  # Manual calculation of the expected values
  expected_returns = torch.tensor([1.0 + 0.99 * (0.3 + 0.95 * 0.2), 0.5])
  expected_advantages = expected_returns - torch.tensor([0.2, 0.3])
  torch.testing.assert_close(returns, expected_returns, rtol=1e-5, atol=1e-4)
  torch.testing.assert_close(advantages, expected_advantages, rtol=1e-5, atol=1e-4)


def test_a3c_trainer_runs_with_dummy_environment() -> None:
  config = {
    'total_timesteps': 6,
    'n_steps': 2,
    'learning_rate': 1e-3,
    'num_workers': 1,
  }

  progress: List[Tuple[int, dict]] = []

  trainer = A3CTrainer(_dummy_env_factory, config, device='cpu')
  result = trainer.train(progress_callback=lambda t, m: progress.append((t, m)))

  assert result['status'] == 'completed'
  assert result['total_timesteps'] >= 6
  assert progress, 'progress callback should have been invoked'
  # Ensure the final callback flagged a forced emit
  assert progress[-1][1].get('force_emit') is True


def test_a3c_trainer_handles_multiple_workers() -> None:
  config = {
    'total_timesteps': 8,
    'n_steps': 2,
    'learning_rate': 1e-3,
    'num_workers': 3,
  }

  trainer = A3CTrainer(_dummy_env_factory, config, device='cpu')
  result = trainer.train()

  assert result['status'] == 'completed'
  assert result['total_timesteps'] >= 8


@pytest.mark.asyncio()
async def test_a3c_training_service_supports_custom_env_factory() -> None:
  config = {
    'total_timesteps': 4,
    'n_steps': 2,
    'learning_rate': 5e-4,
    'num_workers': 1,
    'env_factory': _dummy_env_factory,
  }

  service = A3CTrainingService()
  progress: list[int] = []

  result = await service.start_training(
    config=config,
    progress_callback=lambda t, _: progress.append(t),
  )

  assert result['status'] == 'completed'
  assert progress, 'progress callback should have recorded timesteps'
  assert progress[-1] >= 4

