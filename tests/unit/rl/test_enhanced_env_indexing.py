
import pytest
from rl.environments.enhanced_env import EnhancedSecurityEnvironment

def test_enhanced_env_grid_indexing():
    """Verify that visit_count and last_visited use row-major indexing [y][x]."""
    # Create an environment with distinct width and height to detect indexing errors
    width = 10
    height = 5
    env = EnhancedSecurityEnvironment(width=width, height=height)
    env.reset()
    
    # Check initialization dimensions
    # Should be [height][width]
    assert len(env.visit_count) == height
    assert len(env.visit_count[0]) == width
    assert len(env.last_visited) == height
    assert len(env.last_visited[0]) == width
    
    # Check access
    # Robot starts at a specific position. Let's force it to (x=2, y=1)
    env.robot_x = 2
    env.robot_y = 1
    
    # Manually call internal update to check if it crashes or updates wrong cell
    env._update_exploration_state()
    
    # Check if the correct cell was updated: grid[y][x] -> grid[1][2]
    assert env.visit_count[1][2] >= 1
    assert env.last_visited[1][2] == env.time_step
    
    # Ensure it didn't update [x][y] -> [2][1] if they were swapped (and valid)
    # In this case [2][1] is valid (y=2, x=1)
    # But since we only updated (2, 1), (1, 2) should be 0 if we were using [x][y]
    # Wait, if we used [x][y], we would access visit_count[2][1].
    # If we use [y][x], we access visit_count[1][2].
    
    # Let's check that [2][1] is NOT updated (unless it's the same cell, which it isn't)
    # visit_count[2][1] corresponds to y=2, x=1
    assert env.visit_count[2][1] == 0

