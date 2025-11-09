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

        # バッテリーシステム
        self.initial_battery = 100.0
        self.battery_percentage = 100.0
        self.battery_drain_rate = 0.001  # 1ステップあたり0.001% (1000ステップで1%)
        self.battery_charge_rate = 1.0  # 1ステップあたり1%
        self.charging_station_x = 0  # reset()で設定
        self.charging_station_y = 0  # reset()で設定
        self.is_charging = False

        self.observation_space = spaces.Box(
            low=0,
            high=1,
            shape=(width, height, 5),  # 3→5チャンネルに拡張
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

        # 充電ステーションをランダムな位置に配置
        self._place_charging_station()

        # ロボットを充電ステーション上に配置
        self.robot_x = self.charging_station_x
        self.robot_y = self.charging_station_y
        self.robot_direction = 0
        self.time_step = 0

        # バッテリーを100%に初期化
        self.battery_percentage = self.initial_battery
        self.is_charging = False

        return self._get_observation(), self._get_info()

    def step(self, action: int) -> tuple[list[list[list[float]]], float, bool, bool, dict]:
        self.time_step += 1

        # バッテリー更新
        self._update_battery()

        # バッテリー切れチェック
        if self.battery_percentage <= 0.0:
            # 特大ペナルティとエピソード終了
            reward = -100.0
            terminated = True
            return self._get_observation(), reward, terminated, False, self._get_info()

        self._update_threat_levels()
        self._add_suspicious_objects()

        # 充電中は警備活動を制限
        if self.is_charging:
            reward = self._calculate_charging_reward()
        else:
            reward = self._execute_action(action)

        # バッテリー関連の報酬調整
        reward += self._calculate_battery_penalty()

        terminated = self.time_step >= 1000

        return self._get_observation(), reward, terminated, False, self._get_info()

    def render(self, mode: str = "human") -> None:
        if mode != "human":
            return

        print(f"Time: {self.time_step}")
        print(
            f"Robot position: ({self.robot_x}, {self.robot_y}), Direction: {self.robot_direction}"
        )
        print(f"Battery: {self.battery_percentage:.1f}% {'[CHARGING]' if self.is_charging else ''}")
        print(f"Charging station: ({self.charging_station_x}, {self.charging_station_y})")
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
        observation = [[[0.0] * 5 for _ in range(self.height)] for _ in range(self.width)]

        for x in range(self.width):
            for y in range(self.height):
                # チャンネル0: 脅威レベル
                observation[x][y][0] = float(self.threat_levels[x][y])

                # チャンネル1: 障害物
                observation[x][y][1] = 1.0 if self.obstacles[x][y] else 0.0

                # チャンネル3: 充電ステーション
                if x == self.charging_station_x and y == self.charging_station_y:
                    observation[x][y][3] = 1.0

                # チャンネル4: バッテリー残量（正規化）
                observation[x][y][4] = self.battery_percentage / 100.0

        # チャンネル2: ロボット位置・向き
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
                    self.last_patrol_info.append(f"脅威度除去 ({x},{y}): +{threat_reward:.1f}")

                self.threat_levels[x][y] = 0.0
                self.last_patrolled[x][y] = self.time_step

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
            if not self.obstacles[x][y]:
                self.charging_station_x = x
                self.charging_station_y = y
                return

        # 配置できない場合は中央に配置（フォールバック）
        self.charging_station_x = self.width // 2
        self.charging_station_y = self.height // 2
        # 中央の障害物を強制的に削除
        self.obstacles[self.charging_station_x][self.charging_station_y] = False

    # ------------------------------------------------------------------
    # Battery management
    # ------------------------------------------------------------------

    def _update_battery(self) -> None:
        """バッテリー残量を更新"""
        # 充電ステーション上にいる場合
        if (
            self.robot_x == self.charging_station_x
            and self.robot_y == self.charging_station_y
        ):
            # 充電
            if self.battery_percentage < 100.0:
                self.battery_percentage = min(
                    100.0, self.battery_percentage + self.battery_charge_rate
                )
                self.is_charging = True
            else:
                self.is_charging = False
        else:
            # 充電ステーション外では消費
            self.battery_percentage -= self.battery_drain_rate
            self.battery_percentage = max(0.0, self.battery_percentage)
            self.is_charging = False

    def _calculate_battery_penalty(self) -> float:
        """バッテリー関連のペナルティを計算"""
        penalty = 0.0

        # バッテリー低下警告
        if self.battery_percentage < 20.0:
            penalty -= 0.5 * (20.0 - self.battery_percentage) / 20.0

        if self.battery_percentage < 10.0:
            penalty -= 1.0 * (10.0 - self.battery_percentage) / 10.0

        # 充電ステーションからの距離ペナルティ(バッテリー低下時)
        if self.battery_percentage < 30.0:
            distance = abs(self.robot_x - self.charging_station_x) + abs(
                self.robot_y - self.charging_station_y
            )
            max_distance = self.width + self.height
            penalty -= (
                0.2
                * (distance / max_distance)
                * (1.0 - self.battery_percentage / 30.0)
            )

        return penalty

    def _calculate_charging_reward(self) -> float:
        """充電中の報酬を計算"""
        # 平均脅威レベルに応じた機会損失コスト
        avg_threat = sum(sum(row) for row in self.threat_levels) / (
            self.width * self.height
        )
        reward = -0.1 * avg_threat

        # バッテリーが低い場合はコスト減免
        if self.battery_percentage < 30.0:
            reward *= 0.5

        return reward

    def _get_info(self) -> dict:
        """Info辞書を生成"""
        distance_to_station = abs(self.robot_x - self.charging_station_x) + abs(
            self.robot_y - self.charging_station_y
        )

        return {
            "battery_percentage": self.battery_percentage,
            "is_charging": self.is_charging,
            "distance_to_charging_station": distance_to_station,
            "charging_station_position": (
                self.charging_station_x,
                self.charging_station_y,
            ),
        }
