"""Enhanced security patrol environment with advanced reward shaping."""

from __future__ import annotations

import math
import logging
import json
from typing import Any, Literal
import gymnasium as gym
import numpy as np

import numpy as np

from rl.environments.map_generator import MapType

from .security_env import SecurityEnvironment


logger = logging.getLogger(__name__)

class EnhancedSecurityEnvironment(SecurityEnvironment):
  """Extended environment optimised for coverage, exploration, and diversity."""

  def __init__(
    self,
    width: int = 20,
    height: int = 20,
    robot_vision_range: int = 2,
    num_robots: int = 1,
    enable_logging: bool = False,
    coverage_weight: float = 1.0,
    exploration_weight: float = 2.0,
    diversity_weight: float = 1.5,
    threat_penalty_weight: float = 0.0,
    battery_drain_rate: float = 0.001,
    map_type: MapType = "random",
    reward_normalization_mode: Literal["mean", "sum", "sqrt_mean"] = "mean",
    **map_config: Any,
  ) -> None:
    self.coverage_weight = coverage_weight
    self.exploration_weight = exploration_weight
    self.diversity_weight = diversity_weight
    self.threat_penalty_weight = threat_penalty_weight
    self.reward_normalization_mode = reward_normalization_mode

    super().__init__(
      width=width,
      height=height,
      robot_vision_range=robot_vision_range,
      num_robots=num_robots,
      enable_logging=enable_logging,
      map_type=map_type,
      reward_normalization_mode=reward_normalization_mode,
      **map_config,
    )
    self._init_tracking_structures()

    # Override battery drain rate
    self.battery_drain_rate = battery_drain_rate
    self.episode_start_positions = []

  def reset(
    self,
    *,
    seed: int | None = None,
    options: dict | None = None,
  ) -> tuple[np.ndarray, dict]:
    observation, info = super().reset(seed=seed, options=options)
    # Capture starting positions for analysis
    self.episode_start_positions = list(self.robot_positions)
    
    self._init_tracking_structures()

    self._mark_current_position()
    return observation, info

  def step(self, actions: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
    observation, base_reward, terminated, truncated, info = super().step(actions)

    self._update_exploration_state()

    total_cells = self.width * self.height
    visited_count = len(self.visited_cells)
    coverage_ratio = visited_count / total_cells if total_cells else 0.0

    # Calculate enhanced reward for each robot and sum them up?
    # Or calculate globally?
    # The original code calculated based on single action.
    # Now we have multiple actions.
    # Let's calculate based on the collective result.

    # Calculate additional rewards
    # Split into Global (shared) and Per-Robot (individual) rewards

    # Global Rewards: Team-wide achievements normalized by number of robots
    # to maintain consistent reward scale across different team sizes
    global_reward = 0.0
    global_reward += self._calculate_coverage_reward(coverage_ratio) * self.coverage_weight
    global_reward += self._calculate_total_diversity_reward() * self.diversity_weight

    # Threat Penalty Reward (Maintenance)
    # Deduct reward proportional to average threat level
    # This incentivizes keeping the map generally clean (low threat)
    avg_threat = info.get("average_threat_level", 0.0)
    global_reward -= avg_threat * self.threat_penalty_weight

    # Normalize global rewards to maintain scale consistency
    if self.reward_normalization_mode == "sum":
      pass
    elif self.reward_normalization_mode == "sqrt_mean":
      global_reward /= math.sqrt(self.num_robots)
    else:  # "mean"
      global_reward /= self.num_robots

    # Per-Robot Rewards: Calculated per robot, then averaged
    per_robot_reward_sum = 0.0
    for i in range(self.num_robots):
      action = actions[i]
      per_robot_reward_sum += self._calculate_exploration_reward(i) * self.exploration_weight
      per_robot_reward_sum += self._calculate_movement_reward(i, action)
      per_robot_reward_sum += self._calculate_patrol_optimization_reward(i, action)

    # Normalize per-robot reward sum by number of robots to get average per-robot reward
    if self.reward_normalization_mode == "sum":
      average_per_robot_reward = per_robot_reward_sum
    elif self.reward_normalization_mode == "sqrt_mean":
      average_per_robot_reward = per_robot_reward_sum / math.sqrt(self.num_robots)
    else:  # "mean"
      average_per_robot_reward = per_robot_reward_sum / self.num_robots

    # Total Enhanced Reward = Base (already normalized) + Avg Per-Robot + Normalized Global
    # All components are now normalized by num_robots for consistent scale
    enhanced_reward = base_reward + average_per_robot_reward + global_reward

    info.update(
      {
        "coverage_ratio": coverage_ratio,
        "visited_cells": visited_count,
        "exploration_reward_bonus": average_per_robot_reward + global_reward,
        "exploration_score": float(visited_count),
      }
    )

    self.coverage_history.append(coverage_ratio)

    if terminated or truncated:
        self._log_episode_result(enhanced_reward, info)

    return observation, enhanced_reward, terminated, truncated, info

  def _log_episode_result(self, final_reward: float, info: dict) -> None:
      """Log episode results for analysis of optimal start positions."""
      try:
          result = {
              "start_positions": self.episode_start_positions,
              "final_reward": float(final_reward),
              "coverage": float(info.get("coverage_ratio", 0.0)),
              "avg_threat": float(info.get("average_threat_level", 0.0)),
              "steps": self.time_step
          }
          # Use a special prefix for easy grepping
          logger.info(f"EPISODE_RESULT: {json.dumps(result)}")
      except Exception as e:
          logger.error(f"Failed to log episode result: {e}")


  # ------------------------------------------------------------------
  # Tracking helpers
  # ------------------------------------------------------------------

  def _init_tracking_structures(self) -> None:
    # self.visited_cells is handled by base class (set)
    # Grid indexing: grid[y][x] (row-major)
    self.visit_count = [[0 for _ in range(self.width)] for _ in range(self.height)]
    self.last_visited = [[-1 for _ in range(self.width)] for _ in range(self.height)]
    # Track recent positions for EACH robot
    self.recent_positions: list[list[tuple[int, int]]] = [[] for _ in range(self.num_robots)]
    self.position_history_length = 10
    self.coverage_history: list[float] = []

  def _mark_current_position(self) -> None:
    for i in range(self.num_robots):
      x, y = self.robot_positions[i]
      # visited_cells is already updated in base.reset -> but base.reset calls
      # _place_charging_station
      # and sets robot positions.
      # base.reset adds start pos to visited_cells.
      self.visit_count[y][x] = 1
      self.last_visited[y][x] = self.time_step
      self.recent_positions[i] = [(x, y)]

  def _update_exploration_state(self) -> None:
    for i in range(self.num_robots):
      x, y = self.robot_positions[i]
      # visited_cells updated in base.step
      self.visit_count[y][x] += 1
      self.last_visited[y][x] = self.time_step
      self.recent_positions[i].append((x, y))
      if len(self.recent_positions[i]) > self.position_history_length:
        self.recent_positions[i].pop(0)

  # ------------------------------------------------------------------
  # Reward shaping
  # ------------------------------------------------------------------

  # _calculate_enhanced_reward removed/inlined into step

  def _calculate_exploration_reward(self, robot_idx: int) -> float:
    x, y = self.robot_positions[robot_idx]
    visits = self.visit_count[y][x]
    if visits == 1:
      return 5.0
    if visits <= 3:
      return 1.0 / visits
    return -0.5

  def _calculate_coverage_reward(self, coverage_ratio: float) -> float:
    if not self.coverage_history:
      return 0.0

    previous_coverage = self.coverage_history[-1]
    improvement = coverage_ratio - previous_coverage
    if improvement > 0:
      return improvement * 20.0
    return 0.0

  def _calculate_total_diversity_reward(self) -> float:
    """
    Calculate diversity reward based on the diversity of visited locations.

    This calculates the total diversity score across all robots. Each robot's
    position history is evaluated for diversity (how many unique positions vs total),
    and the total diversity reward is returned. The caller will normalize this
    by num_robots along with other global rewards.
    """
    # Calculate average diversity across all robots
    total_diversity_reward = 0.0
    active_robots = 0

    for i in range(self.num_robots):
      history = self.recent_positions[i]
      if not history:
        continue

      active_robots += 1
      unique_positions = len(set(history))
      diversity_ratio = unique_positions / len(history)

      reward = 0.0
      if diversity_ratio > 0.8:
        reward = 2.0
      elif diversity_ratio > 0.6:
        reward = 1.0
      elif diversity_ratio < 0.3:
        reward = -1.0

      total_diversity_reward += reward

    # Return sum (will be normalized by num_robots in step())
    return total_diversity_reward

  def _calculate_movement_reward(self, robot_idx: int, action: int) -> float:
    if action != 0:
      return 0.0

    front_x, front_y = self._get_front_position(robot_idx)
    if not self._is_valid_position(front_x, front_y):
      return 0.0

    if (front_x, front_y) not in self.visited_cells:
      return 1.0
    if self.visit_count[front_y][front_x] < 3:
      return 0.5
    return 0.0

  def _calculate_patrol_optimization_reward(self, robot_idx: int, action: int) -> float:
    if action != 3:
      return 0.0

    unexplored_in_range = 0
    rx, ry = self.robot_positions[robot_idx]
    for dx in range(-self.robot_vision_range, self.robot_vision_range + 1):
      for dy in range(-self.robot_vision_range, self.robot_vision_range + 1):
        x, y = rx + dx, ry + dy
        if self._is_valid_position(x, y) and (x, y) not in self.visited_cells:
          unexplored_in_range += 1

    if unexplored_in_range > 0:
      return unexplored_in_range * 0.5
    return 0.0
