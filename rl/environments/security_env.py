"""Security patrol reinforcement learning environment implementations."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Grid Indexing Convention:
#   - Format: grid[y][x] (row-major)
#   - y: Row index (vertical), 0 is top
#   - x: Column index (horizontal), 0 is left
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

  # Constants
  MOVE_COST = 0.1
  TURN_COST = 0.05
  COLLISION_BASE_PENALTY = 0.5

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
      shape=(width, height, 3 + 2 * self.num_robots),  # Shared global + 2 per robot
    )
    self.action_space = spaces.MultiDiscrete([4] * self.num_robots)

    self.reset()

  @property
  def robot_x(self) -> int:
    """Legacy property for single-agent compatibility."""
    return self.robot_positions[0][0]

  @robot_x.setter
  def robot_x(self, value: int) -> None:
    x, y = self.robot_positions[0]
    self.robot_positions[0] = (value, y)

  @property
  def robot_y(self) -> int:
    """Legacy property for single-agent compatibility."""
    return self.robot_positions[0][1]

  @robot_y.setter
  def robot_y(self, value: int) -> None:
    x, y = self.robot_positions[0]
    self.robot_positions[0] = (x, value)

  @property
  def robot_direction(self) -> int:
    """Legacy property for single-agent compatibility."""
    return self.robot_directions[0]

  @robot_direction.setter
  def robot_direction(self, value: int) -> None:
    self.robot_directions[0] = value

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
    self.last_patrol_info: list[str] = []

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

  def step(self, actions: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
    """
    Execute one time step within the environment.

    Args:
        actions: Array of actions for each robot, shape (num_robots,).
                 Each action must be in range [0, 3]:
                 - 0: Move forward
                 - 1: Turn left
                 - 2: Turn right
                 - 3: Patrol area

    Returns:
        tuple containing:
        - observation (np.ndarray): Current observation, shape (height, width, 3 + 2*num_robots)
        - reward (float): Reward value, normalized by num_robots
        - terminated (bool): Whether episode has ended
        - truncated (bool): Whether episode was truncated (always False)
        - info (dict): Additional information about the environment state
    """
    # 入力の正規化 - accept list for convenience but convert to ndarray
    if not isinstance(actions, np.ndarray):
      actions = np.array(actions, dtype=np.int32)

    if len(actions) != self.num_robots:
      raise ValueError(f"Expected {self.num_robots} actions, got {len(actions)}")
    if np.any((actions < 0) | (actions > 3)):
      raise ValueError("Actions must be in range [0, 3]")

    self.time_step += 1

    # バッテリー更新
    self._update_battery()

    # バッテリー切れチェック
    # Design Decision: Episode ends only when ALL robots run out of battery
    # Rationale:
    #   - Allows for long-term mission scenarios where partial team survival is acceptable
    #   - Remaining robots can continue patrolling even if some fail
    #   - Encourages battery management strategies where not all robots need to charge
    #     simultaneously
    # Alternative approach (not implemented): End when majority of robots are depleted
    # to avoid prolonged single-robot operation that may reduce learning efficiency
    if all(b <= 0.0 for b in self.battery_levels):
      reward = -100.0
      # Always normalize by number of robots to keep scale consistent
      # Even for single robot, ensures consistent scale if num_robots changes
      # dynamically or for comparison
      reward /= self.num_robots
      terminated = True
      return self._get_observation(), reward, terminated, False, self._get_info()

    self._update_threat_levels()
    self._add_suspicious_objects()

    # Initialize patrol info for this step
    self.last_patrol_info = []

    total_reward = 0.0

    # 1. Calculate proposed positions
    proposed_positions = list(self.robot_positions)

    for i in range(self.num_robots):
      if self.battery_levels[i] <= 0.0:
        continue

      if actions[i] == 0 and not self.is_charging_list[i]:
        new_x, new_y = self._get_front_position(i)
        if self._is_valid_position(new_x, new_y):
          proposed_positions[i] = (new_x, new_y)

    # 2. Resolve Collisions
    final_positions, collision_penalty = self._resolve_collisions(proposed_positions)
    total_reward += collision_penalty

    # 3. Apply actions and calculate rewards
    for i in range(self.num_robots):
      if self.battery_levels[i] <= 0.0:
        continue

      action = actions[i]

      # Update position if changed
      if final_positions[i] != self.robot_positions[i]:
        self.robot_positions[i] = final_positions[i]
        self.visited_cells.add(final_positions[i])
        # Move reward logic
        total_reward -= self.MOVE_COST
        total_reward += self._check_suspicious_object_removal(i)
      elif action == 0 and not self.is_charging_list[i]:
        # Failed move (collision or invalid)
        # Collision penalty already applied above if it was a collision.
        # If it was invalid (wall/obstacle), proposed_positions wasn't updated,
        # so we are here. Should we penalize hitting a wall?
        # Original code didn't. Let's stick to collision penalty only for robot-robot.
        pass

      # Handle other actions (Turn, Patrol)
      if self.is_charging_list[i]:
        pass
      elif action == 1:
        self.robot_directions[i] = (self.robot_directions[i] - 1) % 4
        total_reward -= self.TURN_COST
      elif action == 2:
        self.robot_directions[i] = (self.robot_directions[i] + 1) % 4
        total_reward -= self.TURN_COST
      elif action == 3:
        total_reward += self._patrol_area(i)

    # Add charging rewards (calculated globally/summed)
    total_reward += self._calculate_charging_reward()

    # バッテリー関連の報酬調整
    total_reward += self._calculate_battery_penalty()

    # Normalize reward by number of robots to keep scale consistent
    # Always normalize, even for single robot, to ensure consistent scale if num_robots
    # changes dynamically or for comparison
    total_reward /= self.num_robots

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

  def _resolve_collisions(
    self, proposed_positions: list[tuple[int, int]]
  ) -> tuple[list[tuple[int, int]], float]:
    """
    衝突を解決し、最終位置とペナルティを返す。

    Returns:
        (最終位置リスト, 衝突ペナルティの合計)
    """
    final_positions = list(self.robot_positions)
    penalty = 0.0

    # 位置の占有マップを作成
    # Note: pos is in (x, y) format, but grid access uses grid[y][x] (row-major)
    target_map: dict[tuple[int, int], list[int]] = {}
    for i, pos in enumerate(proposed_positions):
      target_map.setdefault(pos, []).append(i)

    # 衝突検出
    for target_pos, robot_indices in target_map.items():
      if len(robot_indices) > 1:
        # Multiple robots targeting same position -> Collision
        # Penalty scales more gradually with number of robots involved:
        # - 2 robots: -0.5 * 2 * 1.0 = -1.0 (avg -0.5 per robot)
        # - 3 robots: -0.5 * 3 * 1.3 = -1.95 (avg -0.65 per robot)
        # - 5 robots: -0.5 * 5 * 1.9 = -4.75 (avg -0.95 per robot, normalized to -0.95)
        # Using 0.3 scale factor for more gradual penalty increase
        scale_factor = 1.0 + (len(robot_indices) - 2) * 0.3
        penalty -= self.COLLISION_BASE_PENALTY * len(robot_indices) * scale_factor

        # final_positions is already self.robot_positions, so no update needed for these indices
        pass
      elif len(robot_indices) == 1:
        robot_idx = robot_indices[0]
        # Dead robots don't move
        if self.battery_levels[robot_idx] <= 0.0:
          continue

        # スワップチェック
        if self._is_swap(robot_idx, target_pos, proposed_positions):
          penalty -= self.COLLISION_BASE_PENALTY
          # Stay in place (default)
        else:
          final_positions[robot_idx] = target_pos

    return final_positions, penalty

  def _is_swap(
    self, robot_idx: int, target: tuple[int, int], proposed: list[tuple[int, int]]
  ) -> bool:
    """ロボット間のスワップを検出"""
    for j, proposed_pos in enumerate(proposed):
      if j == robot_idx:
        continue
      # Swap condition:
      # I am moving to J's current pos (target == self.robot_positions[j])
      # J is moving to MY current pos (proposed_pos == self.robot_positions[robot_idx])
      if target == self.robot_positions[j] and proposed_pos == self.robot_positions[robot_idx]:
        return True
    return False

  # ------------------------------------------------------------------
  # Internal helpers
  # ------------------------------------------------------------------

  def _build_grid(self, fill_value: float) -> list[list[float]]:
    return [[fill_value for _ in range(self.width)] for _ in range(self.height)]

  def _generate_obstacles(self) -> list[list[bool]]:
    generator = create_generator(self.map_type, self.width, self.height, **self.map_config)
    return generator.generate()

  def _get_observation(self) -> np.ndarray:
    # Shape: (height, width, 3 + 2 * num_robots)
    # Shared Global Channels:
    # 0: Threat Levels
    # 1: Obstacles
    # 2: Charging Station
    # Robot-Specific Channels (for robot i):
    # 3 + 2*i: Robot i Position & Direction
    # 4 + 2*i: Robot i Battery

    observation = np.zeros((self.height, self.width, 3 + 2 * self.num_robots), dtype=np.float32)

    # Fill Shared Global Channels
    for y in range(self.height):
      for x in range(self.width):
        # Channel 0: Threat
        observation[y, x, 0] = float(self.threat_levels[y][x])
        # Channel 1: Obstacles
        observation[y, x, 1] = 1.0 if self.obstacles[y][x] else 0.0
        # Channel 2: Charging Station
        if x == self.charging_station_x and y == self.charging_station_y:
          observation[y, x, 2] = 1.0

    # Fill Robot-Specific Channels
    for i in range(self.num_robots):
      base_ch = 3 + i * 2
      rx, ry = self.robot_positions[i]

      # Channel 3 + 2*i: Position & Direction
      # Only mark the specific cell where the robot is
      observation[ry, rx, base_ch] = (self.robot_directions[i] + 1) / 4.0

      # Channel 4 + 2*i: Battery
      # Only mark the specific cell where the robot is
      observation[ry, rx, base_ch + 1] = self.battery_levels[i] / 100.0

    return observation

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

    # Use existing last_patrol_info list
    if not hasattr(self, "last_patrol_info"):
      self.last_patrol_info = []

    rx, ry = self.robot_positions[robot_idx]
    self.last_patrol_info.append(
      f"Robot {robot_idx}: 不審物除去 ({rx},{ry}): +{time_bonus:.1f}"
      f" ({speed_rating}発見, {detection_time}ステップ)"
    )
    return time_bonus

  def _patrol_area(self, robot_idx: int) -> float:
    total_reward = 0.0
    # Do not reset last_patrol_info here

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
          self.last_patrol_info.append(
            f"Robot {robot_idx}: 脅威度除去 ({x},{y}): +{threat_reward:.1f}"
          )

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
      # また、前方(y-1)も空いていることを確認（ロボットは北向きで開始するため）
      # Boundary check added: y > 0
      if not self.obstacles[y][x] and y > 0 and not self.obstacles[y - 1][x]:
        self.charging_station_x = x
        self.charging_station_y = y
        return

    # 配置できない場合は中央に配置（フォールバック）
    logger.warning("Could not find a suitable charging station location. Placing at center.")
    self.charging_station_x = self.width // 2
    self.charging_station_y = self.height // 2
    # 中央とその前方の障害物を強制的に削除
    self.obstacles[self.charging_station_y][self.charging_station_x] = False
    if self.charging_station_y > 0:
      self.obstacles[self.charging_station_y - 1][self.charging_station_x] = False

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

    # If we still don't have enough positions (e.g. trapped), raise error
    if len(positions) < self.num_robots:
      raise ValueError(
        f"Could not find enough unique start positions for {self.num_robots} robots. "
        f"Found {len(positions)}. Robots might be trapped by obstacles."
      )

    return positions

  # ------------------------------------------------------------------
  # Battery management
  # ------------------------------------------------------------------

  def _update_battery(self) -> None:
    """バッテリー残量を更新 (Vectorized)"""
    # Update is_charging_list based on position FIRST
    for i in range(self.num_robots):
      on_station = self.robot_positions[i] == (self.charging_station_x, self.charging_station_y)
      if on_station:
        if self.battery_levels[i] < 100.0:
          self.is_charging_list[i] = True
        else:
          self.is_charging_list[i] = False
      else:
        self.is_charging_list[i] = False

    batteries = np.array(self.battery_levels)
    is_charging = np.array(self.is_charging_list)

    # 充電中のロボット
    if np.any(is_charging):
      batteries[is_charging] = np.minimum(100.0, batteries[is_charging] + self.battery_charge_rate)

    # 移動中のロボット
    if np.any(~is_charging):
      batteries[~is_charging] = np.maximum(0.0, batteries[~is_charging] - self.battery_drain_rate)

    self.battery_levels = batteries.tolist()

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
      "battery_percentage": avg_battery,  # Legacy compatibility
      "battery_levels": self.battery_levels,
      "is_charging": any(self.is_charging_list),  # Legacy
      "is_charging_list": self.is_charging_list,
      "robot_positions": self.robot_positions,
      "coverage_ratio": len(self.visited_cells) / (self.width * self.height),
      "exploration_score": float(len(self.visited_cells)),
      "exploration_reward": 0.0,
    }
