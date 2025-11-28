
import numpy as np

from rl.environments.security_env import SecurityEnvironment


class TestMultiAgentSecurityEnv:
    def test_initialization(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        assert env.num_robots == 2
        assert len(env.robot_positions) == 2
        assert len(env.robot_directions) == 2
        assert len(env.battery_levels) == 2

        from gymnasium.spaces import MultiDiscrete
        
        # Check action space
        # MultiDiscrete([4, 4]) for 2 robots
        assert env.action_space.shape == (2,)
        assert isinstance(env.action_space, MultiDiscrete)
        assert np.all(env.action_space.nvec == [4, 4])

    def test_reset(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=3)
        obs, info = env.reset()

        # Check observation shape
        assert obs.shape == (10, 10, 5)

        # Check if all robots are in the observation (Channel 2)
        # Since they start at the same position (charging station), they overlap.
        # So we check the internal state.
        assert len(env.robot_positions) == 3
        assert len(env.robot_directions) == 3

        # Verify that the charging station cell in observation has a robot
        cx, cy = env.charging_station_x, env.charging_station_y
        assert obs[cy, cx, 2] > 0

    def test_step_movement(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        # Force positions for testing
        env.robot_positions = [(1, 1), (2, 2)]
        env.robot_directions = [1, 1] # Facing East (1)

        # Action: Robot 0 moves forward (0), Robot 1 turns right (2)
        actions = [0, 2]
        obs, reward, terminated, truncated, info = env.step(actions)

        # Robot 0 should have moved to (2, 1)
        assert env.robot_positions[0] == (2, 1)
        # Robot 1 should have turned to South (2)
        assert env.robot_directions[1] == 2

    def test_collision_avoidance(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        # Place robots facing each other
        env.robot_positions = [(1, 1), (2, 1)]
        env.robot_directions = [1, 3] # R0 East, R1 West

        # Both try to move forward into each other
        actions = [0, 0]
        env.step(actions)

        # Should stay in place (simple collision resolution)
        assert env.robot_positions[0] == (1, 1)
        assert env.robot_positions[1] == (2, 1)

    def test_cooperative_reward(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        # Set threat levels
        env.threat_levels[1][2] = 1.0
        env.threat_levels[2][2] = 1.0

        # Position robots to clear threats
        env.robot_positions = [(1, 2), (2, 2)] # R0 at (1,2), R1 at (2,2)
        env.robot_directions = [1, 0] # R0 East, R1 North (irrelevant for patrol)

        # Both patrol (Action 3)
        actions = [3, 3]
        _, reward, _, _, _ = env.step(actions)

        # Should get reward for clearing threats
        # Note: Exact value depends on implementation details, but should be positive
        assert reward > 0

