"""Worker utilities for the custom A3C trainer."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical

from rl.algorithms.a3c.network import A3CNetwork

logger = logging.getLogger(__name__)

Tensor = torch.Tensor


def _to_tensor(array: np.ndarray | Tensor, *, device: torch.device) -> Tensor:
  if isinstance(array, Tensor):
    return array.to(device)
  return torch.as_tensor(array, dtype=torch.float32, device=device)


def compute_gae(
  rewards: list[Tensor],
  values: list[Tensor],
  next_value: Tensor,
  dones: list[bool],
  *,
  gamma: float,
  lam: float,
) -> tuple[Tensor, Tensor]:
  """Compute Generalised Advantage Estimation (GAE) for a rollout."""

  if not rewards:
    raise ValueError('rewards must contain at least one element')

  device = rewards[0].device

  def _as_row(tensor: Tensor) -> Tensor:
    if tensor.device != device:
      tensor = tensor.to(device)
    return tensor.squeeze().unsqueeze(0)

  values_tensor = torch.cat([
    _as_row(value) for value in values
  ] + [_as_row(next_value)])
  rewards_tensor = torch.cat([_as_row(reward) for reward in rewards])

  advantages: list[Tensor] = []
  gae = torch.zeros(1, device=device)

  for step in reversed(range(len(rewards))):
    mask = 0.0 if dones[step] else 1.0
    delta = rewards_tensor[step] + gamma * values_tensor[step + 1] * mask - values_tensor[step]
    gae = delta + gamma * lam * mask * gae
    advantages.append(gae.clone())

  advantages.reverse()
  advantages_tensor = torch.cat([_as_row(adv) for adv in advantages])
  returns_tensor = advantages_tensor + values_tensor[:-1]
  return returns_tensor, advantages_tensor


@dataclass
class RolloutResult:
  timesteps: int
  reward: float
  loss: float
  policy_loss: float
  value_loss: float
  entropy: float
  episode_done: bool


class A3CWorker:
  """Single worker that performs on-policy rollouts and applies gradient updates."""

  def __init__(
    self,
    worker_id: int,
    env_factory: Callable[[], Any],
    global_network: A3CNetwork,
    optimizer: torch.optim.Optimizer,
    *,
    device: torch.device,
    input_dim: int,
    action_dim: int,
    rollout_steps: int = 20,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    entropy_coef: float = 0.01,
    value_loss_coef: float = 0.5,
    max_grad_norm: float = 0.5,
    grad_lock: Lock | None = None,
  ) -> None:
    self.worker_id = worker_id
    self._env_factory = env_factory
    self._env: Any | None = None
    try:
      self._env = env_factory()
      self._state, _ = self._env.reset()
    except Exception:
      if self._env is not None:
        with contextlib.suppress(Exception):
          self._env.close()
      raise
    self._global_network = global_network
    self._optimizer = optimizer
    self._device = device

    self._local_network = A3CNetwork(input_dim, action_dim).to(device)
    self._local_network.load_state_dict(self._global_network.state_dict())

    self._rollout_steps = max(1, rollout_steps)
    self._gamma = gamma
    self._gae_lambda = gae_lambda
    self._entropy_coef = entropy_coef
    self._value_loss_coef = value_loss_coef
    self._max_grad_norm = max_grad_norm
    self._grad_lock = grad_lock
    self._episode_done = False

  def close(self) -> None:
    if self._env is None:
      return
    try:
      self._env.close()
    except Exception as exc:  # pragma: no cover - defensive cleanup
      logger.warning('Worker %d failed to close environment: %s', self.worker_id, exc)

  def run(self) -> RolloutResult:
    """Execute a single rollout and update the shared global network."""

    self._local_network.load_state_dict(self._global_network.state_dict())
    self._local_network.train()
    self._episode_done = False

    states: list[Tensor] = []
    actions: list[Tensor] = []
    rewards: list[Tensor] = []
    values: list[Tensor] = []
    dones: list[bool] = []

    episode_reward = 0.0
    timesteps = 0

    for _ in range(self._rollout_steps):
      state_tensor = _to_tensor(np.asarray(self._state), device=self._device).flatten()
      action_probs, value = self._local_network(state_tensor.unsqueeze(0))
      dist = Categorical(probs=action_probs.squeeze(0))
      action = dist.sample()

      next_state, reward, terminated, truncated, _ = self._env.step(int(action.item()))
      done = bool(terminated or truncated)

      states.append(state_tensor)
      actions.append(action)
      rewards.append(torch.tensor(reward, dtype=torch.float32, device=self._device))
      values.append(value.squeeze(0))
      dones.append(done)

      episode_reward += float(reward)
      timesteps += 1

      self._state = next_state
      if done:
        self._state, _ = self._env.reset()
        self._episode_done = True
        break

    if not states:
      return RolloutResult(0, 0.0, 0.0, 0.0, 0.0, 0.0, False)

    with torch.no_grad():
      if dones[-1]:
        next_value = torch.zeros(1, device=self._device)
      else:
        next_state_tensor = _to_tensor(np.asarray(self._state), device=self._device).flatten()
        _, next_value = self._local_network(next_state_tensor.unsqueeze(0))
        next_value = next_value.squeeze(0)

    returns, advantages = compute_gae(
      rewards,
      values,
      next_value,
      dones,
      gamma=self._gamma,
      lam=self._gae_lambda,
    )

    stacked_states = torch.stack(states).to(self._device)
    stacked_actions = torch.stack(actions).to(self._device)
    stacked_returns = returns.to(self._device)
    stacked_advantages = advantages.to(self._device)

    action_probs, value_predictions = self._local_network(stacked_states)
    dist = Categorical(probs=action_probs)
    log_probs = dist.log_prob(stacked_actions)
    entropy = dist.entropy()

    policy_loss = -(log_probs * stacked_advantages.detach()).sum()
    value_loss = nn.functional.mse_loss(value_predictions, stacked_returns.detach())
    loss = policy_loss + self._value_loss_coef * value_loss - self._entropy_coef * entropy.sum()

    loss.backward()
    torch.nn.utils.clip_grad_norm_(self._local_network.parameters(), self._max_grad_norm)

    def _apply_gradients() -> None:
      self._optimizer.zero_grad()
      with torch.no_grad():
        for global_param, local_param in zip(
          self._global_network.parameters(),
          self._local_network.parameters(),
          strict=True,
        ):
          if local_param.grad is None:
            global_param.grad = torch.zeros_like(global_param)
          else:
            global_param.grad = local_param.grad.detach().clone()

      self._optimizer.step()

    if self._grad_lock is None:
      _apply_gradients()
    else:
      with self._grad_lock:
        _apply_gradients()
    self._local_network.load_state_dict(self._global_network.state_dict())

    return RolloutResult(
      timesteps=timesteps,
      reward=episode_reward,
      loss=float(loss.item()),
      policy_loss=float(policy_loss.item()),
      value_loss=float(value_loss.item()),
      entropy=float(entropy.mean().item()),
      episode_done=self._episode_done,
    )

