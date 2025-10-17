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


def _manual_gae(
  rewards: list[float],
  values: list[float],
  next_value: float,
  dones: list[bool],
  *,
  gamma: float,
  lam: float,
) -> tuple[torch.Tensor, torch.Tensor]:
  values_sequence = values + [next_value]
  advantages: list[float] = []
  gae = 0.0
  for idx in reversed(range(len(rewards))):
    mask = 0.0 if dones[idx] else 1.0
    delta = rewards[idx] + gamma * values_sequence[idx + 1] * mask - values_sequence[idx]
    gae = delta + gamma * lam * mask * gae
    advantages.append(gae)
  advantages.reverse()
  advantages_tensor = torch.tensor(advantages, dtype=torch.float32)
  returns_tensor = advantages_tensor + torch.tensor(values, dtype=torch.float32)
  return returns_tensor, advantages_tensor


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

  manual_returns, manual_advantages = _manual_gae(
    [reward.item() for reward in rewards],
    [value.item() for value in values],
    float(next_value.item()),
    dones,
    gamma=0.99,
    lam=0.95,
  )

  assert returns.shape == torch.Size([2])
  assert advantages.shape == torch.Size([2])
  torch.testing.assert_close(returns, manual_returns, rtol=1e-5, atol=1e-4)
  torch.testing.assert_close(advantages, manual_advantages, rtol=1e-5, atol=1e-4)


def test_compute_gae_handles_longer_rollouts() -> None:
  rewards = [torch.tensor(1.0), torch.tensor(0.5), torch.tensor(0.2)]
  values = [torch.tensor(0.2), torch.tensor(0.3), torch.tensor(0.25)]
  next_value = torch.tensor(0.1)
  dones = [False, False, True]

  returns, advantages = compute_gae(
    rewards,
    values,
    next_value,
    dones,
    gamma=0.99,
    lam=0.95,
  )

  manual_returns, manual_advantages = _manual_gae(
    [reward.item() for reward in rewards],
    [value.item() for value in values],
    float(next_value.item()),
    dones,
    gamma=0.99,
    lam=0.95,
  )

  assert returns.shape == torch.Size([3])
  assert advantages.shape == torch.Size([3])
  torch.testing.assert_close(returns, manual_returns, rtol=1e-5, atol=1e-4)
  torch.testing.assert_close(advantages, manual_advantages, rtol=1e-5, atol=1e-4)


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


@pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA not available')
def test_a3c_trainer_rejects_multi_worker_cuda_configuration() -> None:
  config = {
    'total_timesteps': 4,
    'n_steps': 2,
    'learning_rate': 1e-3,
    'num_workers': 2,
  }

  with pytest.raises(ValueError, match='multiple workers is not supported on CUDA devices'):
    A3CTrainer(_dummy_env_factory, config, device='cuda')


def test_a3c_trainer_respects_stop_signal() -> None:
  config = {
    'total_timesteps': 100,
    'n_steps': 2,
    'learning_rate': 1e-3,
    'num_workers': 1,
  }

  stop_calls = 0

  def _stop_signal() -> bool:
    nonlocal stop_calls
    stop_calls += 1
    return stop_calls >= 2

  trainer = A3CTrainer(_dummy_env_factory, config, device='cpu')
  result = trainer.train(stop_signal=_stop_signal)

  assert result['status'] == 'paused'
  assert result['stop_reason'] == 'pause_requested'
  assert result['total_timesteps'] < config['total_timesteps']


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

