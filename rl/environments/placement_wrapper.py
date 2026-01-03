"""Wrapper to enable RL-based placement selection at episode start.

This wrapper implements a two-phase episode structure:
1. Placement Phase: Agent selects initial position (action = grid index)
2. Patrol Phase: Standard patrol actions (0-3)

The wrapper handles the phase transition automatically.
"""

from __future__ import annotations

from typing import Any, SupportsFloat

import gymnasium as gym
from gymnasium import spaces
import numpy as np


class PlacementLearningWrapper(gym.Wrapper):
  """Gym wrapper that adds a placement selection phase at episode start.

  In placement phase:
    - Action space: Discrete(width * height) - grid cell selection
    - Agent selects starting position

  After placement:
    - Action space: Discrete(4) - standard patrol actions
    - Normal patrol episode continues

  The observation is augmented with a placement_phase indicator in the info dict.
  """

  def __init__(self, env: gym.Env) -> None:
    super().__init__(env)
    self.width: int = env.unwrapped.width  # type: ignore[attr-defined]
    self.height: int = env.unwrapped.height  # type: ignore[attr-defined]
    self.num_robots: int = getattr(env.unwrapped, "num_robots", 1)

    # Placement phase action space: select grid cell
    self.placement_action_space = spaces.Discrete(self.width * self.height)
    # Patrol phase action space: standard 4 actions per robot
    self.patrol_action_space = env.action_space

    # Combined action space for SB3 compatibility
    # During placement: action < width*height means placement
    # During patrol: action >= width*height is shifted to patrol action
    # Actually, simpler approach: use placement action space only at step 0
    self._placement_phase = True

    # Override action space to be the larger one (placement)
    # SB3 will see this as the action space
    self.action_space = self.placement_action_space

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
    grid_size = self.width * self.height
    action = action % grid_size  # Safety: ensure valid range

    x = action % self.width
    y = action // self.width

    # Validate position
    env = self.env.unwrapped
    if not env._is_valid_position(x, y):  # type: ignore[attr-defined]
      # Invalid position: find nearest valid position
      x, y = self._find_nearest_valid_position(x, y)

    # Set robot position(s)
    # For single agent, set position directly
    # For multi-agent, this sets the first robot (can be extended later)
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

    # Change action space for subsequent steps
    self.action_space = self.patrol_action_space

    # Return observation without taking a patrol step
    # Give small positive reward for successful placement
    obs = env._get_observation()  # type: ignore[attr-defined]
    info = env._get_info()  # type: ignore[attr-defined]
    info["placement_phase"] = False
    info["selected_position"] = (x, y)

    # Placement reward: 0 (neutral) - learning comes from episode outcome
    return obs, 0.0, False, False, info

  def _handle_patrol_action(
    self, action: int
  ) -> tuple[Any, SupportsFloat, bool, bool, dict[str, Any]]:
    """Process standard patrol action."""
    # Convert single action to array for multi-robot compatibility
    if self.num_robots == 1:
      actions = np.array([action], dtype=np.int32)
    else:
      # For multi-robot, replicate action (simplified)
      actions = np.array([action] * self.num_robots, dtype=np.int32)

    obs, reward, terminated, truncated, info = self.env.step(actions)
    info["placement_phase"] = False

    # Reset action space back to placement for next episode
    if terminated or truncated:
      self.action_space = self.placement_action_space

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
