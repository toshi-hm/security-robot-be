"""Security patrol reinforcement learning environment implementations."""

from __future__ import annotations

import random

from rl._gym_compat import gym, spaces


class SecurityEnvironment(gym.Env):
    """Grid-based environment modelling a security patrol robot."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        width: int = 20,
        height: int = 20,
        robot_vision_range: int = 2,
        enable_logging: bool = False,
    ) -> None:
        super().__init__()

        self.width = width
        self.height = height
        self.robot_vision_range = robot_vision_range
        self.enable_logging = enable_logging
        self.logger = None

        self.observation_space = spaces.Box(
            low=0,
            high=1,
            shape=(width, height, 3),
        )
        self.action_space = spaces.Discrete(4)

        self.reset()

    def set_logger(self, logger: object) -> None:
        self.logger = logger
        self.enable_logging = True

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[list[list[list[float]]], dict]:
        super().reset(seed=seed)

        self.threat_levels = self._build_grid(0.0)
        self.last_patrolled = self._build_grid(0)
        self.obstacles = self._generate_obstacles()
        self.suspicious_objects: dict[tuple[int, int], int] = {}

        self.robot_x = self.width // 2
        self.robot_y = self.height // 2
        self.robot_direction = 0
        self.time_step = 0

        return self._get_observation(), {}

    def step(
        self, action: int
    ) -> tuple[list[list[list[float]]], float, bool, bool, dict]:
        self.time_step += 1

        self._update_threat_levels()
        self._add_suspicious_objects()

        reward = self._execute_action(action)
        terminated = self.time_step >= 1000

        return self._get_observation(), reward, terminated, False, {}

    def render(self, mode: str = "human") -> None:
        if mode != "human":
            return

        print(f"Time: {self.time_step}")
        print(
            f"Robot position: ({self.robot_x}, {self.robot_y}), Direction: {self.robot_direction}"
        )
        print(f"Threat levels: {self.threat_levels}")
        print(f"Suspicious objects: {len(self.suspicious_objects)}")
        print("-" * 50)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_grid(self, fill_value: float) -> list[list[float]]:
        return [[fill_value for _ in range(self.height)] for _ in range(self.width)]

    def _generate_obstacles(self) -> list[list[bool]]:
        obstacles = [[False for _ in range(self.height)] for _ in range(self.width)]
        count = random.randint(3, 8)
        for _ in range(count):
            x = random.randrange(self.width)
            y = random.randrange(self.height)
            obstacles[x][y] = True
        return obstacles

    def _get_observation(self) -> list[list[list[float]]]:
        observation = [
            [[0.0, 0.0, 0.0] for _ in range(self.height)]
            for _ in range(self.width)
        ]

        for x in range(self.width):
            for y in range(self.height):
                observation[x][y][0] = float(self.threat_levels[x][y])
                observation[x][y][1] = 1.0 if self.obstacles[x][y] else 0.0

        observation[self.robot_x][self.robot_y][2] = (self.robot_direction + 1) / 4.0
        return observation

    def _update_threat_levels(self) -> None:
        for x in range(self.width):
            for y in range(self.height):
                self.threat_levels[x][y] = min(1.0, self.threat_levels[x][y] + 0.01)

        for (x, y), spawn_time in self.suspicious_objects.items():
            elapsed = self.time_step - spawn_time
            increased = self.threat_levels[x][y] + 0.05 * elapsed
            self.threat_levels[x][y] = min(1.0, increased)

    def _add_suspicious_objects(self) -> None:
        if random.random() >= 0.02:
            return

        x = random.randrange(self.width)
        y = random.randrange(self.height)
        if not self.obstacles[x][y] and (x, y) not in self.suspicious_objects:
            self.suspicious_objects[(x, y)] = self.time_step

    def _execute_action(self, action: int) -> float:
        reward = 0.0

        if action == 0:
            new_x, new_y = self._get_front_position()
            if self._is_valid_position(new_x, new_y):
                self.robot_x, self.robot_y = new_x, new_y
                reward -= 0.1
                reward += self._check_suspicious_object_removal()
        elif action == 1:
            self.robot_direction = (self.robot_direction - 1) % 4
            reward -= 0.05
        elif action == 2:
            self.robot_direction = (self.robot_direction + 1) % 4
            reward -= 0.05
        elif action == 3:
            reward += self._patrol_area()

        return reward

    def _get_front_position(self) -> tuple[int, int]:
        dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][self.robot_direction]
        return self.robot_x + dx, self.robot_y + dy

    def _is_valid_position(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height and not self.obstacles[x][y]

    def _check_suspicious_object_removal(self) -> float:
        location = (self.robot_x, self.robot_y)
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
        self.last_patrol_info.append(
            f"不審物除去 ({self.robot_x},{self.robot_y}): +{time_bonus:.1f}"
            f" ({speed_rating}発見, {detection_time}ステップ)"
        )
        return time_bonus

    def _patrol_area(self) -> float:
        total_reward = 0.0
        self.last_patrol_info = []

        for dx in range(-self.robot_vision_range, self.robot_vision_range + 1):
            for dy in range(-self.robot_vision_range, self.robot_vision_range + 1):
                x = self.robot_x + dx
                y = self.robot_y + dy
                if not self._is_valid_position(x, y):
                    continue

                threat_reward = self.threat_levels[x][y] * 10
                if threat_reward > 0:
                    total_reward += threat_reward
                    self.last_patrol_info.append(
                        f"脅威度除去 ({x},{y}): +{threat_reward:.1f}"
                    )

                self.threat_levels[x][y] = 0.0
                self.last_patrolled[x][y] = self.time_step

        return total_reward
