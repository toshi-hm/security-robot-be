"""Wrapper to enable RL-based placement selection at episode start.

This wrapper implements a two-phase episode structure:
1. Placement Phase: Agent selects initial position (action modulo grid_size = cell index)
2. Patrol Phase: Standard patrol actions (action modulo 4)

The wrapper uses a SINGLE action space (Discrete(width*height)) throughout
to maintain compatibility with SB3. Actions are interpreted differently
based on the current phase.
"""

from __future__ import annotations

from typing import Any, SupportsFloat

import gymnasium as gym
from gymnasium import spaces
import numpy as np


class PlacementLearningWrapper(gym.Wrapper):
  """Gym wrapper that adds a placement selection phase at episode start.

  Uses a unified action space throughout (Discrete(width*height)):
  - During placement: action directly selects a grid cell
  - During patrol: action modulo 4 selects patrol action (0-3)

  This design ensures compatibility with Stable-Baselines3 which requires
  a fixed action space throughout training.
  """

  def __init__(self, env: gym.Env) -> None:
    super().__init__(env)
    self.width: int = env.unwrapped.width  # type: ignore[attr-defined]
    self.height: int = env.unwrapped.height  # type: ignore[attr-defined]
    self.num_robots: int = getattr(env.unwrapped, "num_robots", 1)
    self.grid_size = self.width * self.height

    # Use a single unified action space for SB3 compatibility
    # During placement: action = grid cell index (0 to grid_size-1)
    # During patrol: action modulo 4 = patrol action (0-3)
    self.action_space = spaces.Discrete(self.grid_size)

    self._placement_phase = True

  def reset(
    self,
    *,
    seed: int | None = None,
    options: dict[str, Any] | None = None,
  ) -> tuple[Any, dict[str, Any]]:
    """Reset environment and enter placement phase."""
    obs, info = self.env.reset(seed=seed, options=options)
    self._placement_phase = True
    info["placement_phase"] = True
    return obs, info

  def step(self, action: int | np.ndarray) -> tuple[Any, SupportsFloat, bool, bool, dict[str, Any]]:
    """Execute action based on current phase."""
    if isinstance(action, np.ndarray):
      action = int(action.item()) if action.size == 1 else int(action[0])

    if self._placement_phase:
      return self._handle_placement_action(action)
    else:
      return self._handle_patrol_action(action)

  def _handle_placement_action(self, action: int) -> tuple[Any, float, bool, bool, dict[str, Any]]:
    """Process placement action and transition to patrol phase."""
    # Convert action to grid coordinates
    action = action % self.grid_size  # Safety: ensure valid range

    x = action % self.width
    y = action // self.width

    # Validate position
    env = self.env.unwrapped
    if not env._is_valid_position(x, y):  # type: ignore[attr-defined]
      # Invalid position: find nearest valid position
      x, y = self._find_nearest_valid_position(x, y)

    # Set robot position(s)
    env.robot_positions[0] = (x, y)  # type: ignore[attr-defined]

    # Update charging station to match (robot starts at charging station)
    if hasattr(env, "charging_stations") and env.charging_stations:
      env.charging_stations[0] = (x, y)

    # Update visited cells
    env.visited_cells = {(x, y)}  # type: ignore[attr-defined]
    if hasattr(env, "visit_history_map"):
      env.visit_history_map[y][x] = 0.0

    # Capture placement for logging
    if hasattr(env, "episode_start_positions"):
      env.episode_start_positions = [(x, y)]

    # Transition to patrol phase
    self._placement_phase = False

    # Return observation without taking a patrol step
    obs = env._get_observation()  # type: ignore[attr-defined]
    info = env._get_info()  # type: ignore[attr-defined]
    info["placement_phase"] = False
    info["selected_position"] = (x, y)

    # Placement reward: 0 (neutral) - learning comes from episode outcome
    return obs, 0.0, False, False, info

  def _handle_patrol_action(
    self, action: int
  ) -> tuple[Any, SupportsFloat, bool, bool, dict[str, Any]]:
    """Process patrol action by mapping from unified action space."""
    # Map from unified action space to patrol action (0-3)
    patrol_action = action % 4

    # Convert to array for multi-robot compatibility
    if self.num_robots == 1:
      actions = np.array([patrol_action], dtype=np.int32)
    else:
      actions = np.array([patrol_action] * self.num_robots, dtype=np.int32)

    obs, reward, terminated, truncated, info = self.env.step(actions)
    info["placement_phase"] = False

    return obs, reward, terminated, truncated, info

  def _find_nearest_valid_position(self, x: int, y: int) -> tuple[int, int]:
    """Find nearest valid position to the requested coordinates."""
    env = self.env.unwrapped

    # Search in expanding squares
    for radius in range(1, max(self.width, self.height)):
      for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
          if abs(dx) == radius or abs(dy) == radius:
            nx, ny = x + dx, y + dy
            if env._is_valid_position(nx, ny):  # type: ignore[attr-defined]
              return (nx, ny)

    # Fallback: center of grid
    return (self.width // 2, self.height // 2)
