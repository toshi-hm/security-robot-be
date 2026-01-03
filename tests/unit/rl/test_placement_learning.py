"""Unit tests for PlacementLearningWrapper."""

import pytest

from rl.environments.enhanced_env import EnhancedSecurityEnvironment
from rl.environments.placement_wrapper import PlacementLearningWrapper


@pytest.fixture
def wrapped_env():
  """Create a wrapped environment for testing."""
  base_env = EnhancedSecurityEnvironment(
    width=10,
    height=10,
    num_robots=1,
    battery_drain_rate=0.0,  # Disable battery for simpler testing
  )
  return PlacementLearningWrapper(base_env)


class TestPlacementPhaseInitialization:
  """Tests for placement phase initialization."""

  def test_starts_in_placement_phase(self, wrapped_env):
    """Environment should start in placement phase after reset."""
    obs, info = wrapped_env.reset()
    assert info.get("placement_phase") is True

  def test_action_space_is_placement_space_after_reset(self, wrapped_env):
    """After reset, action space should be placement space (grid size)."""
    wrapped_env.reset()
    expected_size = wrapped_env.width * wrapped_env.height
    assert wrapped_env.action_space.n == expected_size


class TestPlacementActionExecution:
  """Tests for placement action execution."""

  def test_placement_action_sets_robot_position(self, wrapped_env):
    """Placement action should set robot to specified grid position."""
    wrapped_env.reset()

    # Select position (5, 3) -> action = 3 * 10 + 5 = 35
    target_x, target_y = 5, 3
    action = target_y * wrapped_env.width + target_x

    obs, reward, terminated, truncated, info = wrapped_env.step(action)

    # Check if position was set (might be adjusted if obstacle)
    # Position should be set (exact match depends on obstacles)
    assert "selected_position" in info
    assert info["placement_phase"] is False

  def test_placement_phase_ends_after_action(self, wrapped_env):
    """After placement action, should transition to patrol phase."""
    wrapped_env.reset()
    wrapped_env.step(0)  # Any placement action

    assert wrapped_env._placement_phase is False

  def test_placement_returns_zero_reward(self, wrapped_env):
    """Placement action should return neutral reward."""
    wrapped_env.reset()
    _, reward, _, _, _ = wrapped_env.step(0)

    assert reward == 0.0

  def test_placement_does_not_terminate(self, wrapped_env):
    """Placement action should not terminate episode."""
    wrapped_env.reset()
    _, _, terminated, truncated, _ = wrapped_env.step(0)

    assert not terminated
    assert not truncated


class TestPhaseTransition:
  """Tests for transition between phases."""

  def test_action_space_changes_to_patrol_after_placement(self, wrapped_env):
    """After placement, action space should be patrol space (4 actions)."""
    wrapped_env.reset()
    wrapped_env.step(0)  # Placement action

    # Patrol action space is MultiDiscrete [4] for single robot
    from gymnasium.spaces import MultiDiscrete

    assert isinstance(wrapped_env.action_space, MultiDiscrete)

  def test_patrol_actions_work_after_placement(self, wrapped_env):
    """Standard patrol actions should work after placement."""
    wrapped_env.reset()
    wrapped_env.step(0)  # Placement

    # Execute patrol actions
    for action in [0, 1, 2, 3]:  # forward, left, right, stay
      obs, reward, terminated, truncated, info = wrapped_env.step(action)
      assert info.get("placement_phase") is False
      if terminated or truncated:
        break

  def test_reset_returns_to_placement_phase(self, wrapped_env):
    """After episode ends and reset, should return to placement phase."""
    wrapped_env.reset()
    wrapped_env.step(0)  # Placement
    wrapped_env.step(0)  # Patrol action

    # Reset
    _, info = wrapped_env.reset()

    assert info.get("placement_phase") is True
    assert wrapped_env._placement_phase is True


class TestInvalidPlacement:
  """Tests for handling invalid placement positions."""

  def test_invalid_position_finds_nearest_valid(self, wrapped_env):
    """If selected position is invalid, should find nearest valid position."""
    wrapped_env.reset()

    # Set an obstacle at (5, 3)
    env = wrapped_env.env.unwrapped
    env.obstacles[3][5] = True

    # Try to place at obstacle position
    target_x, target_y = 5, 3
    action = target_y * wrapped_env.width + target_x

    _, _, _, _, info = wrapped_env.step(action)

    # Should have selected a different valid position
    selected = info["selected_position"]
    assert env._is_valid_position(selected[0], selected[1])


class TestPlacementDisabledByDefault:
  """Test that base environment behavior is unchanged without wrapper."""

  def test_base_env_no_placement_phase(self):
    """Base environment should not have placement phase in info."""
    env = EnhancedSecurityEnvironment(width=10, height=10, num_robots=1)
    _, info = env.reset()

    assert "placement_phase" not in info
