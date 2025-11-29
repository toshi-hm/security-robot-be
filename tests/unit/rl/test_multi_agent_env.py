import numpy as np
import unittest
import pytest

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

    def test_observation_space(self):
        """Test observation space shape and content."""
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        obs, _ = env.reset() # reset returns obs, info

        # Shape should be (width, height, 3 + 2 * num_robots)
        # For 2 robots: 3 + 2*2 = 7 channels
        assert obs.shape == (10, 10, 7)

        # Check channels
        # Channel 0: Threat (Global)
        assert np.any(obs[:, :, 0] >= 0)
        # Channel 1: Obstacles (Global)
        assert np.any(obs[:, :, 1] >= 0)
        # Channel 2: Charging Station (Global)
        assert np.sum(obs[:, :, 2]) == 1.0 # One charging station

        # Robot 0
        # Channel 3: Position
        assert np.sum(obs[:, :, 3]) > 0 # Robot 0 exists
        # Channel 4: Battery
        assert np.sum(obs[:, :, 4]) > 0 # Robot 0 has battery

        # Robot 1
        # Channel 5: Position
        assert np.sum(obs[:, :, 5]) > 0 # Robot 1 exists
        # Channel 6: Battery
        assert np.sum(obs[:, :, 6]) > 0 # Robot 1 has battery

    def test_reset(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=3)
        obs, info = env.reset()

        # Check observation shape
        # 3 global + 2 per robot * 3 robots = 9 channels
        assert obs.shape == (10, 10, 9)

        # Check if all robots are in the observation (Channel 2 for each robot)
        # Robot i is in channel 5*i + 2
        assert len(env.robot_positions) == 3
        assert len(env.robot_directions) == 3

        # Verify positions are unique (scattered)
        unique_positions = set(env.robot_positions)
        assert len(unique_positions) == 3, "Robots should be scattered to unique positions"

        # Verify that the charging station cell in observation has a robot (or near it)
        # One robot should be AT the charging station (start_pos)
        # cx, cy = env.charging_station_x, env.charging_station_y
        # assert (cx, cy) in env.robot_positions # This assertion is removed as robots are scattered

    def test_simultaneous_movement(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        # Place robots side by side facing same direction
        env.robot_positions = [(1, 1), (1, 2)]
        env.robot_directions = [1, 1] # East

        # Ensure not charging so they can move
        env.is_charging_list = [False, False]

        # Both move East
        # R0: (1,1) -> (2,1)
        # R1: (1,2) -> (2,2)
        actions = [0, 0]
        env.step(actions)

        assert env.robot_positions[0] == (2, 1)
        assert env.robot_positions[1] == (2, 2)

    def test_step_movement(self):
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        # Force positions for testing
        env.robot_positions = [(1, 1), (2, 2)]
        env.robot_directions = [1, 1] # Facing East (1)

        # Ensure not charging
        env.is_charging_list = [False, False]

        # Ensure target positions are clear of obstacles
        # Robot 0 moves to (2, 1)
        env.obstacles[1][2] = False
        # Robot 1 stays at (2, 2) (turning)
        env.obstacles[2][2] = False

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

        # Ensure not charging
        env.is_charging_list = [False, False]

        # Both try to move forward into each other
        actions = [0, 0]
        _, reward, _, _, _ = env.step(actions)

        # Should stay in place (simple collision resolution)
        assert env.robot_positions[0] == (1, 1)
        assert env.robot_positions[1] == (2, 1)

        # Verify collision penalty
        # Both collide -> -0.5 * 2 = -1.0
        # Normalized by 2 robots -> -0.5
        # Verify collision penalty
        # Both collide (swap) -> -0.5 * 2 = -1.0
        # Normalized by 2 robots -> -0.5
        assert reward == -0.5

    def test_collision_scaling(self):
        """Test that collision penalty scales with number of robots."""
        env = SecurityEnvironment(width=10, height=10, num_robots=3)
        env.reset()
        
        # Place 3 robots around (1, 1)
        # R0 at (0, 1) facing East -> Target (1, 1)
        # R1 at (1, 0) facing South -> Target (1, 1)
        # R2 at (2, 1) facing West -> Target (1, 1)
        env.robot_positions = [(0, 1), (1, 0), (2, 1)]
        env.robot_directions = [1, 2, 3]
        
        # Ensure target (1, 1) is valid
        env.obstacles[1][1] = False
        
        actions = [0, 0, 0] # All move forward
        _, reward, _, _, _ = env.step(actions)
        
        # All 3 target (1, 1)
        # Penalty formula: -0.5 * N * (1.0 + (N - 2) * 0.5)
        # N=3 -> -0.5 * 3 * (1.0 + 0.5) = -1.5 * 1.5 = -2.25
        # Normalized by 3 robots -> -0.75
        
        # Check expected reward
        # Movement reward: 0 (failed move)
        # Collision penalty: -2.25
        # Total: -2.25 / 3 = -0.75
        
        # Note: There might be other small penalties (battery drain?)
        # Battery drain is small (0.001).
        # Let's check approx value.
        assert -0.76 < reward < -0.74

    def test_reward_normalization(self):
        """Test that rewards are normalized by number of robots."""
        env = SecurityEnvironment(width=10, height=10, num_robots=2)
        env.reset()

        # Manually set positions to avoid collision
        env.robot_positions = [(0, 0), (0, 2)]
        env.robot_directions = [1, 1] # Face East (1, 0) -> (1, 0) and (1, 2)
        # Clear obstacles
        env.obstacles = [[False for _ in range(10)] for _ in range(10)]

        # Move both robots forward (Action 0)
        # Expected raw reward: -0.1 * 2 = -0.2
        # Normalized reward: -0.2 / 2 = -0.1
        _, reward, _, _, _ = env.step([0, 0])
        assert abs(reward - (-0.1)) < 1e-6

        # Test with 4 robots
        env = SecurityEnvironment(width=10, height=10, num_robots=4)
        env.reset()
        # Set positions
        env.robot_positions = [(0, 0), (0, 2), (0, 4), (0, 6)]
        env.robot_directions = [1, 1, 1, 1]
        env.obstacles = [[False for _ in range(10)] for _ in range(10)]

        # Move all 4
        # Raw: -0.1 * 4 = -0.4
        # Normalized: -0.4 / 4 = -0.1
        _, reward, _, _, _ = env.step([0, 0, 0, 0])
        assert abs(reward - (-0.1)) < 1e-6

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

    def test_initialization_trapped(self):
        """Test behavior when charging station is surrounded by obstacles."""
        env = SecurityEnvironment(width=10, height=10, num_robots=5)
        env.reset()
        
        # Manually trap the charging station
        cx, cy = env.charging_station_x, env.charging_station_y
        # Surround with obstacles
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0: continue
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < 10 and 0 <= ny < 10:
                    env.obstacles[ny][nx] = True
                    
        # Force re-scattering
        # Should raise ValueError because robots cannot be placed
        with pytest.raises(ValueError, match="Could not find enough unique start positions"):
            env._get_scattered_start_positions()
        
    def test_charging_station_fallback_clearing(self):
        """Test that charging station placement clears obstacles in fallback mode."""
        env = SecurityEnvironment(width=10, height=10, num_robots=1)
        env.reset()
        
        # Fill map with obstacles to force fallback
        env.obstacles = [[True for _ in range(10)] for _ in range(10)]
        
        # Run placement
        env._place_charging_station()
        
        cx, cy = env.charging_station_x, env.charging_station_y
        
        # Should be at center
        assert cx == 5
        assert cy == 5
        
        # Center should be clear
        assert not env.obstacles[cy][cx]
        # Front (North, y-1) should be clear
        assert not env.obstacles[cy - 1][cx]

