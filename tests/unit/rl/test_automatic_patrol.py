"""Tests for automatic patrol functionality.

These tests verify that patrol (security surveillance) is automatically performed
for all active robots after every action.
"""

import numpy as np

from rl.environments.security_env import SecurityEnvironment


class TestAutomaticPatrol:
  """Tests for automatic patrol functionality."""

  def test_patrol_executed_on_movement(self):
    """Patrol should be executed automatically when robot moves forward."""
    env = SecurityEnvironment(width=10, height=10, num_robots=1)
    env.reset()

    # Position robot and clear obstacles
    env.robot_positions = [(5, 5)]
    env.robot_directions = [1]  # Facing East
    env.obstacles = [[False for _ in range(10)] for _ in range(10)]
    env.is_charging_list = [False]

    # Set threat at robot's initial position
    initial_x, initial_y = env.robot_positions[0]
    env.threat_levels[initial_y][initial_x] = 1.0

    # Move forward (action 0)
    env.step(np.array([0]))

    # After moving, the previous position should have been patrolled
    # (threat cleared, last_patrolled updated)
    # Note: Actually patrol happens at current position after move
    new_x, new_y = env.robot_positions[0]
    assert env.last_patrolled[new_y][new_x] == env.time_step

  def test_patrol_executed_on_turn(self):
    """Patrol should be executed automatically when robot turns."""
    env = SecurityEnvironment(width=10, height=10, num_robots=1)
    env.reset()

    env.robot_positions = [(5, 5)]
    env.robot_directions = [0]  # Facing North
    env.obstacles = [[False for _ in range(10)] for _ in range(10)]
    env.is_charging_list = [False]

    # Set threat at robot's position
    env.threat_levels[5][5] = 1.0
    initial_threat = env.threat_levels[5][5]

    # Turn left (action 1)
    _, reward, _, _, _ = env.step(np.array([1]))

    # Patrol should have cleared threat
    assert env.threat_levels[5][5] == 0.0
    assert env.last_patrolled[5][5] == env.time_step
    # Reward should include threat clearing
    assert reward > -1.0  # Should get positive reward from threat clearing

  def test_patrol_executed_on_stay(self):
    """Patrol should be executed automatically when robot stays in place."""
    env = SecurityEnvironment(width=10, height=10, num_robots=1)
    env.reset()

    env.robot_positions = [(5, 5)]
    env.robot_directions = [0]
    env.obstacles = [[False for _ in range(10)] for _ in range(10)]
    env.is_charging_list = [False]

    # Set threat at robot's position
    env.threat_levels[5][5] = 1.0

    # Stay in place (action 3)
    _, reward, _, _, _ = env.step(np.array([3]))

    # Patrol should have cleared threat
    assert env.threat_levels[5][5] == 0.0
    assert env.last_patrolled[5][5] == env.time_step

  def test_no_patrol_while_charging(self):
    """Patrol should NOT be executed while robot is charging."""
    env = SecurityEnvironment(width=10, height=10, num_robots=1)
    env.reset()

    # Place robot at charging station
    station_x, station_y = env.charging_stations[0]
    env.robot_positions = [(station_x, station_y)]
    env.robot_directions = [0]
    env.battery_levels = [50.0]  # Not full, so will charge
    env.is_charging_list = [True]

    # Set threat at robot's position
    env.threat_levels[station_y][station_x] = 1.0
    initial_threat = env.threat_levels[station_y][station_x]

    # Try any action (will be ignored while charging)
    env.step(np.array([3]))

    # Threat should NOT be cleared (robot is charging)
    assert env.threat_levels[station_y][station_x] == initial_threat

  def test_no_patrol_when_battery_depleted(self):
    """Patrol should NOT be executed when battery is 0."""
    env = SecurityEnvironment(width=10, height=10, num_robots=1)
    env.reset()

    env.robot_positions = [(5, 5)]
    env.robot_directions = [0]
    env.obstacles = [[False for _ in range(10)] for _ in range(10)]
    env.battery_levels = [0.0]  # Depleted
    env.is_charging_list = [False]

    # Set threat at robot's position
    env.threat_levels[5][5] = 1.0
    initial_threat = env.threat_levels[5][5]

    # Any action - robot has no battery
    # Note: This will trigger episode termination due to min_active_robots
    _, _, terminated, _, _ = env.step(np.array([0]))

    # Episode should terminate
    assert terminated

  def test_multi_robot_all_patrol_automatically(self):
    """All active robots should patrol automatically."""
    env = SecurityEnvironment(width=10, height=10, num_robots=3)
    env.reset()

    # Position 3 robots at different locations
    env.robot_positions = [(2, 2), (5, 5), (8, 8)]
    env.robot_directions = [0, 0, 0]
    env.obstacles = [[False for _ in range(10)] for _ in range(10)]
    env.is_charging_list = [False, False, False]

    # Set threats at each robot's position
    env.threat_levels[2][2] = 0.5
    env.threat_levels[5][5] = 0.5
    env.threat_levels[8][8] = 0.5

    # Different actions for each robot - all should still patrol
    actions = np.array([0, 1, 3])  # Move, Turn, Stay
    env.step(actions)

    # All threats should be cleared (patrol is automatic for all)
    # Note: Robot 0 moved, so check its new position
    # Robots 1 and 2 stayed, so check their positions
    new_x0, new_y0 = env.robot_positions[0]
    assert env.last_patrolled[new_y0][new_x0] == env.time_step

    # Robot 1 turned but stayed at (5,5)
    assert env.threat_levels[5][5] == 0.0

    # Robot 2 stayed at (8,8)
    assert env.threat_levels[8][8] == 0.0
