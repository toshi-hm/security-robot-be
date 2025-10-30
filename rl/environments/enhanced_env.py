"""Enhanced security patrol environment with advanced reward shaping."""

from __future__ import annotations

from .security_env import SecurityEnvironment


class EnhancedSecurityEnvironment(SecurityEnvironment):
    """Extended environment optimised for coverage, exploration, and diversity."""

    def __init__(
        self,
        width: int = 20,
        height: int = 20,
        robot_vision_range: int = 2,
        enable_logging: bool = False,
        coverage_weight: float = 1.0,
        exploration_weight: float = 2.0,
        diversity_weight: float = 1.5,
    ) -> None:
        self.coverage_weight = coverage_weight
        self.exploration_weight = exploration_weight
        self.diversity_weight = diversity_weight

        super().__init__(
            width=width,
            height=height,
            robot_vision_range=robot_vision_range,
            enable_logging=enable_logging,
        )
        self._init_tracking_structures()

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[list[list[list[float]]], dict]:
        observation, info = super().reset(seed=seed, options=options)
        self._init_tracking_structures()

        self._mark_current_position()
        return observation, info

    def step(
        self, action: int
    ) -> tuple[list[list[list[float]]], float, bool, bool, dict]:
        observation, base_reward, terminated, truncated, info = super().step(action)

        self._update_exploration_state()

        total_cells = self.width * self.height
        visited_count = sum(
            1 for column in self.visited_cells for cell in column if cell
        )
        coverage_ratio = visited_count / total_cells if total_cells else 0.0

        enhanced_reward = self._calculate_enhanced_reward(
            action, base_reward, coverage_ratio
        )

        info.update(
            {
                "coverage_ratio": coverage_ratio,
                "visited_cells": visited_count,
                "exploration_reward": enhanced_reward - base_reward,
            }
        )

        self.coverage_history.append(coverage_ratio)
        return observation, enhanced_reward, terminated, truncated, info

    # ------------------------------------------------------------------
    # Tracking helpers
    # ------------------------------------------------------------------

    def _init_tracking_structures(self) -> None:
        self.visited_cells = [
            [False for _ in range(self.height)] for _ in range(self.width)
        ]
        self.visit_count = [
            [0 for _ in range(self.height)] for _ in range(self.width)
        ]
        self.last_visited = [
            [-1 for _ in range(self.height)] for _ in range(self.width)
        ]
        self.recent_positions: list[tuple[int, int]] = []
        self.position_history_length = 10
        self.coverage_history: list[float] = []

    def _mark_current_position(self) -> None:
        self.visited_cells[self.robot_x][self.robot_y] = True
        self.visit_count[self.robot_x][self.robot_y] = 1
        self.last_visited[self.robot_x][self.robot_y] = self.time_step
        self.recent_positions = [(self.robot_x, self.robot_y)]

    def _update_exploration_state(self) -> None:
        x, y = self.robot_x, self.robot_y
        self.visited_cells[x][y] = True
        self.visit_count[x][y] += 1
        self.last_visited[x][y] = self.time_step
        self.recent_positions.append((x, y))
        if len(self.recent_positions) > self.position_history_length:
            self.recent_positions.pop(0)

    # ------------------------------------------------------------------
    # Reward shaping
    # ------------------------------------------------------------------

    def _calculate_enhanced_reward(
        self, action: int, base_reward: float, coverage_ratio: float
    ) -> float:
        total_reward = base_reward
        total_reward += self._calculate_exploration_reward() * self.exploration_weight
        total_reward += (
            self._calculate_coverage_reward(coverage_ratio) * self.coverage_weight
        )
        total_reward += self._calculate_diversity_reward() * self.diversity_weight
        total_reward += self._calculate_movement_reward(action)
        total_reward += self._calculate_patrol_optimization_reward(action)
        return total_reward

    def _calculate_exploration_reward(self) -> float:
        visits = self.visit_count[self.robot_x][self.robot_y]
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

    def _calculate_diversity_reward(self) -> float:
        if len(self.recent_positions) < self.position_history_length:
            return 0.0

        unique_positions = len(set(self.recent_positions))
        diversity_ratio = unique_positions / len(self.recent_positions)

        if diversity_ratio > 0.8:
            return 2.0
        if diversity_ratio > 0.6:
            return 1.0
        if diversity_ratio < 0.3:
            return -1.0
        return 0.0

    def _calculate_movement_reward(self, action: int) -> float:
        if action != 0:
            return 0.0

        front_x, front_y = self._get_front_position()
        if not self._is_valid_position(front_x, front_y):
            return 0.0

        if not self.visited_cells[front_x][front_y]:
            return 1.0
        if self.visit_count[front_x][front_y] < 3:
            return 0.5
        return 0.0

    def _calculate_patrol_optimization_reward(self, action: int) -> float:
        if action != 3:
            return 0.0

        unexplored_in_range = 0
        for dx in range(-self.robot_vision_range, self.robot_vision_range + 1):
            for dy in range(-self.robot_vision_range, self.robot_vision_range + 1):
                x, y = self.robot_x + dx, self.robot_y + dy
                if self._is_valid_position(x, y) and not self.visited_cells[x][y]:
                    unexplored_in_range += 1

        if unexplored_in_range > 0:
            return unexplored_in_range * 0.5
        return 0.0
