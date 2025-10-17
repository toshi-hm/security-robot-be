"""Coordinator for running the custom A3C training loop."""

from __future__ import annotations

import contextlib
import logging
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Iterable, Optional

import numpy as np
import torch

from app.core.config import settings
from rl.algorithms.a3c.network import A3CNetwork
from rl.algorithms.a3c.worker import A3CWorker, RolloutResult


DEFAULT_MAX_WORKERS = 16


logger = logging.getLogger(__name__)


def _resolve_max_workers() -> int:
  value = getattr(settings, 'max_a3c_workers', DEFAULT_MAX_WORKERS)
  try:
    max_workers = int(value)
  except (TypeError, ValueError):
    logger.warning(
      'Invalid max_a3c_workers value %r; falling back to default of %s',
      value,
      DEFAULT_MAX_WORKERS,
    )
    return DEFAULT_MAX_WORKERS
  if max_workers < 1:
    logger.warning(
      'Configured max_a3c_workers %s is less than 1; using default of %s',
      max_workers,
      DEFAULT_MAX_WORKERS,
    )
    return DEFAULT_MAX_WORKERS
  return max_workers


MAX_WORKERS = _resolve_max_workers()


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
    workers_config = self._config.get('num_workers', 1)
    try:
      requested_workers = int(workers_config)
    except (TypeError, ValueError) as exc:
      raise ValueError('num_workers must be an integer value') from exc
    if requested_workers < 1:
      raise ValueError('num_workers must be a positive integer')
    if requested_workers > MAX_WORKERS:
      raise ValueError(f'num_workers must not exceed {MAX_WORKERS}')
    if self._device.type == 'cuda' and requested_workers > 1:
      raise ValueError(
        'A3C training with multiple workers is not supported on CUDA devices. '
        'Set num_workers=1 when using CUDA or switch to CPU execution for '
        'multi-worker training.'
      )
    self._num_workers = requested_workers
    self._rollout_steps = max(1, int(self._config.get('n_steps', 20)))
    self._gamma = float(self._config.get('gamma', 0.99))
    self._gae_lambda = float(self._config.get('gae_lambda', 0.95))
    self._entropy_coef = float(self._config.get('entropy_coef', 0.01))
    self._value_loss_coef = float(self._config.get('value_loss_coef', 0.5))
    self._max_grad_norm = float(self._config.get('max_grad_norm', 0.5))
    self._learning_rate = float(self._config.get('learning_rate', 3e-4))

    self._global_network = A3CNetwork(self._input_dim, self._action_dim).to(self._device)
    self._optimizer = torch.optim.Adam(self._global_network.parameters(), lr=self._learning_rate)
    self._grad_lock = Lock()
    self._metrics_lock = Lock()

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
        grad_lock=self._grad_lock,
      )

  def train(
    self,
    *,
    progress_callback: Optional[Callable[[int, dict[str, Any]], None]] = None,
    stop_signal: Optional[Callable[[], bool]] = None,
  ) -> dict[str, Any]:
    """Execute training until the configured timestep target is reached."""

    workers = list(self._create_workers())

    total_timesteps = 0
    episodes = 0
    last_metrics: Optional[RolloutResult] = None

    futures: dict[Future[RolloutResult], A3CWorker] = {}

    external_stop_requested = False

    try:
      with ThreadPoolExecutor(max_workers=self._num_workers) as executor:
        def _schedule(worker: A3CWorker) -> None:
          future = executor.submit(worker.run)
          futures[future] = worker

        for worker in workers:
          _schedule(worker)

        stop_requested = False

        while futures:
          done, _ = wait(set(futures.keys()), return_when=FIRST_COMPLETED)
          for future in done:
            worker = futures.pop(future)
            try:
              result = future.result()
            except Exception:
              for pending in futures:
                pending.cancel()
              raise

            if result.timesteps == 0:
              if not stop_requested:
                _schedule(worker)
              continue

            if stop_requested:
              continue

            with self._metrics_lock:
              total_timesteps += result.timesteps
              last_metrics = result
              if result.episode_done:
                episodes += 1
              current_timesteps = total_timesteps
              current_episode = episodes
            if progress_callback is not None:
              metrics_payload = {
                'episode': current_episode,
                'reward': result.reward,
                'loss': result.loss,
                'additional_metrics': {
                  'policy_loss': result.policy_loss,
                  'value_loss': result.value_loss,
                  'entropy': result.entropy,
                },
              }
              progress_callback(current_timesteps, metrics_payload)

            reached_target = current_timesteps >= self._total_timesteps_target
            external_stop_triggered = False
            if not reached_target and stop_signal is not None:
              try:
                external_stop_triggered = bool(stop_signal())
              except Exception:
                logger.exception('stop_signal callable raised unexpectedly')

            if reached_target:
              stop_requested = True
            elif external_stop_triggered:
              stop_requested = True
              external_stop_requested = True

            if not stop_requested:
              _schedule(worker)
    finally:
      for worker in workers:
        worker.close()

    with self._metrics_lock:
      final_timesteps = total_timesteps
      final_episodes = episodes
      final_metrics = last_metrics

    if progress_callback is not None and final_metrics is not None:
      metrics_payload = {
        'episode': final_episodes,
        'reward': final_metrics.reward,
        'loss': final_metrics.loss,
        'additional_metrics': {
          'policy_loss': final_metrics.policy_loss,
          'value_loss': final_metrics.value_loss,
          'entropy': final_metrics.entropy,
        },
        'force_emit': True,
      }
      progress_callback(final_timesteps, metrics_payload)

    model_path = self._config.get('model_path')
    if model_path:
      path = Path(model_path)
      path.parent.mkdir(parents=True, exist_ok=True)
      torch.save(self._global_network.state_dict(), path)

    result_status = 'paused' if external_stop_requested else 'completed'
    result_payload: dict[str, Any] = {
      'status': result_status,
      'algorithm': 'a3c',
      'total_timesteps': final_timesteps,
      'episodes_completed': final_episodes,
    }

    if model_path:
      result_payload['model_path'] = model_path
    if final_metrics is not None:
      result_payload['loss'] = final_metrics.loss
      result_payload['policy_loss'] = final_metrics.policy_loss
      result_payload['value_loss'] = final_metrics.value_loss
      result_payload['entropy'] = final_metrics.entropy

    if external_stop_requested:
      result_payload['stop_reason'] = 'pause_requested'

    return result_payload

