"""Enhanced security patrol environment with advanced reward shaping."""

from __future__ import annotations

import json
import logging
import math
import random
from typing import Any, Literal

import numpy as np

from rl.environments.map_generator import MapType

from .security_env import SecurityEnvironment

logger = logging.getLogger(__name__)

# Optimal start positions are now passed via config or generated dynamically


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
    episode_log_file: str | None = None,
    strategic_init_mode: bool = False,
    optimal_start_positions: list[tuple[int, int]] | None = None,
    map_type: MapType = "random",
    reward_normalization_mode: Literal["mean", "sum", "sqrt_mean"] = "mean",
    **map_config: Any,
  ) -> None:
    self.coverage_weight = coverage_weight
    self.exploration_weight = exploration_weight
    self.diversity_weight = diversity_weight
    self.threat_penalty_weight = threat_penalty_weight
    self.reward_normalization_mode = reward_normalization_mode

    # Must set this before super().__init__ because it calls reset()
    self.strategic_init_mode = strategic_init_mode
    self.optimal_start_positions = optimal_start_positions or []
    self.episode_start_positions: list[Any] = []

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

    # Override battery drain rate (must be AFTER super init or it gets reset to 0.001)
    self.battery_drain_rate = battery_drain_rate
    self.episode_log_file = episode_log_file
    self.episode_cumulative_reward = 0.0

    # DEBUG PRINT
    print(
      f"DEBUG: EnhancedEnv Initialized with BatteryDrain={self.battery_drain_rate}, "
      f"ThreatPenalty={self.threat_penalty_weight}"
    )

  def reset(
    self,
    *,
    seed: int | None = None,
    options: dict | None = None,
  ) -> tuple[np.ndarray, dict]:
    # Check if there was a previous episode to log
    if hasattr(self, "time_step") and self.time_step > 0:
      # Calculate final metrics for the previous episode
      total_cells = self.width * self.height
      visited_count = len(self.visited_cells)
      coverage_ratio = visited_count / total_cells if total_cells else 0.0

      # Note: obtaining final_reward is tricky here because reset() doesn't return it.
      # But we can log the coverage and threat, which are most important for analysis.
      # For reward, we might need to track cumulative reward in the env.
      info = {
        "coverage_ratio": coverage_ratio,
        "average_threat_level": np.mean(self.threat_levels)
        if hasattr(self, "threat_levels")
        else 0.0,
      }
      # DEBUG PRINT
      print(f"DEBUG: Logging Episode Result: Reward={self.episode_cumulative_reward}, Info={info}")
      self._log_episode_result(self.episode_cumulative_reward, info)

    observation, info = super().reset(seed=seed, options=options)

    # Strategic Initialization Logic
    if self.strategic_init_mode:
      if self.optimal_start_positions:
        available_optimals = list(self.optimal_start_positions)
      else:
        # Fallback: Dynamic generation based on map dimensions
        available_optimals = self._generate_fallback_start_positions()

      random.shuffle(available_optimals)

      new_positions: list[tuple[int, int]] = []
      for pos in available_optimals:
        if len(new_positions) >= self.num_robots:
          break
        x, y = pos
        if self._is_valid_position(x, y) and (x, y) not in new_positions:
          new_positions.append((x, y))

      # Fill remaining with existing random positions if needed
      if len(new_positions) < self.num_robots:
        for pos in self.robot_positions:
          if len(new_positions) >= self.num_robots:
            break
          if pos not in new_positions:
            new_positions.append(pos)

      self.robot_positions = new_positions
      # Reset visited cells to match new start positions
      self.visited_cells = set(self.robot_positions)

    # Capture starting positions for analysis
    self.episode_start_positions = list(self.robot_positions)

    self._init_tracking_structures()
    self.episode_cumulative_reward = 0.0
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
    self.episode_cumulative_reward += enhanced_reward

    info.update(
      {
        "coverage_ratio": coverage_ratio,
        "visited_cells": visited_count,
        "exploration_reward_bonus": average_per_robot_reward + global_reward,
        "exploration_score": float(visited_count),
      }
    )

    self.coverage_history.append(coverage_ratio)

    # Logging moved to reset() to handle TimeLimit wrapper truncation correctly

    return observation, enhanced_reward, terminated, truncated, info

  def _log_episode_result(self, final_reward: float, info: dict) -> None:
    """Log episode results for analysis of optimal start positions."""
    try:
      result = {
        "start_positions": self.episode_start_positions,
        "final_reward": float(final_reward),
        "coverage": float(info.get("coverage_ratio", 0.0)),
        "avg_threat": float(info.get("average_threat_level", 0.0)),
        "steps": self.time_step,
        # Add config verification
        "config_drain": self.battery_drain_rate,
        "config_threat_penalty": self.threat_penalty_weight,
      }

      # 1. Log to logger (stdout/stderr)
      logger.info(f"EPISODE_RESULT: {json.dumps(result)}")

      # 2. Log to direct file if configured
      if self.episode_log_file:
        try:
          with open(self.episode_log_file, "a") as f:
            f.write(json.dumps(result) + "\n")
          # Also print confirmation that we wrote to file
          print(f"DEBUG: Wrote episode result to {self.episode_log_file}")
        except Exception as e:
          logger.error(f"Failed to write to episode log file: {e}")

    except Exception as e:
      logger.error(f"Failed to log episode result: {e}")

  def _generate_fallback_start_positions(self) -> list[tuple[int, int]]:
    """Generate spread-out positions based on map dimensions (Corners, Center, Mid-Edges)."""
    w, h = self.width, self.height
    candidates = [
      (1, 1),
      (w - 2, 1),
      (1, h - 2),
      (w - 2, h - 2),  # Corners (padded)
      (w // 2, h // 2),  # Center
      (w // 2, 1),
      (w // 2, h - 2),
      (1, h // 2),
      (w - 2, h // 2),  # Mid-edges
    ]
    # Filter valid positions
    return [p for p in candidates if self._is_valid_position(p[0], p[1])]

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
