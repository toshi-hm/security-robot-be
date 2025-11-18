"""Utility helpers for lightweight policy evaluation."""

from __future__ import annotations

import random
from statistics import mean
from typing import Any

from rl.environments import get_environment_spec


def evaluate_model(
  model_path: str,
  *,
  environment_id: str = "base",
  episodes: int = 5,
  max_steps: int = 200,
  seed: int | None = None,
) -> dict[str, Any]:
  """Evaluate a trained policy by running rollouts in the registered environment.

  A concrete model integration will be added in later prompts; for now the
  function performs random rollouts to expose environment statistics through
  the API while preserving the interface expected by downstream services.
  """

  spec = get_environment_spec(environment_id)
  env = spec.create()

  rng = random.Random(seed)
  episode_rewards: list[float] = []
  coverage_scores: list[float] = []

  for _ in range(max(1, episodes)):
    reset_seed = rng.randint(0, 2**31 - 1)
    _, _ = env.reset(seed=reset_seed)

    total_reward = 0.0
    terminated = False
    truncated = False
    step_count = 0

    while not terminated and not truncated and step_count < max_steps:
      action = env.action_space.sample()
      _, reward, terminated, truncated, info = env.step(action)
      total_reward += float(reward)
      step_count += 1

    episode_rewards.append(total_reward)

    if hasattr(env, "coverage_history") and env.coverage_history:
      coverage_scores.append(float(env.coverage_history[-1]))

  result: dict[str, Any] = {
    "model_path": model_path,
    "environment_id": environment_id,
    "episodes": len(episode_rewards),
    "average_reward": mean(episode_rewards),
    "episode_rewards": episode_rewards,
  }

  if coverage_scores:
    result["average_coverage_ratio"] = mean(coverage_scores)

  return result
