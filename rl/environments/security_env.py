"""Security patrol reinforcement learning environment implementations."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
  # For type checking, import gymnasium directly
  import gymnasium as gym
  from gymnasium import spaces
else:
  # For runtime, use compatibility layer
  from rl._gym_compat import gym, spaces

from rl.environments.map_generator import MapType, create_generator

# -----------------------------------------------------------------------------
# Grid Indexing Convention:
#   - Format: grid[y][x] (row-major)
#   - y: row index (0 to height-1)
#   - x: col index (0 to width-1)
#   - Access: grid[y][x]
# -----------------------------------------------------------------------------


def calculate_dynamic_max_steps(width: int, height: int, coefficient: int = 4) -> int:
  """
  Calculate dynamic maximum episode steps based on grid dimensions.

  The formula is: max(1000, width * height * coefficient)

  This ensures smaller environments (10x10) maintain the legacy 1000 step limit
  while larger environments (20x20, 30x30) get proportionally more steps to
  allow for multiple patrol cycles, obstacle avoidance, and charging behavior.

  Args:
      width: Environment width
      height: Environment height
      coefficient: Multiplier for area (default 4 = ~4 patrol cycles)

  Returns:
      Maximum episode steps
  """
  return max(1000, width * height * coefficient)


class SecurityEnvironment(gym.Env):
  """Grid-based environment modelling a security patrol robot.

  Inherits from gymnasium.Env for compatibility with Stable-Baselines3
  and other RL frameworks that expect Gymnasium environments.
  """

  metadata = {"render_modes": ["human"]}

  def __init__(
    self,
    width: int = 20,
    height: int = 20,
    robot_vision_range: int = 2,
    enable_logging: bool = False,
    max_episode_steps: int | None = None,
    map_type: MapType = "random",
    num_robots: int = 1,
    **map_config: Any,
  ) -> None:
    # Initialize parent Gymnasium Env class
    super().__init__()

    self.width = width
    self.height = height
    self.robot_vision_range = robot_vision_range
    self.enable_logging = enable_logging
    self.map_type = map_type
    self.num_robots = num_robots
    self.map_config = map_config
    self.logger: object | None = None

    # エピソードステップ上限（None の場合は動的に計算）
    if max_episode_steps is None:
      self.max_episode_steps = calculate_dynamic_max_steps(width, height)
    else:
      self.max_episode_steps = max_episode_steps

    # バッテリーシステム (Multi-agent: list of values)
    self.initial_battery = 100.0
    self.battery_levels: list[float] = [100.0] * self.num_robots
    self.battery_drain_rate = 0.001
    self.battery_charge_rate = 1.0
    self.charging_station_x = 0
    self.charging_station_y = 0
    self.is_charging_list: list[bool] = [False] * self.num_robots

    # Robot states
    self.robot_positions: list[tuple[int, int]] = [(0, 0)] * self.num_robots
    self.robot_directions: list[int] = [0] * self.num_robots

    self.observation_space = spaces.Box(
      low=0,
      high=1,
      shape=(width, height, 5),  # 3→5チャンネルに拡張
    )
    self.action_space = spaces.MultiDiscrete([4] * self.num_robots)

    self.reset()

  def set_logger(self, logger: object) -> None:
    self.logger = logger
    self.enable_logging = True

  def reset(
    self,
    *,
    seed: int | None = None,
    options: dict | None = None,
  ) -> tuple[np.ndarray, dict]:
    # Note: seed parameter is accepted for compatibility but not used
    # as we use Python's random module which doesn't support per-instance seeding

    self.threat_levels = self._build_grid(0.0)
    self.last_patrolled = self._build_grid(0)
    self.obstacles = self._generate_obstacles()
    self.suspicious_objects: dict[tuple[int, int], int] = {}
    self.visited_cells: set[tuple[int, int]] = set()

    # 充電ステーションをランダムな位置に配置
    self._place_charging_station()

    # ロボットを充電ステーション周辺に分散配置
    self.robot_positions = self._get_scattered_start_positions()
    self.robot_directions = [0] * self.num_robots

    # Initialize visited cells with starting positions
    for pos in self.robot_positions:
        self.visited_cells.add(pos)

    self.time_step = 0

    # バッテリーを100%に初期化
    self.battery_levels = [self.initial_battery] * self.num_robots
    self.is_charging_list = [False] * self.num_robots

    return self._get_observation(), self._get_info()

  def step(self, actions: list[int] | np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
    self.time_step += 1

    # バッテリー更新
    self._update_battery()

    # バッテリー切れチェック (Any robot dead = episode over? Or just that robot stops?
    # For now, if ANY robot dies, episode over with penalty)
    if any(b <= 0.0 for b in self.battery_levels):
      reward = -100.0
      terminated = True
      return self._get_observation(), reward, terminated, False, self._get_info()

    self._update_threat_levels()
    self._add_suspicious_objects()

    total_reward = 0.0

    # 1. Calculate proposed positions
    proposed_positions = list(self.robot_positions)
    move_intents = [False] * self.num_robots

    for i in range(self.num_robots):
        action = actions[i]
        # Only Action 0 (Move Forward) changes position
        if action == 0 and not self.is_charging_list[i]:
            new_x, new_y = self._get_front_position(i)
            if self._is_valid_position(new_x, new_y):
                proposed_positions[i] = (new_x, new_y)
                move_intents[i] = True

    # 2. Detect and Resolve Collisions
    # Count targets
    target_counts: dict[tuple[int, int], int] = {}
    for pos in proposed_positions:
        target_counts[pos] = target_counts.get(pos, 0) + 1

    # If multiple robots target the same cell, ALL of them stay in place (cancel move)
    # This is a simple rule to ensure fairness and avoid order dependency.
    final_positions = list(self.robot_positions)

    for i in range(self.num_robots):
        target = proposed_positions[i]
        if move_intents[i]:
            # If target is occupied by >1 robot (including self), cancel move
            # OR if target is occupied by another robot that IS NOT moving (stationary obstacle)
            # The target_counts handles "multiple robots moving to same spot"

            # We also need to handle "swapping" or "moving into a stationary robot"
            # If target_counts[target] > 1, it means collision at target -> Cancel
            if target_counts[target] > 1:
                # Collision! Stay in place
                final_positions[i] = self.robot_positions[i]
            else:
                # Target is unique. But is it a swap?
                # Check if any other robot is moving to MY current position,
                # AND I am moving to THEIR current position
                is_swap = False
                for j in range(self.num_robots):
                    if i == j:
                        continue

                    # Swap condition:
                    # I am moving to J's current pos
                    # J is moving to MY current pos
                    if (target == self.robot_positions[j] and
                        proposed_positions[j] == self.robot_positions[i]):
                        is_swap = True
                        break

                if is_swap:
                    final_positions[i] = self.robot_positions[i]
                else:
                    final_positions[i] = target

    # 3. Apply actions and calculate rewards
    for i in range(self.num_robots):
        action = actions[i]

        # Update position if changed
        if final_positions[i] != self.robot_positions[i]:
            self.robot_positions[i] = final_positions[i]
            self.visited_cells.add(final_positions[i])
            # Move reward logic
            total_reward -= 0.1
            total_reward += self._check_suspicious_object_removal(i)
        elif action == 0 and not self.is_charging_list[i]:
            # Failed move (collision or invalid)
            # No penalty for collision specifically in original code, just no move?
            # Original code: if not collision: reward -= 0.1. So if collision, 0 reward?
            # Let's keep it consistent: No move = 0 reward (or maybe small penalty?)
            # Original code didn't penalize collision explicitly, just didn't give move cost?
            # Wait, original code:
            # if not collision: reward -= 0.1
            # else: (implicit) reward = 0
            pass

        # Handle other actions (Turn, Patrol)
        if self.is_charging_list[i]:
             pass
        elif action == 1:
            self.robot_directions[i] = (self.robot_directions[i] - 1) % 4
            total_reward -= 0.05
        elif action == 2:
            self.robot_directions[i] = (self.robot_directions[i] + 1) % 4
            total_reward -= 0.05
        elif action == 3:
            total_reward += self._patrol_area(i)

    # Add charging rewards (calculated globally/summed)
    total_reward += self._calculate_charging_reward()

    # バッテリー関連の報酬調整
    total_reward += self._calculate_battery_penalty()

    terminated = self.time_step >= self.max_episode_steps

    return self._get_observation(), total_reward, terminated, False, self._get_info()

  def render(self, mode: str = "human") -> None:
    if mode != "human":
      return

    print(f"Time: {self.time_step}")
    for i in range(self.num_robots):
        print(
            f"Robot {i}: ({self.robot_positions[i][0]}, {self.robot_positions[i][1]}), "
            f"Dir: {self.robot_directions[i]}"
        )
        print(
            f"  Battery: {self.battery_levels[i]:.1f}% "
            f"{'[CHARGING]' if self.is_charging_list[i] else ''}"
        )
    print(f"Charging station: ({self.charging_station_x}, {self.charging_station_y})")
    print(f"Threat levels: {self.threat_levels}")
    print(f"Suspicious objects: {len(self.suspicious_objects)}")
    print("-" * 50)

  # ------------------------------------------------------------------
  # Internal helpers
  # ------------------------------------------------------------------

  def _build_grid(self, fill_value: float) -> list[list[float]]:
    return [[fill_value for _ in range(self.width)] for _ in range(self.height)]

  def _generate_obstacles(self) -> list[list[bool]]:
    generator = create_generator(self.map_type, self.width, self.height, **self.map_config)
    return generator.generate()

  def _get_observation(self) -> np.ndarray:
    observation = [[[0.0] * 5 for _ in range(self.width)] for _ in range(self.height)]

    for y in range(self.height):
      for x in range(self.width):
        # チャンネル0: 脅威レベル
        observation[y][x][0] = float(self.threat_levels[y][x])

        # チャンネル1: 障害物
        observation[y][x][1] = 1.0 if self.obstacles[y][x] else 0.0

        # チャンネル3: 充電ステーション
        if x == self.charging_station_x and y == self.charging_station_y:
          observation[y][x][3] = 1.0

        # チャンネル4: バッテリー残量（正規化）
        # If multiple robots are on the same cell, take the max battery
        # (or average? Visualizing max is probably better)
        max_battery = 0.0
        for i in range(self.num_robots):
            if self.robot_positions[i] == (x, y):
                max_battery = max(max_battery, self.battery_levels[i])
        observation[y][x][4] = max_battery / 100.0

    # チャンネル2: ロボット位置・向き
    for i in range(self.num_robots):
        rx, ry = self.robot_positions[i]
        # If multiple robots, the last one overwrites. That's acceptable for now.
        observation[ry][rx][2] = (self.robot_directions[i] + 1) / 4.0

    return np.array(observation, dtype=np.float32)

  def _update_threat_levels(self) -> None:
    for y in range(self.height):
      for x in range(self.width):
        self.threat_levels[y][x] = min(1.0, self.threat_levels[y][x] + 0.01)

    for (x, y), spawn_time in self.suspicious_objects.items():
      elapsed = self.time_step - spawn_time
      increased = self.threat_levels[y][x] + 0.05 * elapsed
      self.threat_levels[y][x] = min(1.0, increased)

  def _add_suspicious_objects(self) -> None:
    if random.random() >= 0.02:
      return

    x = random.randrange(self.width)
    y = random.randrange(self.height)
    if not self.obstacles[y][x] and (x, y) not in self.suspicious_objects:
      self.suspicious_objects[(x, y)] = self.time_step



  def _get_front_position(self, robot_idx: int) -> tuple[int, int]:
    dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][self.robot_directions[robot_idx]]
    rx, ry = self.robot_positions[robot_idx]
    return rx + dx, ry + dy

  def _is_valid_position(self, x: int, y: int) -> bool:
    return 0 <= x < self.width and 0 <= y < self.height and not self.obstacles[y][x]

  def _check_suspicious_object_removal(self, robot_idx: int) -> float:
    location = self.robot_positions[robot_idx]
    if location not in self.suspicious_objects:
      return 0.0

    spawn_time = self.suspicious_objects[location]
    detection_time = self.time_step - spawn_time

    if detection_time <= 5:
      time_bonus = 20.0
      speed_rating = "超高速"
    elif detection_time <= 10:
      time_bonus = 15.0
      speed_rating = "高速"
    elif detection_time <= 20:
      time_bonus = 10.0
      speed_rating = "通常"
    elif detection_time <= 50:
      time_bonus = 5.0
      speed_rating = "遅め"
    else:
      time_bonus = 2.0
      speed_rating = "非常に遅い"

    del self.suspicious_objects[location]

    if not hasattr(self, "last_patrol_info"):
      self.last_patrol_info = []
    rx, ry = self.robot_positions[robot_idx]
    self.last_patrol_info.append(
      f"不審物除去 ({rx},{ry}): +{time_bonus:.1f}"
      f" ({speed_rating}発見, {detection_time}ステップ)"
    )
    return time_bonus

  def _patrol_area(self, robot_idx: int) -> float:
    total_reward = 0.0
    self.last_patrol_info = []

    rx, ry = self.robot_positions[robot_idx]

    for dx in range(-self.robot_vision_range, self.robot_vision_range + 1):
      for dy in range(-self.robot_vision_range, self.robot_vision_range + 1):
        x = rx + dx
        y = ry + dy
        if not self._is_valid_position(x, y):
          continue

        threat_reward = self.threat_levels[y][x] * 10
        if threat_reward > 0:
          total_reward += threat_reward
          self.last_patrol_info.append(f"脅威度除去 ({x},{y}): +{threat_reward:.1f}")

        self.threat_levels[y][x] = 0.0
        self.last_patrolled[y][x] = self.time_step

    return total_reward

  def _place_charging_station(self) -> None:
    """充電ステーションをランダムな位置に配置"""
    # 境界から1セル離れた範囲で配置可能な位置を探す
    max_attempts = 100
    for _ in range(max_attempts):
      # 境界から1セル離れた位置をランダムに選択
      x = random.randint(1, self.width - 2)
      y = random.randint(1, self.height - 2)

      # 障害物がない位置に配置
      if not self.obstacles[y][x]:
        self.charging_station_x = x
        self.charging_station_y = y
        return

    # 配置できない場合は中央に配置（フォールバック）
    self.charging_station_x = self.width // 2
    self.charging_station_y = self.height // 2
    # 中央の障害物を強制的に削除
    self.obstacles[self.charging_station_y][self.charging_station_x] = False

  def _get_scattered_start_positions(self) -> list[tuple[int, int]]:
    """Get scattered start positions around charging station using BFS."""
    start_pos = (self.charging_station_x, self.charging_station_y)
    positions = [start_pos]
    queue = [start_pos]
    visited = {start_pos}

    while len(positions) < self.num_robots and queue:
      cx, cy = queue.pop(0)

      # Check neighbors
      for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
        nx, ny = cx + dx, cy + dy

        if (
          0 <= nx < self.width
          and 0 <= ny < self.height
          and not self.obstacles[ny][nx]
          and (nx, ny) not in visited
        ):
          visited.add((nx, ny))
          queue.append((nx, ny))
          positions.append((nx, ny))

          if len(positions) >= self.num_robots:
            break

    # If we still don't have enough positions (e.g. trapped), fill with start_pos
    while len(positions) < self.num_robots:
      positions.append(start_pos)

    return positions

  # ------------------------------------------------------------------
  # Battery management
  # ------------------------------------------------------------------

  def _update_battery(self) -> None:
    """バッテリー残量を更新"""
    for i in range(self.num_robots):
        # 充電ステーション上にいる場合
        if self.robot_positions[i] == (self.charging_station_x, self.charging_station_y):
            # 充電
            if self.battery_levels[i] < 100.0:
                self.battery_levels[i] = min(
                    100.0, self.battery_levels[i] + self.battery_charge_rate
                )
                self.is_charging_list[i] = True
            else:
                self.is_charging_list[i] = False
        else:
            # 充電ステーション外では消費
            self.battery_levels[i] -= self.battery_drain_rate
            self.battery_levels[i] = max(0.0, self.battery_levels[i])
            self.is_charging_list[i] = False

  def _calculate_battery_penalty(self) -> float:
    """バッテリー関連のペナルティを計算 (Sum for all robots)"""
    total_penalty = 0.0

    for i in range(self.num_robots):
        penalty = 0.0
        battery = self.battery_levels[i]

        # バッテリー低下警告
        if battery < 20.0:
            penalty -= 0.5 * (20.0 - battery) / 20.0

        if battery < 10.0:
            penalty -= 1.0 * (10.0 - battery) / 10.0

        # 充電ステーションからの距離ペナルティ(バッテリー低下時)
        if battery < 30.0:
            rx, ry = self.robot_positions[i]
            distance = abs(rx - self.charging_station_x) + abs(ry - self.charging_station_y)
            max_distance = self.width + self.height
            penalty -= 0.2 * (distance / max_distance) * (1.0 - battery / 30.0)

        total_penalty += penalty

    return total_penalty

  def _calculate_charging_reward(self) -> float:
    """充電中の報酬を計算 (Sum for all charging robots)"""
    total_reward = 0.0
    avg_threat = sum(sum(row) for row in self.threat_levels) / (self.width * self.height)

    for i in range(self.num_robots):
        if self.is_charging_list[i]:
            reward = -0.1 * avg_threat
            # バッテリーが低い場合はコスト減免
            if self.battery_levels[i] < 30.0:
                reward *= 0.5
            total_reward += reward

    return total_reward

  def _get_info(self) -> dict:
    """Info辞書を生成"""
    # Use average battery for simple logging, but provide details
    avg_battery = sum(self.battery_levels) / self.num_robots

    return {
      "battery_percentage": avg_battery, # Legacy compatibility
      "battery_levels": self.battery_levels,
      "is_charging": any(self.is_charging_list), # Legacy
      "is_charging_list": self.is_charging_list,
      "robot_positions": self.robot_positions,
      "coverage_ratio": len(self.visited_cells) / (self.width * self.height),
      "exploration_score": float(len(self.visited_cells)),
      "exploration_reward": 0.0,
    }
