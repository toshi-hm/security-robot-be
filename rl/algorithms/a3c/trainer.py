"""Coordinator for running the custom A3C training loop."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import numpy as np
import torch

from rl.algorithms.a3c.network import A3CNetwork
from rl.algorithms.a3c.worker import A3CWorker, RolloutResult


class A3CTrainer:
  """High-level trainer that orchestrates workers and aggregates progress."""

  def __init__(
    self,
    env_factory: Callable[[], Any],
    config: dict[str, Any],
    *,
    device: str | torch.device = 'cpu',
  ) -> None:
    self._env_factory = env_factory
    self._config = dict(config)
    self._device = torch.device(device)

    sample_env = env_factory()
    try:
      sample_obs, _ = sample_env.reset()
      observation = np.asarray(sample_obs, dtype=np.float32)
      self._input_dim = int(observation.size)
      self._action_dim = int(getattr(sample_env.action_space, 'n'))
    finally:
      with contextlib.suppress(Exception):
        sample_env.close()

    if self._action_dim <= 0:
      raise ValueError('environment must expose a discrete action space')

    self._total_timesteps_target = max(1, int(self._config.get('total_timesteps', 10000)))
    self._num_workers = max(1, int(self._config.get('num_workers', 1)))
    self._rollout_steps = max(1, int(self._config.get('n_steps', 20)))
    self._gamma = float(self._config.get('gamma', 0.99))
    self._gae_lambda = float(self._config.get('gae_lambda', 0.95))
    self._entropy_coef = float(self._config.get('entropy_coef', 0.01))
    self._value_loss_coef = float(self._config.get('value_loss_coef', 0.5))
    self._max_grad_norm = float(self._config.get('max_grad_norm', 0.5))
    self._learning_rate = float(self._config.get('learning_rate', 3e-4))

    self._global_network = A3CNetwork(self._input_dim, self._action_dim).to(self._device)
    self._optimizer = torch.optim.Adam(self._global_network.parameters(), lr=self._learning_rate)

  def _create_workers(self) -> Iterable[A3CWorker]:
    for worker_id in range(self._num_workers):
      yield A3CWorker(
        worker_id,
        self._env_factory,
        self._global_network,
        self._optimizer,
        device=self._device,
        input_dim=self._input_dim,
        action_dim=self._action_dim,
        rollout_steps=self._rollout_steps,
        gamma=self._gamma,
        gae_lambda=self._gae_lambda,
        entropy_coef=self._entropy_coef,
        value_loss_coef=self._value_loss_coef,
        max_grad_norm=self._max_grad_norm,
      )

  def train(
    self,
    *,
    progress_callback: Optional[Callable[[int, dict[str, Any]], None]] = None,
  ) -> dict[str, Any]:
    """Execute training until the configured timestep target is reached."""

    workers = list(self._create_workers())

    total_timesteps = 0
    episodes = 0
    last_metrics: Optional[RolloutResult] = None

    try:
      while total_timesteps < self._total_timesteps_target:
        for worker in workers:
          result = worker.run()
          if result.timesteps == 0:
            continue

          total_timesteps += result.timesteps
          last_metrics = result
          if result.episode_done:
            episodes += 1

          if progress_callback is not None:
            metrics_payload = {
              'episode': episodes,
              'reward': result.reward,
              'loss': result.loss,
              'additional_metrics': {
                'policy_loss': result.policy_loss,
                'value_loss': result.value_loss,
                'entropy': result.entropy,
              },
            }
            progress_callback(total_timesteps, metrics_payload)

          if total_timesteps >= self._total_timesteps_target:
            break
    finally:
      for worker in workers:
        worker.close()

    if progress_callback is not None and last_metrics is not None:
      metrics_payload = {
        'episode': episodes,
        'reward': last_metrics.reward,
        'loss': last_metrics.loss,
        'additional_metrics': {
          'policy_loss': last_metrics.policy_loss,
          'value_loss': last_metrics.value_loss,
          'entropy': last_metrics.entropy,
        },
        'force_emit': True,
      }
      progress_callback(total_timesteps, metrics_payload)

    model_path = self._config.get('model_path')
    if model_path:
      path = Path(model_path)
      path.parent.mkdir(parents=True, exist_ok=True)
      torch.save(self._global_network.state_dict(), path)

    result_payload: dict[str, Any] = {
      'status': 'completed',
      'algorithm': 'a3c',
      'total_timesteps': total_timesteps,
      'episodes_completed': episodes,
    }

    if model_path:
      result_payload['model_path'] = model_path
    if last_metrics is not None:
      result_payload['loss'] = last_metrics.loss
      result_payload['policy_loss'] = last_metrics.policy_loss
      result_payload['value_loss'] = last_metrics.value_loss
      result_payload['entropy'] = last_metrics.entropy

    return result_payload

