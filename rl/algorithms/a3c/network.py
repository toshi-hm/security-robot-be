"""Neural network modules used by the custom A3C implementation."""

from __future__ import annotations

from typing import Tuple

import torch
from torch import nn


class A3CNetwork(nn.Module):
  """Shared actor-critic network with independent policy and value heads."""

  def __init__(self, input_dim: int, action_dim: int) -> None:
    super().__init__()

    if input_dim <= 0:
      raise ValueError('input_dim must be positive')
    if action_dim <= 0:
      raise ValueError('action_dim must be positive')

    self.feature = nn.Sequential(
      nn.Linear(input_dim, 128),
      nn.ReLU(),
      nn.Linear(128, 128),
      nn.ReLU(),
    )

    self.actor = nn.Sequential(
      nn.Linear(128, 64),
      nn.ReLU(),
      nn.Linear(64, action_dim),
      nn.Softmax(dim=-1),
    )

    self.critic = nn.Sequential(
      nn.Linear(128, 64),
      nn.ReLU(),
      nn.Linear(64, 1),
    )

  def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    """Return action probabilities and the estimated state-value."""

    if x.dim() == 1:
      x = x.unsqueeze(0)

    features = self.feature(x)
    action_probs = self.actor(features)
    state_values = self.critic(features).squeeze(-1)
    return action_probs, state_values

