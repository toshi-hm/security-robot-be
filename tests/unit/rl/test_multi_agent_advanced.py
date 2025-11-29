
from rl.environments.security_env import SecurityEnvironment


class TestMultiAgentAdvanced:
    def test_five_robots_initialization(self):
        """Test initialization with 5 robots."""
        env = SecurityEnvironment(width=20, height=20, num_robots=5)
        env.reset()

        assert env.num_robots == 5
        assert len(env.robot_positions) == 5
        assert len(env.battery_levels) == 5

        # Verify scattered positions
        unique_pos = set(env.robot_positions)
        assert len(unique_pos) == 5, "All 5 robots should have unique start positions"

    def test_simultaneous_patrol_rewards(self):
        """Test that multiple robots patrolling simultaneously accumulate rewards correctly."""
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        # Manually set threat levels
        # Robot 0 at (1,1), Threat at (2,1)
        # Robot 1 at (5,5), Threat at (6,5)
        env.robot_positions = [(1, 1), (5, 5)]

        # Clear obstacles to ensure threats are valid
        env.obstacles = [[False for _ in range(10)] for _ in range(10)]

        env.threat_levels[1][2] = 1.0
        env.threat_levels[5][6] = 1.0

        env.threat_levels[1][2] = 1.0
        env.threat_levels[5][6] = 1.0

        from unittest.mock import patch

        # Disable background threat update to verify exact reward from patrol
        with patch.object(env, '_update_threat_levels', return_value=None):
            # Both patrol
            actions = [3, 3]
            _, reward, _, _, _ = env.step(actions)

        # Expected reward:
        # R0 clears (2,1): 1.0 * 10 = 10.0
        # R1 clears (6,5): 1.0 * 10 = 10.0
        # Total raw = 20.0
        # Normalized = 20.0 / 2 = 10.0
        assert reward == 10.0

        # Verify last_patrol_info contains both
        assert len(env.last_patrol_info) == 2
        assert "Robot 0" in env.last_patrol_info[0] or "Robot 0" in env.last_patrol_info[1]
        assert "Robot 1" in env.last_patrol_info[0] or "Robot 1" in env.last_patrol_info[1]

    def test_multiple_battery_failures(self):
        """Test behavior when multiple robots run out of battery."""
        env = SecurityEnvironment(width=10, height=10, num_robots=3)
        env.reset()

        # Move robots away from charging station to prevent charging
        # Charging station is usually at random pos, but we can just set robot positions
        # to be far away. Or just overwrite charging station pos?
        # Easier to overwrite robot positions to be safe.
        # Assume 10x10 grid.
        env.robot_positions = [(0, 0), (0, 1), (0, 2)]
        # Ensure charging station is NOT at these positions
        # If it is, move it.
        if (env.charging_station_x, env.charging_station_y) in env.robot_positions:
            env.charging_station_x = 9
            env.charging_station_y = 9

        # Drain batteries partially (2 dead, 1 alive)
        env.battery_levels = [0.0, 10.0, 0.0]

        # Step
        _, reward, terminated, _, _ = env.step([0, 0, 0])

        # Should NOT terminate yet (one robot still alive)
        assert not terminated
        # Reward might be small negative (move cost for alive robot) or 0 if it didn't move

        # Now drain all
        env.battery_levels = [0.0, 0.0, 0.0]
        _, reward, terminated, _, _ = env.step([0, 0, 0])

        # Should terminate with penalty
        assert terminated
        # Normalized penalty: -100.0 / 3 = -33.33...
        assert abs(reward - (-33.333333)) < 0.001

    def test_charging_station_blocking(self):
        """Test that robots block each other at the charging station."""
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        cx, cy = env.charging_station_x, env.charging_station_y

        # Place R0 on charging station
        env.robot_positions[0] = (cx, cy)
        # Place R1 next to it, facing it
        # Find a neighbor cell
        nx, ny = cx + 1, cy
        if env.obstacles[ny][nx]: # Simple check, assuming 10x10 empty-ish map
             nx, ny = cx - 1, cy

        env.robot_positions[1] = (nx, ny)

        # Orient R1 towards station
        # If R1 is at (cx+1, cy), it needs to face West (3) to move to (cx, cy)
        if nx > cx:
            env.robot_directions[1] = 3 # West
        else:
            env.robot_directions[1] = 1 # East

        # R0 stays (charges), R1 tries to move onto station
        # Action 0 = Move Forward
        actions = [0, 0]

        # Force R0 to be charging so it doesn't move even if action is 0?
        # Actually, if R0 is on station, update_battery sets is_charging=True.
        # And step() says: if action == 0 and not self.is_charging_list[i]: move
        # So if R0 is charging, it won't move even if action is 0.
        # But we need to ensure R0 *is* charging.
        env.battery_levels[0] = 50.0 # Needs charge
        env._update_battery() # Set is_charging flags
        assert env.is_charging_list[0]

        # R1 tries to move
        env.step(actions)

        # R0 should still be at station
        assert env.robot_positions[0] == (cx, cy)
        # R1 should be blocked (collision with stationary R0)
        assert env.robot_positions[1] == (nx, ny)
